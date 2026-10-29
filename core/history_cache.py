"""Per-ticker OHLCV cache under data/history/ (Model v5 Step 2)."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from core.config import ROOT
from core.data import get_daily_bars

HISTORY_DIR = ROOT / "data" / "history"
QUALITY_JSON = ROOT / "data" / "history_quality.json"


def history_path(ticker: str, directory: Path = HISTORY_DIR) -> Path:
    return directory / f"{ticker.upper()}.csv"


def load_cached(ticker: str, directory: Path = HISTORY_DIR) -> pd.DataFrame:
    path = history_path(ticker, directory)
    if not path.exists():
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df = pd.read_csv(path)
    df["date"] = df["date"].astype(str)
    return df


def quality_counts(frame: pd.DataFrame) -> dict[str, int]:
    """Standing data-quality flags (Doc): gaps>5 trading days, jumps>40%, zero-vol streaks."""
    out = {"gap_gt_5td": 0, "jump_gt_40pct": 0, "zero_vol_streak_3": 0, "rows": 0}
    if frame is None or frame.empty:
        return out
    out["rows"] = int(len(frame))
    dates = pd.to_datetime(frame["date"])
    if len(dates) > 1:
        # calendar-day gaps > 7 ≈ longer than 5 trading days
        gaps = dates.diff().dt.days.fillna(0)
        out["gap_gt_5td"] = int((gaps > 7).sum())
    rets = frame["close"].astype(float).pct_change().abs()
    out["jump_gt_40pct"] = int((rets > 0.40).sum())
    zero = (frame["volume"].fillna(0).astype(float) == 0).astype(int)
    if len(zero):
        out["zero_vol_streak_3"] = int((zero.rolling(3).sum() >= 3).sum())
    return out


def fetch_and_cache(
    ticker: str,
    start: str = "2014-01-01",
    end: Optional[str] = None,
    directory: Path = HISTORY_DIR,
    *,
    force: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Download once (Yahoo→Alpaca→Stooq via get_daily_bars), cache forever."""
    directory.mkdir(parents=True, exist_ok=True)
    end = end or date.today().isoformat()
    path = history_path(ticker, directory)
    meta: dict[str, Any] = {"ticker": ticker.upper(), "path": str(path)}
    if path.exists() and not force:
        df = load_cached(ticker, directory)
        meta["cached"] = True
        meta["source"] = "cache"
        meta["quality"] = quality_counts(df)
        return df, meta

    df = get_daily_bars(ticker, start, end)
    meta["cached"] = False
    meta["source"] = getattr(df, "attrs", {}).get("source", "unknown")
    meta["data_quality_flags"] = getattr(df, "attrs", {}).get("data_quality", "")
    if df is None or df.empty:
        meta["ok"] = False
        meta["quality"] = quality_counts(pd.DataFrame())
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"]), meta

    df = df.copy()
    df["date"] = df["date"].astype(str)
    df.to_csv(path, index=False)
    meta["ok"] = True
    meta["quality"] = quality_counts(df)
    meta["min_date"] = str(df["date"].iloc[0])
    meta["max_date"] = str(df["date"].iloc[-1])
    return df, meta


def fetch_universe(
    tickers: list[str],
    start: str = "2014-01-01",
    end: Optional[str] = None,
    directory: Path = HISTORY_DIR,
    *,
    max_workers: int = 8,
    force: bool = False,
) -> dict[str, Any]:
    report: dict[str, Any] = {"start": start, "end": end or date.today().isoformat(), "tickers": {}}
    directory.mkdir(parents=True, exist_ok=True)

    def _one(t: str) -> tuple[str, dict[str, Any]]:
        _df, meta = fetch_and_cache(t, start, end, directory, force=force)
        return t, meta

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = [pool.submit(_one, t) for t in tickers]
        for fut in as_completed(futs):
            t, meta = fut.result()
            report["tickers"][t] = meta
            print(f"history {t}: rows={meta.get('quality', {}).get('rows')} src={meta.get('source')}")

    QUALITY_JSON.parent.mkdir(parents=True, exist_ok=True)
    QUALITY_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
