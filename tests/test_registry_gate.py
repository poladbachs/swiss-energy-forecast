"""Tests for the promotion gate in models/registry.py."""
from models.registry import should_promote


def test_promotes_when_no_champion_exists():
    assert should_promote(candidate_rmse=500.0, champion_rmse=None) is True


def test_promotes_on_improvement():
    assert should_promote(candidate_rmse=480.0, champion_rmse=500.0) is True


def test_promotes_on_tie():
    assert should_promote(candidate_rmse=500.0, champion_rmse=500.0) is True


def test_rejects_regression():
    assert should_promote(candidate_rmse=520.0, champion_rmse=500.0) is False
