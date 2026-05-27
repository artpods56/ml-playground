from pathlib import Path
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        if (parent / "pyproject.toml").is_file() and (parent / "apps").is_dir():
            return parent
    raise RuntimeError("Could not find project root.")


REPO_ROOT: Path = _find_repo_root()


class DatabaseSettings(BaseSettings):
    db_scheme: Literal["sqlite", "mysql", "postgres"] = "sqlite"
    db_path: str = "service.db"

    @property
    def database_uri(self) -> str:
        if self.db_scheme == "sqlite":
            return f"sqlite:///{self.db_path}"
        raise NotImplementedError(f"Scheme {self.db_scheme} not yet supported.")


class AppConfig(DatabaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ML_PLAYGROUND_",
        env_file=str(REPO_ROOT / ".env"),
        extra="allow",
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


@lru_cache()
def get_app_config() -> AppConfig:
    return AppConfig()
