"""
Walk-forward evaluation of the Swiss day-ahead price model.

This is the evaluation style a trading desk actually trusts: no single
lucky train/test split. The last N months are replayed one month at a time;
for each fold the model is trained ONLY on data strictly before that month,
then predicts the whole month out-of-sample. 2021-2022 (the European
gas-crisis regime) stays in the training data on purpose: the model has to
learn through the regime break, not have it curated away.

Baselines are the honest ones for this market:
  - naive24:  yesterday's price, same delivery hour (the strongest simple
              baseline for day-ahead prices)
  - naive168: last week's price, same hour

Writes models/artifacts/price_walkforward.json (aggregate + per-fold) and
frontend/public/price_walkforward.json for the dashboard.

Run:
    python -m scripts.walkforward_price
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from dotenv import load_dotenv
load_dotenv()

from models.price_forecast import build_price_frame, evaluate_fold
from storage.db import query_market, query_reservoir

N_FOLD_MONTHS = 24
ART = Path(__file__).resolve().parent.parent / "models" / "artifacts" / "price_walkforward.json"
PUB = Path(__file__).resolve().parent.parent / "frontend" / "public" / "price_walkforward.json"


def main() -> None:
    market = query_market()
    reservoir = query_reservoir()
    if market.empty:
        raise ValueError("market_hourly is empty; run scripts.backfill_market first")

    frame = build_price_frame(market, reservoir)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)

    last = frame.dropna(subset=["label"])["timestamp"].max()
    # Only whole months: the current partial month is excluded.
    fold_starts = pd.date_range(
        end=last.floor("d").replace(day=1), periods=N_FOLD_MONTHS + 1, freq="MS", tz="UTC"
    )[:-1]

    folds, all_residuals = [], []
    for fold_start in fold_starts:
        fold_end = fold_start + pd.offsets.MonthBegin(1)
        train_frame = frame[frame["timestamp"] < fold_start]
        test_frame = frame[(frame["timestamp"] >= fold_start) & (frame["timestamp"] < fold_end)]
        metrics, residuals = evaluate_fold(train_frame, test_frame)
        if metrics is None:
            print(f"[walkforward] {fold_start:%Y-%m}: no usable rows, skipped")
            continue
        metrics["month"] = f"{fold_start:%Y-%m}"
        folds.append(metrics)
        all_residuals.append(residuals)
        print(f"[walkforward] {metrics['month']}: model {metrics['model_mae']:.2f} "
              f"vs naive24 {metrics['naive24_mae']:.2f} EUR/MWh MAE "
              f"({100 * (1 - metrics['model_mae'] / metrics['naive24_mae']):+.1f}%), "
              f"direction hit {100 * metrics['direction_hit_rate']:.1f}%")

    if not folds:
        raise ValueError("No folds produced any metrics")

    residuals = np.concatenate(all_residuals)  # residual = actual - predicted

    total_hours = sum(f["n_hours"] for f in folds)
    weighted = lambda k: float(sum(f[k] * f["n_hours"] for f in folds) / total_hours)
    model_mae = weighted("model_mae")
    naive24_mae = weighted("naive24_mae")
    months_beating = sum(1 for f in folds if f["model_mae"] < f["naive24_mae"])

    out = {
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "n_fold_months": len(folds),
        "total_hours": total_hours,
        "model_mae": round(model_mae, 2),
        "model_rmse": round(weighted("model_rmse"), 2),
        "naive24_mae": round(naive24_mae, 2),
        "naive168_mae": round(weighted("naive168_mae"), 2),
        "mae_improvement_pct": round(100 * (1 - model_mae / naive24_mae), 1),
        "direction_hit_rate_pct": round(100 * weighted("direction_hit_rate"), 1),
        "months_beating_naive24": months_beating,
        # Empirical 80% band from real out-of-sample errors (residual = actual - predicted)
        "residual_p10": round(float(np.quantile(residuals, 0.10)), 2),
        "residual_p90": round(float(np.quantile(residuals, 0.90)), 2),
        "folds": folds,
    }

    payload = json.dumps(out, indent=1) + "\n"
    ART.parent.mkdir(parents=True, exist_ok=True)
    ART.write_text(payload)
    PUB.parent.mkdir(parents=True, exist_ok=True)
    PUB.write_text(payload)
    print(f"\n[walkforward] {len(folds)} months, {total_hours} hours: "
          f"model {model_mae:.2f} vs naive24 {naive24_mae:.2f} EUR/MWh MAE "
          f"({out['mae_improvement_pct']:+.1f}%), beats naive in "
          f"{months_beating}/{len(folds)} months, direction hit {out['direction_hit_rate_pct']}%")


if __name__ == "__main__":
    main()
