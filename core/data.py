"""Price and headline fetches. Priority per addendum; callers never branch on source."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import pandas as pd

from core.secrets import load_alpaca_creds


def get_daily_bars(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Daily OHLCV. Priority: Yahoo → Alpaca → Stooq."""
    for provider in ("yahoo", "alpaca", "stooq"):
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
    """Headlines for ticker/date. Priority: Finnhub → empty (Yahoo news not wired).

    Returns list of dicts with at least {"headline": str}. Top headline is [0].
    """
    key = os.getenv("FINNHUB_API_KEY", "").strip()
    if key:
        try:
            rows = _finnhub_headlines(ticker, date, key)
            if rows:
                return rows
        except Exception:
            time.sleep(2)
            try:
                rows = _finnhub_headlines(ticker, date, key)
                if rows:
                    return rows
            except Exception:
                pass
    return []


def _finnhub_headlines(ticker: str, date: str, key: str) -> list[dict[str, Any]]:
    # company-news window: same calendar day (UTC date string from market date)
    params = urllib.parse.urlencode(
        {
            "symbol": ticker.upper(),
            "from": date,
            "to": date,
            "token": key,
        }
    )
    url = f"https://finnhub.io/api/v1/company-news?{params}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for item in data:
        headline = str(item.get("headline") or "").strip()
        if not headline:
            continue
        out.append(
            {
                "headline": headline[:500],
                "source": str(item.get("source") or "finnhub"),
                "url": str(item.get("url") or ""),
            }
        )
        if len(out) >= 5:
            break
    return out


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

    if provider == "alpaca":
        creds = load_alpaca_creds()
        if creds is None:
            return pd.DataFrame()
        # Data API host (not the trading host)
        data_host = "https://data.alpaca.markets"
        params = urllib.parse.urlencode(
            {
                "timeframe": "1Day",
                "start": start,
                "end": end,
                "adjustment": "split",
                "feed": "iex",
                "limit": 10000,
            }
        )
        url = f"{data_host}/v2/stocks/{ticker.upper()}/bars?{params}"
        req = urllib.request.Request(
            url,
            headers={
                "APCA-API-KEY-ID": creds.key_id,
                "APCA-API-SECRET-KEY": creds.secret_key,
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError:
            return pd.DataFrame()
        bars = payload.get("bars") or []
        if not bars:
            return pd.DataFrame()
        rows = []
        for b in bars:
            ts = str(b.get("t") or "")[:10]
            rows.append(
                {
                    "date": ts,
                    "open": float(b.get("o") or 0),
                    "high": float(b.get("h") or 0),
                    "low": float(b.get("l") or 0),
                    "close": float(b.get("c") or 0),
                    "volume": float(b.get("v") or 0),
                }
            )
        return pd.DataFrame(rows)

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
        if (gaps > 7).any():
            flags.append("gap longer than 5 trading days")
    rets = frame["close"].pct_change().abs()
    if (rets > 0.40).any():
        flags.append("single-day jump over 40%")
    zero = (frame["volume"].fillna(0) == 0).astype(int)
    if len(zero) and zero.rolling(3).sum().max() >= 3:
        flags.append("zero-volume streak of 3+ days")
    frame = frame.copy()
    frame.attrs["data_quality"] = "; ".join(flags) if flags else ""
    return frame
