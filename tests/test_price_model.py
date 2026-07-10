"""Tests for models/price_model.py — the linear price-sensitivity fit."""
import numpy as np
import pandas as pd
import pytest

from models.price_model import fit, predict


def _synthetic_df(n=500, slope=0.5, noise=1.0, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    import_gap = rng.normal(1000, 300, n)
    hour = idx.hour.values
    is_weekend = pd.Series(idx.dayofweek).isin([5, 6]).astype(int).values
    price = (
        50
        + slope * import_gap
        - 10 * np.sin(2 * np.pi * hour / 24)
        - 15 * is_weekend
        + rng.normal(0, noise, n)
    )
    return pd.DataFrame({"timestamp": idx, "import_gap": import_gap, "price_eur_mwh": price})


def test_fit_recovers_known_slope_sign_and_magnitude():
    df = _synthetic_df(slope=0.5, noise=1.0)
    coeffs = fit(df)
    assert coeffs["coef_import_gap"] == pytest.approx(0.5, abs=0.05)
    assert coeffs["r2"] > 0.9
    assert coeffs["n_obs"] == len(df)


def test_predict_matches_fit_on_training_data():
    df = _synthetic_df(slope=0.3, noise=0.5)
    coeffs = fit(df)
    preds = predict(coeffs, df["import_gap"].values, pd.DatetimeIndex(df["timestamp"]))
    assert preds.shape == (len(df),)
    mae = float(np.mean(np.abs(preds - df["price_eur_mwh"].values)))
    assert mae < 5.0
