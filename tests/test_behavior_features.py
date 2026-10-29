"""Model v4 Steps 2–3 tests — trailing-only, lag, composite, exam smoke."""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.behavior_features import (
    BEHAVIOR_FEATURE_ORDER,
    build_behavior_features,
    crowd_mood_from_components,
    trailing_percentile,
)
from core.features import FEATURE_ORDER_V1, FEATURE_ORDER_V4


def test_feature_order_v4() -> None:
    assert FEATURE_ORDER_V4[:8] == FEATURE_ORDER_V1
    assert FEATURE_ORDER_V4[8:] == BEHAVIOR_FEATURE_ORDER
    assert len(FEATURE_ORDER_V4) == 16


def test_crowd_mood_composite_hand_computed() -> None:
    # vix_pct=0.8 → a=20; putcall_pct=0.7 → b=30; spy_pct=0.4 → c=40; avg=30
    assert abs(crowd_mood_from_components(0.8, 0.7, 0.4) - 30.0) < 1e-9
    # missing putcall → (20+40)/2 = 30
    assert abs(crowd_mood_from_components(0.8, None, 0.4) - 30.0) < 1e-9


def test_trailing_only_no_lookahead() -> None:
    """Fake future VIX after day T must not change vix_pct252 / crowd_mood at T."""
    # Need ~125 + 252 sessions for spy_ret125 trailing percentile to warm up
    n = 450
    dates = pd.bdate_range("2022-01-03", periods=n)
    rng = np.random.default_rng(7)
    vix = 15 + rng.normal(0, 2, size=n).cumsum() * 0.01
    spy_close = 400 + rng.normal(0, 1, size=n).cumsum()
    beh = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "vix_close": vix,
            "putcall": np.nan,
            "aaii_bull": 40.0,
            "aaii_bear": 30.0,
        }
    )
    prices = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "close": spy_close,
            "volume": rng.integers(1_000_000, 2_000_000, size=n),
        }
    )
    spy = prices.copy()
    feats = build_behavior_features(
        prices.set_index("date"), spy.set_index("date"), behavior=beh
    )
    t = dates[400].strftime("%Y-%m-%d")
    before_pct = float(feats.loc[t, "vix_pct252"])
    before_mood = float(feats.loc[t, "crowd_mood"])
    assert before_pct == before_pct  # not NaN
    assert before_mood == before_mood

    # Inject huge future VIX after T
    beh2 = beh.copy()
    future_mask = beh2["date"] > t
    beh2.loc[future_mask, "vix_close"] = 80.0
    feats2 = build_behavior_features(
        prices.set_index("date"), spy.set_index("date"), behavior=beh2
    )
    assert abs(float(feats2.loc[t, "vix_pct252"]) - before_pct) < 1e-12
    assert abs(float(feats2.loc[t, "crowd_mood"]) - before_mood) < 1e-9


def test_aaii_lag_via_behavior_table() -> None:
    """Publication-lag: AAII published on P must not affect features before P.

    Behavior table stores session-forward-filled AAII from Step 1; simulate by
    leaving early sessions NA then filling from P.
    """
    dates = pd.bdate_range("2024-01-02", periods=10)
    beh = pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "vix_close": 15.0,
            "putcall": np.nan,
            "aaii_bull": [np.nan, np.nan, 40.0, 40.0, 40.0, 55.0, 55.0, 55.0, 55.0, 55.0],
            "aaii_bear": [np.nan, np.nan, 30.0, 30.0, 30.0, 25.0, 25.0, 25.0, 25.0, 25.0],
        }
    )
    # Need long history for trailing windows — pad with earlier sessions
    pad = pd.bdate_range("2022-01-03", periods=260)
    pad_beh = pd.DataFrame(
        {
            "date": pad.strftime("%Y-%m-%d"),
            "vix_close": 18.0,
            "putcall": np.nan,
            "aaii_bull": 35.0,
            "aaii_bear": 35.0,
        }
    )
    beh = pd.concat([pad_beh, beh], ignore_index=True)
    prices = pd.DataFrame(
        {
            "date": beh["date"],
            "close": np.linspace(100, 120, len(beh)),
            "volume": 1_000_000,
        }
    )
    feats = build_behavior_features(
        prices.set_index("date"), prices.set_index("date"), behavior=beh
    )
    # First two Jan sessions still NA for aaii in table → spread NA
    assert pd.isna(feats.loc["2024-01-02", "aaii_spread"])
    assert pd.isna(feats.loc["2024-01-03", "aaii_spread"])
    assert float(feats.loc["2024-01-04", "aaii_spread"]) == 10.0  # 40-30
    assert float(feats.loc["2024-01-09", "aaii_spread"]) == 30.0  # 55-25


def test_exam_smoke_crowd_mood_aug2024() -> None:
    """crowd_mood on 2024-08-05..07 must print under 40 (VIX spike week)."""
    from core.behavior_data import load_behavior_csv
    from core.data import get_daily_bars

    beh = load_behavior_csv()
    if beh.empty:
        return  # skip if fixtures missing in bare env
    spy = get_daily_bars("SPY", "2019-01-01", "2024-08-15")
    if spy.empty:
        return
    indexed = spy.set_index("date")
    indexed.index = indexed.index.astype(str)
    feats = build_behavior_features(indexed, indexed, behavior=beh)
    for d in ("2024-08-05", "2024-08-06", "2024-08-07"):
        if d not in feats.index:
            continue
        mood = feats.loc[d, "crowd_mood"]
        if pd.isna(mood):
            continue
        assert float(mood) < 40.0, f"{d} crowd_mood={mood}"
