"""
Dependency-free Vercel Python function for the forecast API.

This serves the checked-in forecast artifact directly so the deployment does
not depend on FastAPI, LightGBM, or MLflow at cold start.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs


_ARTIFACT = Path(__file__).resolve().parent / "forecast.json"
_STATIC_FORECAST: dict | None = None


def _load_static_forecast() -> dict:
    if not _ARTIFACT.exists():
        raise RuntimeError(f"Missing forecast artifact: {_ARTIFACT}")
    return json.loads(_ARTIFACT.read_text())


def _as_json(status: int, payload: dict) -> tuple[int, list[tuple[str, str]], bytes]:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    headers = [
        ("content-type", "application/json; charset=utf-8"),
        ("content-length", str(len(body))),
        ("cache-control", "no-store"),
    ]
    return status, headers, body


def _scale_interval(interval: dict, multiplier: float) -> dict:
    return {key: value * multiplier for key, value in interval.items()}


def _apply_multipliers(base: dict, solar_multiplier: float, wind_multiplier: float, horizon: int) -> dict:
    payload = deepcopy(base)
    payload["solar_multiplier"] = solar_multiplier
    payload["wind_multiplier"] = wind_multiplier
    payload["forecasts"] = payload["forecasts"][:horizon]

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

    hours = payload["forecasts"]
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["horizon_hours"] = horizon
    payload["summary"] = {
        "confirmed_surplus_hours": sum(1 for hour in hours if hour["coverage_status"] == "confirmed_surplus"),
        "possible_surplus_hours": sum(1 for hour in hours if hour["coverage_status"] == "possible_surplus"),
        "deficit_hours": sum(1 for hour in hours if hour["coverage_status"] == "deficit"),
    }
    return payload


async def app(scope, receive, send):
    if scope["type"] != "http":
        raise RuntimeError("Unsupported scope type")

    method = scope["method"]
    path = scope["path"]
    query = parse_qs(scope.get("query_string", b"").decode("utf-8"))

    global _STATIC_FORECAST
    if _STATIC_FORECAST is None:
        _STATIC_FORECAST = _load_static_forecast()

    if method == "GET" and path == "/health":
        status, headers, body = _as_json(200, {"status": "ok", "forecast_artifact_loaded": True})
    elif method == "GET" and path == "/forecast":
        horizon = int(query.get("horizon", ["48"])[0])
        horizon = max(1, min(96, horizon))
        solar_multiplier = float(query.get("solar_multiplier", ["1.0"])[0])
        wind_multiplier = float(query.get("wind_multiplier", ["1.0"])[0])
        payload = _apply_multipliers(_STATIC_FORECAST, solar_multiplier, wind_multiplier, horizon)
        status, headers, body = _as_json(200, payload)
    else:
        status, headers, body = _as_json(404, {"detail": "Not Found"})

    await send({"type": "http.response.start", "status": status, "headers": [[k.encode(), v.encode()] for k, v in headers]})
    await send({"type": "http.response.body", "body": body})
