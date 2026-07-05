"""
LightGBM hyperparameter search with Optuna. Each trial trains a full model
and logs its own MLflow run; the best params get a final promotable run.

Run:
    python -m models.tune --target demand_mw --trials 50
"""
import os
import argparse
import optuna
import mlflow
import pandas as pd

from dotenv import load_dotenv
load_dotenv()

from models.train import train, run_target, EXPERIMENT
from storage.db import query as db_query


def tune(df: pd.DataFrame, target: str, n_trials: int = 50) -> dict:
    """Minimise val_rmse over n_trials. Returns the best params dict."""
    mlflow.set_experiment(EXPERIMENT)
    mlflow.lightgbm.autolog(log_models=False)

    def objective(trial: optuna.Trial) -> float:
        params = {
            "n_estimators":  trial.suggest_int("n_estimators", 100, 1000, step=50),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "num_leaves":    trial.suggest_int("num_leaves", 16, 256),
            "max_depth":     trial.suggest_int("max_depth", 3, 12),
            "random_state":  42,
            "n_jobs":        -1,
        }
        with mlflow.start_run(run_name=f"tune-{target}", nested=False):
            mlflow.set_tag("target", target)
            mlflow.log_params(params)
            _, val_rmse = train(df, target, params)
            mlflow.log_metric("val_rmse", val_rmse)
        return val_rmse

    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
    print(f"[tune] best val_rmse={study.best_value:.1f}  params={study.best_params}")
    return study.best_params


def main() -> None:
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5001"))
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["demand_mw", "solar_mw", "wind_mw"], required=True)
    parser.add_argument("--trials", type=int, default=50)
    args = parser.parse_args()

    print(f"[tune] loading data...")
    df = db_query()
    best = tune(df, args.target, args.trials)
    print(f"[tune] best params for {args.target}:", best)
    # final promotable run: retrain + calibrate with the best params (tune trials log no model)
    run_target(df, args.target, {**best, "random_state": 42, "n_jobs": -1})


if __name__ == "__main__":
    main()
