"""
Promote the best MLflow run per target to Production in the Model Registry,
but only if it actually beats the currently deployed champion.

Expects each training run to:
  - Be tagged with  tags.target = "demand_mw" | "solar_mw" | "wind_mw"
  - Log metric      val_rmse
  - Log the MapieRegressor artifact at path "model"
    (i.e. mlflow.sklearn.log_model(mapie, "model") inside the training run)

Usage:
    python -m models.registry
"""
import os
import mlflow
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient
from dotenv import load_dotenv
load_dotenv()

EXPERIMENT = "swiss-energy-forecast"
TARGETS = ["demand_mw", "solar_mw", "wind_mw"]


def get_champion_val_rmse(client: MlflowClient, model_name: str) -> float | None:
    """Return the current @champion's logged val_rmse, or None if no champion exists yet."""
    try:
        mv = client.get_model_version_by_alias(model_name, "champion")
    except MlflowException:
        return None
    run = client.get_run(mv.run_id)
    return run.data.metrics.get("val_rmse")


def should_promote(candidate_rmse: float, champion_rmse: float | None) -> bool:
    """No champion yet -> always promote. Otherwise promote only on tie or improvement."""
    if champion_rmse is None:
        return True
    return candidate_rmse <= champion_rmse


def promote_best() -> list[str]:
    """Promote each target's best new run over its current champion. Returns promoted targets."""
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5001"))
    client = MlflowClient()

    exp = client.get_experiment_by_name(EXPERIMENT)
    if exp is None:
        raise ValueError(f"Experiment '{EXPERIMENT}' not found, run training first")

    promoted = []
    for target in TARGETS:
        model_name = target.replace("_mw", "") + "-lgbm"

        runs = client.search_runs(
            experiment_ids=[exp.experiment_id],
            filter_string=f"tags.target = '{target}' AND tags.model_logged = 'true'",
            order_by=["metrics.val_rmse ASC"],
            max_results=1,
        )
        if not runs:
            print(f"[registry] no runs for {target}, skipping")
            continue

        best = runs[0]
        candidate_rmse = best.data.metrics["val_rmse"]
        champion_rmse = get_champion_val_rmse(client, model_name)

        if not should_promote(candidate_rmse, champion_rmse):
            print(
                f"[registry] {model_name}: candidate val_rmse={candidate_rmse:.1f} "
                f"does not beat champion val_rmse={champion_rmse:.1f}, skipping"
            )
            continue

        model_uri = best.data.tags.get("model_uri", f"runs:/{best.info.run_id}/model")
        mv = mlflow.register_model(model_uri, model_name)
        client.set_registered_model_alias(model_name, "champion", mv.version)
        print(
            f"[registry] {model_name} v{mv.version} → @champion  "
            f"(run {best.info.run_id[:8]}, val_rmse={candidate_rmse:.1f}, "
            f"previous champion={champion_rmse})"
        )
        promoted.append(target)

    return promoted


if __name__ == "__main__":
    promote_best()
