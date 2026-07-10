"""
Vercel Python entrypoint.

Serves the built React frontend from `api/site` and the forecast API from
`/api/forecast`. This keeps the website visible even when the deployment is
treated as a Python function app.
"""
from __future__ import annotations

import json
import mimetypes
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs


_ROOT = Path(__file__).resolve().parent
_SITE = _ROOT / "site"
_FORECAST = _ROOT / "forecast.json"
_BACKTEST = _SITE / "backtest.json"
_STATIC_FORECAST: dict | None = None


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"Missing JSON artifact: {path}")
    return json.loads(path.read_text())


def _load_static_forecast() -> dict:
    return _load_json(_FORECAST)


def _as_response(status: int, body: bytes, content_type: str, cache_control: str = "no-store") -> tuple[int, list[tuple[str, str]], bytes]:
    headers = [
        ("content-type", content_type),
        ("content-length", str(len(body))),
        ("cache-control", cache_control),
    ]
    return status, headers, body


def _as_json(status: int, payload: dict) -> tuple[int, list[tuple[str, str]], bytes]:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return _as_response(status, body, "application/json; charset=utf-8")


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
        hour["supply_gap"] = {"point": gap_point, "lower": gap_lower, "upper": gap_upper}
        hour["coverage_status"] = "confirmed_surplus" if gap_upper < 0 else "possible_surplus" if gap_point < 0 else "deficit"

    hours = payload["forecasts"]
    payload["served_at"] = datetime.now(timezone.utc).isoformat()
    payload["horizon_hours"] = horizon
    payload["summary"] = {
        "confirmed_surplus_hours": sum(1 for hour in hours if hour["coverage_status"] == "confirmed_surplus"),
        "possible_surplus_hours": sum(1 for hour in hours if hour["coverage_status"] == "possible_surplus"),
        "deficit_hours": sum(1 for hour in hours if hour["coverage_status"] == "deficit"),
    }
    return payload


def _serve_file(path: Path) -> tuple[int, list[tuple[str, str]], bytes]:
    if not path.exists() or not path.is_file():
        return _as_json(404, {"detail": "Not Found"})
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    cache_control = "public, max-age=31536000, immutable" if path.suffix in {".js", ".css", ".png", ".jpg", ".jpeg", ".svg", ".woff", ".woff2"} else "no-store"
    return _as_response(200, path.read_bytes(), content_type, cache_control)


def _resolve_site_path(request_path: str) -> Path:
    if request_path == "/" or request_path == "":
        return _SITE / "index.html"

    candidate = (_SITE / request_path.lstrip("/")).resolve()
    site_root = _SITE.resolve()
    if site_root not in candidate.parents and candidate != site_root / "index.html":
        return site_root / "__missing__"
    return candidate


async def app(scope, receive, send):
    if scope["type"] != "http":
        raise RuntimeError("Unsupported scope type")

    method = scope["method"]
    path = scope["path"]
    query = parse_qs(scope.get("query_string", b"").decode("utf-8"))

    global _STATIC_FORECAST
    if _STATIC_FORECAST is None:
        _STATIC_FORECAST = _load_static_forecast()

    if method != "GET":
        status, headers, body = _as_json(405, {"detail": "Method Not Allowed"})
    elif path == "/api/health":
        status, headers, body = _as_json(200, {"status": "ok", "forecast_artifact_loaded": True})
    elif path == "/api/forecast":
        horizon = int(query.get("horizon", ["48"])[0])
        horizon = max(1, min(96, horizon))
        solar_multiplier = float(query.get("solar_multiplier", ["1.0"])[0])
        wind_multiplier = float(query.get("wind_multiplier", ["1.0"])[0])
        payload = _apply_multipliers(_STATIC_FORECAST, solar_multiplier, wind_multiplier, horizon)
        status, headers, body = _as_json(200, payload)
    elif path in {"/favicon.ico", "/favicon.png", "/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"}:
        status, headers, body = _as_response(204, b"", "application/octet-stream")
    elif path == "/backtest.json":
        status, headers, body = _serve_file(_BACKTEST)
    else:
        status, headers, body = _serve_file(_resolve_site_path(path))

    await send({"type": "http.response.start", "status": status, "headers": [[k.encode(), v.encode()] for k, v in headers]})
    await send({"type": "http.response.body", "body": body})
