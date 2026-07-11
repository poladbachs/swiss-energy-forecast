"""
Day-ahead price forecast for the Swiss bidding zone.

The information-set discipline is the whole point of this module. All
European day-ahead auctions clear SIMULTANEOUSLY in the coupled market
(~12:45 CET on day D for delivery day D+1), so when forecasting Swiss prices
for D+1, neighboring zones' D+1 prices do not exist yet. A model fed
same-hour neighbor prices scores spectacularly and is completely fake.

What is genuinely known before the auction, and therefore allowed here:
  - every zone's prices for delivery day D and earlier (cleared >= 1 day ago)
    -> price features enter ONLY with a lag of >= 24 hours
  - the TSOs' day-ahead LOAD FORECASTS for D+1 (published ~10:00, before
    the auction) -> usable at the target hour itself, no lag
  - the day-ahead wind+solar generation forecast for DE-LU (published before
    the auction; the dominant fundamental in the region) -> usable at t
  - weekly Swiss reservoir levels, published with a delay -> lagged 7 days
  - the calendar

Model: one LightGBM over all 24 delivery hours, hour-of-day as a feature,
mirroring how the demand model in this repo works.
"""
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from features.engineer import CH_HOLIDAYS

NEIGHBOR_ZONES = ["DE_LU", "FR", "IT_NORD"]

PARAMS = {
    "n_estimators": 500,
    "learning_rate": 0.05,
    "max_depth": -1,
    "num_leaves": 63,
    "random_state": 42,
    "n_jobs": -1,
    "verbose": -1,
}

FEATURE_COLS = (
    ["price_CH_lag24", "price_CH_lag48", "price_CH_lag168",
     "price_CH_roll168_mean", "price_CH_roll168_std"]
    + [f"price_{z}_lag24" for z in NEIGHBOR_ZONES]
    + [f"load_forecast_{z}" for z in ["CH"] + NEIGHBOR_ZONES]
    + ["wind_solar_forecast_DE_LU", "reservoir_lag7d",
       "hour_of_day", "day_of_week", "month", "is_ch_holiday"]
)


def build_price_frame(market: pd.DataFrame, reservoir: pd.DataFrame) -> pd.DataFrame:
    """market: long df (timestamp, zone, price_eur_mwh, load_forecast_mw,
    wind_solar_forecast_mw). reservoir: (week_start, filling_mwh).
    Returns one row per hour with FEATURE_COLS + label (realized CH price).
    Rows are NOT dropna'd here; the caller decides."""
    wide = market.pivot(index="timestamp", columns="zone")
    wide.columns = [f"{val}_{zone}" for val, zone in wide.columns]

    # One row per hour so .shift(24) is exactly one delivery day even across gaps.
    idx = pd.date_range(wide.index.min(), wide.index.max(), freq="h", tz="UTC")
    wide = wide.reindex(idx)

    out = pd.DataFrame(index=idx)

    # --- prices: lagged >= 24h only (see module docstring) ---
    ch = wide["price_eur_mwh_CH"]
    out["price_CH_lag24"] = ch.shift(24)
    out["price_CH_lag48"] = ch.shift(48)
    out["price_CH_lag168"] = ch.shift(168)
    # min_periods: a handful of missing price hours must not poison a whole
    # week of rolling features downstream; >=120 of 168 hours is still a
    # perfectly good weekly anchor.
    out["price_CH_roll168_mean"] = ch.shift(24).rolling(168, min_periods=120).mean()
    out["price_CH_roll168_std"] = ch.shift(24).rolling(168, min_periods=120).std()
    for z in NEIGHBOR_ZONES:
        out[f"price_{z}_lag24"] = wide[f"price_eur_mwh_{z}"].shift(24)

    # --- day-ahead forecasts: published pre-auction, usable at t ---
    for z in ["CH"] + NEIGHBOR_ZONES:
        out[f"load_forecast_{z}"] = wide[f"load_forecast_mw_{z}"]
    out["wind_solar_forecast_DE_LU"] = wide.get("wind_solar_forecast_mw_DE_LU")

    # --- reservoir: weekly, forward-filled, then lagged a full week to cover
    #     the publication delay conservatively ---
    res = reservoir.set_index("week_start")["filling_mwh"].reindex(idx, method="ffill")
    out["reservoir_lag7d"] = res.shift(168)

    # --- calendar ---
    out["hour_of_day"] = idx.hour
    out["day_of_week"] = idx.dayofweek
    out["month"] = idx.month
    out["is_ch_holiday"] = [int(d in CH_HOLIDAYS) for d in idx.date]

    out["label"] = ch
    return out.rename_axis("timestamp").reset_index()


# Rows need a label to train on and the baseline lags to be scored against;
# every OTHER feature may be NaN, which LightGBM handles natively (missing
# values get their own branch direction). Dropping rows for any NaN feature
# would silently discard most hours around data gaps.
_REQUIRED = ["label", "price_CH_lag24", "price_CH_lag168"]


def train_price_model(frame: pd.DataFrame) -> LGBMRegressor:
    d = frame.dropna(subset=["label"])
    model = LGBMRegressor(**PARAMS)
    model.fit(d[FEATURE_COLS], d["label"])
    return model


def evaluate_fold(train_frame: pd.DataFrame, test_frame: pd.DataFrame):
    """Train on everything before the fold, predict the fold. Returns
    (metrics dict, signed out-of-sample residuals) so the caller can build an
    empirical uncertainty band from real errors, or (None, None) if the fold
    has no usable rows."""
    model = train_price_model(train_frame)
    test = test_frame.dropna(subset=_REQUIRED)
    if test.empty:
        return None, None

    pred = model.predict(test[FEATURE_COLS])
    y = test["label"].values
    naive24 = test["price_CH_lag24"].values
    naive168 = test["price_CH_lag168"].values

    move = y - naive24
    pred_move = pred - naive24
    nonzero = move != 0

    metrics = {
        "n_hours": int(len(test)),
        "model_mae": float(np.abs(y - pred).mean()),
        "model_rmse": float(np.sqrt(((y - pred) ** 2).mean())),
        "naive24_mae": float(np.abs(y - naive24).mean()),
        "naive168_mae": float(np.abs(y - naive168).mean()),
        "direction_hit_rate": float((np.sign(pred_move[nonzero]) == np.sign(move[nonzero])).mean()),
    }
    return metrics, (y - pred)
