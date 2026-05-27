from typing import override

from core.domain import model, protocols, dto


class CeleryTaskRunner(protocols.TaskRunner):
    @override
    def schedule_task(self, entry: dto.OutboxEntryDTO) -> None:
        from worker.main import app

        task_name = model.TASK_NAMES.get(entry.event_type)
        if task_name is None:
            raise ValueError(f"No task configured for event type: {entry.event_type}")

        _ = app.send_task(
            task_name,
            task_id=entry.id,
            kwargs={**entry.payload},
        )

    @override
    def revoke_task(self, task_id: str) -> None:
        from worker.main import app

        _ = app.control.revoke(task_id, terminate=True)
