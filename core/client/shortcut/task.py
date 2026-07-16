# coding: utf-8
"""
快捷键任务模块

管理单个快捷键的录音任务状态
"""

from __future__ import annotations
import asyncio
import time
import uuid
from threading import Event
from typing import TYPE_CHECKING, Optional

from . import logger
from core.tools.my_status import Status
 
if TYPE_CHECKING:
    from core.client.shortcut.shortcut_config import Shortcut
    from core.client.state import ClientState
    from core.client.audio.recorder import AudioRecorder
    from core.client.app import CapsWriterClient



class ShortcutTask:
    """
    单个快捷键的录音任务

    跟踪每个快捷键独立的录音状态，防止互相干扰。
    """

    def __init__(self, app: CapsWriterClient, shortcut: Shortcut, recorder_class=None):
        """
        初始化快捷键任务

        Args:
            app: 客户端 App 实例
            shortcut: 快捷键配置
            recorder_class: AudioRecorder 类（可选，用于延迟导入）
        """
        self.app = app
        self.shortcut = shortcut
        self._recorder_class = recorder_class

        # 任务状态
        self.task: Optional[asyncio.Future] = None
        self.pipeline_task_id: Optional[str] = None
        self.delivery_sequence: Optional[int] = None
        self.recording_start_time: float = 0.0
        self.is_recording: bool = False
        self._owns_direct_stream: bool = False

        # hold_mode 状态跟踪
        self.pressed: bool = False
        self.released: bool = True
        self.event: Event = Event()

        # 线程池（用于 countdown）
        self.pool = None

        # 录音状态动画
        self._status = Status('开始录音', spinner='point')

    @property
    def state(self) -> ClientState:
        """快捷访问状态单例"""
        return self.app.state

    def _get_recorder(self) -> AudioRecorder:
        """获取 AudioRecorder 实例"""
        if self._recorder_class is None:
            from core.client.audio.recorder import AudioRecorder
            self._recorder_class = AudioRecorder
        return self._recorder_class(self.app)

    def prepare(self) -> None:
        """长按已确认但麦克风尚未就绪时进入准备态。"""
        self.pipeline_task_id = str(uuid.uuid1())
        self.delivery_sequence = None
        self.app.island.preparing(self.pipeline_task_id)

    def cancel_preparing(self) -> None:
        """取消尚未开始录音的准备态。"""
        if self.pipeline_task_id:
            self.app.island.cancelled(self.pipeline_task_id)
            self.pipeline_task_id = None
            self.delivery_sequence = None

    def launch(self, *, start_time: float | None = None, initial_audio: list[dict] | None = None) -> None:
        """启动录音任务"""
        logger.info(f"[{self.shortcut.key}] 触发：开始录音")

        self._owns_direct_stream = initial_audio is None
        if self._owns_direct_stream and not self.app.stream.begin_direct_recording():
            logger.warning(f"[{self.shortcut.key}] 麦克风打开失败，录音任务未启动")
            self._owns_direct_stream = False
            return

        # 记录开始时间
        self.recording_start_time = start_time if start_time is not None else time.time()
        self.pipeline_task_id = self.pipeline_task_id or str(uuid.uuid1())
        self.delivery_sequence = self.app.delivery_order.register(
            self.pipeline_task_id,
            self.recording_start_time,
        )
        self.is_recording = True
        self.app.island.recording(self.pipeline_task_id)

        async def enqueue_start() -> None:
            await self.state.queue_in.put({
                'type': 'begin',
                'time': self.recording_start_time,
                'data': None,
            })
            for message in initial_audio or []:
                await self.state.queue_in.put(message)

        asyncio.run_coroutine_threadsafe(enqueue_start(), self.app.loop)

        # 更新录音状态
        self.state.start_recording(self.recording_start_time)

        # 打印动画：正在录音
        self._status.start()

        # 启动识别任务
        recorder = self._get_recorder()
        recorder.task_id = self.pipeline_task_id
        self.task = asyncio.run_coroutine_threadsafe(
            recorder.record_and_send(),
            self.app.loop,
        )

    def cancel(self, *, release_stream: bool = True) -> None:
        """取消录音任务；退出阶段可把音频释放交给守护执行器。"""
        logger.debug(f"[{self.shortcut.key}] 取消录音任务（时间过短）")

        self.is_recording = False
        self.state.stop_recording()
        self._status.stop()
        task_id = self.pipeline_task_id
        self.app.island.cancelled(task_id)
        if task_id:
            self.app.delivery_order.cancel(task_id)
        self.pipeline_task_id = None
        self.delivery_sequence = None

        if self.task is not None:
            self.task.cancel()
            self.task = None
        if self._owns_direct_stream:
            if release_stream:
                self.app.stream.stop()
            self._owns_direct_stream = False

    def finish(self) -> None:
        """完成录音任务"""
        logger.info(f"[{self.shortcut.key}] 释放：完成录音")

        self.is_recording = False
        self.state.stop_recording()
        self._status.stop()
        task_id = self.pipeline_task_id
        self.app.island.recognizing(task_id)
        # Recorder 已持有自己的 task_id；释放 ShortcutTask 字段，确保下一次
        # direct/click launch 不会复用旧任务身份。
        self.pipeline_task_id = None
        self.delivery_sequence = None

        asyncio.run_coroutine_threadsafe(
            self.state.queue_in.put({
                'type': 'finish',
                'time': time.time(),
                'data': None
            }),
            self.app.loop
        )

        if self._owns_direct_stream:
            self.app.stream.stop()
            self._owns_direct_stream = False

        # 执行 restore（可恢复按键 + 非阻塞模式）
        # 阻塞模式下按键不会发送到系统，状态不会改变，不需要恢复
        if self.shortcut.is_toggle_key() and not self.shortcut.suppress:
            self._restore_key()

    def _restore_key(self) -> None:
        """恢复按键状态（防自捕获逻辑由 ShortcutManager 处理）"""
        # 通知管理器执行 restore
        # 防自捕获：管理器会设置 flag 再发送按键
        manager = self._manager_ref()
        if manager:
            logger.debug(f"[{self.shortcut.key}] 自动恢复按键状态 (suppress={self.shortcut.suppress})")
            manager.schedule_restore(self.shortcut.key)
        else:
            logger.warning(f"[{self.shortcut.key}] manager 引用丢失，无法 restore")
