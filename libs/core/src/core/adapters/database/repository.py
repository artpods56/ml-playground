import abc
from collections.abc import Sequence
from datetime import datetime
from typing import final, override

from sqlalchemy import select, func
from sqlalchemy.orm.session import Session

from core.adapters.database import orm
from core.domain import enums, model
from core.domain.exceptions import DomainException


# --- Abstract Repositories ---


class AbstractJobRepository(abc.ABC):
    @abc.abstractmethod
    def add(self, job: model.Job) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get(self, job_id: str) -> model.Job | None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_or_raise(self, job_id: str) -> model.Job:
        raise NotImplementedError

    @abc.abstractmethod
    def list_by_status(self, job_status: enums.JobStatus) -> Sequence[model.Job]:
        raise NotImplementedError

    @abc.abstractmethod
    def list_by_filters(
        self,
        status: enums.JobStatus | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Sequence[model.Job]:
        raise NotImplementedError

    @abc.abstractmethod
    def count_by_filters(
        self,
        status: enums.JobStatus | None = None,
    ) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def delete(self, job: model.Job) -> None:
        raise NotImplementedError


class AbstractOutboxRepository(abc.ABC):
    @abc.abstractmethod
    def add(self, entry: model.OutboxEntry) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def get(self, entry_id: str) -> model.OutboxEntry | None:
        raise NotImplementedError

    @abc.abstractmethod
    def get_or_raise(self, entry_id: str) -> model.OutboxEntry:
        raise NotImplementedError

    @abc.abstractmethod
    def list_pending(self, limit: int = 100) -> Sequence[model.OutboxEntry]:
        raise NotImplementedError

    @abc.abstractmethod
    def mark_as_relayed(self, entry_id: str) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def delete_relayed_older_than(self, cutoff: datetime) -> int:
        raise NotImplementedError


# --- SQLAlchemy Repositories ---


@final
class SQLAlchemyJobRepository(AbstractJobRepository):
    def __init__(self, session: Session):
        self._session = session

    @override
    def add(self, job: model.Job) -> None:
        self._session.add(job)

    @override
    def get(self, job_id: str) -> model.Job | None:
        statement = select(model.Job).where(orm.training_jobs.c.id == job_id)
        return self._session.scalar(statement)

    @override
    def get_or_raise(self, job_id: str) -> model.Job:
        job = self.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id=job_id)
        return job

    @override
    def list_by_status(self, job_status: enums.JobStatus) -> Sequence[model.Job]:
        statement = select(model.Job).where(orm.training_jobs.c.status == job_status)
        return self._session.scalars(statement).all()

    @override
    def list_by_filters(
        self,
        status: enums.JobStatus | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Sequence[model.Job]:
        statement = select(model.Job)
        if status is not None:
            statement = statement.where(orm.training_jobs.c.status == status)
        statement = statement.order_by(orm.training_jobs.c.created_at.desc())
        statement = statement.offset(skip).limit(limit)
        return self._session.scalars(statement).all()

    @override
    def count_by_filters(
        self,
        status: enums.JobStatus | None = None,
    ) -> int:
        statement = select(func.count()).select_from(orm.training_jobs)
        if status is not None:
            statement = statement.where(orm.training_jobs.c.status == status)
        result = self._session.execute(statement).scalar()
        return result if result is not None else 0

    @override
    def delete(self, job: model.Job) -> None:
        self._session.delete(job)


@final
class SQLAlchemyOutboxRepository(AbstractOutboxRepository):
    def __init__(self, session: Session):
        self._session = session

    @override
    def add(self, entry: model.OutboxEntry) -> None:
        self._session.add(entry)

    @override
    def get(self, entry_id: str) -> model.OutboxEntry | None:
        statement = select(model.OutboxEntry).where(orm.outbox_entries.c.id == entry_id)
        return self._session.scalar(statement)

    @override
    def get_or_raise(self, entry_id: str) -> model.OutboxEntry:
        entry = self.get(entry_id)
        if entry is None:
            raise OutboxEntryNotFoundError(entry_id=entry_id)
        return entry

    @override
    def list_pending(self, limit: int = 100) -> Sequence[model.OutboxEntry]:
        statement = (
            select(model.OutboxEntry)
            .where(orm.outbox_entries.c.relayed_at.is_(None))
            .order_by(orm.outbox_entries.c.created_at.asc())
            .limit(limit)
        )
        return self._session.scalars(statement).all()

    @override
    def mark_as_relayed(self, entry_id: str) -> None:
        entry = self.get_or_raise(entry_id)
        entry.mark_as_relayed()

    @override
    def delete_relayed_older_than(self, cutoff: datetime) -> int:
        statement = select(model.OutboxEntry).where(
            orm.outbox_entries.c.relayed_at.isnot(None),
            orm.outbox_entries.c.relayed_at < cutoff,
        )
        entries = self._session.scalars(statement).all()
        count = len(entries)
        for entry in entries:
            self._session.delete(entry)
        return count


# --- Domain-specific errors ---


class JobNotFoundError(DomainException):
    code: str = "JOB_NOT_FOUND"

    def __init__(self, job_id: str, message: str | None = None):
        msg = message or f"Training job not found: {job_id}"
        super().__init__(message=msg, job_id=job_id)


class OutboxEntryNotFoundError(DomainException):
    code: str = "OUTBOX_ENTRY_NOT_FOUND"

    def __init__(self, entry_id: str, message: str | None = None):
        msg = message or f"Outbox entry not found: {entry_id}"
        super().__init__(message=msg, entry_id=entry_id)
