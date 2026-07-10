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
from data.entsoe import fetch_energy, fetch_day_ahead_price


def ingest(start: date, end: date) -> None:
    if not os.environ.get("ENTSOE_API_KEY"):
        raise RuntimeError("ENTSOE_API_KEY is required")

    create_schema()

    print(f"[ingest] energy source=entsoe  {start} → {end}")
    energy = fetch_energy(start, end)

    print(f"[ingest] day-ahead price  {start} → {end}")
    price = fetch_day_ahead_price(start, end)

    print(f"[ingest] weather  {start} → {end}")
    weather = fetch_historical(start, end)

    # Left-joined onto energy/weather (inner) so a temporary price-feed gap
    # never drops otherwise-good demand/weather rows.
    df = energy.merge(weather, on="timestamp", how="inner").merge(price, on="timestamp", how="left")
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
