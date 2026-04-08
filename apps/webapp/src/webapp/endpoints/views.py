import json
import os
import logging
from pathlib import Path

from django.http import JsonResponse, FileResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[5]


def get_dataset_dir() -> Path | None:
    env_dir = os.getenv("DATASET_DIR") or os.getenv("dataset_dir")
    if env_dir:
        return Path(env_dir)

    default_dir = REPO_ROOT / "datasets"
    if default_dir.exists():
        return default_dir

    return None

@csrf_exempt
@require_POST
def load_file(request):
    data = json.loads(request.body)
    file = data.get("datasetFileName")
    dataset_dir = get_dataset_dir()
    try:
        if dataset_dir is None:
            return JsonResponse({"error": "Dataset directory is not configured"}, status=404)

        file_path = dataset_dir / file
        logger.debug("File path: %s", file_path)

        if file_path.exists():
            return FileResponse(open(file_path, "rb"), as_attachment=True, filename=file)
        return JsonResponse({"error": "File not found"}, status=404)

    except (OSError, ValueError) as e:
        logger.error("Error while loading file: %s", e)
        return JsonResponse({"error": str(e)}, status=500)
