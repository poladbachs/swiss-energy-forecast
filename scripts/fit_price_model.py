"""
Fit the linear price-sensitivity model (models/price_model.py) against real
ENTSO-E day-ahead prices and the historical import gap, and save its
coefficients + validation stats for static_forecast.py / static_backtest.py.

Fit window is the trailing 365 days, not full history. Fitting across all 6
years dilutes the fit with 2021-2022, when European gas prices spiked and
decoupled Swiss prices from domestic demand/supply almost entirely (r^2 on
full history is ~0.05; on the trailing year it's ~0.30). That's a real
structural break, not noise, so training through it gives a number that's
technically "more data" but less representative of how the market behaves now.

Run:
    python -m scripts.fit_price_model
"""
import json
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
load_dotenv()

from models.price_model import fit
from storage.db import query as db_query

OUT = Path(__file__).resolve().parent.parent / "models" / "artifacts" / "price_sensitivity.json"
TRAILING_DAYS = 365


def main() -> None:
    df = db_query()
    df = df.dropna(subset=["price_eur_mwh", "demand_mw", "solar_mw", "wind_mw", "hydro_mw", "nuclear_mw"]).copy()
    if df.empty:
        raise ValueError("No rows with price + full generation mix available to fit the price model")

    cutoff = df["timestamp"].max() - pd.Timedelta(days=TRAILING_DAYS)
    df = df[df["timestamp"] >= cutoff]

    df["import_gap"] = df["demand_mw"] - (df["solar_mw"] + df["wind_mw"] + df["hydro_mw"] + df["nuclear_mw"])
    coeffs = fit(df)
    coeffs["fit_window_days"] = TRAILING_DAYS

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(coeffs, indent=2))
    print(
        f"[price-model] fit on trailing {TRAILING_DAYS}d, {coeffs['n_obs']} hours, r2={coeffs['r2']:.3f}, "
        f"slope={coeffs['slope_eur_per_100mw']:.2f} EUR/MWh per 100MW import gap"
    )


if __name__ == "__main__":
    main()
