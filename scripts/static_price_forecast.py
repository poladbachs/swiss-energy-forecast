"""
Generate the deployable day-ahead price artifact for the dashboard.

Two parts, so the page is honest AND never empty:

1. latest_auction: the most recent delivery day with cleared prices, replayed
   out-of-sample. The model is trained ONLY on rows before that delivery day
   (everything it would have known before the auction), then predicts the
   day's 24 hours; the realized clearing prices sit next to the predictions.
   This refreshes daily and is a genuine forecast-vs-outcome comparison, not
   an in-sample fit.

2. next_auction: hours after the last cleared price whose pre-auction inputs
   (day-ahead load forecast, yesterday's price) already exist. Populated
   during the real daily window between the TSO load-forecast publication
   (~10:00 CET) and the auction clearing (~12:45 CET); empty the rest of the
   day, exactly like a real desk's forecast queue.

The uncertainty band is empirical: p10/p90 of signed out-of-sample errors
from the 24-month walk-forward (scripts/walkforward_price.py).

Run (after backfill_market and walkforward_price):
    python -m scripts.static_price_forecast
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from dotenv import load_dotenv
load_dotenv()

from models.price_forecast import FEATURE_COLS, build_price_frame, train_price_model
from storage.db import query_market, query_reservoir

WALKFORWARD = Path(__file__).resolve().parent.parent / "models" / "artifacts" / "price_walkforward.json"
OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "price_forecast_da.json"


def _hours_payload(timestamps, preds, band_lo, band_hi, actuals=None, naive=None):
    rows = []
    for i, (ts, p) in enumerate(zip(timestamps, preds)):
        row = {
            "timestamp": ts.isoformat(),
            "forecast": round(float(p), 2),
            "band_low": round(float(p + band_lo), 2),
            "band_high": round(float(p + band_hi), 2),
        }
        if actuals is not None:
            a = actuals[i]
            row["actual"] = round(float(a), 2) if not np.isnan(a) else None
        if naive is not None:
            n = naive[i]
            row["naive24"] = round(float(n), 2) if not np.isnan(n) else None
        rows.append(row)
    return rows


def main() -> None:
    market = query_market()
    reservoir = query_reservoir()
    frame = build_price_frame(market, reservoir)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)

    wf = json.loads(WALKFORWARD.read_text()) if WALKFORWARD.exists() else None
    band_lo = wf["residual_p10"] if wf else 0.0
    band_hi = wf["residual_p90"] if wf else 0.0

    last_priced = frame.dropna(subset=["label"])["timestamp"].max()
    latest_day = last_priced.floor("d")

    # --- 1. latest cleared auction, replayed out-of-sample ---
    train_frame = frame[frame["timestamp"] < latest_day]
    day_frame = frame[(frame["timestamp"] >= latest_day) & (frame["timestamp"] <= last_priced)]
    model_replay = train_price_model(train_frame)
    replay_pred = model_replay.predict(day_frame[FEATURE_COLS])
    replay = {
        "delivery_day": f"{latest_day:%Y-%m-%d}",
        "mae": round(float(np.abs(day_frame["label"].values - replay_pred).mean()), 2),
        "naive24_mae": round(float(np.abs(day_frame["label"].values - day_frame["price_CH_lag24"].values).mean()), 2),
        "hours": _hours_payload(
            day_frame["timestamp"], replay_pred, band_lo, band_hi,
            actuals=day_frame["label"].values, naive=day_frame["price_CH_lag24"].values,
        ),
    }

    # --- 2. next auction, when the pre-auction window is open ---
    model_full = train_price_model(frame)
    future = frame[frame["timestamp"] > last_priced].dropna(subset=["load_forecast_CH", "price_CH_lag24"])
    next_auction = None
    if not future.empty:
        preds = model_full.predict(future[FEATURE_COLS])
        next_auction = {
            "delivery_day": f"{future['timestamp'].min().floor('d'):%Y-%m-%d}",
            "hours": _hours_payload(future["timestamp"], preds, band_lo, band_hi),
        }

    out = {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "walkforward": {k: wf[k] for k in (
            "model_mae", "naive24_mae", "naive168_mae", "mae_improvement_pct",
            "direction_hit_rate_pct", "n_fold_months", "months_beating_naive24", "total_hours",
        )} if wf else None,
        "latest_auction": replay,
        "next_auction": next_auction,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    status = f"next auction {next_auction['delivery_day']} ({len(next_auction['hours'])}h)" if next_auction else "pre-auction window closed"
    print(f"wrote {OUT}: replay {replay['delivery_day']} "
          f"(model {replay['mae']} vs naive {replay['naive24_mae']} EUR/MWh), {status}")


if __name__ == "__main__":
    main()
