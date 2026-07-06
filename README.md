# Swiss Energy Forecast

This project forecasts Swiss electricity demand, solar, and wind for the next 48 hours. It also shows a supply gap for each hour and marks whether renewables are enough to cover demand.

The forecast uses weather. Historical weather is part of training and backtesting, and forecast weather is used for the live prediction path.

## What it is

The current version is a forecast app, not just a data ingestion script. It has:

- a Python pipeline that ingests data, trains models, and exports artifacts
- a FastAPI `/forecast` endpoint for live predictions
- a React dashboard that reads static JSON files from `frontend/public`
- daily ingest and weekly retrain automation

## Data used

- Demand data comes from Swissgrid by default.
- If `DATA_SOURCE=entsoe` and `ENTSOE_API_KEY` is set, the ingest path can use ENTSO-E instead.
- Solar and wind are modeled separately.
- Weather comes from Open-Meteo.

## How the model works

For each target hour, the model predicts demand, solar, and wind, then computes:

`supply_gap = demand - (solar + wind)`

The dashboard shows a point forecast plus a conformal interval around it. The interval is used to classify each hour as:

- confirmed surplus
- possible surplus
- deficit

This is an empirical coverage method, not a guarantee.

## Current workflow

1. Daily ingest updates the database with recent energy and weather data.
2. Weekly retrain fits models, promotes the best runs, exports artifacts, and refreshes the frontend JSON files.
3. Vercel serves the built React app and the committed static artifacts.

## Local setup

```bash
docker compose up -d
pixi install
pixi run python -m data.ingest --start 2020-01-01 --end $(date +%F)
pixi run python -m models.train
pixi run python -m models.registry
pixi run python -m scripts.retrain_pipeline
cd frontend && npm install && npm run dev
```

## Tests

```bash
pixi run pytest
```

## Notes

- Timestamps are shown in UTC.
- The deployed dashboard is static.
- Swissgrid data currently ends at the latest published workbook date, which can lag behind today.
- The conformal interval is meant to be checked against holdout coverage, not treated as a dispatch promise.
