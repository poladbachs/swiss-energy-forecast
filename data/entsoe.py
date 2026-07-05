"""
ENTSO-E Transparency API client.
Requires ENTSOE_API_KEY in environment. Set DATA_SOURCE=entsoe to activate.

Rate limit is 400 requests/day, so historical pulls are batched per year.
"""
import os
import requests
import xmltodict
import pandas as pd
from datetime import date

_BASE = "https://web-api.tp.entsoe.eu/api"
_AREA = "10YCH-SWISSGRIDZ"


def _fmt(d: date) -> str:
    return d.strftime("%Y%m%d0000")


def _get(key: str, params: dict) -> dict:
    resp = requests.get(_BASE, params={"securityToken": key, **params}, timeout=60)
    resp.raise_for_status()
    return xmltodict.parse(resp.text)


_RES_MIN = {"PT15M": 15, "PT30M": 30, "PT60M": 60, "P1D": 1440}


def _parse_timeseries(doc: dict) -> list[tuple[pd.Timestamp, float]]:
    """Flatten TimeSeries > Period > Point into (timestamp, value) pairs, honoring resolution."""
    ts_list = doc.get("TimeSeries", [])
    if isinstance(ts_list, dict):
        ts_list = [ts_list]
    rows = []
    for ts in ts_list:
        periods = ts.get("Period", [])
        if isinstance(periods, dict):
            periods = [periods]
        for period in periods:
            start = pd.Timestamp(period["timeInterval"]["start"])
            step = pd.Timedelta(minutes=_RES_MIN.get(period.get("resolution", "PT60M"), 60))
            points = period.get("Point", [])
            if isinstance(points, dict):
                points = [points]
            for pt in points:
                pos = int(pt["position"]) - 1
                rows.append((start + pos * step, float(pt["quantity"])))
    return rows


def _fetch_series(key: str, params: dict, col: str, start: date, end: date) -> pd.DataFrame:
    """Fetch one series in ~1-year chunks (API max range per request), resampled hourly."""
    frames = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + pd.Timedelta(days=360).to_pytimedelta(), end)
        doc = _get(key, {**params, "periodStart": _fmt(chunk_start), "periodEnd": _fmt(chunk_end)})
        rows = _parse_timeseries(doc.get("GL_MarketDocument", {}))
        if rows:
            frames.append(pd.DataFrame(rows, columns=["timestamp", col]))
        chunk_start = chunk_end
    if not frames:
        return pd.DataFrame(columns=["timestamp", col])
    df = pd.concat(frames, ignore_index=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    # sub-hourly (PT15M) → hourly mean
    return df.set_index("timestamp").resample("h").mean().dropna().reset_index()


def fetch_energy(start: date, end: date) -> pd.DataFrame:
    """Returns DataFrame with columns: timestamp (UTC), demand_mw, solar_mw, wind_mw."""
    key = os.environ["ENTSOE_API_KEY"]

    # A65 = actual total load; A75 = actual generation per type (A69 would be the *forecast*)
    demand = _fetch_series(key, {"documentType": "A65", "processType": "A16", "outBiddingZone_Domain": _AREA}, "demand_mw", start, end)
    solar  = _fetch_series(key, {"documentType": "A75", "processType": "A16", "in_Domain": _AREA, "psrType": "B16"}, "solar_mw", start, end)
    wind   = _fetch_series(key, {"documentType": "A75", "processType": "A16", "in_Domain": _AREA, "psrType": "B19"}, "wind_mw", start, end)

    df = demand.merge(solar, on="timestamp", how="outer").merge(wind, on="timestamp", how="outer")
    # ENTSO-E omits zero-generation points (solar at night), so treat gaps as 0
    # wherever the grid published anything at all for that hour
    mask = df["demand_mw"].notna()
    df.loc[mask, ["solar_mw", "wind_mw"]] = df.loc[mask, ["solar_mw", "wind_mw"]].fillna(0.0)
    return df.sort_values("timestamp").reset_index(drop=True)


def fetch_generation(psr_type: str, start: date, end: date) -> pd.DataFrame:
    """Hourly actual generation for one production type, columns: timestamp, mw."""
    key = os.environ["ENTSOE_API_KEY"]
    return _fetch_series(key, {"documentType": "A75", "processType": "A16", "in_Domain": _AREA, "psrType": psr_type}, "mw", start, end)
