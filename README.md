# Alpine Grid Pulse

A 48-hour Swiss electricity demand forecast, checked against a real baseline, with a typical-price
outlook fit on real historical prices. Demand is the headline output; everything else exists to
answer two questions: is the forecast actually better than guessing, and does it have anything to do
with what the market pays.

## Data

- Demand, solar, wind, hydro, nuclear, and day-ahead price all come from the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/) (`data/entsoe.py`), keyed by `ENTSOE_API_KEY`. Hydro combines run-of-river and reservoir generation (psrType `B12`/`B11`); pumped storage (`B10`) is excluded because ENTSO-E only reports its generation leg, not the pumping leg, which would double-count energy.
- Weather (temperature, solar radiation, wind speed, cloud cover) comes from Open-Meteo, historical for training/backtesting, forecast for live predictions.

## How the model works

One LightGBM model per target (`demand_mw`, `solar_mw`, `wind_mw`) per forecast horizon (1-48h ahead), using lagged actuals, rolling stats, calendar features (hour, weekday, month, Swiss public holidays), and weather at the target hour. Split-conformal calibration (MAPIE) wraps each model so the forecast band has an empirical coverage guarantee rather than being an arbitrary quantile. `models/export.py` also writes out each target's top LightGBM gain-based feature importances, shown on the dashboard, a checkable answer to "why did the model predict that."

## Is it actually better than guessing?

The backtest compares the model's 24h-ahead demand forecast against a **seasonal-naive** baseline (same hour, one week earlier) over a rolling 14-day replay, the fair bar for data with strong weekly seasonality, not the much weaker 24h-persistence baseline (also reported for transparency, but not the headline). Both live in `frontend/public/backtest.json` and on the dashboard.

## Signal exploration: does a new signal actually help?

Weather and a legal-holiday flag are the obvious signals; the real test is whether a less obvious one
holds up. `scripts/experiment_bridge_day.py` is a committed, runnable experiment testing one:
**bridge days**, working days squeezed between a public holiday and the weekend (the Friday after a
Thursday holiday, the Monday before a Tuesday one), which the existing holiday flag doesn't catch.

- **The raw pattern is real and large.** Across 6 years of real ENTSO-E demand, daytime demand on
  bridge days runs about 12% below an ordinary Monday or Friday.
- **It didn't survive rigorous testing.** Only 11 bridge days exist in the whole dataset, too few
  for a tree model to learn a reliable split from. Retraining with the feature added made held-out
  accuracy *on bridge-day hours specifically* worse, not better, and the trained model ranks the
  feature near the bottom of its own importance list.
- **Not shipped.** `features/engineer.py` keeps `is_bridge_day()` for the experiment script to import,
  but excludes it from the production feature set. A real pattern that a model can't yet learn from
  reliably is not the same as a useful feature, and shipping it anyway would have been the wrong call.

Run it yourself: `pixi run python -m scripts.experiment_bridge_day`

## Does any of this correlate with price?

`models/price_model.py` fits a plain linear regression of the realized Swiss day-ahead price on the demand-minus-domestic-generation gap, plus hour-of-day and weekend controls, refit on the **trailing 12 months only** (`scripts/fit_price_model.py`). Fitting across the full 6-year history dilutes the result with 2021-2022, when the European gas-price shock decoupled Swiss prices from domestic demand almost entirely (full-history r² ≈ 0.05 vs trailing-12-month r² ≈ 0.30). This is deliberately not a price forecaster: day-ahead prices are already a market-clearing outcome published a day ahead, so "forecasting" the same window doesn't make sense as a target. What it produces instead is a typical-price estimate per forecast hour, shown on the dashboard, plus the honest r² of how much of real price movement that estimate actually explains.

## What it includes

- a Python pipeline: ingest → feature engineering → train → conformal calibration → MLflow registry (gated promotion, only promotes if it beats the current champion) → export to plain LightGBM boosters + feature importances for serving
- a signal-exploration experiment with a documented negative result (`scripts/experiment_bridge_day.py`)
- a linear price-sensitivity fit on a trailing 12-month window, refit alongside every retrain (`scripts/fit_price_model.py`)
- a Vercel Python function (`api/main.py`) serving `/api/forecast` and `/api/health` from the exported artifacts, no live model inference per request
- a React dashboard: demand forecast, backtest vs. seasonal-naive baseline, price outlook, feature importances
- daily ingest + weekly retrain GitHub Actions, with a coverage-drift check that fails the retrain job if the live model's rolling interval coverage drops below 80%

The pipeline also computes a broader domestic-generation balance (demand minus solar, wind, hydro,
and nuclear) and precomputed scenario reruns (cold snap, holiday, low wind, low solar, each a real
rerun of the trained model with one input perturbed, not a rescaled output). Both are real, tested,
and available in the backtest/forecast JSON, but not part of the shipped dashboard; they were cut in
favor of a narrower, more defensible product surface.

## Setup

```bash
# 1. Install Python dependencies
pixi install

# 2. Install frontend dependencies
cd frontend && npm install

# 3. Backfill history (respects ENTSO-E's 400 requests/day limit)
pixi run python -m data.ingest --start 2020-01-01 --end $(date +%F)

# 4. Train, promote, export, fit the price model, and refresh the served JSON in one shot
pixi run python -m scripts.retrain_pipeline

# 5. Run the frontend
cd frontend && npm run dev
```

Run the first four commands from the repo root. For offline/local training without DagsHub credentials, point MLflow at a local store instead of the DagsHub URL in `.env`, e.g. `MLFLOW_TRACKING_URI=sqlite:///.mlflow_local.db pixi run python -m scripts.retrain_pipeline`.

## Deployment

The app is deployed on Vercel.

- The frontend build comes from `frontend`, copied into `api/site` at build time (see `vercel.json`).
- `api/main.py` serves `/api/forecast` and `/api/health` from `api/forecast.json`, and serves the built frontend for everything else.
- The dashboard calls `/api/forecast` first and falls back to the committed `frontend/public/forecast.json` if the API is unavailable.
- `scripts/static_forecast.py` writes both `frontend/public/forecast.json` and `api/forecast.json` on every refresh so the two never drift apart.

## Tests

```bash
pixi run pytest
```

## Notes

- Timestamps are shown in UTC.
- The forecast range is calibrated against holdout coverage, not a dispatch guarantee.
- Docker is not required for the normal local setup; `docker-compose.yml` is only for running a local MLflow server if you want one.
