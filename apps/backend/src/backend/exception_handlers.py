from typing import final

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from core.adapters.database import repository
from core.domain import exceptions


@final
class ExceptionResponseFactory:
    def __init__(self, status_code: int):
        self.status_code = status_code

    def __call__(self, request: Request, exception: Exception) -> JSONResponse:
        return JSONResponse(
            content={"detail": getattr(exception, "message", str(exception))},
            status_code=self.status_code,
        )


def register_handlers(app: FastAPI):
    app.add_exception_handler(
        exceptions.InvalidJobStatusTransitionError,
        ExceptionResponseFactory(status.HTTP_400_BAD_REQUEST),
    )
    app.add_exception_handler(
        exceptions.UnknownJobStatusError,
        ExceptionResponseFactory(status.HTTP_400_BAD_REQUEST),
    )
    app.add_exception_handler(
        repository.JobNotFoundError,
        ExceptionResponseFactory(status.HTTP_404_NOT_FOUND),
    )
    app.add_exception_handler(
        ValueError,
        ExceptionResponseFactory(status.HTTP_400_BAD_REQUEST),
    )
