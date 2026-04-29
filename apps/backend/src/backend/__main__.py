"""CLI entrypoint for running the FastAPI backend locally."""

import os

import uvicorn


def main() -> None:
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    reload_enabled = os.getenv("BACKEND_RELOAD", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
    )
