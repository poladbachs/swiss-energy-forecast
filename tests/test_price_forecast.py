"""Tests for models/price_forecast.py, above all the leakage discipline:
day-ahead auctions clear simultaneously across Europe, so no price may enter
the feature set with a lag under 24 hours. If a refactor ever breaks that,
the model's backtest becomes fiction; these tests are the tripwire."""
import numpy as np
import pandas as pd
import pytest

from models.price_forecast import FEATURE_COLS, NEIGHBOR_ZONES, build_price_frame


def _synthetic_market(n_hours=24 * 30):
    idx = pd.date_range("2024-01-01", periods=n_hours, freq="h", tz="UTC")
    rng = np.random.default_rng(7)
    rows = []
    for zone in ["CH"] + NEIGHBOR_ZONES:
        rows.append(pd.DataFrame({
            "timestamp": idx,
            "zone": zone,
            "price_eur_mwh": rng.uniform(20, 200, n_hours),
            "load_forecast_mw": rng.uniform(4000, 9000, n_hours),
            "wind_solar_forecast_mw": rng.uniform(0, 30000, n_hours) if zone == "DE_LU" else np.nan,
        }))
    return pd.concat(rows, ignore_index=True)


def _synthetic_reservoir():
    weeks = pd.date_range("2023-12-01", periods=10, freq="7D", tz="UTC")
    return pd.DataFrame({"week_start": weeks, "filling_mwh": np.linspace(5e6, 6e6, 10)})


def test_frame_has_all_feature_cols_and_label():
    frame = build_price_frame(_synthetic_market(), _synthetic_reservoir())
    for col in FEATURE_COLS + ["label"]:
        assert col in frame.columns


def test_no_price_leakage_same_hour():
    """Plant a sentinel CH price at one hour; no feature row at that hour may
    see it, and it must surface exactly 24h later in price_CH_lag24."""
    market = _synthetic_market()
    t = pd.Timestamp("2024-01-15 12:00", tz="UTC")
    market.loc[(market["zone"] == "CH") & (market["timestamp"] == t), "price_eur_mwh"] = 99999.0

    frame = build_price_frame(market, _synthetic_reservoir()).set_index("timestamp")

    row_t = frame.loc[t]
    assert row_t["label"] == 99999.0
    assert not any(row_t[c] == 99999.0 for c in FEATURE_COLS), (
        "the realized price at hour t leaked into hour t's own features"
    )
    assert frame.loc[t + pd.Timedelta(hours=24), "price_CH_lag24"] == 99999.0


def test_no_neighbor_price_leakage_same_hour():
    """Same tripwire for a neighbor zone: DE-LU's price for the delivery hour
    clears at the same instant as CH's, so it must never appear unlagged."""
    market = _synthetic_market()
    t = pd.Timestamp("2024-01-15 12:00", tz="UTC")
    market.loc[(market["zone"] == "DE_LU") & (market["timestamp"] == t), "price_eur_mwh"] = 88888.0

    frame = build_price_frame(market, _synthetic_reservoir()).set_index("timestamp")

    assert not any(frame.loc[t, c] == 88888.0 for c in FEATURE_COLS)
    assert frame.loc[t + pd.Timedelta(hours=24), "price_DE_LU_lag24"] == 88888.0


def test_load_forecast_is_used_at_target_hour():
    """The day-ahead load forecast is published before the auction, so unlike
    prices it is legitimately available for the target hour itself."""
    market = _synthetic_market()
    t = pd.Timestamp("2024-01-15 12:00", tz="UTC")
    market.loc[(market["zone"] == "CH") & (market["timestamp"] == t), "load_forecast_mw"] = 77777.0

    frame = build_price_frame(market, _synthetic_reservoir()).set_index("timestamp")
    assert frame.loc[t, "load_forecast_CH"] == 77777.0


def test_reservoir_lagged_a_full_week():
    """Weekly reservoir data publishes with a delay; the feature must only
    expose values at least 168 hours old."""
    market = _synthetic_market()
    weeks = pd.date_range("2023-12-01", periods=10, freq="7D", tz="UTC")
    reservoir = pd.DataFrame({"week_start": weeks, "filling_mwh": np.arange(10, dtype=float)})

    frame = build_price_frame(market, reservoir).set_index("timestamp")
    # At any hour t, the exposed value must equal the ffilled series at t-168h.
    t = pd.Timestamp("2024-01-20 00:00", tz="UTC")
    ffilled_at_lag = reservoir.set_index("week_start")["filling_mwh"].reindex(
        [t - pd.Timedelta(hours=168)], method="ffill"
    ).iloc[0]
    assert frame.loc[t, "reservoir_lag7d"] == ffilled_at_lag
