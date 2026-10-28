"""Feature engineering. Formulas must match train.py / paper_trade.py (later)."""

from __future__ import annotations

import pandas as pd


FEATURE_ORDER: list[str] = [
    "ret1",
    "ret5",
    "ret21",
    "vol21",
    "rsi14",
    "dist_ma50",
    "drawdown63",
    "volz",
]


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
    """Build the 8 prototype features from a close/volume frame.

    Skeleton: returns an empty frame with the right columns when input is empty.
    Full parity with train.py is enforced in H step tests.
    """
    cols = FEATURE_ORDER.copy()
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
    """Hindsight label rule: forward 5-day return vs ±0.03 thresholds.

    Exactly +3.0% is hold (not buy). Exactly -3.0% is hold (not sell).
    """
    if prices is None or prices.empty:
        return pd.Series(dtype="object")
    close = prices["close"].astype(float)
    # Round so exact ±3.0% boundaries are hold (float 103/100-1 is not 0.03).
    forward = (close.shift(-5) / close - 1.0).round(10)
    labels = pd.Series("hold", index=prices.index, dtype="object")
    labels = labels.mask(forward > buy_th, "buy")
    labels = labels.mask(forward < sell_th, "sell")
    labels.iloc[-5:] = pd.NA
    return labels
