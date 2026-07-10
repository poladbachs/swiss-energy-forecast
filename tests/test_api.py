"""Tests for the Vercel ASGI app (api/main.py) that serves the static forecast."""
import json

import pytest
from starlette.testclient import TestClient

import api.main as api_main
from api.main import app


@pytest.fixture(autouse=True)
def _reset_cache():
    """api/main.py lazy-loads and caches forecast.json in a module global."""
    api_main._STATIC_FORECAST = None
    yield
    api_main._STATIC_FORECAST = None


@pytest.fixture
def client():
    return TestClient(app)


def _base_hour():
    return {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "demand": {"point": 7000.0, "lower": 6500.0, "upper": 7500.0},
        "solar": {"point": 100.0, "lower": 0.0, "upper": 300.0},
        "wind": {"point": 20.0, "lower": 0.0, "upper": 60.0},
        "hydro_mw": 2500.0,
        "nuclear_mw": 2000.0,
        "import_gap": {"point": 2380.0, "lower": 1640.0, "upper": 2900.0},
        "coverage_status": "deficit",
    }


@pytest.fixture
def stub_forecast(tmp_path, monkeypatch):
    """Point _FORECAST at a small, deterministic fixture instead of the real artifact."""
    hours = [_base_hour() for _ in range(48)]
    payload = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "horizon_hours": 48,
        "solar_multiplier": 1.0,
        "wind_multiplier": 1.0,
        "forecasts": hours,
        "summary": {"confirmed_surplus_hours": 0, "possible_surplus_hours": 0, "deficit_hours": 48},
    }
    path = tmp_path / "forecast.json"
    path.write_text(json.dumps(payload))
    monkeypatch.setattr(api_main, "_FORECAST", path)
    return payload


def test_health(client, stub_forecast):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "forecast_artifact_loaded": True}


def test_forecast_default_horizon(client, stub_forecast):
    r = client.get("/api/forecast")
    assert r.status_code == 200
    body = r.json()
    assert len(body["forecasts"]) == 48
    hour = body["forecasts"][0]
    for key in ("demand", "solar", "wind", "import_gap"):
        assert set(hour[key]) == {"point", "lower", "upper"}
    assert hour["coverage_status"] in ("confirmed_surplus", "possible_surplus", "deficit")


def test_forecast_horizon_query_and_clamping(client, stub_forecast):
    assert len(client.get("/api/forecast?horizon=10").json()["forecasts"]) == 10
    assert len(client.get("/api/forecast?horizon=0").json()["forecasts"]) == 1
    assert len(client.get("/api/forecast?horizon=500").json()["forecasts"]) == 48  # capped at 96, only 48 available


def test_import_gap_and_status_consistent(client, stub_forecast):
    body = client.get("/api/forecast").json()
    for h in body["forecasts"]:
        gap = h["import_gap"]
        domestic = h["hydro_mw"] + h["nuclear_mw"]
        assert gap["point"] == pytest.approx(h["demand"]["point"] - h["solar"]["point"] - h["wind"]["point"] - domestic)
        assert gap["lower"] == pytest.approx(h["demand"]["lower"] - h["solar"]["upper"] - h["wind"]["upper"] - domestic)
        assert gap["upper"] == pytest.approx(h["demand"]["upper"] - h["solar"]["lower"] - h["wind"]["lower"] - domestic)
        if gap["upper"] < 0:
            assert h["coverage_status"] == "confirmed_surplus"
        elif gap["point"] < 0:
            assert h["coverage_status"] == "possible_surplus"
        else:
            assert h["coverage_status"] == "deficit"
    counts = body["summary"]
    assert counts["confirmed_surplus_hours"] + counts["possible_surplus_hours"] + counts["deficit_hours"] == 48


def test_multiplier_scales_solar_and_wind(client, stub_forecast):
    base = client.get("/api/forecast").json()
    boosted = client.get("/api/forecast?solar_multiplier=3.0&wind_multiplier=0.0").json()
    for b, x in zip(base["forecasts"], boosted["forecasts"]):
        assert x["solar"]["point"] == pytest.approx(3.0 * b["solar"]["point"])
        assert x["wind"]["point"] == pytest.approx(0.0)


def test_unknown_path_is_404(client, stub_forecast):
    r = client.get("/does-not-exist")
    assert r.status_code == 404


def test_post_is_405(client, stub_forecast):
    r = client.post("/api/forecast")
    assert r.status_code == 405
