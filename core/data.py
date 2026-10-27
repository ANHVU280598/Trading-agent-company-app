"""Price and headline fetches. v1: Yahoo primary; fallbacks per addendum."""

from __future__ import annotations

import time
from typing import Any

import pandas as pd


def get_daily_bars(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Daily OHLCV. Priority: Yahoo → (Alpaca later) → Stooq."""
    for provider in ("yahoo", "stooq"):
        try:
            frame = _fetch_bars(provider, ticker, start, end)
            if frame is not None and not frame.empty:
                frame = _quality_check(frame)
                frame.attrs["source"] = provider
                frame.attrs["stale"] = False
                return frame
        except Exception:
            time.sleep(2)
            try:
                frame = _fetch_bars(provider, ticker, start, end)
                if frame is not None and not frame.empty:
                    frame = _quality_check(frame)
                    frame.attrs["source"] = provider
                    return frame
            except Exception:
                continue
    return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])


def get_headlines(ticker: str, date: str) -> list[dict[str, Any]]:
    """Headlines for ticker/date. Finnhub when keyed; else empty."""
    import os

    _ = date
    key = os.getenv("FINNHUB_API_KEY")
    if not key:
        return []
    # Finnhub wiring reserved for Phase 2 when key exists — no call without key.
    _ = ticker
    return []


def _fetch_bars(provider: str, ticker: str, start: str, end: str) -> pd.DataFrame:
    if provider == "yahoo":
        import yfinance as yf

        raw = yf.download(
            ticker,
            start=start,
            end=end,
            progress=False,
            auto_adjust=True,
        )
        if raw is None or raw.empty:
            return pd.DataFrame()
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [c[0].lower() for c in raw.columns]
        else:
            raw.columns = [str(c).lower() for c in raw.columns]
        out = raw.reset_index()
        date_col = "date" if "date" in out.columns else out.columns[0]
        out = out.rename(columns={date_col: "date"})
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
        cols = ["date", "open", "high", "low", "close", "volume"]
        for c in cols:
            if c not in out.columns:
                out[c] = pd.NA
        return out[cols]

    if provider == "stooq":
        url = f"https://stooq.com/q/d/l/?s={ticker.lower()}.us&i=d"
        raw = pd.read_csv(url)
        if raw.empty:
            return pd.DataFrame()
        raw.columns = [c.lower() for c in raw.columns]
        raw = raw.rename(columns={"date": "date"})
        raw["date"] = pd.to_datetime(raw["date"]).dt.strftime("%Y-%m-%d")
        mask = (raw["date"] >= start) & (raw["date"] <= end)
        return raw.loc[mask, ["date", "open", "high", "low", "close", "volume"]]

    return pd.DataFrame()


def _quality_check(frame: pd.DataFrame) -> pd.DataFrame:
    """Flag duplicate dates, long gaps, huge jumps, zero-volume streaks."""
    flags: list[str] = []
    if frame["date"].duplicated().any():
        flags.append("duplicate timestamps")
        frame = frame.drop_duplicates("date", keep="last")
    dates = pd.to_datetime(frame["date"])
    if len(dates) > 1:
        gaps = dates.diff().dt.days.fillna(0)
        if (gaps > 7).any():  # ~5 trading days ≈ 7 calendar
            flags.append("gap longer than 5 trading days")
    rets = frame["close"].pct_change().abs()
    if (rets > 0.40).any():
        flags.append("single-day jump over 40%")
    zero = (frame["volume"].fillna(0) == 0).astype(int)
    if zero.rolling(3).sum().max() >= 3:
        flags.append("zero-volume streak of 3+ days")
    frame = frame.copy()
    frame.attrs["data_quality"] = "; ".join(flags) if flags else ""
    return frame
