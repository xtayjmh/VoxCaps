"""动态状态岛生命周期与线程安全事件入口。"""

from __future__ import annotations

from queue import Queue
from threading import Event, Lock, Thread
from typing import Optional

from core.client import logger

from .state_machine import IslandEvent, IslandStage


class DynamicIslandController:
    """由客户端创建和释放；禁用或 UI 失败时退化为无操作对象。"""

    def __init__(
        self,
        enabled: bool = True,
        width: int = 138,
        height: int = 34,
        bottom_margin: int = 42,
        hold_delay_ms: int = 180,
    ) -> None:
        self.enabled = enabled
        self.width = max(96, int(width))
        self.height = max(26, int(height))
        self.bottom_margin = max(0, int(bottom_margin))
        self.hold_delay_ms = max(0, int(hold_delay_ms))
        self._events: Queue[IslandEvent] = Queue()
        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self._lock = Lock()

    def start(self) -> None:
        if not self.enabled:
            return
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = Thread(
                target=self._run,
                name='CapsWriterDynamicIsland',
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        if not self.enabled:
            return
        self._stop_event.set()
        self._events.put(IslandEvent(IslandStage.STOP))
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=1.5)
        self._thread = None

    def recording(self, task_id: str) -> None:
        self._publish(IslandStage.RECORDING, task_id)

    def cancelled(self, task_id: Optional[str]) -> None:
        self._publish(IslandStage.IDLE, task_id)

    def recognizing(self, task_id: Optional[str]) -> None:
        self._publish(IslandStage.RECOGNIZING, task_id)

    def delivered(self, task_id: Optional[str]) -> None:
        self._publish(IslandStage.DELIVERED, task_id)

    def error(self, task_id: Optional[str], message: str = '') -> None:
        self._publish(IslandStage.ERROR, task_id, message)

    def _publish(
        self,
        stage: IslandStage,
        task_id: Optional[str] = None,
        message: str = '',
    ) -> None:
        if not self.enabled or self._stop_event.is_set():
            return
        self._events.put(IslandEvent(stage, task_id, message))

    def _run(self) -> None:
        try:
            from .view import DynamicIslandView

            DynamicIslandView(
                events=self._events,
                stop_event=self._stop_event,
                width=self.width,
                height=self.height,
                bottom_margin=self.bottom_margin,
                hold_delay_ms=self.hold_delay_ms,
            ).run()
        except Exception as exc:
            # UI 永远不能阻断录音和识别主流程。
            logger.warning(f'动态状态岛启动失败，已静默禁用: {exc}', exc_info=True)
