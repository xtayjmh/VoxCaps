# coding: utf-8
"""
音频流管理模块

提供 AudioStreamManager 类用于管理音频输入流，包括流的创建、
启动、停止和设备检测。
"""

from __future__ import annotations

import time
import threading
from collections import deque
from enum import Enum
from typing import TYPE_CHECKING, Callable, Optional

import numpy as np
import sounddevice as sd

from core.client.state import console
from . import logger

if TYPE_CHECKING:
    from core.client.state import ClientState
    from ..app import CapsWriterClient


class CaptureMode(str, Enum):
    IDLE = 'idle'
    CANDIDATE = 'candidate'
    RECORDING = 'recording'
    DIRECT = 'direct'



class AudioStreamManager:
    """
    音频流管理器

    负责管理音频输入流的生命周期，包括：
    - 检测和选择音频设备
    - 创建和启动音频流
    - 处理音频数据回调
    - 流的重启和关闭

    Attributes:
        state: 客户端状态实例
        sample_rate: 采样率（默认 48000Hz）
        block_duration: 每个数据块的时长（秒，默认 0.05s）
    """

    SAMPLE_RATE = 48000
    BLOCK_DURATION = 0.05  # 50ms

    def __init__(self, app: CapsWriterClient):
        """
        初始化音频流管理器

        Args:
            app: 客户端 App 实例
        """
        self.app = app
        self._channels = 1
        self._running = False  # 标志是否应该运行
        self._lifecycle_lock = threading.RLock()
        self._capture_lock = threading.RLock()
        self._capture_mode = CaptureMode.IDLE
        # 最多保留约 2 秒候选音频，防止调度异常造成内存持续增长。
        self._candidate_frames: deque[dict] = deque(maxlen=40)

    @property
    def state(self) -> ClientState:
        """快捷访问状态单例"""
        return self.app.state

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info,
        status: sd.CallbackFlags
    ) -> None:
        """
        音频数据回调函数

        当音频流接收到新数据时调用，将数据放入异步队列中。
        """
        message = {
            'type': 'data',
            'time': time.time(),
            'data': indata.copy(),
        }
        with self._capture_lock:
            if self._capture_mode is CaptureMode.CANDIDATE:
                self._candidate_frames.append(message)
                return
            direct_recording = (
                self._capture_mode is CaptureMode.DIRECT
                and self.state.recording
            )
            if self._capture_mode is not CaptureMode.RECORDING and not direct_recording:
                return

            import asyncio
            if self.app.loop and self.state.queue_in:
                asyncio.run_coroutine_threadsafe(
                    self.state.queue_in.put(message),
                    self.app.loop
                )

    def begin_candidate(self) -> bool:
        """打开麦克风并把音频暂存在内存候选缓冲中。"""
        with self._lifecycle_lock:
            with self._capture_lock:
                if self._capture_mode is not CaptureMode.IDLE:
                    return False
                self._candidate_frames.clear()
                self._capture_mode = CaptureMode.CANDIDATE

            stream = self._start_locked()
            if stream is not None:
                return True

            with self._capture_lock:
                self._candidate_frames.clear()
                self._capture_mode = CaptureMode.IDLE
            return False

    def begin_direct_recording(self) -> bool:
        """兼容单击和 UDP 触发：按任务生命周期打开实时录音流。"""
        with self._lifecycle_lock:
            with self._capture_lock:
                if self._capture_mode is not CaptureMode.IDLE:
                    return False
                self._capture_mode = CaptureMode.DIRECT

            stream = self._start_locked()
            if stream is not None:
                return True
            with self._capture_lock:
                self._capture_mode = CaptureMode.IDLE
            return False

    def commit_candidate(self, start_recording: Callable[[list[dict]], None]) -> bool:
        """原子提交候选帧，并切换到实时录音模式。"""
        with self._capture_lock:
            if self._capture_mode is not CaptureMode.CANDIDATE:
                return False
            frames = list(self._candidate_frames)
            start_recording(frames)
            self._candidate_frames.clear()
            self._capture_mode = CaptureMode.RECORDING
            return True

    def discard_candidate(self) -> None:
        """丢弃候选音频并释放麦克风。"""
        with self._lifecycle_lock:
            with self._capture_lock:
                self._candidate_frames.clear()
                self._capture_mode = CaptureMode.IDLE
            self._stop_locked()

    def _on_stream_finished(self) -> None:
        """音频流结束回调"""
        if not threading.main_thread().is_alive():
            return
        if not self._running:
            return

        logger.info("音频流意外结束，正在尝试重启...")
        self.reopen()

    def start(self) -> Optional[sd.InputStream]:
        with self._lifecycle_lock:
            return self._start_locked()

    def _start_locked(self) -> Optional[sd.InputStream]:
        """
        启动音频流

        Returns:
            创建的音频输入流，如果失败返回 None
        """
        if self._running:
            logger.debug("音频流已在运行，跳过启动")
            return self.state.stream

        # 检测音频设备
        try:
            device = sd.query_devices(kind='input')
            self._channels = min(2, device['max_input_channels'])
            device_name = device.get('name', '未知设备')
            console.print(
                f'使用默认音频设备：[italic]{device_name}，声道数：{self._channels}',
                end='\n\n'
            )
            logger.info(f"找到音频设备: {device_name}, 声道数: {self._channels}")
        except UnicodeDecodeError:
            logger.warning("无法获取音频设备名称（编码问题）")
        except sd.PortAudioError:
            logger.error("未找到麦克风设备")
            return None

        # 创建音频流
        try:
            stream = sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                blocksize=int(self.BLOCK_DURATION * self.SAMPLE_RATE),
                device=None,
                dtype="float32",
                channels=self._channels,
                callback=self._audio_callback,
                finished_callback=self._on_stream_finished,
            )
            stream.start()

            self.state.stream = stream
            self._running = True
            logger.debug(
                f"音频流已启动: 采样率={self.SAMPLE_RATE}, "
                f"块大小={int(self.BLOCK_DURATION * self.SAMPLE_RATE)}"
            )
            return stream

        except sd.PortAudioError as e:
            logger.error(f"创建音频流失败: {e}", exc_info=True)
            if '-9999' in str(e):
                console.print("""
[bold red]检测到麦克风被占用或权限异常（错误码 -9999）[/bold red]
请尝试以下解决方案：

  1. 设置 > 隐私和安全性 > 麦克风，将「允许桌面应用访问麦克风」打开
  2. 状态栏右下角音量图标 > 右键菜单 > 声音 > 麦克风的属性，关闭「允许应用程序独占控制该设备」
  3. 状态栏右下角音量图标 > 右键菜单 > 声音 > 麦克风的属性，关闭「增强效果」
""")
            return None
        except Exception as e:
            logger.error(f"创建音频流失败: {e}", exc_info=True)
            return None

    def stop(self) -> None:
        """停止音频流"""
        with self._lifecycle_lock:
            self._stop_locked()

    def _stop_locked(self) -> None:
        with self._capture_lock:
            self._capture_mode = CaptureMode.IDLE
            self._candidate_frames.clear()
        if not self._running:
            return

        self._running = False  # 标记为停止
        if self.state.stream is not None:
            try:
                self.state.stream.close()
                logger.debug("音频流已停止")
            except Exception as e:
                logger.debug(f"停止音频流时发生错误: {e}")
            finally:
                self.state.stream = None

    def reopen(self) -> Optional[sd.InputStream]:
        """
        重新启动音频流

        Returns:
            新创建的音频输入流
        """
        with self._lifecycle_lock:
            logger.info("正在重启音频流...")
            with self._capture_lock:
                previous_mode = self._capture_mode
                previous_candidate_frames = list(self._candidate_frames)

            self._stop_locked()

            try:
                sd._terminate()
                sd._ffi.dlclose(sd._lib)
                sd._lib = sd._ffi.dlopen(sd._libname)
                sd._initialize()
            except Exception as e:
                logger.warning(f"重载 PortAudio 时发生警告: {e}")

            time.sleep(0.1)
            stream = self._start_locked()
            if stream is not None:
                with self._capture_lock:
                    self._capture_mode = previous_mode
                    self._candidate_frames.extend(previous_candidate_frames)
            return stream
