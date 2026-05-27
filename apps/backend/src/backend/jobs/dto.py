from dataclasses import dataclass
from datetime import datetime
from typing import Self

from core.domain import model


@dataclass(frozen=True)
class JobDTO:
    id: str
    task_id: str | None
    status: str
    algorithm: str
    dataset_name: str
    target_column: str
    feature_columns: str
    params_json: str
    results_json: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None

    @classmethod
    def from_domain(cls, job: model.Job) -> Self:
        return cls(
            id=job.id,
            task_id=job.task_id,
            status=job.status.value,
            algorithm=job.algorithm,
            dataset_name=job.dataset_name,
            target_column=job.target_column,
            feature_columns=job.feature_columns,
            params_json=job.params_json,
            results_json=job.results_json,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error_message=job.error_message,
        )
