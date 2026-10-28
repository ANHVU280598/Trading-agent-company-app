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

FEATURE_ORDER_V3: list[str] = FEATURE_ORDER_V1 + CALENDAR_FEATURE_ORDER

# Back-compat alias (v1 / prototype)
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
    # Normalize index to date strings for join
    sessions = pd.Index(pd.to_datetime(idx).date)
    cal = build_calendar_features(list(sessions), events, ticker)
    # align
    out = base.copy()
    out.index = pd.Index([str(d) for d in sessions])
    cal = cal.reindex(out.index)
    for col in CALENDAR_FEATURE_ORDER:
        out[col] = cal[col].values if col in cal.columns else 0.0
    # Fill any gaps from missing calendar rows with safe defaults
    out["days_to_fomc"] = out["days_to_fomc"].fillna(30.0)
    out["days_to_cpi"] = out["days_to_cpi"].fillna(31.0)
    out["days_to_earnings"] = out["days_to_earnings"].fillna(63.0)
    for col in CALENDAR_FEATURE_ORDER:
        if col.startswith("days_to_"):
            continue
        out[col] = out[col].fillna(0.0)
    return out[FEATURE_ORDER_V3]
