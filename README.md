# Alpine Grid Pulse

A Swiss power-market forecasting stack: it predicts the next 48 hours of electricity demand, tracks how much of that demand Switzerland's own generation (solar, wind, hydro, nuclear) can actually cover, and checks — honestly, with real numbers — whether that signal has anything to do with price.

Demand is the headline output. Everything else exists to answer one question: is the system tight or loose, and does that tightness show up anywhere that matters (price)?

## Data

- Demand, solar, wind, hydro, nuclear, and day-ahead price all come from the [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/) (`data/entsoe.py`), keyed by `ENTSOE_API_KEY`. Hydro combines run-of-river and reservoir generation (psrType `B12`/`B11`); pumped storage (`B10`) is excluded because ENTSO-E only reports its generation leg, not the pumping leg, which would double-count energy.
- Weather (temperature, solar radiation, wind speed, cloud cover) comes from Open-Meteo — historical for training/backtesting, forecast for live predictions.
- Switzerland's wind and solar fleets are small relative to demand, but hydro and nuclear cover most of the rest, so **import dependency** (demand minus all four) is usually a modest few hundred MW to low GW — not the near-permanent deficit you'd get from subtracting wind+solar alone. That's the real reason hydro/nuclear are in this calculation and not just a nice-to-have.

## How the model works

One LightGBM model per target (`demand_mw`, `solar_mw`, `wind_mw`) per forecast horizon (1–48h ahead), using lagged actuals, rolling stats, calendar features (hour, weekday, month, Swiss holidays), and weather at the target hour. Split-conformal calibration (MAPIE) wraps each model so the forecast band has an empirical coverage guarantee rather than being an arbitrary quantile.

Hydro and nuclear are **not** ML-forecasted for the forward-looking chart — nuclear is near-constant baseload and hydro dispatch isn't weather-driven the way solar/wind are, so a trailing same-hour average stands in for a trained model there. It's a point estimate, not conformal-calibrated, and the code says so where it matters (`scripts/static_forecast.py`).

```
import_gap = demand - (solar + wind + hydro + nuclear)
```

Each forecast hour is classified as `confirmed_surplus` / `possible_surplus` / `deficit` based on where the import-gap band sits relative to zero — surplus means CH generation covers demand (net exporter), deficit means it needs imports or storage.

## Scenarios: real model reruns, not sliders pretending to be a model

"Cold snap," "holiday," "low wind," and "low solar" perturb an actual input the trained model uses (temperature, the holiday calendar flag, wind speed, solar radiation) and rerun the real boosters. The result is whatever the model actually learned about that input — including surprises a hand-picked multiplier can't produce: in July, the cold-snap scenario *lowers* demand, because less cooling load beats more heating load in summer. A constant like "cold snap = demand × 1.15" would have gotten that backwards.

"Event shock" (e.g. a strike) and the raw sliders are the exception: there's no strike/outage feature in the model, so there's nothing to perturb. Those stay an explicit, labeled multiplier overlay — the frontend says so directly rather than dressing up a guess as a prediction.

## Is it actually better than guessing?

The backtest compares the model's 24h-ahead demand forecast against a **seasonal-naive** baseline (same hour, one week earlier) over a rolling 14-day replay — the fair bar for data with strong weekly seasonality, not the much weaker 24h-persistence baseline (also reported, for transparency, but not the headline). Both live in `frontend/public/backtest.json` and on the dashboard: does the model actually beat the dumbest reasonable baseline, by how much, and does its uncertainty band actually cover what happened.

## Does any of this correlate with price?

`models/price_model.py` fits a plain linear regression of the realized Swiss day-ahead price (also from ENTSO-E) on the import gap, plus hour-of-day and weekend controls. This is deliberately **not** a price forecaster — day-ahead prices are already a market-clearing outcome published a day ahead, so "forecasting" the same window doesn't make sense as a target. What it validates: does import dependency, the signal this whole project computes, actually track what the market paid.

The honest answer, from the real fit: **r² ≈ 0.05**. Import gap has a small, correctly-signed, statistically non-trivial relationship with price (+1.2 EUR/MWh per 100MW, on 57k hours), but it explains only ~5% of price variance. Swiss day-ahead prices are set mostly by the wider European market (Germany/France/Italy coupling), not by Switzerland's own balance alone. That's a real finding about how this market works, not a failure to hide — the dashboard states it plainly rather than dressing up a weak result.

## What drives the forecast

`models/export.py` writes out each target's top LightGBM gain-based feature importances (`frontend/public/feature_importance.json`), shown on the dashboard. For demand: recent load level (rolling 24h mean) dominates, followed by solar radiation (a proxy for daylight/season), hour-of-day, and day-of-week — a sanity-checkable answer to "why did the model predict that," not a black box.

## What it includes

- a Python pipeline: ingest → feature engineering → train → conformal calibration → MLflow registry (gated promotion, only promotes if it beats the current champion) → export to plain LightGBM boosters + feature importances for serving
- a linear price-sensitivity fit (`scripts/fit_price_model.py`), refit alongside every retrain
- a Vercel Python function (`api/main.py`) serving `/api/forecast` and `/api/health` from the exported artifacts, no live model inference per request
- a React dashboard: demand forecast, import-gap chart, a real-rerun scenario lab, backtest vs seasonal-naive, price validation, and feature importances
- daily ingest + weekly retrain GitHub Actions, with a coverage-drift check that fails the retrain job if the live model's rolling interval coverage drops below 80%

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
- The forecast range is calibrated against holdout coverage, not a dispatch guarantee. Hydro/nuclear estimates are a trailing average, explicitly not calibrated the same way.
- Docker is not required for the normal local setup; `docker-compose.yml` is only for running a local MLflow server if you want one.
