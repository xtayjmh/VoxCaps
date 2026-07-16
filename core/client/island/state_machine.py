"""动态状态岛的纯状态机，不依赖 Tk，便于测试。"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from enum import Enum
from time import monotonic
from typing import Optional


class IslandStage(str, Enum):
    IDLE = 'idle'
    PREPARING = 'preparing'
    RECORDING = 'recording'
    RECOGNIZING = 'recognizing'
    STOP = 'stop'


@dataclass(frozen=True)
class IslandEvent:
    stage: IslandStage
    task_id: Optional[str] = None
    message: str = ''
    created_at: float = 0.0

    def __post_init__(self) -> None:
        if self.created_at == 0.0:
            object.__setattr__(self, 'created_at', monotonic())


@dataclass(frozen=True)
class IslandState:
    stage: IslandStage = IslandStage.IDLE
    task_id: Optional[str] = None
    message: str = ''
    changed_at: float = 0.0
    revision: int = 0


class IslandStateMachine:
    """只接受当前任务的后续事件，忽略迟到的旧识别结果。"""

    def __init__(self) -> None:
        self.state = IslandState(changed_at=monotonic())
        self._retired_order: deque[str] = deque()
        self._retired_ids: set[str] = set()

    def apply(self, event: IslandEvent) -> bool:
        current = self.state

        if event.stage is IslandStage.STOP:
            self.state = replace(
                current,
                stage=IslandStage.STOP,
                message='',
                changed_at=event.created_at,
                revision=current.revision + 1,
            )
            return True

        if current.revision and event.created_at < current.changed_at:
            return False

        if event.task_id and event.task_id in self._retired_ids:
            return False

        if event.stage in (IslandStage.PREPARING, IslandStage.RECORDING):
            if not event.task_id:
                return False
            if current.task_id and current.task_id != event.task_id:
                self._retire(current.task_id)
            self.state = IslandState(
                stage=event.stage,
                task_id=event.task_id,
                message=event.message,
                changed_at=event.created_at,
                revision=current.revision + 1,
            )
            return True

        event_task_id = event.task_id or current.task_id
        if current.task_id and event_task_id != current.task_id:
            return False

        if event.stage is IslandStage.IDLE:
            self._retire(event_task_id)
            self.state = IslandState(
                stage=IslandStage.IDLE,
                changed_at=event.created_at,
                revision=current.revision + 1,
            )
            return True

        if not event_task_id:
            return False

        self.state = IslandState(
            stage=event.stage,
            task_id=event_task_id,
            message=event.message,
            changed_at=event.created_at,
            revision=current.revision + 1,
        )
        return True

    def _retire(self, task_id: Optional[str]) -> None:
        if not task_id or task_id in self._retired_ids:
            return
        if len(self._retired_order) >= 128:
            expired = self._retired_order.popleft()
            self._retired_ids.discard(expired)
        self._retired_order.append(task_id)
        self._retired_ids.add(task_id)
