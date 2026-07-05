"""
Generate a static 48h forecast JSON for the deployed dashboard.

Pulls recent actuals straight from ENTSO-E (no database needed) plus the
Open-Meteo weather forecast, runs the exported LightGBM boosters, applies the
conformal radii, and writes frontend/public/forecast.json in the same shape
as the /forecast API response at 1.0x multipliers. The frontend applies
counterfactual multipliers client side.

Run:
    python -m scripts.static_forecast
Needs ENTSOE_API_KEY in the environment.
"""
import json
import os
from datetime import date, timedelta
from pathlib import Path

import lightgbm as lgb
import pandas as pd

from dotenv import load_dotenv
load_dotenv()

from data.entsoe import fetch_energy, fetch_generation
from data.weather import fetch_forecast
from features.engineer import inference_features, get_feature_cols

TARGETS = ["demand_mw", "solar_mw", "wind_mw"]
# nuclear plus hydro (pumped storage, run-of-river, reservoir)
CLEAN_BASELOAD_TYPES = ["B14", "B10", "B11", "B12"]
HORIZON = 48
ART = Path(__file__).resolve().parent.parent / "models" / "artifacts"
OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "forecast.json"


def classify(gap_pt: float, gap_hi: float) -> str:
    if gap_hi < 0:
        return "confirmed_surplus"
    if gap_pt < 0:
        return "possible_surplus"
    return "deficit"


def clean_baseload_profile() -> dict[int, float]:
    """
    Typical nuclear + hydro generation by hour of day, from the last 14 days.
    These are dispatchable (or baseload) sources, so a recent hourly profile is
    a more honest reference than a weather-driven forecast would be.
    """
    start, end = date.today() - timedelta(days=14), date.today() + timedelta(days=1)
    total = None
    for psr in CLEAN_BASELOAD_TYPES:
        df = fetch_generation(psr, start, end)
        if df.empty:
            continue
        s = df.set_index("timestamp")["mw"]
        total = s if total is None else total.add(s, fill_value=0)
    prof = total.groupby(total.index.hour).mean()
    return {int(h): float(v) for h, v in prof.items()}


def main() -> None:
    now = pd.Timestamp.now(tz="UTC").floor("h")
    # 168h lags plus slack; ENTSO-E publishes with a few hours delay
    history = fetch_energy(date.today() - timedelta(days=10), date.today() + timedelta(days=1))
    history = history[history["timestamp"] <= now]
    weather = fetch_forecast(horizon_hours=HORIZON)

    clean_profile = clean_baseload_profile()
    radii = json.loads((ART / "radii.json").read_text())
    preds = {}
    for target in TARGETS:
        booster = lgb.Booster(model_file=str(ART / f"{target}.txt"))
        X = inference_features(history, target, weather, now, HORIZON)
        point = booster.predict(X[get_feature_cols(target)])
        r = radii[target]
        lower, upper = point - r, point + r
        if target in ("solar_mw", "wind_mw"):  # generation can't go negative
            point, lower = point.clip(min=0), lower.clip(min=0)
        preds[target] = (point, lower, upper)

    hours = []
    for h in range(HORIZON):
        d_pt, d_lo, d_hi = (preds["demand_mw"][k][h] for k in range(3))
        s_pt, s_lo, s_hi = (preds["solar_mw"][k][h] for k in range(3))
        w_pt, w_lo, w_hi = (preds["wind_mw"][k][h] for k in range(3))
        gap_pt = d_pt - (s_pt + w_pt)
        gap_lo = d_lo - (s_hi + w_hi)
        gap_hi = d_hi - (s_lo + w_lo)
        ts = now + pd.Timedelta(hours=h + 1)
        hours.append({
            "timestamp": ts.isoformat(),
            "clean_mw": round(clean_profile.get(ts.hour, 0.0), 1),
            "demand": {"point": d_pt, "lower": d_lo, "upper": d_hi},
            "solar": {"point": s_pt, "lower": s_lo, "upper": s_hi},
            "wind": {"point": w_pt, "lower": w_lo, "upper": w_hi},
            "supply_gap": {"point": gap_pt, "lower": gap_lo, "upper": gap_hi},
            "coverage_status": classify(gap_pt, gap_hi),
        })

    statuses = [h["coverage_status"] for h in hours]
    out = {
        "generated_at": now.isoformat(),
        "horizon_hours": HORIZON,
        "solar_multiplier": 1.0,
        "wind_multiplier": 1.0,
        "forecasts": hours,
        "summary": {
            "confirmed_surplus_hours": statuses.count("confirmed_surplus"),
            "possible_surplus_hours": statuses.count("possible_surplus"),
            "deficit_hours": statuses.count("deficit"),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {OUT} ({len(hours)} hours, generated {now})")


if __name__ == "__main__":
    main()
