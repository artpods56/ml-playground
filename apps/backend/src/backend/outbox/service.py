from datetime import datetime, timedelta
from collections.abc import Sequence

from core.domain import dto
from core.domain.ports import AbstractUnitOfWork
from core.domain.protocols import TaskRunner
from core.utils import get_logger

logger = get_logger(__name__)


def relay_pending_outbox_entries(
    task_runner: TaskRunner,
    uow: AbstractUnitOfWork,
    batch_size: int = 100,
) -> Sequence[dto.OutboxEntryDTO]:
    relayed_entry_ids: set[str] = set()

    with uow:
        pending_entries = uow.outbox.list_pending(limit=batch_size)

        for entry in pending_entries:
            try:
                entry_dto = dto.OutboxEntryDTO.from_domain(entry)
                task_runner.schedule_task(entry_dto)
                entry.mark_as_relayed()
                relayed_entry_ids.add(entry.id)

                logger.info("Relayed outbox entry", extra={"entry_id": entry.id})
            except Exception as e:
                logger.error(
                    "Failed to relay outbox entry",
                    extra={"entry_id": entry.id, "error": str(e)},
                )

        uow.commit()

        return [
            dto.OutboxEntryDTO.from_domain(entry)
            for entry in pending_entries
            if entry.id in relayed_entry_ids
        ]


def cleanup_old_outbox_entries(
    uow: AbstractUnitOfWork,
    retention_hours: int = 24,
) -> int:
    with uow:
        cutoff = datetime.now() - timedelta(hours=retention_hours)
        deleted_count = uow.outbox.delete_relayed_older_than(cutoff)
        uow.commit()

        if deleted_count > 0:
            logger.info(
                "Cleaned up old outbox entries", extra={"deleted_count": deleted_count}
            )

        return deleted_count
