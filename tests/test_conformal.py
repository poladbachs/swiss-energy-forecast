"""Tests for conformal prediction (models/conformal.py)."""
import numpy as np
import pandas as pd
import pytest

from features.engineer import build_training_frame, get_feature_cols
from models.conformal import calibrate, predict_with_intervals
from models.train import train


def _small_df(n=600):
    rng = np.random.default_rng(0)
    idx = pd.date_range("2023-01-01", periods=n, freq="h", tz="UTC")
    hour = idx.hour.values
    return pd.DataFrame({
        "timestamp": idx,
        # daily cycle + noise, so the model has real signal to learn
        "demand_mw": 7000 + 1500 * np.sin(hour / 24 * 2 * np.pi) + rng.normal(0, 200, n),
        "solar_mw":  np.clip(1000 * np.sin(hour / 24 * 2 * np.pi), 0, None) + rng.uniform(0, 100, n),
        "wind_mw":   rng.uniform(0, 500, n),
        "temperature": rng.uniform(0, 25, n),
        "solar_radiation": rng.uniform(0, 800, n),
        "wind_speed": rng.uniform(0, 15, n),
        "cloud_cover": rng.uniform(0, 100, n),
    })


@pytest.fixture(scope="module")
def fitted():
    df = _small_df()
    target = "demand_mw"
    params = {"n_estimators": 50, "num_leaves": 31, "random_state": 42, "n_jobs": -1}
    model, _ = train(df, target, params)
    mapie = calibrate(model, df, target)
    # held-out slice: rows between the 80% train cut and the 90% calibration cut
    frame = build_training_frame(df, target).sort_values("timestamp").reset_index(drop=True)
    holdout = frame.iloc[int(len(frame) * 0.8):int(len(frame) * 0.9)]
    return mapie, holdout, target


def test_intervals_shape(fitted):
    mapie, holdout, target = fitted
    X = holdout[get_feature_cols(target)].head(50)
    point, lower, upper = predict_with_intervals(mapie, X)
    assert point.shape == lower.shape == upper.shape == (50,)


def test_lower_leq_point_leq_upper(fitted):
    mapie, holdout, target = fitted
    X = holdout[get_feature_cols(target)]
    point, lower, upper = predict_with_intervals(mapie, X)
    assert (lower <= point + 1e-9).all()
    assert (point <= upper + 1e-9).all()


def test_empirical_coverage(fitted):
    mapie, holdout, target = fitted
    X = holdout[get_feature_cols(target)]
    y = holdout["label"].values
    _, lower, upper = predict_with_intervals(mapie, X)
    coverage = ((y >= lower) & (y <= upper)).mean()
    assert coverage >= 0.85, f"coverage {coverage:.2f} below 0.85"
