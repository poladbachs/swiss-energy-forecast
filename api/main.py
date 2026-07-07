"""
FastAPI app for the deployed forecast endpoint.

On Vercel we serve the checked-in forecast artifact directly so the function
does not depend on heavy ML runtime packages at cold start.
"""
import json
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Query
from pydantic import BaseModel


_ARTIFACT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "forecast.json"
_STATIC_FORECAST = None
_models = {}
db_query = None
fetch_forecast = None


def _load_static_forecast() -> dict:
    if not _ARTIFACT.exists():
        raise RuntimeError(f"Missing forecast artifact: {_ARTIFACT}")
    return json.loads(_ARTIFACT.read_text())


def _scale_interval(interval: dict, multiplier: float) -> dict:
    return {key: value * multiplier for key, value in interval.items()}


def _apply_multipliers(base: dict, solar_multiplier: float, wind_multiplier: float) -> dict:
    payload = deepcopy(base)
    payload["solar_multiplier"] = solar_multiplier
    payload["wind_multiplier"] = wind_multiplier

    for hour in payload["forecasts"]:
        demand = hour["demand"]
        solar = _scale_interval(hour["solar"], solar_multiplier)
        wind = _scale_interval(hour["wind"], wind_multiplier)
        gap_point = demand["point"] - (solar["point"] + wind["point"])
        gap_lower = demand["lower"] - (solar["upper"] + wind["upper"])
        gap_upper = demand["upper"] - (solar["lower"] + wind["lower"])

        hour["solar"] = solar
        hour["wind"] = wind
        hour["supply_gap"] = {
            "point": gap_point,
            "lower": gap_lower,
            "upper": gap_upper,
        }
        if gap_upper < 0:
            hour["coverage_status"] = "confirmed_surplus"
        elif gap_point < 0:
            hour["coverage_status"] = "possible_surplus"
        else:
            hour["coverage_status"] = "deficit"
    return payload


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _STATIC_FORECAST
    _STATIC_FORECAST = _load_static_forecast()
    yield
    _STATIC_FORECAST = None


app = FastAPI(title="Swiss Energy Forecast", lifespan=lifespan)


class Interval(BaseModel):
    point: float
    lower: float
    upper: float


class ForecastHour(BaseModel):
    timestamp: datetime
    demand: Interval
    solar: Interval
    wind: Interval
    supply_gap: Interval
    coverage_status: str


class ForecastSummary(BaseModel):
    confirmed_surplus_hours: int
    possible_surplus_hours: int
    deficit_hours: int


class ForecastResponse(BaseModel):
    generated_at: datetime
    horizon_hours: int
    solar_multiplier: float
    wind_multiplier: float
    forecasts: list[ForecastHour]
    summary: ForecastSummary


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "forecast_artifact_loaded": _STATIC_FORECAST is not None,
    }


@app.get("/forecast", response_model=ForecastResponse)
async def forecast(
    horizon: int = Query(48, ge=1, le=96),
    solar_multiplier: float = Query(1.0, ge=0.1, le=5.0),
    wind_multiplier: float = Query(1.0, ge=0.1, le=5.0),
):
    if _STATIC_FORECAST is None:
        base = _load_static_forecast()
    else:
        base = _STATIC_FORECAST

    payload = _apply_multipliers(base, solar_multiplier, wind_multiplier)
    payload["forecasts"] = payload["forecasts"][:horizon]
    payload["horizon_hours"] = horizon
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    hours = payload["forecasts"]
    payload["summary"] = {
        "confirmed_surplus_hours": sum(1 for hour in hours if hour["coverage_status"] == "confirmed_surplus"),
        "possible_surplus_hours": sum(1 for hour in hours if hour["coverage_status"] == "possible_surplus"),
        "deficit_hours": sum(1 for hour in hours if hour["coverage_status"] == "deficit"),
    }
    return payload
