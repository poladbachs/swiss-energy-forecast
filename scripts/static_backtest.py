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
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from dotenv import load_dotenv
load_dotenv()

from features.engineer import build_training_frame, get_feature_cols
from models.price_model import predict as predict_price
from storage.db import query as db_query

TARGETS = ["demand_mw", "solar_mw", "wind_mw"]
HORIZON_H = 24        # fixed lead time being backtested
BACKTEST_DAYS = 14     # how many days of replay to serve
LOOKBACK_DAYS = 16     # buffer for the 168h seasonal-naive lookup + 24h rolling features
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

    # Full-resolution actuals lookup, keyed by timestamp, for the seasonal-naive
    # baseline and for hydro/nuclear/price actuals (none of which are model
    # targets — they're read straight from what really happened).
    hist_idx = history.set_index("timestamp")

    radii = json.loads((ART / "radii.json").read_text())
    price_coeffs_path = ART / "price_sensitivity.json"
    price_coeffs = json.loads(price_coeffs_path.read_text()) if price_coeffs_path.exists() else None

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

        # frame[target] is the raw, unshifted series value at base time t
        # (= target_ts - 24h), i.e. the naive-persistence baseline.
        series[target] = pd.DataFrame({
            "timestamp": target_ts.reset_index(drop=True),
            "point": point, "lower": lower, "upper": upper,
            "actual": frame["label"].values,
            "naive_24h": frame[target].values,
        }).set_index("timestamp")

    merged = series["demand_mw"].join(
        series["solar_mw"], lsuffix="_demand", rsuffix="_solar"
    ).join(series["wind_mw"].add_suffix("_wind"), how="inner").dropna()

    points, covered = [], 0
    demand_covered = 0
    demand_abs_errors, demand_naive24_abs_errors, demand_naive168_abs_errors = [], [], []
    price_abs_errors = []
    for ts, r in merged.iterrows():
        d = dict(point=r.point_demand, lower=r.lower_demand, upper=r.upper_demand, actual=r.actual_demand)
        s = dict(point=r.point_solar, lower=r.lower_solar, upper=r.upper_solar, actual=r.actual_solar)
        w = dict(point=r.point_wind, lower=r.lower_wind, upper=r.upper_wind, actual=r.actual_wind)

        # Domestic generation actuals for this hour (real, since this is retrospective).
        hydro_a = float(hist_idx["hydro_mw"].get(ts, np.nan))
        nuclear_a = float(hist_idx["nuclear_mw"].get(ts, np.nan))
        domestic_actual = s["actual"] + w["actual"] + hydro_a + nuclear_a
        domestic_point = s["point"] + w["point"] + hydro_a + nuclear_a  # hydro/nuclear held at actual (not modeled)

        gap = dict(
            point=d["point"] - domestic_point,
            lower=d["lower"] - (s["upper"] + w["upper"] + hydro_a + nuclear_a),
            upper=d["upper"] - (s["lower"] + w["lower"] + hydro_a + nuclear_a),
            actual=d["actual"] - domestic_actual,
        )

        # Seasonal-naive baseline: same hour, one week earlier. A much harder
        # bar than 24h-persistence for demand data with strong weekly seasonality.
        naive_168h = float(hist_idx["demand_mw"].get(ts - pd.Timedelta(hours=168), np.nan))

        is_covered = bool(gap["lower"] <= gap["actual"] <= gap["upper"])
        demand_is_covered = bool(d["lower"] <= d["actual"] <= d["upper"])
        covered += int(is_covered)
        demand_covered += int(demand_is_covered)
        demand_abs_errors.append(abs(d["actual"] - d["point"]))
        demand_naive24_abs_errors.append(abs(d["actual"] - r.naive_24h_demand))
        if not np.isnan(naive_168h):
            demand_naive168_abs_errors.append(abs(d["actual"] - naive_168h))

        price_actual = hist_idx["price_eur_mwh"].get(ts, np.nan)
        price_point = None
        if price_coeffs is not None and not pd.isna(price_actual):
            price_point = float(predict_price(price_coeffs, [gap["point"]], pd.DatetimeIndex([ts]))[0])
            price_abs_errors.append(abs(float(price_actual) - price_point))

        points.append({
            "timestamp": iso_utc(ts),
            "demand": {**{k: float(v) for k, v in d.items()}, "naive_24h": float(r.naive_24h_demand),
                       "naive_168h": naive_168h if not np.isnan(naive_168h) else None},
            "solar": {k: float(v) for k, v in s.items()},
            "wind": {k: float(v) for k, v in w.items()},
            "hydro_mw": hydro_a,
            "nuclear_mw": nuclear_a,
            "import_gap": {k: float(v) for k, v in gap.items()},
            "price_eur_mwh": float(price_actual) if not pd.isna(price_actual) else None,
            "price_implied_eur_mwh": price_point,
            "coverage_status": classify(gap["point"], gap["upper"]),
            "covered": is_covered,
            "demand_covered": demand_is_covered,
        })

    def mae(errors):
        return float(sum(errors) / len(errors)) if errors else 0

    demand_mae = mae(demand_abs_errors)
    demand_naive24_mae = mae(demand_naive24_abs_errors)
    demand_naive168_mae = mae(demand_naive168_abs_errors)
    price_mae = mae(price_abs_errors) if price_abs_errors else None

    out = {
        "horizon_h": HORIZON_H,
        "generated_at": iso_utc(now),
        "points": points,
        "summary": {
            "hours": len(points),
            "covered_hours": covered,
            "coverage_pct": round(100 * covered / len(points), 1) if points else 0,
            "demand_mae": round(demand_mae, 1),
            "demand_naive_24h_mae": round(demand_naive24_mae, 1),
            "demand_naive_168h_mae": round(demand_naive168_mae, 1),
            # The seasonal-naive (same hour, last week) baseline is the fair
            # comparison for daily/weekly-periodic demand; 24h-persistence is
            # kept alongside for transparency but is a weaker bar to clear.
            "demand_mae_improvement_pct": round(100 * (1 - demand_mae / demand_naive168_mae), 1) if demand_naive168_mae else 0,
            "demand_coverage_pct": round(100 * demand_covered / len(points), 1) if points else 0,
            "price_mae_eur_mwh": round(price_mae, 1) if price_mae is not None else None,
            "price_model": price_coeffs,
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {OUT} ({len(points)} hours, {out['summary']['coverage_pct']}% covered)")


if __name__ == "__main__":
    main()
