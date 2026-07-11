"""PostgreSQL schema creation, upsert, and query."""
import os
import psycopg2
import psycopg2.extras
import pandas as pd
from contextlib import contextmanager

_DDL = """
CREATE TABLE IF NOT EXISTS energy_hourly (
    timestamp       TIMESTAMPTZ PRIMARY KEY,
    demand_mw       FLOAT,
    solar_mw        FLOAT,
    wind_mw         FLOAT,
    hydro_mw        FLOAT,
    nuclear_mw      FLOAT,
    price_eur_mwh   FLOAT,
    temperature     FLOAT,
    solar_radiation FLOAT,
    wind_speed      FLOAT,
    cloud_cover     FLOAT
);
ALTER TABLE energy_hourly ADD COLUMN IF NOT EXISTS hydro_mw FLOAT;
ALTER TABLE energy_hourly ADD COLUMN IF NOT EXISTS nuclear_mw FLOAT;
ALTER TABLE energy_hourly ADD COLUMN IF NOT EXISTS price_eur_mwh FLOAT;

CREATE TABLE IF NOT EXISTS market_hourly (
    timestamp              TIMESTAMPTZ NOT NULL,
    zone                   TEXT NOT NULL,
    price_eur_mwh          FLOAT,
    load_forecast_mw       FLOAT,
    wind_solar_forecast_mw FLOAT,
    PRIMARY KEY (timestamp, zone)
);

CREATE TABLE IF NOT EXISTS reservoir_weekly (
    week_start  TIMESTAMPTZ PRIMARY KEY,
    filling_mwh FLOAT
);
"""

_COLS = ["timestamp", "demand_mw", "solar_mw", "wind_mw", "hydro_mw", "nuclear_mw", "price_eur_mwh",
         "temperature", "solar_radiation", "wind_speed", "cloud_cover"]


@contextmanager
def _conn():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def create_schema() -> None:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(_DDL)


_UPDATE_COLS = [c for c in _COLS if c != "timestamp"]


def upsert(df: pd.DataFrame) -> int:
    """Insert rows, updating on timestamp conflict. Returns row count."""
    df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
    for col in _COLS:
        if col not in df.columns:
            df[col] = None
    rows = [tuple(row) for row in df[_COLS].itertuples(index=False, name=None)]
    sql = f"""
        INSERT INTO energy_hourly ({', '.join(_COLS)})
        VALUES %s
        ON CONFLICT (timestamp) DO UPDATE SET
            {', '.join(f'{c} = EXCLUDED.{c}' for c in _UPDATE_COLS)}
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, sql, rows)
    return len(rows)


def query(start=None, end=None) -> pd.DataFrame:
    """Fetch rows in [start, end]. Either bound can be None."""
    clauses, params = [], []
    if start is not None:
        clauses.append("timestamp >= %s")
        params.append(start)
    if end is not None:
        clauses.append("timestamp <= %s")
        params.append(end)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT {', '.join(_COLS)} FROM energy_hourly {where} ORDER BY timestamp"
    with _conn() as conn:
        df = pd.read_sql(sql, conn, params=params or None, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


_MARKET_VALUE_COLS = ["price_eur_mwh", "load_forecast_mw", "wind_solar_forecast_mw"]


def upsert_market(df: pd.DataFrame, zone: str) -> int:
    """Upsert one zone's market series. Different series arrive from separate
    API calls, so a NULL in the incoming frame must never wipe a value already
    stored for that (timestamp, zone): each column COALESCEs with the existing
    row instead of overwriting it."""
    df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last").copy()
    for col in _MARKET_VALUE_COLS:
        if col not in df.columns:
            df[col] = None
    df["zone"] = zone
    cols = ["timestamp", "zone"] + _MARKET_VALUE_COLS
    df = df.astype(object).where(pd.notna(df), None)
    rows = [tuple(row) for row in df[cols].itertuples(index=False, name=None)]
    sql = f"""
        INSERT INTO market_hourly ({', '.join(cols)})
        VALUES %s
        ON CONFLICT (timestamp, zone) DO UPDATE SET
            {', '.join(f'{c} = COALESCE(EXCLUDED.{c}, market_hourly.{c})' for c in _MARKET_VALUE_COLS)}
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, sql, rows)
    return len(rows)


def query_market(start=None, end=None) -> pd.DataFrame:
    """All zones' market rows in [start, end], long format (one row per timestamp+zone)."""
    clauses, params = [], []
    if start is not None:
        clauses.append("timestamp >= %s")
        params.append(start)
    if end is not None:
        clauses.append("timestamp <= %s")
        params.append(end)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT timestamp, zone, {', '.join(_MARKET_VALUE_COLS)} FROM market_hourly {where} ORDER BY timestamp"
    with _conn() as conn:
        df = pd.read_sql(sql, conn, params=params or None, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def upsert_reservoir(df: pd.DataFrame) -> int:
    rows = [tuple(row) for row in df[["week_start", "filling_mwh"]].itertuples(index=False, name=None)]
    sql = """
        INSERT INTO reservoir_weekly (week_start, filling_mwh)
        VALUES %s
        ON CONFLICT (week_start) DO UPDATE SET filling_mwh = EXCLUDED.filling_mwh
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(cur, sql, rows)
    return len(rows)


def query_reservoir() -> pd.DataFrame:
    with _conn() as conn:
        df = pd.read_sql("SELECT week_start, filling_mwh FROM reservoir_weekly ORDER BY week_start",
                         conn, parse_dates=["week_start"])
    df["week_start"] = pd.to_datetime(df["week_start"], utc=True)
    return df
