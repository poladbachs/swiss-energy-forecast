"""
Ingestion script: pull energy + weather data and upsert to PostgreSQL.

Usage:
    python -m data.ingest --start 2020-01-01 --end 2024-01-01   # historical backfill
    python -m data.ingest                                         # last 7 days (weekly cron)
"""
import os
import argparse
from datetime import date, timedelta

from dotenv import load_dotenv
load_dotenv()

from storage.db import create_schema, upsert
from data.weather import fetch_historical


def ingest(start: date, end: date) -> None:
    source = os.environ.get("DATA_SOURCE", "swissgrid")
    if source == "entsoe":
        from data.entsoe import fetch_energy
    else:
        from data.swissgrid import fetch_energy

    create_schema()

    print(f"[ingest] energy source={source}  {start} → {end}")
    energy = fetch_energy(start, end)

    print(f"[ingest] weather  {start} → {end}")
    weather = fetch_historical(start, end)

    df = energy.merge(weather, on="timestamp", how="inner")
    n = upsert(df)
    print(f"[ingest] upserted {n} rows")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat, default=date.today() - timedelta(days=7))
    parser.add_argument("--end",   type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    ingest(args.start, args.end)


if __name__ == "__main__":
    main()
