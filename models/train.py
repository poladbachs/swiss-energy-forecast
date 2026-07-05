"""
Train one LightGBM model per target (demand, solar, wind) with MLflow tracking.

Run:
    python -m models.train
"""
import os
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error

from dotenv import load_dotenv
load_dotenv()

from features.engineer import build_training_frame, get_feature_cols
from models.conformal import calibrate
from storage.db import query as db_query

EXPERIMENT = "swiss-energy-forecast"
TARGETS = ["demand_mw", "solar_mw", "wind_mw"]
HORIZONS = list(range(1, 49))

DEFAULT_PARAMS = {
    "n_estimators":  500,
    "learning_rate": 0.05,
    "max_depth":     -1,
    "num_leaves":    63,
    "random_state":  42,
    "n_jobs":        -1,
}


def train(df: pd.DataFrame, target: str, params: dict | None = None) -> tuple[LGBMRegressor, float]:
    """
    Fit LightGBM on df for the given target across all 48 horizons.
    Chronological 80/20 split, no shuffle. Pure function, no MLflow side effects.
    Returns (fitted_lgbm, val_rmse).
    """
    frame = build_training_frame(df, target, HORIZONS)
    frame = frame.sort_values("timestamp").reset_index(drop=True)

    feature_cols = get_feature_cols(target)
    split = int(len(frame) * 0.8)
    train_df, val_df = frame.iloc[:split], frame.iloc[split:]

    X_train, y_train = train_df[feature_cols], train_df["label"]
    X_val, y_val = val_df[feature_cols], val_df["label"]

    model = LGBMRegressor(**(params or DEFAULT_PARAMS), verbose=-1)
    model.fit(X_train, y_train)

    pred = model.predict(X_val)
    val_rmse = float(np.sqrt(mean_squared_error(y_val, pred)))
    return model, val_rmse


def run_pipeline() -> None:
    """Load data, train all targets, calibrate MAPIE, log one MLflow run per target."""
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5001"))
    mlflow.set_experiment(EXPERIMENT)

    df = db_query()
    print(f"[train] loaded {len(df)} rows from DB")

    for target in TARGETS:
        run_target(df, target, DEFAULT_PARAMS)


def run_target(df: pd.DataFrame, target: str, params: dict) -> float:
    """Train + calibrate one target in a promotable MLflow run. Returns val_rmse."""
    model_name = target.replace("_mw", "") + "-lgbm"
    print(f"[train] training {target}...")

    with mlflow.start_run(run_name=model_name):
        mlflow.set_tag("target", target)
        mlflow.set_tag("model_logged", "true")
        mlflow.log_params(params)

        lgbm, val_rmse = train(df, target, params)
        mlflow.log_metric("val_rmse", val_rmse)
        print(f"[train] {target} val_rmse={val_rmse:.1f}")

        mapie = calibrate(lgbm, df, target)
        # skops (mlflow.sklearn's serializer) audits pickled types by default;
        # trust our own training output rather than arbitrary untrusted files.
        info = mlflow.sklearn.log_model(
            mapie,
            name="model",
            skops_trusted_types=[
                "collections.OrderedDict",
                "lightgbm.basic.Booster",
                "lightgbm.sklearn.LGBMRegressor",
                "mapie.conformity_scores.bounds.absolute.AbsoluteConformityScore",
                "mapie.estimator.regressor.EnsembleRegressor",
                "mapie.regression.regression.SplitConformalRegressor",
                "mapie.regression.regression._MapieRegressor",
            ],
        )
        # DagsHub's MLflow proxy doesn't resolve runs:/<id>/model to the
        # underlying logged model, so registry.py registers via this URI
        # instead of reconstructing one from the run id.
        mlflow.set_tag("model_uri", info.model_uri)
        print(f"[train] logged MapieRegressor for {target}")
    return val_rmse


if __name__ == "__main__":
    run_pipeline()
