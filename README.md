# Swiss Energy Forecast

48-hour forecasts of Swiss electricity demand, solar and wind production, with
conformal prediction intervals instead of the usual uncalibrated error bands. The
dashboard shows which hours renewables provably cover demand and lets you drag
sliders to see what 2x solar or 3x wind capacity would change.

## Why conformal prediction

Quantile regression can output an interval labelled "90%", but nothing forces the
true coverage to be 90%. It might be 70%. You only find out after the fact.

Split conformal calibration works differently. The model's residuals on a held-out
calibration set determine the interval width, and if the calibration data is
exchangeable with future data, at least 90% of future observations land inside the
bounds. That holds no matter how badly the underlying model is calibrated, which is
the property you actually want when someone plans around your forecast.

## Coverage classification

For each hour the supply gap is demand minus (solar + wind). The bounds are built
pessimistically:

```
gap_lower = demand_lower - (solar_upper + wind_upper)   # best case for the grid
gap_upper = demand_upper - (solar_lower + wind_lower)   # worst case for the grid
```

| Status | Condition | Meaning |
|---|---|---|
| confirmed_surplus | `gap_upper < 0` | renewables beat demand even in the worst case |
| possible_surplus | `gap_point < 0` | likely surplus, but the interval straddles zero |
| deficit | `gap_point >= 0` | demand exceeds renewables |

The counterfactual sliders scale the solar and wind forecasts and their bounds
before the gap is recomputed, so the classification stays honest under
counterfactuals.

## Architecture

```
ENTSO-E Transparency API (demand A65, solar/wind actuals A75)
Open-Meteo API (temperature, radiation, wind speed, cloud cover)
    |
PostgreSQL: energy_hourly, hourly since 2020 (~57k rows)
    |
Feature engineering: lags at base time t, calendar + weather at target time t+h
    |
LightGBM x3 (one model per target, all 48 horizons via an hours_ahead feature)
    |  MLflow tracking, Optuna tuning, champion alias promotion
MAPIE split conformal calibration (90%, calibrated across all horizons)
    |
FastAPI /forecast: intervals, supply gaps, coverage status, multipliers
    |
React + Vite + Tailwind + Recharts
```

## Run locally

```bash
# 1. Services. MLflow is on host port 5001 because macOS AirPlay sits on 5000.
docker compose up -d

# 2. Environment
cp .env.example .env       # add your ENTSOE_API_KEY, set DATA_SOURCE=entsoe
pixi install

# 3. Backfill history (energy + weather, 2020 to today)
pixi run python -m data.ingest --start 2020-01-01 --end $(date +%F)

# 4. Train, calibrate, promote
pixi run python -m models.train
pixi run python -m models.registry

# optional hyperparameter search, one target at a time
pixi run python -m models.tune --target demand_mw --trials 50

# 5. API
pixi run uvicorn api.main:app --reload --port 8000

# 6. Frontend
cd frontend && npm install && npm run dev   # http://localhost:5173
```

MLflow UI: http://localhost:5001. One experiment (`swiss-energy-forecast`), runs
tagged by target, best val_rmse per target promoted to the `champion` alias.

## Tests

```bash
pixi run pytest
```

The tests cover the training/inference feature-time alignment (calendar and weather
features must describe the target hour t+h, not the base hour t), interval validity,
empirical coverage of at least 85% on held-out data, and the API contract: gap
formula, status consistency, multiplier scaling.

## Data sources

- [ENTSO-E Transparency Platform](https://transparency.entsoe.eu): demand (`A65`)
  and actual generation per type (`A75`, solar `B16`, wind onshore `B19`) for
  bidding zone `10YCH-SWISSGRIDZ`. Free API key required. The API omits
  zero-generation points (solar at night); the client fills them as 0.
- [Swissgrid energy statistics](https://www.swissgrid.ch): keyless XLSX fallback,
  `DATA_SOURCE=swissgrid`.
- [Open-Meteo](https://open-meteo.com): historical and forecast weather, no key.

## Limitations

- The deployed dashboard is static: CI refreshes `forecast.json` and
  `backtest.json`, then Vercel serves the built React app.
- Timestamps are shown in UTC. Backtest points are the observed hours; each
  forecast was made `horizon_h` hours earlier.
- ENTSO-E and Swissgrid data can arrive late or be revised after publication.
- Open-Meteo historical weather lags by a few days, so the backtest window avoids
  the most recent incomplete archive period.
- The 90% conformal interval is an empirical coverage target, not an operational
  dispatch guarantee.
