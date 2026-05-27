from dataclasses import dataclass
from datetime import datetime
from typing import Self

from core.domain import model, enums


@dataclass
class OutboxEntryDTO:
    id: str
    event_type: enums.OutboxEventType
    aggregate_id: str
    payload: model.OutboxPayload
    created_at: datetime
    is_pending: bool
    relayed_at: datetime | None = None

    @classmethod
    def from_domain(cls, entry: model.OutboxEntry) -> Self:
        return cls(
            id=entry.id,
            event_type=entry.event_type,
            aggregate_id=entry.aggregate_id,
            payload=entry.payload,
            created_at=entry.created_at,
            relayed_at=entry.relayed_at,
            is_pending=entry.relayed_at is None,
        )
