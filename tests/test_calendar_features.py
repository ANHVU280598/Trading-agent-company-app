"""Model v3 Step 2 — calendar feature truth, frequency, leakage."""

from __future__ import annotations

from datetime import date

import pandas as pd

from core.calendar_features import (
    CALENDAR_FEATURE_ORDER,
    build_calendar_features,
    next_event_line,
    trading_days_index,
)
from core.events_calendar import load_events_csv
from core.features import FEATURE_ORDER_V1, FEATURE_ORDER_V3
from core.gate import evaluate_gate


def _events() -> pd.DataFrame:
    return load_events_csv()


def test_feature_order_v3_exact() -> None:
    assert FEATURE_ORDER_V3[:8] == FEATURE_ORDER_V1
    assert FEATURE_ORDER_V3[8:] == CALENDAR_FEATURE_ORDER
    assert len(FEATURE_ORDER_V3) == 26


def test_known_fomc_and_witching_flags() -> None:
    ev = _events()
    assert not ev.empty
    # 2024-01-31 is FOMC decision day from Fed calendar
    sessions = [date(2024, 1, 31), date(2024, 3, 15)]
    feats = build_calendar_features(sessions, ev, "AAPL")
    assert float(feats.loc["2024-01-31", "fomc_day"]) == 1.0
    assert float(feats.loc["2024-03-15", "witching_day"]) == 1.0
    assert float(feats.loc["2024-03-15", "opex_day"]) == 1.0


def test_fomc_day_fires_8_times_in_2024() -> None:
    ev = _events()
    holidays = set(ev.loc[ev["type"] == "holiday", "date"].tolist())
    sessions = trading_days_index(date(2024, 1, 1), date(2024, 12, 31), holidays)
    feats = build_calendar_features(sessions, ev, "AAPL")
    assert int(feats["fomc_day"].sum()) == 8
    assert int(feats["witching_day"].sum()) == 4
    assert int(feats["opex_day"].sum()) == 12


def test_santa_and_quarter_turn_frequencies_2024() -> None:
    ev = _events()
    holidays = set(ev.loc[ev["type"] == "holiday", "date"].tolist())
    sessions = trading_days_index(date(2024, 1, 1), date(2024, 12, 31), holidays)
    feats = build_calendar_features(sessions, ev, "MSFT")
    santa = int(feats["santa_window"].sum())
    qt = int(feats["quarter_turn"].sum())
    # Muse: santa ~7, quarter_turn ~20 — allow small tolerance
    assert 5 <= santa <= 9, santa
    assert 16 <= qt <= 24, qt


def test_pre_holiday_before_july4_2024() -> None:
    ev = _events()
    # 2024-07-04 holiday; prior session 2024-07-03 should be pre_holiday
    sessions = [date(2024, 7, 3), date(2024, 7, 5)]
    feats = build_calendar_features(sessions, ev, "AAPL")
    assert float(feats.loc["2024-07-03", "pre_holiday"]) == 1.0


def test_leakage_past_only_flags_ignore_future_event_deletes() -> None:
    """Day-T flags / just_reported must not depend on events after T.

    days_to_* intentionally use published future schedule (allowed by Muse);
    this test covers past/same-day fields.
    """
    ev = _events()
    t = date(2024, 6, 12)  # CPI day in 2024
    sessions = [t]
    full = build_calendar_features(sessions, ev, "AAPL")
    clipped = ev[ev["date"] <= t.isoformat()].copy()
    # Keep a stub future FOMC so days_to columns exist but flags should match
    past = build_calendar_features(sessions, clipped, "AAPL")
    for col in (
        "fomc_day",
        "cpi_day",
        "nfp_day",
        "witching_day",
        "opex_day",
        "january_flag",
        "september_flag",
        "may_oct_flag",
        "december_flag",
        "day_of_week",
        "just_reported",
        "quarter_turn",
        "santa_window",
        "pre_holiday",
    ):
        assert float(full.loc["2024-06-12", col]) == float(past.loc["2024-06-12", col])


def test_gate_pass_and_fail() -> None:
    base = {
        "accuracy": 0.55,
        "buy_precision": 0.40,
        "sell_precision": 0.35,
        "walk_forward": [{"month": "2024-01", "accuracy": 0.50}],
    }
    good = {
        "accuracy": 0.56,
        "buy_precision": 0.41,
        "sell_precision": 0.35,
        "walk_forward": [{"month": "2024-01", "accuracy": 0.51}],
    }
    bad = {
        "accuracy": 0.54,
        "buy_precision": 0.50,
        "sell_precision": 0.50,
        "walk_forward": [{"month": "2024-01", "accuracy": 0.50}],
    }
    assert evaluate_gate(base, good).passed
    assert not evaluate_gate(base, bad).passed


def test_next_event_line_formats() -> None:
    ev = _events()
    # On a witching day
    line = next_event_line("2024-03-15", "AAPL", ev)
    assert "Witching" in line or "FOMC" in line or "CPI" in line or "Earnings" in line
