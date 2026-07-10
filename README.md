# Alpine Grid Pulse

Alpine Grid Pulse is a Swiss power-demand forecasting dashboard. It predicts the next 48 hours of load, shows how much supply pressure remains after solar and wind, and lets you stress the forecast with market-style scenarios.

Weather is part of the model. Historical weather is used for training and backtesting, and forecast weather is used for live predictions.

## What it does

The current version is a demand-first forecasting app, not just a data script. It includes:

- a Python pipeline that ingests data, trains models, and exports artifacts
- a FastAPI `/forecast` endpoint for live predictions
- a React dashboard that reads forecast and backtest JSON files
- daily ingest and weekly retrain automation

## Data used

- Demand data comes from ENTSO-E when `ENTSOE_API_KEY` is available.
- Swissgrid is kept as a fallback for demand-only historical ingestion.
- Solar and wind are modeled separately as support signals.
- Weather comes from Open-Meteo.

## How the model works

For each target hour, the model predicts demand, solar, and wind, then computes:

`supply_gap = demand - (solar + wind)`

The dashboard shows a point forecast plus a forecast range around it. The range is used to classify each hour as:

- confirmed surplus
- possible surplus
- deficit

This is an empirical coverage method, not a guarantee.

## Workflow

1. Daily ingest updates the database with the latest energy and weather data.
2. Weekly retrain fits models, promotes the best runs, exports artifacts, and refreshes the frontend JSON snapshots.
3. Vercel serves the built React app and the forecast endpoint.

## Setup

```bash
# 1. Install Python dependencies
pixi install

# 2. Install frontend dependencies
cd frontend && npm install

# 3. Optional: backfill history
pixi run python -m data.ingest --start 2020-01-01 --end $(date +%F)

# 4. Train and export artifacts
pixi run python -m models.train
pixi run python -m models.registry
pixi run python -m scripts.retrain_pipeline

# 5. Run the frontend
cd frontend && npm run dev
```

Run the first two commands from the repo root, then start the frontend from `frontend/`.

To use ENTSO-E instead of Swissgrid, set `ENTSOE_API_KEY` and leave `DATA_SOURCE` unset or set it to `entsoe`.

## Deployment

The app is deployed on Vercel.

- The frontend build comes from `frontend`.
- The API and static frontend assets are served through `api/main.py`.
- The dashboard first calls `/api/forecast` and falls back to the committed `frontend/public/forecast.json` if the API is unavailable.

## Tests

```bash
pixi run pytest
```

## Notes

- Timestamps are shown in UTC.
- Swissgrid data currently stops at the latest published workbook date, which can lag behind today.
- The forecast range is meant to be checked against holdout coverage, not treated as a dispatch promise.
- Docker is not required for the normal local setup.
