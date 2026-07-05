"""
Open-Meteo weather client. Free, no API key.
Switzerland coordinates: lat=46.8, lon=8.2
"""
import httpx
import pandas as pd
from datetime import date

_HIST = "https://archive-api.open-meteo.com/v1/archive"
_FCST = "https://api.open-meteo.com/v1/forecast"
_LAT, _LON = 46.8, 8.2
_VARS = "temperature_2m,direct_radiation,diffuse_radiation,wind_speed_10m,cloud_cover"


def _parse(data: dict) -> pd.DataFrame:
    h = data["hourly"]
    return pd.DataFrame({
        "timestamp":       pd.to_datetime(h["time"], utc=True),
        "temperature":     h["temperature_2m"],
        "solar_radiation": [d + f for d, f in zip(h["direct_radiation"], h["diffuse_radiation"])],
        "wind_speed":      h["wind_speed_10m"],
        "cloud_cover":     h["cloud_cover"],
    })


def fetch_historical(start: date, end: date) -> pd.DataFrame:
    resp = httpx.get(_HIST, params={
        "latitude": _LAT, "longitude": _LON,
        "hourly": _VARS,
        "start_date": start.isoformat(),
        "end_date":   end.isoformat(),
        "timezone": "UTC",
    }, timeout=60)
    resp.raise_for_status()
    return _parse(resp.json())


def fetch_forecast(horizon_hours: int = 48) -> pd.DataFrame:
    """Returns weather forecast for the next horizon_hours hours (from now)."""
    resp = httpx.get(_FCST, params={
        "latitude": _LAT, "longitude": _LON,
        "hourly": _VARS,
        "forecast_days": (horizon_hours // 24) + 2,
        "timezone": "UTC",
    }, timeout=30)
    resp.raise_for_status()
    df = _parse(resp.json())
    now = pd.Timestamp.now(tz="UTC").floor("h")
    return df[df["timestamp"] > now].head(horizon_hours).reset_index(drop=True)
