import pandas as pd
import numpy as np
import pytest
from features.engineer import build_features, inference_features, get_feature_cols

_RNG = np.random.default_rng(42)

def _sample_df(n: int = 250) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame({
        "timestamp":       idx,
        "demand_mw":       _RNG.uniform(5000, 9000, n),
        "solar_mw":        _RNG.uniform(0, 2000, n),
        "wind_mw":         _RNG.uniform(0, 500, n),
        "temperature":     np.arange(n, dtype=float),  # monotone: row i has temp=i
        "solar_radiation": _RNG.uniform(0, 800, n),
        "wind_speed":      _RNG.uniform(0, 15, n),
        "cloud_cover":     _RNG.uniform(0, 100, n),
    })

_NOW = pd.Timestamp("2024-01-05", tz="UTC")  # row 96; 154 future rows available


# --- build_features: column presence ---

def test_lag_features_present():
    df = build_features(_sample_df(), "demand_mw", 1)
    for lag in [1, 24, 48, 168]:
        assert f"demand_mw_lag_{lag}h" in df.columns

def test_calendar_features_present():
    df = build_features(_sample_df(), "demand_mw", 1)
    for col in ["hour_of_day", "day_of_week", "month", "is_weekend", "is_swiss_holiday"]:
        assert col in df.columns

def test_hours_ahead_column():
    df = build_features(_sample_df(), "demand_mw", 12)
    assert (df["hours_ahead"] == 12).all()

def test_rolling_features_present():
    df = build_features(_sample_df(), "demand_mw", 1)
    assert "demand_mw_rolling_24h_mean" in df.columns
    assert "demand_mw_rolling_24h_std"  in df.columns

def test_no_nan_in_feature_cols():
    df = build_features(_sample_df(), "demand_mw", 1).dropna(subset=get_feature_cols("demand_mw"))
    assert len(df) > 0

def test_lag_features_nan_across_gap_not_wrong_value():
    """A missing hour must not silently shift lag values from the wrong hour."""
    df = _sample_df()
    df.loc[49, "demand_mw"] = -12345.0  # sentinel a buggy positional shift would leak
    gapped = df.drop(index=50).reset_index(drop=True)  # hour 50 missing entirely

    out = build_features(gapped, "demand_mw", hours_ahead=1)
    hour_51 = pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(hours=51)
    row = out[out["timestamp"] == hour_51]
    assert len(row) == 1
    assert pd.isna(row.iloc[0]["demand_mw_lag_1h"]), (
        "lag_1h at hour 51 must be NaN (hour 50 is missing), not hour 49's sentinel value"
    )


# --- build_features: target-time correctness ---

def test_calendar_at_target_time():
    """hour_of_day must reflect t+hours_ahead, not t."""
    df = _sample_df()
    # Row 0: 2024-01-01 00:00 UTC. With hours_ahead=6, target = 06:00 → hour=6.
    out = build_features(df, "demand_mw", hours_ahead=6)
    assert out.iloc[0]["hour_of_day"] == 6, (
        "hour_of_day should be 6 (target 06:00), not 0 (base 00:00)"
    )

def test_weather_at_target_time():
    """Weather features must reflect t+hours_ahead, not t."""
    df = _sample_df()
    # temperature[i] == i, so base row 0 has temp=0; target row 5 has temp=5.
    out = build_features(df, "demand_mw", hours_ahead=5)
    assert out.iloc[0]["temperature"] == pytest.approx(5.0), (
        "temperature should be 5.0 (from target row 5), not 0.0 (base row 0)"
    )

def test_calendar_varies_with_hours_ahead():
    """Different hours_ahead must produce different calendar features for the same base row."""
    df = _sample_df()
    out_1  = build_features(df, "demand_mw", hours_ahead=1)
    out_12 = build_features(df, "demand_mw", hours_ahead=12)
    # Row 0 base = 00:00; h=1 → 01:00; h=12 → 12:00
    assert out_1.iloc[0]["hour_of_day"]  == 1
    assert out_12.iloc[0]["hour_of_day"] == 12


# --- inference_features ---

def _inference_fixtures(horizon: int = 48):
    df = _sample_df()
    history = df[df["timestamp"] <= _NOW].copy()
    weather = (
        df[df["timestamp"] > _NOW]
        .head(horizon)[["timestamp", "temperature", "solar_radiation", "wind_speed", "cloud_cover"]]
        .copy()
    )
    return history, weather

def test_inference_features_columns():
    history, weather = _inference_fixtures()
    out = inference_features(history, "demand_mw", weather, _NOW, horizon=48)
    assert list(out.columns) == get_feature_cols("demand_mw")

def test_inference_features_shape():
    history, weather = _inference_fixtures()
    out = inference_features(history, "demand_mw", weather, _NOW, horizon=48)
    assert out.shape[0] == 48

def test_inference_hours_ahead_sequence():
    history, weather = _inference_fixtures(10)
    out = inference_features(history, "demand_mw", weather, _NOW, horizon=10)
    assert list(out["hours_ahead"]) == list(range(1, 11))

def test_inference_lag_constant_across_horizons():
    """Lag features must be identical for all horizons (all from base time 'now')."""
    df = _sample_df()
    # Pin demand to 9999 at exactly now-1h
    df.loc[df["timestamp"] == _NOW - pd.Timedelta(hours=1), "demand_mw"] = 9999.0
    history = df[df["timestamp"] <= _NOW].copy()
    weather = df[df["timestamp"] > _NOW].head(48)[
        ["timestamp", "temperature", "solar_radiation", "wind_speed", "cloud_cover"]
    ].copy()
    out = inference_features(history, "demand_mw", weather, _NOW, horizon=48)
    # lag_1h = demand at now-1h = 9999 for every forecast row
    assert (out["demand_mw_lag_1h"] == 9999.0).all(), (
        "lag_1h should be constant (base time now-1h) across all forecast horizons"
    )
