# coding: utf-8
"""连续口述结果的线程安全顺序送达队列。"""

from __future__ import annotations

import asyncio
import threading
from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass
class _Entry:
    sequence: int
    start_time: float
    status: str = 'pending'
    submitted_generation: int | None = None
    payload: Any = None


class OrderedDeliveryQueue:
    """按正式录音登记顺序释放结果，失败或取消的会话自动跳过。"""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._owner_thread = threading.get_ident()
        self._lock = threading.Lock()
        self._next_sequence = 1
        self._entries: dict[str, _Entry] = {}
        self._order: deque[str] = deque()
        self._ready: asyncio.Queue[Any] = asyncio.Queue()
        self._closed_order: deque[str] = deque()
        self._closed_ids: set[str] = set()

    def register(self, task_id: str, start_time: float) -> int:
        """登记正式录音并返回单调递增的本地会话序号。"""
        with self._lock:
            if task_id in self._closed_ids:
                return 0
            existing = self._entries.get(task_id)
            if existing is not None:
                return existing.sequence
            sequence = self._next_sequence
            self._next_sequence += 1
            self._entries[task_id] = _Entry(sequence, start_time)
            self._order.append(task_id)
            return sequence

    def complete(self, task_id: str, payload: Any) -> bool:
        """标记结果已完成；只有队首连续就绪结果才进入送达队列。"""
        with self._lock:
            if task_id in self._closed_ids:
                return False
            entry = self._entries.get(task_id)
            if entry is None:
                # 兼容非麦克风或旧协议调用；正常麦克风任务会在录音开始时登记。
                sequence = self._next_sequence
                self._next_sequence += 1
                entry = _Entry(sequence, float('inf'))
                self._entries[task_id] = entry
                self._order.append(task_id)
            entry.status = 'ready'
            entry.payload = payload
            ready = self._flush_locked()
        self._dispatch(ready)
        return True

    def mark_submitted(self, task_id: str, connection_generation: int) -> bool:
        """记录 final 请求实际使用的连接代次。"""
        with self._lock:
            if task_id in self._closed_ids:
                return False
            entry = self._entries.get(task_id)
            if entry is None or entry.status != 'pending':
                return False
            entry.submitted_generation = connection_generation
            return True

    def fail(self, task_id: str) -> None:
        """标记会话失败并跳过，以免永久阻塞后续结果。"""
        with self._lock:
            entry = self._entries.get(task_id)
            if entry is None:
                self._remember_closed_locked(task_id)
                return
            entry.status = 'skipped'
            ready = self._flush_locked()
        self._dispatch(ready)

    def cancel(self, task_id: str) -> None:
        self.fail(task_id)

    def fail_submitted(self, connection_generation: int) -> None:
        """连接中断时只跳过已提交到该连接、不会再返回的会话。"""
        with self._lock:
            for entry in self._entries.values():
                if (
                    entry.status == 'pending'
                    and entry.submitted_generation == connection_generation
                ):
                    entry.status = 'skipped'
            ready = self._flush_locked()
        self._dispatch(ready)

    async def get(self) -> Any:
        return await self._ready.get()

    def task_done(self) -> None:
        self._ready.task_done()

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._entries)

    def ready_empty(self) -> bool:
        return self._ready.empty()

    def clear(self) -> None:
        """退出时释放所有登记和已就绪结果。"""
        with self._lock:
            self._entries.clear()
            self._order.clear()
            self._closed_order.clear()
            self._closed_ids.clear()
        if threading.get_ident() == self._owner_thread:
            self._clear_ready()
        elif self._loop.is_running():
            self._loop.call_soon_threadsafe(self._clear_ready)

    def _flush_locked(self) -> list[Any]:
        ready: list[Any] = []
        while self._order:
            task_id = self._order[0]
            entry = self._entries[task_id]
            if entry.status == 'pending':
                break
            self._order.popleft()
            self._entries.pop(task_id, None)
            self._remember_closed_locked(task_id)
            if entry.status == 'ready':
                ready.append(entry.payload)
        return ready

    def _remember_closed_locked(self, task_id: str) -> None:
        if task_id in self._closed_ids:
            return
        if len(self._closed_order) >= 256:
            expired = self._closed_order.popleft()
            self._closed_ids.discard(expired)
        self._closed_order.append(task_id)
        self._closed_ids.add(task_id)

    def _dispatch(self, payloads: list[Any]) -> None:
        for payload in payloads:
            if self._loop.is_running():
                self._loop.call_soon_threadsafe(self._ready.put_nowait, payload)
            else:
                self._ready.put_nowait(payload)

    def _clear_ready(self) -> None:
        while True:
            try:
                self._ready.get_nowait()
            except asyncio.QueueEmpty:
                return
            else:
                self._ready.task_done()
