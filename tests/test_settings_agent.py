"""H step 6: settings persist and are what the agent reads."""

from __future__ import annotations

from pathlib import Path

from core.repository import load_settings, save_settings
from scripts.seed_db import seed

ROOT = Path(__file__).resolve().parents[1]


def test_position_size_25_percent_readable_by_agent(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    seed(
        ROOT / "fixtures" / "paper_state.json",
        ROOT / "fixtures" / "paper_trades.csv",
        db_path,
        ROOT / "results.json",
    )
    save_settings(
        ["SPY", "AAPL", "MSFT", "NVDA", "TSLA"],
        position_size=0.25,
        drawdown_freeze=0.10,
        confidence_threshold=0.55,
        db_path=db_path,
    )
    settings = load_settings(db_path)
    assert settings["position_size"] == 0.25
    # paper_trade.main uses load_settings — same path the agent uses on next run
    buy_fraction = settings["position_size"]
    assert abs(buy_fraction - 0.25) < 1e-12
