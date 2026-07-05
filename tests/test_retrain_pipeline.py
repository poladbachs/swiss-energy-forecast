"""Tests for scripts/retrain_pipeline.py."""
import json
from unittest.mock import call, patch

import pytest

from scripts.retrain_pipeline import check_drift, main


def test_check_drift_raises_below_floor(tmp_path, monkeypatch):
    backtest = tmp_path / "backtest.json"
    backtest.write_text(json.dumps({"summary": {"coverage_pct": 75.0}}))
    monkeypatch.setattr("scripts.retrain_pipeline.BACKTEST_PATH", backtest)

    with pytest.raises(SystemExit):
        check_drift()


def test_check_drift_passes_at_or_above_floor(tmp_path, monkeypatch):
    backtest = tmp_path / "backtest.json"
    backtest.write_text(json.dumps({"summary": {"coverage_pct": 92.0}}))
    monkeypatch.setattr("scripts.retrain_pipeline.BACKTEST_PATH", backtest)

    check_drift()  # should not raise


def test_main_calls_steps_in_order():
    with patch("scripts.retrain_pipeline.ingest") as mock_ingest, \
         patch("scripts.retrain_pipeline.run_pipeline") as mock_train, \
         patch("scripts.retrain_pipeline.promote_best", return_value=["demand_mw"]) as mock_promote, \
         patch("scripts.retrain_pipeline.export_promoted") as mock_export, \
         patch("scripts.retrain_pipeline.check_drift") as mock_drift:
        main()

    mock_ingest.assert_called_once()
    mock_train.assert_called_once()
    mock_promote.assert_called_once()
    mock_export.assert_called_once_with(["demand_mw"])
    mock_drift.assert_called_once()
