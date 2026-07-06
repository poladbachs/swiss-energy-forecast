"""
Swissgrid energy balance XLSX fallback.

Swissgrid publishes the demand series in the 15-minute time-series sheet, but it
does not publish separate solar and wind generation series. This fallback keeps
the ingest pipeline working without ENTSO-E by zero-filling the renewable
columns, which preserves the expected schema but is not equivalent data.
"""
import io
from datetime import date

import pandas as pd
import requests

_URL = "https://www.swissgrid.ch/dam/dataimport/energy-statistic/EnergieUebersichtCH-{year}.xlsx"


def _fetch_demand_year(year: int) -> pd.DataFrame:
    resp = requests.get(_URL.format(year=year), timeout=120)
    resp.raise_for_status()

    # The real series lives in Zeitreihen0h15. Row 1 contains labels, row 2 units,
    # and the quarter-hour values start on row 3.
    raw = pd.read_excel(
        io.BytesIO(resp.content),
        sheet_name="Zeitreihen0h15",
        header=None,
        usecols="A:B",
        engine="openpyxl",
    )
    raw = raw.iloc[2:].copy()
    raw.columns = ["timestamp", "demand_kwh"]
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], format="%d.%m.%Y %H:%M", utc=True, errors="coerce")
    raw["demand_kwh"] = pd.to_numeric(raw["demand_kwh"], errors="coerce")
    raw = raw.dropna(subset=["timestamp", "demand_kwh"])

    # Swissgrid stores quarter-hour energy in kWh. Convert to hourly average MW:
    # kWh per 15 minutes -> kW average over the interval -> divide by 1000.
    # Since each row is a 15-minute interval, MW = kWh / 250.
    raw["demand_mw"] = raw["demand_kwh"] / 250.0
    hourly = (
        raw.set_index("timestamp")
        .resample("h")
        .mean(numeric_only=True)
        .reset_index()[["timestamp", "demand_mw"]]
    )
    return hourly


def fetch_energy(start: date, end: date) -> pd.DataFrame:
    """Returns DataFrame with columns: timestamp (UTC), demand_mw, solar_mw, wind_mw."""
    demand = pd.concat([_fetch_demand_year(y) for y in range(start.year, end.year + 1)], ignore_index=True)
    demand = demand[(demand["timestamp"].dt.date >= start) & (demand["timestamp"].dt.date <= end)]

    df = demand.copy()
    df["solar_mw"] = 0.0
    df["wind_mw"] = 0.0
    return df.sort_values("timestamp").reset_index(drop=True)
