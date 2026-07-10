"""
Price-sensitivity model: a plain linear regression of the realized Swiss
day-ahead price on the import gap (demand minus domestic generation), with
hour-of-day and weekend controls.

This is deliberately not a day-ahead price forecaster. Day-ahead prices are
already a market-clearing outcome published a day ahead of delivery, so
"forecasting" them for the same window our demand model covers isn't a
sensible target. What this *does* do is answer a concrete, checkable question:
does the import-gap signal this project already computes actually correlate
with what the market paid? The coefficient on import_gap is the empirical
answer, in EUR/MWh per 100MW, along with the R^2 of the whole fit.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

FEATURE_COLS = ["import_gap", "hour_sin", "hour_cos", "is_weekend"]


def _features(df: pd.DataFrame) -> pd.DataFrame:
    hour = df["timestamp"].dt.hour
    return pd.DataFrame({
        "import_gap": df["import_gap"].values,
        "hour_sin": np.sin(2 * np.pi * hour / 24).values,
        "hour_cos": np.cos(2 * np.pi * hour / 24).values,
        "is_weekend": df["timestamp"].dt.dayofweek.isin([5, 6]).astype(int).values,
    })


def fit(df: pd.DataFrame) -> dict:
    """df must have columns timestamp, import_gap, price_eur_mwh (already dropna'd by the caller)."""
    X = _features(df)
    y = df["price_eur_mwh"].values
    model = LinearRegression().fit(X, y)
    return {
        "intercept": float(model.intercept_),
        "coef_import_gap": float(model.coef_[0]),
        "coef_hour_sin": float(model.coef_[1]),
        "coef_hour_cos": float(model.coef_[2]),
        "coef_is_weekend": float(model.coef_[3]),
        "r2": float(model.score(X, y)),
        "slope_eur_per_100mw": float(model.coef_[0]) * 100,
        "n_obs": int(len(df)),
    }


def predict(coeffs: dict, import_gap, timestamps) -> np.ndarray:
    """Vectorized price estimate for arbitrary (import_gap, timestamp) pairs."""
    ts = pd.DatetimeIndex(timestamps)
    hour = ts.hour.to_numpy()
    is_weekend = np.isin(ts.dayofweek.to_numpy(), [5, 6]).astype(int)
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)
    gap = np.asarray(import_gap, dtype=float)
    return (
        coeffs["intercept"]
        + coeffs["coef_import_gap"] * gap
        + coeffs["coef_hour_sin"] * hour_sin
        + coeffs["coef_hour_cos"] * hour_cos
        + coeffs["coef_is_weekend"] * is_weekend
    )
