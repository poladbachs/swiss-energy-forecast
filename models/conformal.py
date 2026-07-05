"""
Split conformal prediction via MAPIE.

Quantile regression labels an interval "90%" without any guarantee that 90% of
observations actually land inside it. Split conformal calibration fixes that:
hold out a calibration set the model never trained on, take the (1-alpha)
quantile of its absolute residuals as the interval radius, and the resulting
intervals cover at least 90% of future observations as long as calibration and
future data are exchangeable.

MAPIE >=1.0 renamed MapieRegressor(cv="prefit") to SplitConformalRegressor(prefit=True).
See https://mapie.readthedocs.io/en/stable/theoretical_description_regression.html
"""
import numpy as np
import pandas as pd
from mapie.regression import SplitConformalRegressor
from lightgbm import LGBMRegressor
from features.engineer import build_training_frame, get_feature_cols

# Chronological fraction of training data used for MAPIE calibration (never seen by LightGBM)
CAL_FRACTION = 0.10
CONFIDENCE_LEVEL = 0.90


def calibrate(model: LGBMRegressor, df: pd.DataFrame, target: str) -> SplitConformalRegressor:
    """
    Wrap a fitted LightGBM in a split conformal regressor, calibrated on the
    chronologically last CAL_FRACTION of df. train.py only fits on the first
    80%, so these rows are unseen by the model.

    df:     raw energy_hourly rows (or a pre-built frame with a "label" column)
    target: one of "demand_mw", "solar_mw", "wind_mw"
    """
    if "label" not in df.columns:
        df = build_training_frame(df, target)
    df = df.sort_values("timestamp").reset_index(drop=True)
    cal = df.iloc[int(len(df) * (1 - CAL_FRACTION)):]

    feature_cols = get_feature_cols(target)
    X_cal = cal[feature_cols].dropna()
    y_cal = cal.loc[X_cal.index, "label"]

    scr = SplitConformalRegressor(estimator=model, confidence_level=CONFIDENCE_LEVEL, prefit=True)
    scr.conformalize(X_cal, y_cal)
    return scr


def predict_with_intervals(
    mapie: SplitConformalRegressor,
    X: pd.DataFrame,
    alpha: float = 0.10,  # kept for API compat; level is fixed at calibration time
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Run conformal prediction on feature matrix X.
    Returns (point, lower, upper) as 1-D numpy arrays, shape (n,).
    """
    point, intervals = mapie.predict_interval(X)
    lower = intervals[:, 0, 0]
    upper = intervals[:, 1, 0]
    return point, lower, upper
