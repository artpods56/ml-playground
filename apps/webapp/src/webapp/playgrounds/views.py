import json
import os
from pathlib import Path

import requests
from django.http import HttpResponse
from django.shortcuts import render

REPO_ROOT = Path(__file__).resolve().parents[5]


def get_fastapi_url() -> str:
    return os.getenv("FASTAPI_URL", "http://127.0.0.1:8000").rstrip("/")


def get_dataset_dir() -> Path | None:
    env_dir = os.getenv("DATASET_DIR") or os.getenv("dataset_dir")
    if env_dir:
        return Path(env_dir)

    default_dir = REPO_ROOT / "datasets"
    if default_dir.exists():
        return default_dir

    return None


def home_view(request):
    available_algorithms = []
    backend_error = None

    try:
        response = requests.get(f"{get_fastapi_url()}/algorithms", timeout=5)
        response.raise_for_status()
        available_algorithms = response.json()
    except requests.RequestException:
        backend_error = (
            "The FastAPI backend is not reachable. Start it on "
            f"{get_fastapi_url()} to load algorithm metadata."
        )

    dataset_dir = get_dataset_dir()
    available_datasets = []
    if dataset_dir and dataset_dir.exists():
        available_datasets = sorted(
            dataset_file.name for dataset_file in dataset_dir.glob("*.csv")
        )

    context = {
        "algorithms": available_algorithms,
        "backend_error": backend_error,
        "datasets": available_datasets,
    }

    return render(request, "pages/playground.html", context=context)


def algorithm_form(request, algorithm_name):
    try:
        resp = requests.get(
            f"{get_fastapi_url()}/algorithms/{algorithm_name}/config_schema",
            timeout=5,
        )
    except requests.RequestException:
        return HttpResponse("Could not fetch schema", status=500)

    if resp.status_code != 200:
        return HttpResponse("Could not fetch schema", status=500)

    schema = resp.json()
    return render(request, "partials/algorithm_inputs.html", {"schema": schema})
