"""动态状态岛的纯状态机，不依赖 Tk，便于测试。"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from time import monotonic
from typing import Optional


class IslandStage(str, Enum):
    IDLE = 'idle'
    RECORDING = 'recording'
    RECOGNIZING = 'recognizing'
    DELIVERED = 'delivered'
    ERROR = 'error'
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

        if event.stage is IslandStage.RECORDING:
            if not event.task_id:
                return False
            self.state = IslandState(
                stage=event.stage,
                task_id=event.task_id,
                message=event.message,
                changed_at=event.created_at,
                revision=current.revision + 1,
            )
            return True

        # 无 task_id 的错误只允许作用于当前活动任务。
        event_task_id = event.task_id or current.task_id
        if current.task_id and event_task_id != current.task_id:
            return False

        if event.stage is IslandStage.IDLE:
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
