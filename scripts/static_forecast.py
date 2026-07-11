"""
Generate a static 48h forecast JSON for the deployed dashboard.

Pulls recent actuals from the database, uses the Open-Meteo weather forecast,
runs the exported LightGBM boosters, applies the conformal radii, and writes
frontend/public/forecast.json (and api/forecast.json, see API_OUT below) in
the shape the dashboard reads. Baseline (1.0x) plus a small set of named
scenarios are precomputed here, each by actually perturbing the model's real
inputs and rerunning the trained boosters — not by post-hoc multiplying the
output.

Run:
    python -m scripts.static_forecast
"""
import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from dotenv import load_dotenv
load_dotenv()

from data.weather import fetch_forecast
from features.engineer import inference_features, get_feature_cols
from storage.db import query as db_query

TARGETS = ["demand_mw", "solar_mw", "wind_mw"]
HORIZON = 48
ART = Path(__file__).resolve().parent.parent / "models" / "artifacts"
OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "forecast.json"
# api/main.py (the live Vercel /api/forecast route) reads its own copy rather
# than reaching into frontend/public, so both must be written on every refresh
# or the deployed API silently drifts from the dashboard's static fallback.
API_OUT = Path(__file__).resolve().parent.parent / "api" / "forecast.json"

# Cold snap / low wind / low solar / holiday perturb a real model input and
# rerun the trained boosters, so the resulting shift is whatever the model
# actually learned about that input — not a hand-picked multiplier. "Event
# shock" (e.g. a strike) has no counterpart feature in the model at all, so
# it's deliberately left out here and stays a manual, clearly-labeled overlay
# in the frontend instead of being dressed up as a model output.
SCENARIO_WEATHER_OVERRIDES = {
    "cold_snap": {"temperature": lambda s: s - 5.0},
    "low_wind":  {"wind_speed": lambda s: s * 0.3},
    "low_solar": {"solar_radiation": lambda s: s * 0.3, "cloud_cover": lambda s: np.minimum(s + 40, 100)},
}
SCENARIO_HOLIDAY_OVERRIDE = "holiday"  # forces is_swiss_holiday=1 for every forecast hour


def classify(gap_pt: float, gap_hi: float) -> str:
    if gap_hi < 0:
        return "confirmed_surplus"
    if gap_pt < 0:
        return "possible_surplus"
    return "deficit"


def _trailing_hourly_profile(history: pd.DataFrame, col: str, now: pd.Timestamp, lookback_days: int = 7):
    """Mean of `col` by hour-of-day over the trailing window, for carrying an
    unmodeled series (hydro, nuclear) forward without training a model for it."""
    recent = history[history["timestamp"] > now - pd.Timedelta(days=lookback_days)]
    if recent.empty:
        recent = history
    return recent.groupby(recent["timestamp"].dt.hour)[col].mean(), recent[col].mean()


def _estimate_domestic_baseload(history: pd.DataFrame, now: pd.Timestamp, horizon: int):
    """Hydro (run-of-river + reservoir) and nuclear aren't ML-forecasted here —
    nuclear is near-constant baseload and hydro dispatch isn't weather-driven
    the way solar/wind are, so a trailing same-hour average is a defensible,
    much cheaper stand-in than training two more 48-horizon models. This is a
    point estimate only; it is not conformal-calibrated like demand/solar/wind."""
    hydro_prof, hydro_mean = _trailing_hourly_profile(history, "hydro_mw", now)
    nuclear_prof, nuclear_mean = _trailing_hourly_profile(history, "nuclear_mw", now)
    hydro_est, nuclear_est = [], []
    for h in range(1, horizon + 1):
        hour = (now + pd.Timedelta(hours=h)).hour
        hydro_est.append(float(hydro_prof.get(hour, hydro_mean)))
        nuclear_est.append(float(nuclear_prof.get(hour, nuclear_mean)))
    return np.array(hydro_est), np.array(nuclear_est)


def _predict_targets(history, weather, now, boosters, radii, horizon, force_holiday=False):
    """Run inference for all three ML targets against a given weather frame,
    optionally forcing every forecast hour's holiday flag. Returns
    {target: (point, lower, upper)}."""
    preds = {}
    for target in TARGETS:
        X = inference_features(history, target, weather, now, horizon)
        if force_holiday:
            X = X.copy()
            X["is_swiss_holiday"] = 1
        point = boosters[target].predict(X[get_feature_cols(target)])
        r = radii[target]
        lower, upper = point - r, point + r
        if target in ("solar_mw", "wind_mw"):  # generation can't go negative
            point, lower = point.clip(min=0), lower.clip(min=0)
        preds[target] = (point, lower, upper)
    return preds


def _build_hours(preds, hydro_est, nuclear_est, now, horizon):
    hours = []
    for h in range(horizon):
        d_pt, d_lo, d_hi = (preds["demand_mw"][k][h] for k in range(3))
        s_pt, s_lo, s_hi = (preds["solar_mw"][k][h] for k in range(3))
        w_pt, w_lo, w_hi = (preds["wind_mw"][k][h] for k in range(3))
        hyd, nuc = float(hydro_est[h]), float(nuclear_est[h])

        gap_pt = d_pt - (s_pt + w_pt + hyd + nuc)
        gap_lo = d_lo - (s_hi + w_hi + hyd + nuc)
        gap_hi = d_hi - (s_lo + w_lo + hyd + nuc)
        ts = now + pd.Timedelta(hours=h + 1)

        hours.append({
            "timestamp": ts.isoformat(),
            "demand": {"point": d_pt, "lower": d_lo, "upper": d_hi},
            "solar": {"point": s_pt, "lower": s_lo, "upper": s_hi},
            "wind": {"point": w_pt, "lower": w_lo, "upper": w_hi},
            "hydro_mw": hyd,
            "nuclear_mw": nuc,
            "import_gap": {"point": gap_pt, "lower": gap_lo, "upper": gap_hi},
            "coverage_status": classify(gap_pt, gap_hi),
        })
    return hours


def _summary(hours):
    statuses = [h["coverage_status"] for h in hours]
    return {
        "confirmed_surplus_hours": statuses.count("confirmed_surplus"),
        "possible_surplus_hours": statuses.count("possible_surplus"),
        "deficit_hours": statuses.count("deficit"),
    }


def main() -> None:
    history = db_query(start=pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=180))
    if history.empty:
        raise ValueError("No history rows available for forecast generation")
    now = history["timestamp"].max().floor("h")
    history = history[history["timestamp"] <= now]
    weather = fetch_forecast(horizon_hours=HORIZON)

    radii = json.loads((ART / "radii.json").read_text())
    boosters = {t: lgb.Booster(model_file=str(ART / f"{t}.txt")) for t in TARGETS}
    hydro_est, nuclear_est = _estimate_domestic_baseload(history, now, HORIZON)

    baseline_preds = _predict_targets(history, weather, now, boosters, radii, HORIZON)
    hours = _build_hours(baseline_preds, hydro_est, nuclear_est, now, HORIZON)

    scenarios = {}
    for name, overrides in SCENARIO_WEATHER_OVERRIDES.items():
        w = weather.copy()
        for col, fn in overrides.items():
            w[col] = fn(w[col])
        preds = _predict_targets(history, w, now, boosters, radii, HORIZON)
        scenarios[name] = _build_hours(preds, hydro_est, nuclear_est, now, HORIZON)
    holiday_preds = _predict_targets(history, weather, now, boosters, radii, HORIZON, force_holiday=True)
    scenarios[SCENARIO_HOLIDAY_OVERRIDE] = _build_hours(holiday_preds, hydro_est, nuclear_est, now, HORIZON)

    out = {
        "generated_at": now.isoformat(),
        "horizon_hours": HORIZON,
        "solar_multiplier": 1.0,
        "wind_multiplier": 1.0,
        "forecasts": hours,
        "scenarios": scenarios,
        "summary": _summary(hours),
    }
    payload = json.dumps(out, indent=2) + "\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(payload)
    API_OUT.parent.mkdir(parents=True, exist_ok=True)
    API_OUT.write_text(payload)
    print(f"wrote {OUT} and {API_OUT} ({len(hours)} hours, generated {now}, {len(scenarios)} scenarios)")


if __name__ == "__main__":
    main()
