import pandas as pd

from scripts.static_backtest import iso_utc


def test_iso_utc_keeps_utc_offset():
    ts = pd.Timestamp("2026-06-19 12:00:00", tz="UTC")

    assert iso_utc(ts) == "2026-06-19T12:00:00+00:00"
