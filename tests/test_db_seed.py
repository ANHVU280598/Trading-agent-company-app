"""Database round-trip and seed checks (spec section M)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core import db
from scripts.seed_db import seed

ROOT = Path(__file__).resolve().parents[1]


def test_seed_dashboard_matches_paper_report(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    totals = seed(
        ROOT / "fixtures" / "paper_state.json",
        ROOT / "fixtures" / "paper_trades.csv",
        db_path,
        ROOT / "results.json",
    )
    assert abs(totals["portfolio_value"] - 102340.0) < 0.01
    assert abs(totals["cash"] - 61200.0) < 0.01
    hist = db.read_portfolio_history(db_path)
    assert not hist.empty
    assert float(hist.iloc[-1]["value"]) == 102340.0
    trades = db.read_trades(db_path)
    assert len(trades) == 6
    positions = db.read_positions(db_path)
    assert set(positions["ticker"]) == {"AAPL", "MSFT", "NVDA"}


def test_settings_round_trip(tmp_path: Path) -> None:
    db_path = tmp_path / "settings.db"
    db.init_db(db_path)
    db.upsert_setting("position_size", "0.25", db_path)
    db.upsert_setting("watchlist", "SPY,AAPL", db_path)
    m = db.get_settings_map(db_path)
    assert m["position_size"] == "0.25"
    assert m["watchlist"] == "SPY,AAPL"


def test_empty_reads_have_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.db"
    db.init_db(db_path)
    assert list(db.read_signals(db_path).columns) == db.SIGNAL_COLUMNS
    assert isinstance(db.read_trades(db_path), pd.DataFrame)
