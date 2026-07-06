"""Shared MLflow setup for local and DagsHub-backed tracking."""
import os

import mlflow


def configure_mlflow() -> None:
    """Initialize MLflow against local tracking or DagsHub with auth."""
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5001")
    if tracking_uri.startswith("https://dagshub.com/"):
        try:
            import dagshub
        except ImportError as exc:
            raise RuntimeError(
                "dagshub is required when MLFLOW_TRACKING_URI points to DagsHub. "
                "Install the dependency or switch MLFLOW_TRACKING_URI to a local MLflow server."
            ) from exc

        dagshub.init(
            repo_owner=os.environ.get("DAGSHUB_REPO_OWNER", "poladbachs"),
            repo_name=os.environ.get("DAGSHUB_REPO_NAME", "swiss-energy-forecast"),
            mlflow=True,
        )
        return

    mlflow.set_tracking_uri(tracking_uri)