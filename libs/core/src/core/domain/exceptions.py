from typing import Any

from core.domain.enums import JobStatus


class DomainException(Exception):
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, **context: Any):
        super().__init__(message)
        self.context: dict[str, Any] = context
        self.context["code"] = self.code


class InvalidJobStatusTransitionError(DomainException):
    code: str = "INVALID_JOB_STATUS_TRANSITION"

    def __init__(
        self, job_id: str, current: JobStatus, attempted: JobStatus, reason: str
    ):
        msg = (
            f"Job: {job_id} cannot transition from {current.name} to {attempted.name}."
            f"{reason}"
        )
        super().__init__(
            message=msg,
            job_id=job_id,
            current_status=current.value,
            attempted_status=attempted.value,
        )


class UnknownJobStatusError(DomainException):
    code: str = "UNKNOWN_JOB_STATUS"

    def __init__(self, status: str, message: str | None = None):
        msg = message or f"Unknown job status {status}."
        super().__init__(message=msg, status=status)


class OutboxEntryAlreadyRelayedError(DomainException):
    code: str = "OUTBOX_ENTRY_ALREADY_RELAYED"

    def __init__(self, entry_id: str, message: str | None = None):
        msg = message or f"Outbox entry {entry_id} has already been relayed."
        super().__init__(message=msg, entry_id=entry_id)
