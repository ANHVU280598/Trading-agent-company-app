"""Default configuration. Settings table overrides these at runtime (step 6)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "app.db"
ASSETS_DIR = ROOT / "assets"
STYLE_CSS = ASSETS_DIR / "style.css"

DEFAULT_WATCHLIST: list[str] = ["SPY", "AAPL", "MSFT", "NVDA", "TSLA"]
DEFAULT_POSITION_SIZE: float = 0.20
DEFAULT_DRAWDOWN_FREEZE: float = 0.10
DEFAULT_CONFIDENCE_THRESHOLD: float = 0.55
STARTING_PAPER_CASH: float = 100_000.0

APP_NAME = "Trading Agent Company App"
EMPTY_TRADES_COPY = "No trades yet. The agent is watching."
LOADING_COPY = "Loading latest data…"
SIGNAL_NOTE = "Signals are the model's read at the last close. Demo model — not trade advice."
MODEL_HONESTY = (
    "Labels right now come from a hindsight rule, not a real trader's history. "
    "Numbers below describe a demo model. The upgrade that matters most is training "
    "on Tuan's real trades."
)
SETTINGS_CONFIDENCE_CAPTION = (
    "The agent only buys or sells when the model's confidence is at or above this."
)
SETTINGS_LIVE_CAPTION = (
    "Live trading is locked during the paper phase. It unlocks only after the "
    "Phase 5 review with Muse."
)
SETTINGS_APPLY_NOTE = "Settings apply on the agent's next daily run."
SETTINGS_SAVED = "Saved"
EMPTY_SIGNALS_COPY = "No signals yet. Run paper_trade.py once, then refresh."
