"""FastAPI application providing endpoints for machine learning algorithm configurations.

This module serves as the main entry point for the ML Playground API, providing endpoints
to list available algorithms, fetch their configurations, and handle WebSocket connections
for real-time interactions.
"""

import io
import json
import logging
from typing import Dict, List, Type

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from schemas.configs.decision_tree_config import DecisionTreeParams
from schemas.configs.k_nearest_neighbour_config import KNeighborsParams
from schemas.configs.kmeans_config import KMeansParams
from schemas.configs.linear_regression_configs import LinearRegressionParams
from schemas.configs.logistic_regression_config import LogisticRegressionParams
from schemas.configs.polynomial_regression_configs import PolynomialRegressionParams
from schemas.interface.algorithm_interface import AlgorithmInfo
from utils.metrics import mean_absolute_error, mean_squared_error, r2_score

app = FastAPI(
    title="ML Playground API",
    description="API to fetch configurations for machine learning algorithms.",
    version="1.0.0",
)


class AlgorithmRegistryEntry:
    """Registry entry for ML algorithms containing metadata and configuration schema.

    Attributes:
        info: Algorithm metadata including name and description
        pydantic_model: Configuration schema class for the algorithm
    """

    def __init__(self, info: AlgorithmInfo, pydantic_model: Type):
        self.info = info
        self.pydantic_model = pydantic_model


ALGORITHM_REGISTRY: Dict[str, AlgorithmRegistryEntry] = {
    "linear_regression": AlgorithmRegistryEntry(
        AlgorithmInfo(
            internal_name="linear_regression",
            display_name="Linear Regression",
            description="A simple linear regression model.",
        ),
        LinearRegressionParams,
    ),
    "decision_tree": AlgorithmRegistryEntry(
        AlgorithmInfo(
            internal_name="decision_tree",
            display_name="Decision Tree",
            description="A decision tree algorithm for classification and regression.",
        ),
        DecisionTreeParams,
    ),
    "k_nearest_neighbours": AlgorithmRegistryEntry(
        AlgorithmInfo(
            internal_name="k_nearest_neighbours",
            display_name="K-Nearest Neighbours",
            description=(
                "A k-nearest neighbours algorithm for classification and regression."
            ),
        ),
        KNeighborsParams,
    ),
    "kmeans": AlgorithmRegistryEntry(
        AlgorithmInfo(
            internal_name="kmeans",
            display_name="K-Means Clustering",
            description="A k-means clustering algorithm to partition data into k clusters.",
        ),
        KMeansParams,
    ),
    "logistic_regression": AlgorithmRegistryEntry(
        AlgorithmInfo(
            internal_name="logistic_regression",
            display_name="Logistic Regression",
            description="A logistic regression algorithm for binary classification.",
        ),
        LogisticRegressionParams,
    ),
    "polynomial_regression": AlgorithmRegistryEntry(
        AlgorithmInfo(
            internal_name="polynomial_regression",
            display_name="Polynomial Regression",
            description="A polynomial regression algorithm for non-linear relationships.",
        ),
        PolynomialRegressionParams,
    ),
}

# Configure logging
logging.basicConfig(level=logging.INFO)

connected_clients = []


@app.get("/algorithms", response_model=List[AlgorithmInfo])
async def list_available_algorithms():
    """List all available machine learning algorithms.

    Returns:
        List[AlgorithmInfo]: List of algorithm metadata including names and descriptions
    """
    return [entry.info for entry in ALGORITHM_REGISTRY.values()]


@app.get("/algorithms/{algorithm_name}/config_schema")
async def get_algorithm_config_schema(algorithm_name: str):
    """Retrieve the configuration schema for a specific algorithm.

    Args:
        algorithm_name (str): Name of the algorithm to get configuration for

    Returns:
        dict: JSON schema for the algorithm's configuration

    Raises:
        HTTPException: If the specified algorithm is not found (404)
    """
    entry = ALGORITHM_REGISTRY.get(algorithm_name)
    if not entry:
        raise HTTPException(status_code=404, detail="Algorithm not found")
    return entry.pydantic_model.model_json_schema()


def _sanitize_params(params: dict) -> dict:
    """Sanitize algorithm parameters from the frontend form.

    The form may send empty strings for optional fields. Convert them to
    proper Python types expected by the pydantic config models.
    """
    cleaned = {}
    for key, value in params.items():
        if value == "" or value is None:
            continue
        cleaned[key] = value
    return cleaned


async def _run_linear_regression(
    websocket: WebSocket,
    dataset_csv: str,
    dependent_variable: str,
    independent_variable: str,
    params: dict,
):
    """Run linear regression epoch-by-epoch, streaming results via WebSocket."""
    import asyncio

    from algorithms.supervised.linear_regression import LinearRegression

    logging.info(
        "Starting linear regression: dep=%s indep=%s params=%s",
        dependent_variable,
        independent_variable,
        params,
    )

    df = pd.read_csv(io.StringIO(dataset_csv))
    logging.info("Dataset loaded: %d rows, columns=%s", len(df), list(df.columns))

    y_raw = df[dependent_variable].values.astype(np.float64)
    X_raw = df[independent_variable].values.astype(np.float64).reshape(-1, 1)

    # Standardize features and target to prevent gradient explosion
    x_mean, x_std = X_raw.mean(), X_raw.std()
    y_mean, y_std = y_raw.mean(), y_raw.std()
    if x_std == 0:
        x_std = 1.0
    if y_std == 0:
        y_std = 1.0
    X = (X_raw - x_mean) / x_std
    y = (y_raw - y_mean) / y_std

    total_epochs = int(params.get("epochs", 100))

    # Build clean param dict with safe defaults
    batch_size = params.get("batch_size")
    if batch_size is not None:
        batch_size = int(batch_size)

    reg_type = params.get("reg_type") or None

    lr_params = LinearRegressionParams(
        learning_rate=float(params.get("learning_rate", 0.01)),
        epochs=1,  # We run one epoch at a time to stream updates
        batch_size=batch_size,
        reg_type=reg_type,
        reg_strength=float(params.get("reg_strength", 0.01)),
        loss=params.get("loss", "mse"),
        verbose=False,
    )

    logging.info("LinearRegressionParams created: %s", lr_params)

    model = LinearRegression(lr_params)
    model._initialize_parameters(X.shape[1])

    x_plot = np.linspace(float(X.min()), float(X.max()), 100).reshape(-1, 1)

    all_epochs: list[int] = []
    all_r2: list[float] = []
    all_mse: list[float] = []
    all_rmse: list[float] = []
    all_mae: list[float] = []
    all_loss: list[float] = []

    logging.info("Starting training loop for %d epochs", total_epochs)

    for epoch in range(1, total_epochs + 1):
        # Run one epoch
        if model.params.batch_size is None:
            dw, db = model._compute_gradients(X, y)
            model._update_parameters(dw, db)
        else:
            actual_batch_size = model.params.batch_size
            indices = np.random.permutation(len(X))
            for i in range(0, len(X), actual_batch_size):
                batch_idx = indices[i : i + actual_batch_size]
                dw, db = model._compute_gradients(X[batch_idx], y[batch_idx])
                model._update_parameters(dw, db)

        current_loss = model._compute_loss(X, y)
        model.loss_history.append(current_loss)

        y_pred = model.predict(X)

        r2_val = float(r2_score(y, y_pred))
        mse_val = float(mean_squared_error(y, y_pred))
        rmse_val = float(np.sqrt(mse_val))
        mae_val = float(mean_absolute_error(y, y_pred))

        all_epochs.append(epoch)
        all_r2.append(r2_val)
        all_mse.append(mse_val)
        all_rmse.append(rmse_val)
        all_mae.append(mae_val)
        all_loss.append(float(current_loss))

        # Send update every 10 epochs or on last epoch
        if epoch % 10 == 0 or epoch == total_epochs:
            y_plot = model.predict(x_plot)
            payload = {
                "task": "update_plot",
                "current_epoch": epoch,
                "total_epochs": total_epochs,
                "x_data": X.flatten().tolist(),
                "y_data": y.tolist(),
                "x_plot": x_plot.flatten().tolist(),
                "y_pred": y_plot.tolist(),
                "r2": r2_val,
                "mse": mse_val,
                "rmse": rmse_val,
                "mae": mae_val,
                "epochs": all_epochs,
                "r2_values": all_r2,
                "mse_values": all_mse,
                "rmse_values": all_rmse,
                "mae_values": all_mae,
                "loss_values": all_loss,
            }
            await websocket.send_json(payload)
            # Yield to the event loop so the client can process the message
            await asyncio.sleep(0.05)

    # Send completion message
    y_plot = model.predict(x_plot)
    await websocket.send_json({
        "task": "training_complete",
        "current_epoch": total_epochs,
        "total_epochs": total_epochs,
        "x_data": X.flatten().tolist(),
        "y_data": y.tolist(),
        "x_plot": x_plot.flatten().tolist(),
        "y_pred": y_plot.tolist(),
        "r2": all_r2[-1] if all_r2 else 0,
        "mse": all_mse[-1] if all_mse else 0,
        "rmse": all_rmse[-1] if all_rmse else 0,
        "mae": all_mae[-1] if all_mae else 0,
        "epochs": all_epochs,
        "r2_values": all_r2,
        "mse_values": all_mse,
        "rmse_values": all_rmse,
        "mae_values": all_mae,
        "loss_values": all_loss,
    })
    logging.info("Training complete. Final R2=%.4f MSE=%.4f", all_r2[-1] if all_r2 else 0, all_mse[-1] if all_mse else 0)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections for real-time communication.

    Args:
        websocket (WebSocket): WebSocket connection instance
    """
    await websocket.accept()

    while True:
        try:
            data = await websocket.receive_json()
            task = data.get("task")
            logging.info("Received task: %s", task)

            if task == "prepare_model":
                # Store dataset info on the websocket for subsequent train_model
                websocket.state.dataset = data.get("dataset")
                websocket.state.dependent_variable = data.get("dependent_variable")
                websocket.state.independent_variable = data.get("independent_variable")
                websocket.state.algorithm = data.get("algorithm", "linear_regression")
                websocket.state.params = data.get("params", {})

                await websocket.send_json({"task": "prepare_model", "status": "ready"})

            elif task == "train_model":
                dataset = getattr(websocket.state, "dataset", None)
                dep_var = getattr(websocket.state, "dependent_variable", None)
                indep_var = getattr(websocket.state, "independent_variable", None)
                params = getattr(websocket.state, "params", {})
                algorithm = getattr(websocket.state, "algorithm", "linear_regression")

                logging.info(
                    "train_model: algorithm=%s dep=%s indep=%s dataset_len=%d",
                    algorithm, dep_var, indep_var,
                    len(dataset) if dataset else 0,
                )

                if not dataset or not dep_var or not indep_var:
                    await websocket.send_json({"task": "error", "message": "Model not prepared. Run Prepare Model first."})
                    continue

                if algorithm == "linear_regression":
                    await _run_linear_regression(websocket, dataset, dep_var, indep_var, params)
                else:
                    await websocket.send_json({"task": "error", "message": f"Algorithm '{algorithm}' training not yet implemented."})

            else:
                logging.warning("Unknown task: %s", task)

        except WebSocketDisconnect:
            logging.info("WebSocket disconnected")
            break
        except Exception as e:
            logging.error("WebSocket error: %s", e, exc_info=True)
            try:
                await websocket.send_json({"task": "error", "message": str(e)})
            except Exception:
                break