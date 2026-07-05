"""Tests for models/export.py — MLflow registry -> static artifact bridge."""
import json
from unittest.mock import MagicMock, patch

import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest

from models.conformal import calibrate
from models.export import export_promoted, export_target
from models.train import train


def _small_df(n=600):
    rng = np.random.default_rng(0)
    idx = pd.date_range("2023-01-01", periods=n, freq="h", tz="UTC")
    hour = idx.hour.values
    return pd.DataFrame({
        "timestamp": idx,
        "demand_mw": 7000 + 1500 * np.sin(hour / 24 * 2 * np.pi) + rng.normal(0, 200, n),
        "solar_mw":  np.clip(1000 * np.sin(hour / 24 * 2 * np.pi), 0, None) + rng.uniform(0, 100, n),
        "wind_mw":   rng.uniform(0, 500, n),
        "temperature": rng.uniform(0, 25, n),
        "solar_radiation": rng.uniform(0, 800, n),
        "wind_speed": rng.uniform(0, 15, n),
        "cloud_cover": rng.uniform(0, 100, n),
    })


@pytest.fixture
def fitted_mapie():
    df = _small_df()
    params = {"n_estimators": 50, "num_leaves": 31, "random_state": 42, "n_jobs": -1}
    model, _ = train(df, "demand_mw", params)
    return calibrate(model, df, "demand_mw"), df


def test_export_target_writes_valid_booster(tmp_path, fitted_mapie, monkeypatch):
    mapie, df = fitted_mapie
    monkeypatch.setattr("models.export.ART", tmp_path)
    monkeypatch.setattr("models.export.RADII_PATH", tmp_path / "radii.json")
    (tmp_path / "radii.json").write_text(json.dumps({"solar_mw": 1.0, "wind_mw": 2.0}))

    with patch("mlflow.sklearn.load_model", return_value=mapie):
        export_target("demand_mw", df)

    booster = lgb.Booster(model_file=str(tmp_path / "demand_mw.txt"))
    assert booster.num_trees() > 0


def test_export_target_updates_only_its_own_radius(tmp_path, fitted_mapie, monkeypatch):
    mapie, df = fitted_mapie
    monkeypatch.setattr("models.export.ART", tmp_path)
    monkeypatch.setattr("models.export.RADII_PATH", tmp_path / "radii.json")
    (tmp_path / "radii.json").write_text(json.dumps({"solar_mw": 1.0, "wind_mw": 2.0}))

    with patch("mlflow.sklearn.load_model", return_value=mapie):
        export_target("demand_mw", df)

    radii = json.loads((tmp_path / "radii.json").read_text())
    assert radii["solar_mw"] == 1.0
    assert radii["wind_mw"] == 2.0
    assert "demand_mw" in radii and radii["demand_mw"] > 0


def test_export_promoted_noop_when_nothing_promoted(tmp_path, monkeypatch):
    monkeypatch.setattr("models.export.ART", tmp_path)
    with patch("mlflow.sklearn.load_model") as mock_load:
        export_promoted([])
    mock_load.assert_not_called()
