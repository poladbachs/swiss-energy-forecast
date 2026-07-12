# Alpine Power Pulse | https://swisspowerforecast.vercel.app

A day-ahead electricity price forecast for the Swiss bidding zone, built only on information that
exists before each auction clears, and evaluated the way a trading desk would evaluate it: a
24-month walk-forward replay against the strongest simple baseline.

**Result: 11.4 vs. 16.8 EUR/MWh MAE against yesterday's-price naive (-32% error) across 17,137
out-of-sample hours, beating the baseline in 23 of 24 months, with a 72.9% directional hit rate.**

## Why the information set is the whole game

All European day-ahead auctions clear simultaneously (~12:45 CET for next-day delivery), so
tomorrow's German price cannot be used to predict tomorrow's Swiss price: it doesn't exist yet.
A model fed same-hour neighbor prices backtests spectacularly and is completely fake. This model
uses only what is really available pre-auction:

- **Cleared prices through today** for CH, DE-LU, FR and IT-North (entering only with a lag of
  24 hours or more)
- **The TSOs' own day-ahead load forecasts** for all four zones (published before the auction)
- **The German wind+solar day-ahead forecast**, the dominant price fundamental in the region
- **Weekly Swiss hydro reservoir levels**, lagged a full week to cover the publication delay
- The calendar (hour, weekday, month, Swiss holidays)

All data from the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/), the EU's
official market-data source. `tests/test_price_forecast.py` contains leakage tripwires: sentinel
prices planted at hour t must never appear in hour t's own features, and must surface exactly 24
hours later. If a refactor ever breaks the discipline, the suite fails.

## How it's evaluated

`scripts/walkforward_price.py` replays the last 24 months one month at a time; each fold trains
only on data strictly before that month, then predicts the whole month out-of-sample. The
2021-2022 gas-crisis regime stays in the training data on purpose: the model has to learn through
the break, not have it curated away. The baseline is yesterday's price at the same hour, which is
genuinely hard to beat in this market. Per-fold results, including the four months the model lost,
are in `models/artifacts/price_walkforward.json` and on the dashboard.

The dashboard also replays the latest cleared auction blind after every auction: a model trained
only on data before that delivery day, next to what actually cleared. The forecast band is the
middle 80% of real out-of-sample errors from the walk-forward, not a distributional assumption.

## Supporting models and experiments

- **Swiss demand forecast, 48h ahead** (LightGBM + weather + calendar, split-conformal calibrated
  bands), backtested against a seasonal-naive baseline. Demand is one of the price model's core
  fundamentals, so it earns its place on the page.
- **A signal experiment with a documented negative result** (`scripts/experiment_bridge_day.py`):
  bridge days (the working day between a holiday and the weekend) show ~12% lower demand in 6
  years of raw data, but with only 11 occurrences the model couldn't learn a reliable split;
  adding the feature made held-out accuracy on those hours worse, so it was tested and not
  shipped. Rejecting your own hypothesis with numbers is part of the job.

## What it includes

- ENTSO-E ingestion for 4 bidding zones (prices, pre-auction load forecasts, renewables
  forecasts, reservoir levels) + Swiss demand/generation + Open-Meteo weather, into PostgreSQL
- the leakage-safe price feature builder and LightGBM model (`models/price_forecast.py`)
- the 24-month walk-forward evaluation (`scripts/walkforward_price.py`)
- a daily-refreshing artifact: latest auction replayed blind + next-auction forecast when the
  pre-auction window is open (`scripts/static_price_forecast.py`)
- the demand pipeline: train → split-conformal calibration → MLflow registry with gated
  promotion → export to plain boosters
- a React dashboard (price model first, demand as the supporting act)
- GitHub Actions: daily ingest + artifact refresh, weekly retrain + walk-forward, with a
  coverage-drift check that fails the job if the demand model degrades

## Setup

```bash
pixi install                       # Python deps
cd frontend && npm install         # frontend deps

# Backfill (respects ENTSO-E's 400 requests/day limit)
pixi run python -m data.ingest --start 2020-01-01 --end $(date +%F)
pixi run python -m scripts.backfill_market

# Evaluate + generate artifacts
pixi run python -m scripts.walkforward_price
pixi run python -m scripts.static_price_forecast

# Full weekly pipeline in one shot (demand retrain + price walk-forward + artifacts)
pixi run python -m scripts.retrain_pipeline

# Run the dashboard
cd frontend && npm run dev
```

For offline/local training without DagsHub credentials, point MLflow at a local store, e.g.
`MLFLOW_TRACKING_URI=sqlite:///.mlflow_local.db pixi run python -m scripts.retrain_pipeline`.

## Tests

```bash
pixi run pytest
```

43 tests, including the price-model leakage tripwires, demand feature-builder correctness
(calendar/weather at target time, lags at base time, gap handling), conformal calibration, the
export bridge, and the pipeline wiring.

## Notes

- Timestamps are UTC throughout.
- Deployed on Vercel: `api/main.py` serves the built frontend and the demand API from committed
  artifacts; CI refreshes the price artifact daily after each auction.
- Docker is only needed if you want a local MLflow server (`docker-compose.yml`).
