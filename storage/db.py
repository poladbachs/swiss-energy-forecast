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
    temperature     FLOAT,
    solar_radiation FLOAT,
    wind_speed      FLOAT,
    cloud_cover     FLOAT
);
"""

_COLS = ["timestamp", "demand_mw", "solar_mw", "wind_mw",
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


def upsert(df: pd.DataFrame) -> int:
    """Insert rows, updating on timestamp conflict. Returns row count."""
    rows = [tuple(row) for row in df[_COLS].itertuples(index=False, name=None)]
    sql = """
        INSERT INTO energy_hourly
            (timestamp, demand_mw, solar_mw, wind_mw, temperature, solar_radiation, wind_speed, cloud_cover)
        VALUES %s
        ON CONFLICT (timestamp) DO UPDATE SET
            demand_mw       = EXCLUDED.demand_mw,
            solar_mw        = EXCLUDED.solar_mw,
            wind_mw         = EXCLUDED.wind_mw,
            temperature     = EXCLUDED.temperature,
            solar_radiation = EXCLUDED.solar_radiation,
            wind_speed      = EXCLUDED.wind_speed,
            cloud_cover     = EXCLUDED.cloud_cover
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
        return pd.read_sql(sql, conn, params=params or None, parse_dates=["timestamp"])
