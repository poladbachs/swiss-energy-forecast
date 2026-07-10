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
