"""
Backfill the market_hourly and reservoir_weekly tables from ENTSO-E:
day-ahead prices for CH + DE-LU + FR + IT-North, the day-ahead LOAD FORECASTS
for those zones (the forecast that existed before each auction cleared, so
it's a legitimate model input), the DE-LU wind+solar day-ahead forecast (the
dominant price fundamental in the region), and weekly Swiss reservoir levels.

Rate budget: ~2 requests per zone-series-year, well under ENTSO-E's 400/day.

Run:
    python -m scripts.backfill_market                      # full 2020 -> today
    python -m scripts.backfill_market --start 2026-07-01   # incremental top-up
"""
import argparse
from datetime import date, timedelta

from dotenv import load_dotenv
load_dotenv()

from data.entsoe import ZONES, fetch_price, fetch_load_forecast, fetch_wind_solar_forecast, fetch_reservoir_level
from storage.db import create_schema, upsert_market, upsert_reservoir


def backfill(start: date, end: date) -> None:
    create_schema()

    for zone in ZONES:
        print(f"[market] {zone}: day-ahead price {start} -> {end}")
        price = fetch_price(start, end, zone=zone)
        if not price.empty:
            n = upsert_market(price, zone)
            print(f"[market] {zone}: upserted {n} price rows")

        print(f"[market] {zone}: day-ahead load forecast {start} -> {end}")
        loadfc = fetch_load_forecast(start, end, zone)
        if not loadfc.empty:
            n = upsert_market(loadfc, zone)
            print(f"[market] {zone}: upserted {n} load-forecast rows")

    print(f"[market] DE_LU: wind+solar day-ahead forecast {start} -> {end}")
    wsfc = fetch_wind_solar_forecast(start, end, "DE_LU")
    if not wsfc.empty:
        n = upsert_market(wsfc, "DE_LU")
        print(f"[market] DE_LU: upserted {n} wind+solar forecast rows")

    print(f"[market] CH: weekly reservoir levels {start} -> {end}")
    res = fetch_reservoir_level(start, end)
    if not res.empty:
        n = upsert_reservoir(res)
        print(f"[market] CH: upserted {n} reservoir weeks")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=date.fromisoformat, default=date(2020, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date.today() + timedelta(days=2))
    parser.add_argument("--days", type=int, default=None,
                        help="shortcut: only refresh the trailing N days (for the daily cron)")
    args = parser.parse_args()
    start = date.today() - timedelta(days=args.days) if args.days else args.start
    backfill(start, args.end)


if __name__ == "__main__":
    main()
