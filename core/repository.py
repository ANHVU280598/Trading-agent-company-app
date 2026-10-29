"""App read model — SQLite only. Pages never call market APIs directly."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from core import db
from core.config import (
    DB_PATH,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_DRAWDOWN_FREEZE,
    DEFAULT_POSITION_SIZE,
    DEFAULT_WATCHLIST,
    ROOT,
)

ET = ZoneInfo("America/New_York")
RESULTS_PATH = ROOT / "results.json"
V1_V2_REPORT_PATH = ROOT / "models" / "v1_vs_v2_report.json"
V1_V3_REPORT_PATH = ROOT / "models" / "v1_vs_v3_report.json"
V1_V4_REPORT_PATH = ROOT / "models" / "v1_vs_v4_report.json"
PANIC_EXAM_REPORT_PATH = ROOT / "models" / "panic_exam_v4.json"
ACTIVE_MODEL_PATH = ROOT / "models" / "active_model.json"


def market_is_open(now: Optional[datetime] = None) -> bool:
    now = now or datetime.now(ET)
    if now.weekday() >= 5:
        return False
    minutes = now.hour * 60 + now.minute
    return (9 * 60 + 30) <= minutes < (16 * 60)


def last_updated_label(hist: pd.DataFrame) -> str:
    if hist.empty:
        return "—"
    d = str(hist.iloc[-1]["date"])
    return f"{d} 16:05 ET"


def portfolio_meta(db_path: Path = DB_PATH) -> dict[str, Any]:
    hist = db.read_portfolio_history(db_path)
    if hist.empty:
        return {
            "empty": True,
            "last_updated": "—",
            "market_open": market_is_open(),
            "buys_frozen": False,
        }
    last = hist.iloc[-1]
    start = hist.iloc[0]
    agent_ret = float(last["value"]) / float(start["value"]) - 1.0
    bench_ret = float(last["benchmark_value"]) / float(start["benchmark_value"]) - 1.0
    high = float(hist["value"].max())
    settings = load_settings(db_path)
    dd = float(last["drawdown"])
    freeze = float(settings["drawdown_freeze"])
    return {
        "empty": False,
        "last_updated": last_updated_label(hist),
        "market_open": market_is_open(),
        "portfolio_value": float(last["value"]),
        "portfolio_ret": agent_ret,
        "start_date": str(start["date"]),
        "agent_ret": agent_ret,
        "bench_ret": bench_ret,
        "cash": float(last["cash"]),
        "cash_pct": float(last["cash"]) / float(last["value"]) if float(last["value"]) else 0.0,
        "drawdown": dd,
        "high_water": high,
        "buys_frozen": dd <= -abs(freeze),
        "history": hist,
    }


def positions_with_prices(db_path: Path = DB_PATH) -> pd.DataFrame:
    pos = db.read_positions(db_path)
    signals = latest_signals(db_path)
    if pos.empty:
        return pos
    price_map = {}
    if not signals.empty:
        price_map = {str(r["ticker"]): float(r["price"]) for _, r in signals.iterrows()}
    out = pos.copy()
    out["price"] = out["ticker"].map(lambda t: price_map.get(str(t), float("nan")))
    return out


def latest_signals(db_path: Path = DB_PATH) -> pd.DataFrame:
    sig = db.read_signals(db_path)
    if sig.empty:
        return sig
    latest = str(sig["date"].max())
    watch = load_settings(db_path)["watchlist"]
    frame = sig[sig["date"] == latest].copy()
    # Preserve watchlist order
    frame["_ord"] = frame["ticker"].apply(
        lambda t: watch.index(t) if t in watch else 999
    )
    return frame.sort_values("_ord").drop(columns=["_ord"])


def load_settings(db_path: Path = DB_PATH) -> dict[str, Any]:
    raw = db.get_settings_map(db_path)
    watch = raw.get("watchlist", ",".join(DEFAULT_WATCHLIST))
    tickers = [t.strip().upper() for t in watch.split(",") if t.strip()]
    if not tickers:
        tickers = list(DEFAULT_WATCHLIST)
    return {
        "watchlist": tickers,
        "position_size": float(raw.get("position_size", DEFAULT_POSITION_SIZE)),
        "drawdown_freeze": float(raw.get("drawdown_freeze", DEFAULT_DRAWDOWN_FREEZE)),
        "confidence_threshold": float(
            raw.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD)
        ),
    }


def save_settings(
    watchlist: list[str],
    position_size: float,
    drawdown_freeze: float,
    confidence_threshold: float,
    db_path: Path = DB_PATH,
) -> None:
    db.upsert_setting("watchlist", ",".join(watchlist), db_path)
    db.upsert_setting("position_size", f"{position_size:.4f}", db_path)
    db.upsert_setting("drawdown_freeze", f"{drawdown_freeze:.4f}", db_path)
    db.upsert_setting("confidence_threshold", f"{confidence_threshold:.4f}", db_path)


def load_results(path: Path = RESULTS_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_v1_v2_report(path: Path = V1_V2_REPORT_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_v1_v3_report(path: Path = V1_V3_REPORT_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_v1_v4_report(path: Path = V1_V4_REPORT_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_panic_exam_report(path: Path = PANIC_EXAM_REPORT_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_active_model_meta(path: Path = ACTIVE_MODEL_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def keys_connected() -> dict[str, bool]:
    from core.secrets import alpaca_creds_present, finnhub_key_present, xai_key_present

    return {
        "alpaca": alpaca_creds_present(),
        "finnhub": finnhub_key_present(),
        "xai": xai_key_present(),
    }
