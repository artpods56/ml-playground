from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from starlette import status
from starlette.responses import Response

from backend import dependencies
from . import schema, service

router = APIRouter()


@router.post(
    "",
    response_model=schema.JobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_training_job(
    request: schema.CreateTrainingJobRequest,
    uow: dependencies.UnitOfWorkDep,
) -> schema.JobResponse:
    return schema.JobResponse.from_dto(
        service.submit_training_job(
            algorithm=request.algorithm,
            dataset_name=request.dataset_name,
            target_column=request.target_column,
            feature_columns=request.feature_columns,
            params_json=request.params_json,
            uow=uow,
        )
    )


@router.post("/{job_id}/start")
def start_training_job(
    job_id: UUID,
    uow: dependencies.UnitOfWorkDep,
) -> schema.JobResponse:
    try:
        job_dto = service.start_job_processing(str(job_id), uow=uow)
        return schema.JobResponse.from_dto(job_dto)
    except Exception as e:
        job_dto = service.fail_training_job(str(job_id), str(e), uow=uow)
        return schema.JobResponse.from_dto(job_dto)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_training_job(
    job_id: UUID,
    uow: dependencies.UnitOfWorkDep,
) -> Response:
    service.delete_training_job(str(job_id), uow)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{job_id}/retry",
    response_model=schema.JobResponse,
    status_code=status.HTTP_201_CREATED,
)
def retry_training_job(
    job_id: UUID,
    uow: dependencies.UnitOfWorkDep,
) -> schema.JobResponse:
    return schema.JobResponse.from_dto(service.retry_training_job(str(job_id), uow))


@router.get("", response_model=schema.JobListResponse)
def list_training_jobs(
    uow: dependencies.UnitOfWorkDep,
    job_status: Annotated[
        str | None,
        Query(
            alias="status",
            description="Filter by job status (pending, processing, completed, failed)",
        ),
    ] = None,
    skip: Annotated[
        int,
        Query(ge=0, description="Number of items to skip (offset)"),
    ] = 0,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Maximum number of items to return (max: 100)"),
    ] = 20,
) -> schema.JobListResponse:
    job_dtos, total = service.get_training_jobs(
        uow=uow,
        status=job_status,
        skip=skip,
        limit=limit,
    )

    return schema.JobListResponse(
        jobs=[schema.JobResponse.from_dto(d) for d in job_dtos],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{job_id}",
    response_model=schema.JobResponse,
    status_code=status.HTTP_200_OK,
)
def get_training_job_by_id(
    job_id: UUID,
    uow: dependencies.UnitOfWorkDep,
) -> schema.JobResponse:
    return schema.JobResponse.from_dto(service.get_training_job(str(job_id), uow))


@router.post("/{job_id}/cancel")
def cancel_training_job(
    job_id: UUID,
    task_runner: dependencies.TaskRunnerDep,
    uow: dependencies.UnitOfWorkDep,
) -> schema.JobResponse:
    return schema.JobResponse.from_dto(
        service.cancel_training_job(str(job_id), task_runner, uow)
    )
