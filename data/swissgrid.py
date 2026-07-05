"""
Swissgrid energy balance XLSX fallback. No API key required.
Set DATA_SOURCE=swissgrid (default) to activate.
"""
import io
import requests
import pandas as pd
from datetime import date

_URL = "https://www.swissgrid.ch/dam/dataimport/energy-statistic/EnergieUebersichtCH-{year}.xlsx"

# Substring matches for Swissgrid column names (German headers, can vary slightly by year)
_COL_PATTERNS = {
    "Verbrauch":              "demand_mw",
    "Produktion Photovoltaik": "solar_mw",
    "Produktion Wind":         "wind_mw",
}


def _fetch_year(year: int) -> pd.DataFrame:
    resp = requests.get(_URL.format(year=year), timeout=120)
    resp.raise_for_status()
    raw = pd.read_excel(io.BytesIO(resp.content), header=0, engine="openpyxl")

    # First column is the timestamp
    renames = {raw.columns[0]: "timestamp"}
    for col in raw.columns:
        for pattern, name in _COL_PATTERNS.items():
            if pattern in str(col):
                renames[col] = name
                break
    raw = raw.rename(columns=renames)

    keep = ["timestamp"] + [v for v in _COL_PATTERNS.values() if v in raw.columns]
    raw = raw[keep].dropna(subset=["timestamp"])
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True)

    # Swissgrid publishes GWh/h (= GW); ×1000 → MW
    for col in ["demand_mw", "solar_mw", "wind_mw"]:
        if col in raw.columns:
            raw[col] = raw[col] * 1000

    return raw


def fetch_energy(start: date, end: date) -> pd.DataFrame:
    """Returns DataFrame with columns: timestamp (UTC), demand_mw, solar_mw, wind_mw."""
    df = pd.concat([_fetch_year(y) for y in range(start.year, end.year + 1)], ignore_index=True)
    mask = (df["timestamp"].dt.date >= start) & (df["timestamp"].dt.date <= end)
    return df[mask].sort_values("timestamp").reset_index(drop=True)
