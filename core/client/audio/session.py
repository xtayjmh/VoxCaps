# coding: utf-8
"""按需麦克风语音会话协调。"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol


class _Scheduler(Protocol):
    def call_later(self, delay: float, callback: Callable[[], None]) -> Any:
        ...


class ThreadingScheduler:
    """使用守护 Timer 执行长按确认。"""

    def call_later(self, delay: float, callback: Callable[[], None]) -> threading.Timer:
        timer = threading.Timer(delay, callback)
        timer.daemon = True
        timer.start()
        return timer


@dataclass
class _Session:
    key_name: str
    task: Any
    pressed_at: float
    timer: Any = None
    opened: bool = False
    confirmed: bool = False
    recording: bool = False


class VoiceInputSessionCoordinator:
    """把快捷键事件转换为非阻塞的按需麦克风会话。"""

    def __init__(
        self,
        stream: Any,
        executor: Any,
        restore_short_press: Callable[[str, Any], None],
        scheduler: _Scheduler | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.stream = stream
        self.executor = executor
        self.restore_short_press = restore_short_press
        self.scheduler = scheduler or ThreadingScheduler()
        self.clock = clock
        self._lock = threading.RLock()
        self._session: _Session | None = None
        self._stopped = False

    def press(self, key_name: str, task: Any) -> bool:
        """安排候选录音；不在键盘回调线程中访问麦克风。"""
        with self._lock:
            if self._stopped or self._session is not None:
                return False
            session = _Session(
                key_name=key_name,
                task=task,
                pressed_at=self.clock(),
            )
            self._session = session
            self.executor.submit(self._open_candidate, session)
            session.timer = self.scheduler.call_later(
                task.threshold,
                lambda: self._confirm_hold(session),
            )
            return True

    def release(self, key_name: str) -> bool:
        """释放候选或正式录音，并按触发意图处理默认按键。"""
        with self._lock:
            session = self._session
            if session is None or session.key_name != key_name:
                return False

            elapsed = self.clock() - session.pressed_at
            if not session.confirmed and elapsed > session.task.threshold:
                session.confirmed = True
                if session.opened:
                    self._start_recording(session)

            if session.timer is not None:
                session.timer.cancel()

            if session.recording:
                session.task.finish()
                self.stream.stop()
            else:
                self.stream.discard_candidate()
                if not session.confirmed:
                    self.restore_short_press(key_name, session.task)

            self._session = None
            return True

    def shutdown(self) -> None:
        """停止接受新会话，并释放候选或正式录音资源。"""
        with self._lock:
            self._stopped = True
            session = self._session
            self._session = None
            if session is not None and session.timer is not None:
                session.timer.cancel()

        if session is None:
            self.stream.stop()
        elif session.recording:
            session.task.cancel()
            self.stream.stop()
        else:
            self.stream.discard_candidate()

    def _open_candidate(self, session: _Session) -> None:
        opened = bool(self.stream.begin_candidate())
        with self._lock:
            if self._session is not session:
                if opened:
                    self.stream.discard_candidate()
                return
            session.opened = opened
            if opened and session.confirmed:
                self._start_recording(session)

    def _confirm_hold(self, session: _Session) -> None:
        with self._lock:
            if self._session is not session:
                return
            elapsed = self.clock() - session.pressed_at
            if elapsed <= session.task.threshold:
                delay = max(0.001, session.task.threshold - elapsed + 0.001)
                session.timer = self.scheduler.call_later(
                    delay,
                    lambda: self._confirm_hold(session),
                )
                return
            session.confirmed = True
            if session.opened:
                self._start_recording(session)

    def _start_recording(self, session: _Session) -> None:
        if session.recording:
            return
        committed = self.stream.commit_candidate(
            lambda frames: session.task.launch(
                start_time=session.pressed_at,
                initial_audio=frames,
            )
        )
        session.recording = bool(committed)
