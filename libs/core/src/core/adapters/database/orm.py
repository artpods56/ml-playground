from typing import Any, final, override

import msgspec
from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    MetaData,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import registry
from sqlalchemy.types import TypeDecorator

from core.domain import enums, model

mapper_registry = registry()
metadata = MetaData()

training_jobs = Table(
    "training_jobs",
    metadata,
    Column("id", String(255), primary_key=True),
    Column("created_at", DateTime),
    Column("error_message", String(1024), nullable=True),
    Column("started_at", DateTime, nullable=True),
    Column("completed_at", DateTime, nullable=True),
    Column("task_id", String(255), nullable=True),
    Column("status", Enum(enums.JobStatus), nullable=False),
    Column("algorithm", String(100), nullable=False, default="linear_regression"),
    Column("dataset_name", String(500), nullable=False, default=""),
    Column("target_column", String(255), nullable=False, default=""),
    Column("feature_columns", Text, nullable=False, default=""),
    Column("params_json", Text, nullable=False, default="{}"),
    Column("results_json", Text, nullable=True),
)


@final
class JsonType(TypeDecorator[dict[str, Any] | None]):
    impl = Text
    cache_ok = True

    @override
    def process_bind_param(
        self, value: dict[str, Any] | None, dialect: object
    ) -> str | None:
        if value is None:
            return None
        return msgspec.json.encode(value).decode("utf-8")

    @override
    def process_result_value(
        self, value: str | None, dialect: object
    ) -> dict[str, Any] | None:
        if value is None:
            return None
        return msgspec.json.decode(value, type=dict[str, Any])


outbox_entries = Table(
    "outbox_entries",
    metadata,
    Column("id", String(255), primary_key=True),
    Column("event_type", Enum(enums.OutboxEventType), nullable=False),
    Column("aggregate_id", String(255), nullable=False, index=True),
    Column("payload", JsonType, nullable=False),
    Column("created_at", DateTime, nullable=False, index=True),
    Column("relayed_at", DateTime, nullable=True, index=True),
)


def start_mappers() -> None:
    if mapper_registry.mappers:
        return

    _ = mapper_registry.map_imperatively(model.Job, training_jobs)
    _ = mapper_registry.map_imperatively(model.OutboxEntry, outbox_entries)
