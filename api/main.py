"""
FastAPI app. Load models at startup, serve /forecast, /health, /metrics.

Run locally:
    uvicorn api.main:app --reload
"""
import json
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None
else:
    load_dotenv()

import lightgbm as lgb
import pandas as pd
from fastapi import FastAPI, Query
from pydantic import BaseModel

from data.weather import fetch_forecast
from features.engineer import inference_features, get_feature_cols
from storage.db import query as db_query

_TARGETS = ["demand_mw", "solar_mw", "wind_mw"]
_ARTIFACTS = Path(__file__).resolve().parent.parent / "models" / "artifacts"
_models: dict[str, lgb.Booster] = {}
_radii: dict[str, float] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not _ARTIFACTS.exists():
        raise RuntimeError(f"Missing model artifacts directory: {_ARTIFACTS}")
    radii_path = _ARTIFACTS / "radii.json"
    if not radii_path.exists():
        raise RuntimeError(f"Missing conformal radii file: {radii_path}")

    _radii.update(json.loads(radii_path.read_text()))
    for target in _TARGETS:
        model_path = _ARTIFACTS / f"{target}.txt"
        if not model_path.exists():
            raise RuntimeError(f"Missing model artifact: {model_path}")
        _models[target] = lgb.Booster(model_file=str(model_path))
        print(f"[startup] loaded {model_path.name}")
    yield
    _models.clear()
    _radii.clear()


app = FastAPI(title="Swiss Energy Forecast", lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# --- Pydantic response models ---

class Interval(BaseModel):
    point: float
    lower: float
    upper: float


class ForecastHour(BaseModel):
    timestamp: datetime
    demand:      Interval
    solar:       Interval
    wind:        Interval
    supply_gap:  Interval
    coverage_status: str  # "confirmed_surplus" | "possible_surplus" | "deficit"


class ForecastSummary(BaseModel):
    confirmed_surplus_hours: int
    possible_surplus_hours:  int
    deficit_hours:           int


class ForecastResponse(BaseModel):
    generated_at:     datetime
    horizon_hours:    int
    solar_multiplier: float
    wind_multiplier:  float
    forecasts:        list[ForecastHour]
    summary:          ForecastSummary


# --- Endpoints ---

@app.get("/health")
async def health():
    return {"status": "ok", "models_loaded": list(_models.keys())}


@app.get("/forecast", response_model=ForecastResponse)
async def forecast(
    horizon:          int   = Query(48,  ge=1,  le=96),
    solar_multiplier: float = Query(1.0, ge=0.1, le=5.0),
    wind_multiplier:  float = Query(1.0, ge=0.1, le=5.0),
):
    now = pd.Timestamp.now(tz="UTC").floor("h")
    history = db_query(start=now - pd.Timedelta(hours=200))
    weather = fetch_forecast(horizon_hours=horizon)

    # Collect (point, lower, upper) per target
    predictions: dict[str, tuple[pd.Series, pd.Series, pd.Series]] = {}
    for target in _TARGETS:
        X = inference_features(history, target, weather, now, horizon)
        point = pd.Series(_models[target].predict(X[get_feature_cols(target)]))
        radius = float(_radii[target])
        lower = point - radius
        upper = point + radius
        if target in ("solar_mw", "wind_mw"):  # generation can't go negative
            point, lower = point.clip(min=0), lower.clip(min=0)
        predictions[target] = (point, lower, upper)

    # Apply capacity multipliers to solar and wind (point, lower, upper all scale linearly)
    s_pt, s_lo, s_hi = predictions["solar_mw"]
    predictions["solar_mw"] = (s_pt * solar_multiplier, s_lo * solar_multiplier, s_hi * solar_multiplier)

    w_pt, w_lo, w_hi = predictions["wind_mw"]
    predictions["wind_mw"] = (w_pt * wind_multiplier, w_lo * wind_multiplier, w_hi * wind_multiplier)

    # Build per-hour forecast objects
    hours: list[ForecastHour] = []
    for h in range(horizon):
        d_pt, d_lo, d_hi = (predictions["demand_mw"][k][h] for k in range(3))
        s_pt, s_lo, s_hi = (predictions["solar_mw"][k][h]  for k in range(3))
        w_pt, w_lo, w_hi = (predictions["wind_mw"][k][h]   for k in range(3))

        gap_pt = d_pt - (s_pt + w_pt)
        gap_lo = d_lo - (s_hi + w_hi)  # best case for the grid (least deficit)
        gap_hi = d_hi - (s_lo + w_lo)  # worst case (most deficit)

        if gap_hi < 0:
            status = "confirmed_surplus"  # renewables exceed demand even in the worst case
        elif gap_pt < 0:
            status = "possible_surplus"
        else:
            status = "deficit"

        hours.append(ForecastHour(
            timestamp=now + pd.Timedelta(hours=h + 1),
            demand=     Interval(point=d_pt, lower=d_lo, upper=d_hi),
            solar=      Interval(point=s_pt, lower=s_lo, upper=s_hi),
            wind=       Interval(point=w_pt, lower=w_lo, upper=w_hi),
            supply_gap= Interval(point=gap_pt, lower=gap_lo, upper=gap_hi),
            coverage_status=status,
        ))

    confirmed = sum(1 for h in hours if h.coverage_status == "confirmed_surplus")
    possible  = sum(1 for h in hours if h.coverage_status == "possible_surplus")
    deficit   = sum(1 for h in hours if h.coverage_status == "deficit")

    return ForecastResponse(
        generated_at=now.to_pydatetime(),
        horizon_hours=horizon,
        solar_multiplier=solar_multiplier,
        wind_multiplier=wind_multiplier,
        forecasts=hours,
        summary=ForecastSummary(
            confirmed_surplus_hours=confirmed,
            possible_surplus_hours=possible,
            deficit_hours=deficit,
        ),
    )
