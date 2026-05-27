from typing import Protocol, runtime_checkable

from core.domain import dto


@runtime_checkable
class TaskRunner(Protocol):
    def schedule_task(self, entry: dto.OutboxEntryDTO) -> None: ...

    def revoke_task(self, task_id: str) -> None: ...
