"""Price and headline fetches. v1: Yahoo only (wired in later steps)."""

from __future__ import annotations

from typing import Any

import pandas as pd


def get_daily_bars(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Return daily OHLCV bars for ticker between start and end (inclusive).

    Skeleton stub — real Yahoo implementation lands in a later H step.
    """
    _ = (ticker, start, end)
    return pd.DataFrame(
        columns=["date", "open", "high", "low", "close", "volume"]
    )


def get_headlines(ticker: str, date: str) -> list[dict[str, Any]]:
    """Return headline dicts for ticker on date. Skeleton stub."""
    _ = (ticker, date)
    return []
