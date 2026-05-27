from functools import lru_cache
from typing import Annotated, TypeAlias

from fastapi import Depends
from sqlalchemy.engine.base import Engine
from sqlalchemy.engine.create import create_engine
from sqlalchemy.orm.session import Session, sessionmaker

from core import config
from core.adapters.database import uow
from core.adapters.queue import runner
from core.config import get_app_config
from core.domain import ports, protocols


@lru_cache
def get_config() -> config.AppConfig:
    return get_app_config()


@lru_cache
def get_engine(database_uri: str | None = None) -> Engine:
    app_config = get_config()
    if database_uri is None:
        database_uri = app_config.database_uri
    return create_engine(database_uri)


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    if engine is None:
        engine = get_engine()
    return sessionmaker(bind=engine)


def get_uow() -> ports.AbstractUnitOfWork:
    return uow.SqlAlchemyUnitOfWork(
        session_factory=get_session_factory(),
    )


def fresh_uow() -> ports.AbstractUnitOfWork:
    return uow.SqlAlchemyUnitOfWork(
        session_factory=get_session_factory(),
    )


def get_task_runner() -> protocols.TaskRunner:
    return runner.CeleryTaskRunner()


UnitOfWorkDep: TypeAlias = Annotated[ports.AbstractUnitOfWork, Depends(get_uow)]
TaskRunnerDep: TypeAlias = Annotated[protocols.TaskRunner, Depends(get_task_runner)]
