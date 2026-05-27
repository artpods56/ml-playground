from typing import Sequence

from core.domain import enums, exceptions, model
from core.domain.ports import AbstractUnitOfWork
from core.domain.protocols import TaskRunner
from core.utils import get_logger
from core.domain.model import generate_id
from . import dto

logger = get_logger(__name__)


def get_training_job(job_id: str, uow: AbstractUnitOfWork) -> dto.JobDTO:
    with uow:
        return dto.JobDTO.from_domain(uow.jobs.get_or_raise(job_id))


def get_training_jobs(
    uow: AbstractUnitOfWork,
    status: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[Sequence[dto.JobDTO], int]:
    with uow:
        if status:
            if status not in [s.value for s in enums.JobStatus]:
                raise exceptions.UnknownJobStatusError(status=status)

        job_status = enums.JobStatus(status) if status else None

        jobs = uow.jobs.list_by_filters(
            status=job_status,
            skip=skip,
            limit=limit,
        )

        total = uow.jobs.count_by_filters(status=job_status)

        return [dto.JobDTO.from_domain(job) for job in jobs], total


def submit_training_job(
    algorithm: str,
    dataset_name: str,
    target_column: str,
    feature_columns: str,
    params_json: str,
    uow: AbstractUnitOfWork,
) -> dto.JobDTO:
    logger.info(
        "Submitting training job",
        extra={"algorithm": algorithm, "dataset": dataset_name},
    )

    with uow:
        job = model.Job(
            id=generate_id(),
            algorithm=algorithm,
            dataset_name=dataset_name,
            target_column=target_column,
            feature_columns=feature_columns,
            params_json=params_json,
        )
        uow.jobs.add(job)
        uow.commit()

        logger.info(
            "Training job created", extra={"job_id": job.id, "algorithm": algorithm}
        )
        return dto.JobDTO.from_domain(job)


def start_job_processing(job_id: str, uow: AbstractUnitOfWork) -> dto.JobDTO:
    task_id = generate_id()

    with uow:
        job = uow.jobs.get_or_raise(job_id)
        job.assign_task_id(task_id)
        job.update_status(enums.JobStatus.PROCESSING)

        payload: model.JobProcessingPayload = {
            "type": "job_processing",
            "job_id": job.id,
        }

        outbox_entry = model.OutboxEntry(
            id=generate_id(),
            event_type=enums.OutboxEventType.JOB_SCHEDULING,
            aggregate_id=job.id,
            payload=payload,
        )
        uow.outbox.add(outbox_entry)
        uow.commit()

        logger.info(
            "Job marked as processing",
            extra={"job_id": job_id, "task_id": task_id},
        )

        return dto.JobDTO.from_domain(job)


def complete_training_job(
    job_id: str, results_json: str, uow: AbstractUnitOfWork
) -> dto.JobDTO:
    with uow:
        job = uow.jobs.get_or_raise(job_id)
        job.results_json = results_json
        job.update_status(enums.JobStatus.COMPLETED)
        uow.commit()

        return dto.JobDTO.from_domain(job)


def fail_training_job(
    job_id: str, error_message: str, uow: AbstractUnitOfWork
) -> dto.JobDTO:
    with uow:
        job = uow.jobs.get_or_raise(job_id)
        job.update_status(enums.JobStatus.FAILED, error_message=error_message)
        uow.commit()

        return dto.JobDTO.from_domain(job)


def cancel_training_job(
    job_id: str, task_runner: TaskRunner, uow: AbstractUnitOfWork
) -> dto.JobDTO:
    with uow:
        job = uow.jobs.get_or_raise(job_id)

        match job.status:
            case enums.JobStatus.PENDING:
                job.update_status(
                    enums.JobStatus.FAILED, error_message="Cancelled by user"
                )
            case enums.JobStatus.PROCESSING:
                task_id = job.task_id
                if task_id:
                    try:
                        task_runner.revoke_task(task_id)
                    except Exception as e:
                        logger.exception(
                            "Failed to revoke task",
                            extra={"task_id": task_id, "error": str(e)},
                        )

                job.update_status(
                    enums.JobStatus.FAILED,
                    error_message="Cancelled by user",
                )
            case _:
                return dto.JobDTO.from_domain(job)

        uow.commit()
        return dto.JobDTO.from_domain(job)


def retry_training_job(job_id: str, uow: AbstractUnitOfWork) -> dto.JobDTO:
    logger.info("Retrying failed job", extra={"job_id": job_id})

    with uow:
        original_job = uow.jobs.get_or_raise(job_id)

        if original_job.status != enums.JobStatus.FAILED:
            raise exceptions.InvalidJobStatusTransitionError(
                job_id=job_id,
                current=original_job.status,
                attempted=enums.JobStatus.PENDING,
                reason="Only failed jobs can be retried.",
            )

        new_job = model.Job(
            id=generate_id(),
            algorithm=original_job.algorithm,
            dataset_name=original_job.dataset_name,
            target_column=original_job.target_column,
            feature_columns=original_job.feature_columns,
            params_json=original_job.params_json,
        )
        uow.jobs.add(new_job)
        uow.commit()

        logger.info(
            "Created retry job",
            extra={"original_job_id": job_id, "new_job_id": new_job.id},
        )
        return dto.JobDTO.from_domain(new_job)


def delete_training_job(job_id: str, uow: AbstractUnitOfWork) -> None:
    with uow:
        job = uow.jobs.get_or_raise(job_id)

        if not job.is_terminal:
            raise exceptions.InvalidJobStatusTransitionError(
                job_id=job_id,
                current=job.status,
                attempted=enums.JobStatus.FAILED,
                reason="Cannot delete non-terminal jobs.",
            )

        uow.jobs.delete(job)
        uow.commit()

        logger.info("Deleted training job", extra={"job_id": job_id})
