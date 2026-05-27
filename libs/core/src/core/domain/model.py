import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar, Literal, TypedDict

from core.domain.enums import JobStatus, OutboxEventType
from core.domain.exceptions import (
    InvalidJobStatusTransitionError,
    OutboxEntryAlreadyRelayedError,
)
from core.consts import WORKER_NAMESPACE


def generate_id() -> str:
    return str(uuid.uuid4())


type AllowedJobStatusTransitions = dict[JobStatus, tuple[tuple[JobStatus, ...], str]]


@dataclass
class Job:
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=datetime.now)
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    task_id: str | None = None
    status: JobStatus = JobStatus.PENDING

    # Training job fields
    algorithm: str = "linear_regression"
    dataset_name: str = ""
    target_column: str = ""
    feature_columns: str = ""  # JSON-encoded list
    params_json: str = "{}"  # JSON-encoded params dict

    # Training results
    results_json: str | None = None  # JSON-encoded training results

    _ALLOWED_TRANSITIONS: ClassVar[AllowedJobStatusTransitions] = {
        JobStatus.PENDING: (
            (JobStatus.PROCESSING, JobStatus.FAILED),
            "Pending jobs can only start processing or fail.",
        ),
        JobStatus.PROCESSING: (
            (JobStatus.COMPLETED, JobStatus.FAILED),
            "Processing jobs can only complete or fail.",
        ),
        JobStatus.COMPLETED: (
            (),
            "Completed jobs cannot transition to another status.",
        ),
        JobStatus.FAILED: (
            (),
            "Failed jobs cannot transition to another status.",
        ),
    }

    @property
    def is_terminal(self) -> bool:
        return self.status in (JobStatus.FAILED, JobStatus.COMPLETED)

    @property
    def is_active(self) -> bool:
        return self.status in (JobStatus.PENDING, JobStatus.PROCESSING)

    def assign_task_id(self, task_id: str):
        self.task_id = task_id

    def update_status(self, new_status: JobStatus, error_message: str | None = None):
        if self.status == new_status:
            return

        transitions_with_reason = self._ALLOWED_TRANSITIONS.get(self.status)
        if transitions_with_reason is None:
            raise InvalidJobStatusTransitionError(
                job_id=self.id,
                current=self.status,
                attempted=new_status,
                reason="Unknown job status has been provided.",
            )

        allowed_targets, reason = transitions_with_reason
        if new_status not in allowed_targets:
            raise InvalidJobStatusTransitionError(
                job_id=self.id,
                current=self.status,
                attempted=new_status,
                reason=reason,
            )

        match new_status:
            case JobStatus.PROCESSING:
                self.started_at = datetime.now()
            case JobStatus.COMPLETED:
                self.completed_at = datetime.now()
            case JobStatus.FAILED:
                self.completed_at = datetime.now()
                self.error_message = error_message
            case _:
                pass

        self.status = new_status


# --- Outbox Pattern ---


class JobProcessingPayload(TypedDict):
    type: Literal["job_processing"]
    job_id: str


type OutboxPayload = JobProcessingPayload

TASK_NAMES = {
    OutboxEventType.JOB_SCHEDULING: ".".join(
        [WORKER_NAMESPACE, "tasks", "process_training_job"]
    ),
}


@dataclass
class OutboxEntry:
    event_type: OutboxEventType
    aggregate_id: str
    payload: OutboxPayload
    id: str = field(default_factory=generate_id)
    created_at: datetime = field(default_factory=datetime.now)
    relayed_at: datetime | None = None

    @property
    def is_relayed(self) -> bool:
        return self.relayed_at is not None

    def mark_as_relayed(self) -> None:
        if self.is_relayed:
            raise OutboxEntryAlreadyRelayedError(entry_id=self.id)
        self.relayed_at = datetime.now()
