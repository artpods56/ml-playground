from datetime import datetime
from typing import Self, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from core.domain import enums
from . import dto


class CreateTrainingJobRequest(BaseModel):
    algorithm: str = Field(
        default="linear_regression", description="Algorithm to train"
    )
    dataset_name: str = Field(..., description="Name/path of the dataset")
    target_column: str = Field(..., description="Target variable column name")
    feature_columns: str = Field(..., description="JSON list of feature column names")
    params_json: str = Field(
        default="{}", description="JSON object of algorithm parameters"
    )


class JobResponse(BaseModel):
    id: UUID
    status: enums.JobStatus
    algorithm: str
    dataset_name: str
    target_column: str
    feature_columns: str
    params_json: str
    results_json: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(use_enum_values=False)

    @classmethod
    def from_dto(cls, job: dto.JobDTO) -> Self:
        return cls(
            id=UUID(job.id),
            status=enums.JobStatus(job.status),
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


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
    skip: int
    limit: int
