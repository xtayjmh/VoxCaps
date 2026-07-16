# coding: utf-8
"""不会阻止客户端退出的串行后台执行器。"""

from __future__ import annotations

import queue
import threading
from concurrent.futures import Executor, Future
from typing import Any, Callable


class DaemonSerialExecutor(Executor):
    """在单个守护线程中按提交顺序执行可能阻塞的设备操作。

    Windows 音频驱动调用进入原生代码后无法被 Python 强制中断。使用守护
    worker 可以保持正常打开/关闭操作串行，同时确保极端驱动死锁不会阻止
    VoxCaps 进程退出。
    """

    _STOP = object()

    def __init__(self, thread_name: str = 'VoxCapsMic') -> None:
        self._queue: queue.Queue[Any] = queue.Queue()
        self._lock = threading.Lock()
        self._shutdown = False
        self._thread = threading.Thread(
            target=self._run,
            name=thread_name,
            daemon=True,
        )
        self._thread.start()

    @property
    def worker_is_daemon(self) -> bool:
        """供诊断和自动化验证使用。"""
        return self._thread.daemon

    def submit(
        self,
        fn: Callable[..., Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Future:
        with self._lock:
            if self._shutdown:
                raise RuntimeError('cannot schedule new futures after shutdown')
            future = Future()
            self._queue.put((future, fn, args, kwargs))
            return future

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        with self._lock:
            if not self._shutdown:
                self._shutdown = True
                if cancel_futures:
                    self._cancel_pending_locked()
                self._queue.put(self._STOP)

        if wait and threading.current_thread() is not self._thread:
            self._thread.join()

    def _cancel_pending_locked(self) -> None:
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                return
            if item is self._STOP:
                continue
            future, _fn, _args, _kwargs = item
            future.cancel()

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is self._STOP:
                return

            future, fn, args, kwargs = item
            if not future.set_running_or_notify_cancel():
                continue
            try:
                result = fn(*args, **kwargs)
            except BaseException as exc:
                future.set_exception(exc)
            else:
                future.set_result(result)
