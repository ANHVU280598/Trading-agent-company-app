"""Model v4 Step 2 — eight behavior features (exact Muse order).

crowd_mood formula (do not change silently — log DECISIONS + new model version):
  average of trailing-only percentile components on a 0–100 greed scale:
  (a) 100 × (1 − vix_pct252)
  (b) 100 × (1 − putcall trailing percentile)   # high put/call = fear
  (c) 100 × SPY trailing percentile of its 125-day return
  If putcall is missing for day T, average (a) and (c) only.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from core.behavior_data import load_behavior_csv, putcall_in_force

BEHAVIOR_FEATURE_ORDER: list[str] = [
    "vix_close",
    "vix_chg5",
    "vix_pct252",
    "putcall",
    "crowd_mood",
    "aaii_spread",
    "capitulation_ticker",
    "capitulation_spy",
]

_PUTCALL_MISSING_LOGGED = False


def trailing_percentile(series: pd.Series, window: int) -> pd.Series:
    """Trailing percentile rank of the last value in each window, in [0, 1]."""

    def _pct(arr: np.ndarray) -> float:
        if len(arr) == 0 or np.isnan(arr[-1]):
            return float("nan")
        valid = arr[~np.isnan(arr)]
        if len(valid) < 2:
            return float("nan")
        last = valid[-1]
        return float((valid <= last).sum()) / float(len(valid))

    return series.astype(float).rolling(window, min_periods=window).apply(
        _pct, raw=True
    )


def crowd_mood_from_components(
    vix_pct252: float,
    putcall_pct: Optional[float],
    spy_ret125_pct: float,
) -> float:
    """Hand-checkable crowd_mood on fixed component inputs (0–100)."""
    a = 100.0 * (1.0 - float(vix_pct252))
    c = 100.0 * float(spy_ret125_pct)
    if putcall_pct is None or (isinstance(putcall_pct, float) and np.isnan(putcall_pct)):
        return (a + c) / 2.0
    b = 100.0 * (1.0 - float(putcall_pct))
    return (a + b + c) / 3.0


def crowd_mood_label(value: float) -> str:
    if value < 20:
        return "Extreme fear"
    if value < 40:
        return "Fear"
    if value < 60:
        return "Neutral"
    if value < 80:
        return "Greed"
    return "Extreme greed"


def _capitulation(close: pd.Series, volume: pd.Series) -> pd.Series:
    ret1 = close.pct_change(1)
    vol_ma = volume.rolling(21).mean()
    return (
        (ret1 <= -0.03) & (volume >= 2.0 * vol_ma) & ret1.notna() & vol_ma.notna()
    ).astype(float)


def build_behavior_features(
    prices: pd.DataFrame,
    spy_prices: pd.DataFrame,
    behavior: Optional[pd.DataFrame] = None,
    *,
    putcall_lag: bool = True,
) -> pd.DataFrame:
    """Build the 8 Muse behavior features aligned to `prices` sessions.

    `prices` / `spy_prices` should include history from ~2019 so trailing
    windows warm up; callers still filter training rows to 2021+.
    """
    if prices is None or prices.empty:
        return pd.DataFrame(columns=BEHAVIOR_FEATURE_ORDER)

    beh = behavior if behavior is not None else load_behavior_csv()
    px = prices.copy()
    if "date" in px.columns:
        px = px.set_index("date")
    px.index = px.index.astype(str)
    close = px["close"].astype(float)
    volume = px["volume"].astype(float)
    sessions = list(px.index)

    spy = spy_prices.copy()
    if "date" in spy.columns:
        spy = spy.set_index("date")
    spy.index = spy.index.astype(str)
    spy_close = spy["close"].astype(float)

    out = pd.DataFrame(index=px.index)

    if beh is None or beh.empty:
        vix_s = pd.Series(np.nan, index=sessions, dtype=float)
        aaii_spread = pd.Series(np.nan, index=sessions, dtype=float)
        pc_raw = pd.DataFrame(columns=["date", "putcall"])
    else:
        b = beh.copy()
        b["date"] = b["date"].astype(str)
        indexed = b.set_index("date")
        vix_s = indexed["vix_close"].astype(float).reindex(sessions)
        # Step 1 already publication-lag forward-filled AAII onto sessions
        aaii_spread = (
            indexed["aaii_bull"].astype(float) - indexed["aaii_bear"].astype(float)
        ).reindex(sessions)
        pc_raw = b.dropna(subset=["putcall"])[["date", "putcall"]]

    out["vix_close"] = vix_s.astype(float).values
    out["vix_chg5"] = vix_s.pct_change(5).astype(float).values
    out["vix_pct252"] = trailing_percentile(vix_s, 252).values

    pc_force = putcall_in_force(sessions, pc_raw, lag_one_session=putcall_lag)
    pc_num = pd.to_numeric(pc_force, errors="coerce")
    # When CBOE series is stale/missing (Doc fallback), keep putcall in the
    # exact feature order but impute a constant median of published values so
    # training rows are not dropped. Crowd_mood still ignores putcall on NA days.
    if pc_num.notna().any():
        _pc_fill = float(pc_num.median())
    else:
        _pc_fill = 1.0  # neutral-ish historical total P/C level
    out["putcall"] = pc_num.fillna(_pc_fill).values
    pc_pct = trailing_percentile(pc_num, 252)  # trailing on real values only

    spy_ret125 = spy_close.pct_change(125)
    spy_ret125.index = spy_ret125.index.astype(str)
    spy_ret125_pct = trailing_percentile(spy_ret125.reindex(sessions), 252)

    mood: list[float] = []
    global _PUTCALL_MISSING_LOGGED
    putcall_missing_any = False
    for i, _d in enumerate(sessions):
        vp = out["vix_pct252"].iloc[i]
        sp = spy_ret125_pct.iloc[i]
        pp = pc_pct.iloc[i]
        # putcall component only when real (non-imputed) trailing pct exists
        if pd.isna(pp):
            putcall_missing_any = True
            pp_arg: Optional[float] = None
        else:
            pp_arg = float(pp)
        # Warm-up: average whichever percentile components exist (VIX required).
        if pd.isna(vp):
            mood.append(float("nan"))
        elif pd.isna(sp):
            # SPY 125d×252 trailing not warm yet — VIX-only (± putcall) meter
            a = 100.0 * (1.0 - float(vp))
            if pp_arg is None:
                mood.append(a)
            else:
                b = 100.0 * (1.0 - float(pp_arg))
                mood.append((a + b) / 2.0)
        else:
            mood.append(crowd_mood_from_components(float(vp), pp_arg, float(sp)))
    if putcall_missing_any and not _PUTCALL_MISSING_LOGGED:
        _PUTCALL_MISSING_LOGGED = True
        print(
            "behavior_features: putcall missing on some sessions — "
            "crowd_mood uses VIX+SPY components only (Doc fallback)"
        )
    out["crowd_mood"] = mood
    out["aaii_spread"] = aaii_spread.astype(float).values
    out["capitulation_ticker"] = _capitulation(close, volume).values
    spy_vol = (
        spy["volume"].astype(float)
        if "volume" in spy.columns
        else pd.Series(1.0, index=spy.index)
    )
    out["capitulation_spy"] = (
        _capitulation(spy_close, spy_vol).reindex(sessions).fillna(0.0).astype(float).values
    )
    return out[BEHAVIOR_FEATURE_ORDER]
