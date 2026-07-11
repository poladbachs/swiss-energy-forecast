"""
ENTSO-E Transparency API client.
Requires ENTSOE_API_KEY in environment.

Rate limit is 400 requests/day, so historical pulls are batched per year.
"""
import os
import requests
import xmltodict
import pandas as pd
from datetime import date

_BASE = "https://web-api.tp.entsoe.eu/api"
_AREA = "10YCH-SWISSGRIDZ"

# Bidding zones for the day-ahead price model: Switzerland plus the three
# neighbors it is physically interconnected with. DE-LU exists as a combined
# zone since Oct 2018, so a 2020+ backfill never touches the old DE-AT-LU EIC.
ZONES = {
    "CH": "10YCH-SWISSGRIDZ",
    "DE_LU": "10Y1001A1001A82H",
    "FR": "10YFR-RTE------C",
    "IT_NORD": "10Y1001A1001A73I",
}


def _fmt(d: date) -> str:
    return d.strftime("%Y%m%d0000")


def _get(key: str, params: dict) -> dict:
    resp = requests.get(_BASE, params={"securityToken": key, **params}, timeout=60)
    resp.raise_for_status()
    return xmltodict.parse(resp.text)


_RES_MIN = {"PT15M": 15, "PT30M": 30, "PT60M": 60, "P1D": 1440, "P7D": 10080}


def _parse_timeseries(doc: dict, value_key: str = "quantity") -> list[tuple[pd.Timestamp, float]]:
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
                rows.append((start + pos * step, float(pt[value_key])))
    return rows


def _fetch_series(
    key: str, params: dict, col: str, start: date, end: date,
    doc_root: str = "GL_MarketDocument", value_key: str = "quantity",
) -> pd.DataFrame:
    """Fetch one series in ~1-year chunks (API max range per request), resampled hourly."""
    frames = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + pd.Timedelta(days=360).to_pytimedelta(), end)
        doc = _get(key, {**params, "periodStart": _fmt(chunk_start), "periodEnd": _fmt(chunk_end)})
        rows = _parse_timeseries(doc.get(doc_root, {}), value_key)
        if rows:
            frames.append(pd.DataFrame(rows, columns=["timestamp", col]))
        chunk_start = chunk_end
    if not frames:
        return pd.DataFrame(columns=["timestamp", col])
    df = pd.concat(frames, ignore_index=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    # sub-hourly (PT15M) → hourly mean
    return df.set_index("timestamp").resample("h").mean().dropna().reset_index()


# Hydro run-of-river (B12) and reservoir (B11) together cover the large majority
# of Swiss domestic generation; nuclear (B14) is the other major baseload source.
# Pumped storage (B10) is deliberately excluded: ENTSO-E reports its *generation*
# leg only, not the pumping/consumption leg, so including it would double-count
# energy that was originally drawn from the grid rather than newly produced.
_DOMESTIC_PSR = {"hydro_mw": ["B11", "B12"], "nuclear_mw": ["B14"]}


def fetch_energy(start: date, end: date) -> pd.DataFrame:
    """Returns DataFrame with columns: timestamp (UTC), demand_mw, solar_mw, wind_mw, hydro_mw, nuclear_mw."""
    key = os.environ["ENTSOE_API_KEY"]

    # A65 = actual total load; A75 = actual generation per type (A69 would be the *forecast*)
    demand = _fetch_series(key, {"documentType": "A65", "processType": "A16", "outBiddingZone_Domain": _AREA}, "demand_mw", start, end)
    solar  = _fetch_series(key, {"documentType": "A75", "processType": "A16", "in_Domain": _AREA, "psrType": "B16"}, "solar_mw", start, end)
    wind   = _fetch_series(key, {"documentType": "A75", "processType": "A16", "in_Domain": _AREA, "psrType": "B19"}, "wind_mw", start, end)

    df = demand.merge(solar, on="timestamp", how="outer").merge(wind, on="timestamp", how="outer")

    for col, psr_types in _DOMESTIC_PSR.items():
        parts = [fetch_generation(psr, start, end).rename(columns={"mw": f"{psr}_mw"}) for psr in psr_types]
        merged = parts[0]
        for p in parts[1:]:
            merged = merged.merge(p, on="timestamp", how="outer")
        merged[col] = merged[[c for c in merged.columns if c != "timestamp"]].sum(axis=1, min_count=1)
        df = df.merge(merged[["timestamp", col]], on="timestamp", how="outer")

    # ENTSO-E omits zero-generation points (solar at night), so treat gaps as 0
    # wherever the grid published anything at all for that hour
    mask = df["demand_mw"].notna()
    df.loc[mask, ["solar_mw", "wind_mw", "hydro_mw", "nuclear_mw"]] = \
        df.loc[mask, ["solar_mw", "wind_mw", "hydro_mw", "nuclear_mw"]].fillna(0.0)
    return df.sort_values("timestamp").reset_index(drop=True)


def fetch_generation(psr_type: str, start: date, end: date) -> pd.DataFrame:
    """Hourly actual generation for one production type, columns: timestamp, mw."""
    key = os.environ["ENTSOE_API_KEY"]
    return _fetch_series(key, {"documentType": "A75", "processType": "A16", "in_Domain": _AREA, "psrType": psr_type}, "mw", start, end)


def _parse_price_rows(doc: dict) -> list[tuple[pd.Timestamp, float, int]]:
    """Like _parse_timeseries but for A44 price documents: keeps only the
    daily day-ahead auction (contract type A01, when tagged), skips intraday
    auction series, and tags each row with its resolution in minutes so the
    caller can prefer the hourly curve where both 60-min and 15-min products
    exist (DE-LU publishes both since the 15-min MTU went live)."""
    ts_list = doc.get("TimeSeries", [])
    if isinstance(ts_list, dict):
        ts_list = [ts_list]
    rows = []
    for ts in ts_list:
        contract = ts.get("contract_MarketAgreement.type")
        if contract is not None and contract != "A01":
            continue
        periods = ts.get("Period", [])
        if isinstance(periods, dict):
            periods = [periods]
        for period in periods:
            start = pd.Timestamp(period["timeInterval"]["start"])
            res = _RES_MIN.get(period.get("resolution", "PT60M"), 60)
            step = pd.Timedelta(minutes=res)
            points = period.get("Point", [])
            if isinstance(points, dict):
                points = [points]
            for pt in points:
                pos = int(pt["position"]) - 1
                rows.append((start + pos * step, float(pt["price.amount"]), res))
    return rows


def fetch_price(start: date, end: date, zone: str = "CH") -> pd.DataFrame:
    """Hourly realized day-ahead price (EUR/MWh) for one bidding zone,
    columns: timestamp, price_eur_mwh. Where a zone publishes both hourly and
    15-minute curves for the same hours, the hourly auction curve wins; hours
    covered only by the 15-minute curve use its within-hour mean."""
    key = os.environ["ENTSOE_API_KEY"]
    area = ZONES[zone]

    rows = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + pd.Timedelta(days=360).to_pytimedelta(), end)
        doc = _get(key, {
            "documentType": "A44", "in_Domain": area, "out_Domain": area,
            "periodStart": _fmt(chunk_start), "periodEnd": _fmt(chunk_end),
        })
        rows.extend(_parse_price_rows(doc.get("Publication_MarketDocument", {})))
        chunk_start = chunk_end
    if not rows:
        return pd.DataFrame(columns=["timestamp", "price_eur_mwh"])

    df = pd.DataFrame(rows, columns=["timestamp", "price_eur_mwh", "res_min"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    hourly = (
        df[df["res_min"] == 60]
        .drop_duplicates(subset="timestamp", keep="first")
        .set_index("timestamp")["price_eur_mwh"]
    )
    sub = (
        df[df["res_min"] < 60]
        .set_index("timestamp")["price_eur_mwh"]
        .resample("h").mean().dropna()
    )
    combined = hourly.combine_first(sub).sort_index()
    return combined.rename("price_eur_mwh").reset_index()


def fetch_day_ahead_price(start: date, end: date) -> pd.DataFrame:
    """Hourly realized Swiss day-ahead price; kept as the name data/ingest.py uses."""
    return fetch_price(start, end, zone="CH")


def fetch_load_forecast(start: date, end: date, zone: str) -> pd.DataFrame:
    """Hourly day-ahead TOTAL LOAD FORECAST (A65/A01) as the TSO published it,
    columns: timestamp, load_forecast_mw. This is the forecast that existed
    BEFORE the day-ahead auction for that delivery day cleared, which makes it
    a legitimate (leakage-free) input for a price model."""
    key = os.environ["ENTSOE_API_KEY"]
    return _fetch_series(
        key, {"documentType": "A65", "processType": "A01", "outBiddingZone_Domain": ZONES[zone]},
        "load_forecast_mw", start, end,
    )


def fetch_wind_solar_forecast(start: date, end: date, zone: str) -> pd.DataFrame:
    """Hourly day-ahead wind+solar generation forecast (A69/A01) summed across
    solar (B16), wind offshore (B18) and wind onshore (B19), columns:
    timestamp, wind_solar_forecast_mw. Published before the auction, so
    leakage-free for a price model; the dominant fundamental for DE-LU."""
    key = os.environ["ENTSOE_API_KEY"]
    area = ZONES[zone]
    parts = []
    for psr in ("B16", "B18", "B19"):
        p = _fetch_series(
            key, {"documentType": "A69", "processType": "A01", "in_Domain": area, "psrType": psr},
            f"fc_{psr}", start, end,
        )
        if not p.empty:
            parts.append(p.set_index("timestamp"))
    if not parts:
        return pd.DataFrame(columns=["timestamp", "wind_solar_forecast_mw"])
    merged = pd.concat(parts, axis=1)
    merged["wind_solar_forecast_mw"] = merged.sum(axis=1, min_count=1)
    return merged["wind_solar_forecast_mw"].dropna().reset_index()


def fetch_reservoir_level(start: date, end: date) -> pd.DataFrame:
    """Weekly Swiss hydro reservoir filling (A72), columns: week_start (UTC),
    filling_mwh. Weekly resolution as published; NOT resampled to hourly here,
    since the consumer must decide how to lag it to stay leakage-free."""
    key = os.environ["ENTSOE_API_KEY"]
    rows = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + pd.Timedelta(days=360).to_pytimedelta(), end)
        doc = _get(key, {
            "documentType": "A72", "processType": "A16", "in_Domain": _AREA,
            "periodStart": _fmt(chunk_start), "periodEnd": _fmt(chunk_end),
        })
        rows.extend(_parse_timeseries(doc.get("GL_MarketDocument", {})))
        chunk_start = chunk_end
    if not rows:
        return pd.DataFrame(columns=["week_start", "filling_mwh"])
    df = pd.DataFrame(rows, columns=["week_start", "filling_mwh"])
    df["week_start"] = pd.to_datetime(df["week_start"], utc=True)
    return df.drop_duplicates(subset="week_start").sort_values("week_start").reset_index(drop=True)
