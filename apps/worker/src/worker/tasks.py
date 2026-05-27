import json
from typing import Any, Unpack
from celery.utils.log import get_task_logger

from backend.dependencies import fresh_uow, get_task_runner
from backend.jobs import service as jobs_service
from backend.outbox import service as outbox_service
from core.domain import model
from .main import app

logger = get_task_logger(__name__)


def _run_linear_regression_training(
    dataset_name: str,
    target_column: str,
    feature_columns: list[str],
    params: dict,
) -> dict[str, Any]:
    """Run linear regression training and return results."""
    import numpy as np
    import pandas as pd

    from algorithms.supervised.linear_regression import LinearRegression
    from schemas.configs.linear_regression_configs import LinearRegressionParams
    from utils.metrics import r2_score, mean_squared_error, mean_absolute_error

    # Load dataset
    dataset_path = dataset_name
    df = pd.read_csv(dataset_path)

    y = df[target_column].values.astype(np.float64)
    features = (
        feature_columns
        if feature_columns
        else [c for c in df.columns if c != target_column]
    )
    X = df[features].values.astype(np.float64)

    # Build params
    lr_params = LinearRegressionParams(
        learning_rate=float(params.get("learning_rate", 0.01)),
        epochs=int(params.get("epochs", 100)),
        batch_size=int(params["batch_size"]) if params.get("batch_size") else None,
        reg_type=params.get("reg_type") or None,
        reg_strength=float(params.get("reg_strength", 0.01)),
        loss=params.get("loss", "mse"),
        verbose=False,
    )

    model_instance = LinearRegression(lr_params)
    model_instance.fit(X, y)

    y_pred = model_instance.predict(X)
    r2 = float(r2_score(y, y_pred))
    mse = float(mean_squared_error(y, y_pred))
    mae = float(mean_absolute_error(y, y_pred))

    coefficients = model_instance.get_coefficients()
    history = model_instance.get_training_history()

    # Serialize numpy arrays
    results = {
        "r2": r2,
        "mse": mse,
        "mae": mae,
        "weights": coefficients["weights"].tolist(),
        "bias": float(coefficients["bias"]),
        "loss_history": history["training_loss"],
        "features": features,
        "n_samples": int(X.shape[0]),
    }
    return results


# --- Outbox Relay Tasks ---


@app.task(bind=True, max_retries=3)
def relay_outbox_task(self) -> dict[str, Any]:
    task_runner = get_task_runner()

    try:
        relayed_entries = outbox_service.relay_pending_outbox_entries(
            task_runner=task_runner,
            uow=fresh_uow(),
            batch_size=100,
        )
        return {"relayed_count": len(relayed_entries)}
    except Exception as exc:
        logger.error(f"Failed to relay outbox entries: {exc}")
        raise self.retry(exc=exc, countdown=10)


@app.task(bind=True, max_retries=3)
def cleanup_outbox_task(self) -> dict[str, int]:
    try:
        with fresh_uow() as uow:
            deleted_count = outbox_service.cleanup_old_outbox_entries(
                uow=uow,
                retention_hours=24,
            )
        return {"deleted_count": deleted_count}
    except Exception as exc:
        logger.error(f"Failed to clean up outbox entries: {exc}")
        raise self.retry(exc=exc, countdown=60)


# --- Training Task ---


@app.task(bind=True, max_retries=3)
def process_training_job(self, **kwargs: Unpack[model.JobProcessingPayload]):
    """Process a training job asynchronously."""
    job_id = kwargs["job_id"]

    try:
        with fresh_uow() as uow:
            job_dto = jobs_service.get_training_job(job_id, uow)

        params = json.loads(job_dto.params_json) if job_dto.params_json else {}
        feature_columns = (
            json.loads(job_dto.feature_columns) if job_dto.feature_columns else []
        )

        logger.info(
            f"Starting training for job {job_id}, algorithm={job_dto.algorithm}"
        )

        results = _run_linear_regression_training(
            dataset_name=job_dto.dataset_name,
            target_column=job_dto.target_column,
            feature_columns=feature_columns,
            params=params,
        )

        with fresh_uow() as uow:
            jobs_service.complete_training_job(job_id, json.dumps(results), uow)
            uow.commit()

        logger.info(f"Successfully processed training job {job_id}")

    except Exception as exc:
        logger.error(f"Error processing training job {job_id}: {exc}")

        if self.max_retries is not None and self.request.retries >= self.max_retries:
            try:
                with fresh_uow() as uow:
                    jobs_service.fail_training_job(job_id, str(exc), uow)
                    uow.commit()
                logger.info(f"Marked job {job_id} as failed after exhausting retries")
            except Exception as fail_exc:
                logger.error(f"Failed to mark job {job_id} as failed: {fail_exc}")

        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries))
