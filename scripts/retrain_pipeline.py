"""
Weekly retrain pipeline: ingest -> train -> gated promote -> export -> drift check.

Runs the whole cycle in one process so the promotion gate's result (which
targets actually got promoted) passes straight into export, with no need to
serialize state between separate CLI steps. Invoked by .github/workflows/retrain.yml.

Run:
    python -m scripts.retrain_pipeline
"""
import json
import os
from datetime import date, timedelta
from pathlib import Path

from data.ingest import ingest
from models.export import export_promoted
from models.registry import promote_best
from models.train import run_pipeline

BACKTEST_PATH = Path(__file__).resolve().parent.parent / "frontend" / "public" / "backtest.json"
COVERAGE_FLOOR = 80.0


def check_drift() -> None:
    """Fail loudly if the currently-serving model's rolling coverage has degraded."""
    backtest = json.loads(BACKTEST_PATH.read_text())
    coverage = backtest["summary"]["coverage_pct"]
    msg = f"14-day conformal coverage: {coverage}% (floor {COVERAGE_FLOOR}%)"

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(msg + "\n")

    print(f"[drift] {msg}")
    if coverage < COVERAGE_FLOOR:
        raise SystemExit(f"[drift] {msg} — below floor, investigate before next retrain")


def main() -> None:
    ingest(date.today() - timedelta(days=7), date.today())
    run_pipeline()
    promoted = promote_best()
    export_promoted(promoted)
    check_drift()


if __name__ == "__main__":
    main()
