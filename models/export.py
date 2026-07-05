"""
Export the current @champion model per target to the static serving format.

Bridges the MLflow model registry (models/registry.py) to the plain-file
format models/artifacts/{target}.txt + radii.json that scripts/static_forecast.py
and scripts/static_backtest.py load directly (no sklearn/mapie needed at serving
time). Only called for targets that were actually promoted this run.

Run:
    python -m models.export
"""
import json
import os
from pathlib import Path

import mlflow
import mlflow.sklearn
import pandas as pd
from dotenv import load_dotenv
load_dotenv()

from features.engineer import build_training_frame, get_feature_cols
from models.conformal import predict_with_intervals
from storage.db import query as db_query

ART = Path(__file__).resolve().parent / "artifacts"
RADII_PATH = ART / "radii.json"


def export_target(target: str, df: pd.DataFrame) -> None:
    """Load @champion for target, write its booster + update its radius in radii.json."""
    model_name = target.replace("_mw", "") + "-lgbm"
    mapie = mlflow.sklearn.load_model(f"models:/{model_name}@champion")

    # SplitConformalRegressor stores the fitted base estimator as `_estimator`
    # (mapie.regression.regression.SplitConformalRegressor.__init__). If a future
    # mapie upgrade renames this, test_export.py's booster assertion catches it.
    booster = mapie._estimator.booster_
    ART.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(ART / f"{target}.txt"))

    frame = build_training_frame(df, target).dropna(subset=get_feature_cols(target)).tail(1)
    _, lower, upper = predict_with_intervals(mapie, frame[get_feature_cols(target)])
    radius = float(upper[0] - lower[0]) / 2

    radii = json.loads(RADII_PATH.read_text()) if RADII_PATH.exists() else {}
    radii[target] = radius
    RADII_PATH.write_text(json.dumps(radii, indent=1))
    print(f"[export] {target}: wrote {target}.txt, radius={radius:.1f}")


def export_promoted(promoted_targets: list[str]) -> None:
    """Export only the targets that were actually promoted this run."""
    if not promoted_targets:
        print("[export] nothing promoted this run, skipping")
        return
    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5001"))
    df = db_query()
    for target in promoted_targets:
        export_target(target, df)


if __name__ == "__main__":
    import sys
    export_promoted(sys.argv[1:])
