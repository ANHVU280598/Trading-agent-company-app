"""Feature engineering. Formulas must match train.py / paper_trade.py."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from core.calendar_features import CALENDAR_FEATURE_ORDER, build_calendar_features


FEATURE_ORDER_V1: list[str] = [
    "ret1",
    "ret5",
    "ret21",
    "vol21",
    "rsi14",
    "dist_ma50",
    "drawdown63",
    "volz",
]

# Phase 4 exact order
FEATURE_ORDER_V2: list[str] = FEATURE_ORDER_V1 + [
    "sentiment",
    "headline_count",
    "spy_regime",
    "rs21",
]

# Model v3: v1 + 18 calendar features
FEATURE_ORDER_V3: list[str] = FEATURE_ORDER_V1 + CALENDAR_FEATURE_ORDER

# Back-compat alias used by existing imports
FEATURE_ORDER = FEATURE_ORDER_V1


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder RSI (alpha = 1/period). Copied from the prototype contract."""
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def build_features(prices: pd.DataFrame) -> pd.DataFrame:
    """Build the 8 prototype (v1) features from a close/volume frame."""
    cols = FEATURE_ORDER_V1.copy()
    if prices is None or prices.empty:
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame(index=prices.index)
    close = prices["close"].astype(float)
    volume = prices["volume"].astype(float)
    ret = close.pct_change()
    out["ret1"] = close.pct_change(1)
    out["ret5"] = close.pct_change(5)
    out["ret21"] = close.pct_change(21)
    out["vol21"] = ret.rolling(21).std() * (252 ** 0.5)
    out["rsi14"] = rsi(close, 14)
    ma50 = close.rolling(50).mean()
    out["dist_ma50"] = close / ma50 - 1.0
    high63 = close.rolling(63).max()
    out["drawdown63"] = close / high63 - 1.0
    vol_mean = volume.rolling(21).mean()
    vol_std = volume.rolling(21).std()
    out["volz"] = (volume - vol_mean) / vol_std.replace(0, pd.NA)
    return out[cols]


def make_labels(prices: pd.DataFrame, buy_th: float = 0.03, sell_th: float = -0.03) -> pd.Series:
    """Hindsight label rule: forward 5-day return vs ±0.03 thresholds."""
    if prices is None or prices.empty:
        return pd.Series(dtype="object")
    close = prices["close"].astype(float)
    forward = (close.shift(-5) / close - 1.0).round(10)
    labels = pd.Series("hold", index=prices.index, dtype="object")
    labels = labels.mask(forward > buy_th, "buy")
    labels = labels.mask(forward < sell_th, "sell")
    labels.iloc[-5:] = pd.NA
    return labels


def spy_regime_series(spy_close: pd.Series) -> pd.Series:
    """1 if SPY close > 50-day MA, else 0."""
    ma50 = spy_close.astype(float).rolling(50).mean()
    return (spy_close.astype(float) > ma50).astype(float)


def build_features_v2(
    prices: pd.DataFrame,
    spy_prices: pd.DataFrame,
    sentiment: Optional[pd.Series] = None,
    headline_count: Optional[pd.Series] = None,
) -> pd.DataFrame:
    """v1 features + sentiment, headline_count, spy_regime, rs21.

    Missing sentiment → 0.0; missing headline_count → 0 (No news.).
    spy_regime / rs21 use only price data known at the close.
    """
    base = build_features(prices)
    if base.empty:
        return pd.DataFrame(columns=FEATURE_ORDER_V2)

    out = base.copy()
    idx = out.index.astype(str)

    if sentiment is None:
        out["sentiment"] = 0.0
    else:
        aligned = sentiment.reindex(idx)
        out["sentiment"] = aligned.fillna(0.0).astype(float).values

    if headline_count is None:
        out["headline_count"] = 0.0
    else:
        aligned_c = headline_count.reindex(idx)
        out["headline_count"] = aligned_c.fillna(0.0).astype(float).values

    spy = spy_prices.copy()
    if "date" in spy.columns:
        spy = spy.set_index("date")
    spy_close = spy["close"].astype(float)
    spy_close.index = spy_close.index.astype(str)
    regime = spy_regime_series(spy_close).reindex(idx)
    out["spy_regime"] = regime.fillna(0.0).astype(float).values

    ticker_ret21 = prices["close"].astype(float).pct_change(21)
    ticker_ret21.index = ticker_ret21.index.astype(str)
    spy_ret21 = spy_close.pct_change(21).reindex(idx)
    rs = ticker_ret21.reindex(idx) - spy_ret21
    out["rs21"] = rs.astype(float).values

    return out[FEATURE_ORDER_V2]


def build_features_v3(
    prices: pd.DataFrame,
    events: pd.DataFrame,
    ticker: str,
) -> pd.DataFrame:
    """v1 price features + 18 calendar features (Model v3)."""
    base = build_features(prices)
    if base.empty:
        return pd.DataFrame(columns=FEATURE_ORDER_V3)

    idx = base.index
    sessions = pd.Index(pd.to_datetime(idx).date)
    cal = build_calendar_features(list(sessions), events, ticker)
    out = base.copy()
    out.index = pd.Index([str(d) for d in sessions])
    cal = cal.reindex(out.index)
    for col in CALENDAR_FEATURE_ORDER:
        out[col] = cal[col].values if col in cal.columns else 0.0
    out["days_to_fomc"] = out["days_to_fomc"].fillna(30.0)
    out["days_to_cpi"] = out["days_to_cpi"].fillna(31.0)
    out["days_to_earnings"] = out["days_to_earnings"].fillna(63.0)
    for col in CALENDAR_FEATURE_ORDER:
        if col.startswith("days_to_"):
            continue
        out[col] = out[col].fillna(0.0)
    return out[FEATURE_ORDER_V3]
