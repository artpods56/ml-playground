"""CLI helpers for running the Django web app locally."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

from django.core.management import execute_from_command_line

import webapp  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parents[4]
CSS_OUTPUT = REPO_ROOT / "apps/webapp/src/webapp/static/css/styles.css"


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_css() -> None:
    npm_path = shutil.which("npm")
    if npm_path is None:
        raise SystemExit(
            "npm is required to build the frontend CSS. Install Node.js and npm, "
            "then rerun `uv run webapp-css-build`."
        )

    if not (REPO_ROOT / "node_modules").exists():
        subprocess.run([npm_path, "install"], cwd=REPO_ROOT, check=True)

    subprocess.run([npm_path, "run", "webapp:css:build"], cwd=REPO_ROOT, check=True)


def ensure_css() -> None:
    if CSS_OUTPUT.exists() and not _env_bool("WEBAPP_BUILD_CSS", default=False):
        return

    build_css()


def manage() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    execute_from_command_line(sys.argv)


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    ensure_css()

    argv = list(sys.argv)
    if len(argv) == 1:
        host = os.getenv("WEBAPP_HOST", "127.0.0.1")
        port = os.getenv("WEBAPP_PORT", "8050")
        argv.extend(["runserver", f"{host}:{port}"])

    execute_from_command_line(argv)
