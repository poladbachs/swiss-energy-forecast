"""Tests for the FastAPI endpoints. Models, DB and weather are mocked."""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

import api.main as api_main
from api.main import app


def _mock_mapie(point, radius):
    m = MagicMock()

    def predict_interval(X):
        n = len(X)
        pts = np.full(n, point)
        intervals = np.stack([pts - radius, pts + radius], axis=1).reshape(n, 2, 1)
        return pts, intervals

    m.predict_interval.side_effect = predict_interval
    return m


def _mock_history():
    idx = pd.date_range(end=pd.Timestamp.now(tz="UTC").floor("h"), periods=200, freq="h")
    return pd.DataFrame({
        "timestamp": idx,
        "demand_mw": 7000.0, "solar_mw": 800.0, "wind_mw": 100.0,
        "temperature": 10.0, "solar_radiation": 200.0, "wind_speed": 5.0, "cloud_cover": 50.0,
    })


def _mock_weather():
    now = pd.Timestamp.now(tz="UTC").floor("h")
    idx = pd.date_range(now + pd.Timedelta(hours=1), periods=96, freq="h")
    return pd.DataFrame({
        "timestamp": idx,
        "temperature": 10.0, "solar_radiation": 200.0, "wind_speed": 5.0, "cloud_cover": 50.0,
    })


@pytest.fixture
def client():
    models = {
        "demand_mw": _mock_mapie(7000.0, 300.0),
        "solar_mw":  _mock_mapie(800.0, 100.0),
        "wind_mw":   _mock_mapie(100.0, 50.0),
    }
    with patch.object(api_main, "_models", models), \
         patch.object(api_main, "db_query", return_value=_mock_history()), \
         patch.object(api_main, "fetch_forecast", return_value=_mock_weather()):
        # TestClient skips the lifespan; models are patched in directly
        yield TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_forecast_schema(client):
    r = client.get("/forecast?horizon=24")
    assert r.status_code == 200
    body = r.json()
    assert len(body["forecasts"]) == 24
    hour = body["forecasts"][0]
    for key in ("demand", "solar", "wind", "supply_gap"):
        assert set(hour[key]) == {"point", "lower", "upper"}
    assert hour["coverage_status"] in ("confirmed_surplus", "possible_surplus", "deficit")


def test_supply_gap_and_status_consistent(client):
    body = client.get("/forecast?horizon=48").json()
    for h in body["forecasts"]:
        gap = h["supply_gap"]
        assert gap["point"] == pytest.approx(h["demand"]["point"] - h["solar"]["point"] - h["wind"]["point"])
        assert gap["lower"] == pytest.approx(h["demand"]["lower"] - h["solar"]["upper"] - h["wind"]["upper"])
        assert gap["upper"] == pytest.approx(h["demand"]["upper"] - h["solar"]["lower"] - h["wind"]["lower"])
        if gap["upper"] < 0:
            assert h["coverage_status"] == "confirmed_surplus"
        elif gap["point"] < 0:
            assert h["coverage_status"] == "possible_surplus"
        else:
            assert h["coverage_status"] == "deficit"
    counts = body["summary"]
    assert counts["confirmed_surplus_hours"] + counts["possible_surplus_hours"] + counts["deficit_hours"] == 48


def test_negative_solar_wind_clipped_to_zero():
    models = {
        "demand_mw": _mock_mapie(100.0, 300.0),   # point-radius goes negative too
        "solar_mw":  _mock_mapie(10.0, 100.0),    # point=10, lower=-90 -> must clip
        "wind_mw":   _mock_mapie(5.0, 100.0),     # point=5,  lower=-95 -> must clip
    }
    with patch.object(api_main, "_models", models), \
         patch.object(api_main, "db_query", return_value=_mock_history()), \
         patch.object(api_main, "fetch_forecast", return_value=_mock_weather()):
        body = TestClient(app).get("/forecast?horizon=24").json()

    for h in body["forecasts"]:
        assert h["solar"]["point"] >= 0
        assert h["solar"]["lower"] >= 0
        assert h["wind"]["point"] >= 0
        assert h["wind"]["lower"] >= 0
        # demand isn't a generation figure — not clipped, should stay negative here
        assert h["demand"]["lower"] < 0


def test_multiplier_scales_solar(client):
    base = client.get("/forecast?horizon=24").json()
    boosted = client.get("/forecast?horizon=24&solar_multiplier=3.0").json()
    for b, x in zip(base["forecasts"], boosted["forecasts"]):
        assert x["solar"]["point"] == pytest.approx(3.0 * b["solar"]["point"])
    assert boosted["summary"]["deficit_hours"] <= base["summary"]["deficit_hours"]
