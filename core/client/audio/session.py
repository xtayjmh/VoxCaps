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
    open_timeout_timer: Any = None
    open_future: Any = None
    opened: bool = False
    open_failed: bool = False
    confirmed: bool = False
    recording: bool = False
    preparing: bool = False


class VoiceInputSessionCoordinator:
    """把快捷键事件转换为非阻塞的按需麦克风会话。"""

    def __init__(
        self,
        stream: Any,
        executor: Any,
        restore_short_press: Callable[[str, Any], None],
        scheduler: _Scheduler | None = None,
        clock: Callable[[], float] = time.time,
        notify_microphone_error: Callable[[str], None] | None = None,
        open_timeout: float = 1.5,
    ) -> None:
        self.stream = stream
        self.executor = executor
        self.restore_short_press = restore_short_press
        self.scheduler = scheduler or ThreadingScheduler()
        self.clock = clock
        self.notify_microphone_error = notify_microphone_error or (lambda _message: None)
        self.open_timeout = open_timeout
        self._lock = threading.RLock()
        self._session: _Session | None = None
        self._stopped = False
        self._preheat_scheduled = False
        self._preheat_timer: Any = None
        self._preheat_timeout_timer: Any = None
        self._preheat_future: Any = None
        self._preheat_token: object | None = None

    def schedule_preheat(self, delay: float = 1.0, timeout: float = 1.5) -> bool:
        """安排一次后台麦克风预热；成功后立即释放设备。"""
        with self._lock:
            if self._stopped or self._preheat_scheduled:
                return False
            self._preheat_scheduled = True
            self._preheat_timer = self.scheduler.call_later(
                delay,
                lambda: self._begin_preheat(timeout),
            )
            return True

    def _begin_preheat(self, timeout: float) -> None:
        with self._lock:
            if self._stopped:
                self._preheat_scheduled = False
                return
            if self._session is not None:
                self._preheat_scheduled = False
                return
            token = object()
            self._preheat_token = token
            self._preheat_timeout_timer = self.scheduler.call_later(
                timeout,
                lambda: self._on_preheat_timeout(token),
            )
            self._preheat_future = self.executor.submit(self._run_preheat, token)

    def _run_preheat(self, token: object) -> None:
        with self._lock:
            if self._stopped or self._preheat_token is not token:
                return
        opened = bool(self.stream.begin_candidate())
        busy = bool(getattr(self.stream, 'is_capture_active', False)) and not opened
        should_notify = False
        with self._lock:
            if self._preheat_token is token:
                if self._preheat_timeout_timer is not None:
                    self._preheat_timeout_timer.cancel()
                self._preheat_token = None
                self._preheat_scheduled = False
                self._preheat_future = None
                should_notify = not opened and not busy
            if should_notify:
                self.notify_microphone_error('麦克风不可用，请检查 Windows 麦克风权限或安全软件设置。')
        if opened:
            self.stream.discard_candidate()

    def _on_preheat_timeout(self, token: object) -> None:
        with self._lock:
            if self._preheat_token is not token:
                return
            self.notify_microphone_error('麦克风不可用，请检查 Windows 麦克风权限或安全软件设置。')
            if self._preheat_future is not None:
                self._preheat_future.cancel()
            self._preheat_token = None
            self._preheat_scheduled = False
            self._preheat_future = None

    def press(self, key_name: str, task: Any) -> bool:
        """安排候选录音；不在键盘回调线程中访问麦克风。"""
        with self._lock:
            if self._stopped or self._session is not None:
                return False
            self._cancel_preheat_for_session()
            session = _Session(
                key_name=key_name,
                task=task,
                pressed_at=self.clock(),
            )
            self._session = session
            session.open_future = self.executor.submit(self._open_candidate, session)
            session.timer = self.scheduler.call_later(
                task.threshold,
                lambda: self._confirm_hold(session),
            )
            session.open_timeout_timer = self.scheduler.call_later(
                self.open_timeout,
                lambda: self._on_open_timeout(session),
            )
            return True

    def _cancel_preheat_for_session(self) -> None:
        """取消预热所有权，真实按键会话优先使用麦克风。"""
        if self._preheat_timer is not None:
            self._preheat_timer.cancel()
        if self._preheat_timeout_timer is not None:
            self._preheat_timeout_timer.cancel()
        if self._preheat_future is not None:
            self._preheat_future.cancel()
        self._preheat_token = None
        self._preheat_scheduled = False

    def release(self, key_name: str) -> bool:
        """释放候选或正式录音，并按触发意图处理默认按键。"""
        with self._lock:
            session = self._session
            if session is None or session.key_name != key_name:
                return False

            elapsed = self.clock() - session.pressed_at
            if not session.confirmed and elapsed > session.task.threshold:
                session.confirmed = True
                self._prepare_session(session)
                if session.opened:
                    self._start_recording(session)

            if session.confirmed and session.open_failed:
                self._fail_session(session)
                return True

            if session.timer is not None:
                session.timer.cancel()
            if session.open_timeout_timer is not None:
                session.open_timeout_timer.cancel()
            if session.open_future is not None:
                session.open_future.cancel()

            if session.recording:
                session.task.finish()
                self.executor.submit(self.stream.stop)
            else:
                if not session.confirmed:
                    self.restore_short_press(key_name, session.task)
                else:
                    self._cancel_preparing(session)
                if session.opened:
                    self.executor.submit(self.stream.discard_candidate)

            self._session = None
            return True

    def shutdown(self) -> None:
        """停止接受新会话，并异步释放候选或正式录音资源。"""
        with self._lock:
            self._stopped = True
            if self._preheat_timer is not None:
                self._preheat_timer.cancel()
            if self._preheat_timeout_timer is not None:
                self._preheat_timeout_timer.cancel()
            if self._preheat_future is not None:
                self._preheat_future.cancel()
            self._preheat_token = None
            self._preheat_scheduled = False
            session = self._session
            self._session = None
            if session is not None and session.timer is not None:
                session.timer.cancel()
            if session is not None and session.open_timeout_timer is not None:
                session.open_timeout_timer.cancel()
            if session is not None and session.open_future is not None:
                session.open_future.cancel()

        if session is not None and session.recording:
            session.task.cancel()
        elif session is not None and session.confirmed:
            self._cancel_preparing(session)
        # 不在退出线程中等待 PortAudio。串行 executor 会先处理已开始的打开
        # 调用，再执行 stop；若驱动永久卡死，守护 worker 也不会拖住进程退出。
        try:
            self.executor.submit(self.stream.stop)
        except RuntimeError:
            # 执行器已关闭时，操作系统会在进程退出时回收音频句柄。
            pass

    def _open_candidate(self, session: _Session) -> None:
        with self._lock:
            if self._stopped or self._session is not session:
                return
        opened = bool(self.stream.begin_candidate())
        with self._lock:
            if self._session is not session:
                stale_open = opened
            else:
                stale_open = False
                session.opened = opened
                session.open_failed = not opened
                if session.open_timeout_timer is not None:
                    session.open_timeout_timer.cancel()
                if not opened and session.confirmed:
                    self._fail_session(session)
                elif opened and session.confirmed:
                    self._start_recording(session)
        if stale_open:
            self.stream.discard_candidate()

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
            self._prepare_session(session)
            if session.open_failed:
                self._fail_session(session)
            elif session.opened:
                self._start_recording(session)

    def _on_open_timeout(self, session: _Session) -> None:
        with self._lock:
            if self._session is not session or session.opened:
                return
            if not session.confirmed:
                session.confirmed = True
                self._prepare_session(session)
            self._fail_session(session)

    def _fail_session(self, session: _Session) -> None:
        if self._session is not session:
            return
        if session.timer is not None:
            session.timer.cancel()
        if session.open_timeout_timer is not None:
            session.open_timeout_timer.cancel()
        if session.open_future is not None:
            session.open_future.cancel()
        self._cancel_preparing(session)
        self.notify_microphone_error('麦克风不可用，请检查 Windows 麦克风权限或安全软件设置。')
        self._session = None

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
        if committed:
            session.preparing = False
        else:
            self._cancel_preparing(session)

    @staticmethod
    def _prepare_session(session: _Session) -> None:
        if session.preparing:
            return
        session.task.prepare()
        session.preparing = True

    @staticmethod
    def _cancel_preparing(session: _Session) -> None:
        if not session.preparing:
            return
        session.task.cancel_preparing()
        session.preparing = False
