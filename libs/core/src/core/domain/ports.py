import abc
from types import TracebackType
from typing import Self

from core.adapters.database import repository


class AbstractUnitOfWork(abc.ABC):
    jobs: repository.AbstractJobRepository
    outbox: repository.AbstractOutboxRepository

    @abc.abstractmethod
    def rollback(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def __enter__(self) -> Self:
        raise NotImplementedError

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.rollback()

    @abc.abstractmethod
    def commit(self) -> None:
        raise NotImplementedError
