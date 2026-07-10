"""
Fit the linear price-sensitivity model (models/price_model.py) against real
ENTSO-E day-ahead prices and the historical import gap, and save its
coefficients + validation stats for static_forecast.py / static_backtest.py.

Run:
    python -m scripts.fit_price_model
"""
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from models.price_model import fit
from storage.db import query as db_query

OUT = Path(__file__).resolve().parent.parent / "models" / "artifacts" / "price_sensitivity.json"


def main() -> None:
    df = db_query()
    df = df.dropna(subset=["price_eur_mwh", "demand_mw", "solar_mw", "wind_mw", "hydro_mw", "nuclear_mw"]).copy()
    if df.empty:
        raise ValueError("No rows with price + full generation mix available to fit the price model")

    df["import_gap"] = df["demand_mw"] - (df["solar_mw"] + df["wind_mw"] + df["hydro_mw"] + df["nuclear_mw"])
    coeffs = fit(df)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(coeffs, indent=2))
    print(
        f"[price-model] fit on {coeffs['n_obs']} hours, r2={coeffs['r2']:.3f}, "
        f"slope={coeffs['slope_eur_per_100mw']:.2f} EUR/MWh per 100MW import gap"
    )


if __name__ == "__main__":
    main()
