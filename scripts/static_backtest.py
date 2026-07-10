"""
Generate a static backtest JSON: replay the model's 24h-ahead predictions
against what actually happened, for the last BACKTEST_DAYS days.

Same "no sklearn/mapie" serving path as static_forecast.py: exported LightGBM
boosters plus the fixed conformal radius. Historical actuals (energy + weather)
are pulled straight from the database so this can run in the same CI job as the
forecast refresh.

Run:
    python -m scripts.static_backtest
"""
import json
from datetime import date, timedelta
from pathlib import Path

import lightgbm as lgb
import pandas as pd

from dotenv import load_dotenv
load_dotenv()

from features.engineer import build_training_frame, get_feature_cols
from storage.db import query as db_query

TARGETS = ["demand_mw", "solar_mw", "wind_mw"]
HORIZON_H = 24        # fixed lead time being backtested
BACKTEST_DAYS = 14     # how many days of replay to serve
LOOKBACK_DAYS = 9      # buffer for the 168h lag + 24h rolling features
ART = Path(__file__).resolve().parent.parent / "models" / "artifacts"
OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "backtest.json"


def classify(gap_pt: float, gap_hi: float) -> str:
    if gap_hi < 0:
        return "confirmed_surplus"
    if gap_pt < 0:
        return "possible_surplus"
    return "deficit"


def iso_utc(ts) -> str:
    ts = pd.Timestamp(ts)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return ts.isoformat()


def main() -> None:
    history = db_query(start=pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=180))
    if history.empty:
        raise ValueError("No history rows available for backtest generation")

    now = history["timestamp"].max().floor("h")
    window_start = now - pd.Timedelta(days=BACKTEST_DAYS)
    fetch_start = now - pd.Timedelta(days=BACKTEST_DAYS + LOOKBACK_DAYS)

    history = history[(history["timestamp"] >= fetch_start) & (history["timestamp"] <= now)]
    if history.empty:
        raise ValueError("No history rows available for backtest generation")

    radii = json.loads((ART / "radii.json").read_text())
    series = {}
    for target in TARGETS:
        booster = lgb.Booster(model_file=str(ART / f"{target}.txt"))
        frame = build_training_frame(history, target, horizons=[HORIZON_H])
        target_ts = frame["timestamp"] + pd.Timedelta(hours=HORIZON_H)
        mask = (target_ts >= window_start) & (target_ts <= now)
        frame, target_ts = frame.loc[mask], target_ts.loc[mask]

        point = booster.predict(frame[get_feature_cols(target)])
        r = radii[target]
        lower, upper = point - r, point + r
        if target in ("solar_mw", "wind_mw"):
            point, lower = point.clip(min=0), lower.clip(min=0)

        series[target] = pd.DataFrame({
            "timestamp": target_ts.reset_index(drop=True),
            "point": point, "lower": lower, "upper": upper,
            "actual": frame["label"].values,
        }).set_index("timestamp")

    merged = series["demand_mw"].join(
        series["solar_mw"], lsuffix="_demand", rsuffix="_solar"
    ).join(series["wind_mw"].add_suffix("_wind"), how="inner").dropna()

    points, covered = [], 0
    demand_covered, demand_abs_errors = 0, []
    for ts, r in merged.iterrows():
        d = dict(point=r.point_demand, lower=r.lower_demand, upper=r.upper_demand, actual=r.actual_demand)
        s = dict(point=r.point_solar, lower=r.lower_solar, upper=r.upper_solar, actual=r.actual_solar)
        w = dict(point=r.point_wind, lower=r.lower_wind, upper=r.upper_wind, actual=r.actual_wind)
        gap = dict(
            point=d["point"] - (s["point"] + w["point"]),
            lower=d["lower"] - (s["upper"] + w["upper"]),
            upper=d["upper"] - (s["lower"] + w["lower"]),
            actual=d["actual"] - (s["actual"] + w["actual"]),
        )
        is_covered = bool(gap["lower"] <= gap["actual"] <= gap["upper"])
        demand_is_covered = bool(d["lower"] <= d["actual"] <= d["upper"])
        covered += int(is_covered)
        demand_covered += int(demand_is_covered)
        demand_abs_errors.append(abs(d["actual"] - d["point"]))
        points.append({
            "timestamp": iso_utc(ts),
            "demand": {k: float(v) for k, v in d.items()},
            "solar": {k: float(v) for k, v in s.items()},
            "wind": {k: float(v) for k, v in w.items()},
            "supply_gap": {k: float(v) for k, v in gap.items()},
            "coverage_status": classify(gap["point"], gap["upper"]),
            "covered": is_covered,
            "demand_covered": demand_is_covered,
        })

    out = {
        "horizon_h": HORIZON_H,
        "generated_at": iso_utc(now),
        "points": points,
        "summary": {
            "hours": len(points),
            "covered_hours": covered,
            "coverage_pct": round(100 * covered / len(points), 1) if points else 0,
            "demand_mae": round(float(sum(demand_abs_errors) / len(demand_abs_errors)), 1) if demand_abs_errors else 0,
            "demand_coverage_pct": round(100 * demand_covered / len(points), 1) if points else 0,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {OUT} ({len(points)} hours, {out['summary']['coverage_pct']}% covered)")


if __name__ == "__main__":
    main()
