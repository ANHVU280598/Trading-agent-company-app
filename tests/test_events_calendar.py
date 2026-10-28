"""Model v3 Step 1 — events calendar truth + sanity frequency tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from core.events_calendar import (
    EVENT_TYPES,
    _parse_bls_year_page,
    _parse_fomc_decision_days,
    build_nyse_holidays,
    build_opex,
    build_witching,
    counts_report,
)


FIXTURES = Path(__file__).parent / "fixtures"


def test_witching_four_per_year() -> None:
    rows = build_witching(date(2024, 1, 1), date(2024, 12, 31))
    assert len(rows) == 4
    assert [r.date for r in rows] == [
        "2024-03-15",
        "2024-06-21",
        "2024-09-20",
        "2024-12-20",
    ]


def test_opex_twelve_per_year() -> None:
    rows = build_opex(date(2024, 1, 1), date(2024, 12, 31))
    assert len(rows) == 12
    # March opex coincides with witching
    assert any(r.date == "2024-03-15" for r in rows)


def test_known_fomc_decision_day_2024_jan() -> None:
    html = """
    2024 FOMC Meetings
    January
    30-31
    Statement
    March
    19-20*
    Statement
    """
    days = _parse_fomc_decision_days(html)
    assert date(2024, 1, 31) in days
    assert date(2024, 3, 20) in days


def test_bls_year_page_parses_cpi_and_nfp() -> None:
    html = """
    <html><body>
    Friday, January 05, 2024 08:30 AM Employment Situation for December 2023
    Thursday, January 11, 2024 08:30 AM Consumer Price Index for December 2023
    Wednesday, March 20, 2024 10:00 AM Employment Situation of Veterans for Annual 2023
    </body></html>
    """
    rows = _parse_bls_year_page(html, 2024)
    types = {(r.date, r.type) for r in rows}
    assert ("2024-01-05", "nfp") in types
    assert ("2024-01-11", "cpi") in types
    # Veterans special release excluded
    assert ("2024-03-20", "nfp") not in types


def test_nyse_holidays_include_known_2024_dates() -> None:
    rows = build_nyse_holidays(date(2024, 1, 1), date(2024, 12, 31))
    dates = {r.date for r in rows}
    assert "2024-01-01" in dates  # New Year's
    assert "2024-03-29" in dates  # Good Friday 2024
    assert "2024-06-19" in dates  # Juneteenth
    assert "2024-11-28" in dates  # Thanksgiving
    assert "2024-12-25" in dates  # Christmas
    # roughly 10 full-day holidays with Juneteenth
    assert 9 <= len(rows) <= 11


def test_counts_report_sanity_deltas() -> None:
    fomc_dates = [
        "2024-01-31",
        "2024-03-20",
        "2024-05-01",
        "2024-06-12",
        "2024-07-31",
        "2024-09-18",
        "2024-11-07",
        "2024-12-18",
    ]
    opex_rows = build_opex(date(2024, 1, 1), date(2024, 12, 31))
    frame = pd.DataFrame(
        [{"date": d, "type": "fomc", "source": "t", "ticker": ""} for d in fomc_dates]
        + [
            {"date": d, "type": "witching", "source": "t", "ticker": ""}
            for d in ["2024-03-15", "2024-06-21", "2024-09-20", "2024-12-20"]
        ]
        + [
            {"date": r.date, "type": "opex", "source": "t", "ticker": ""}
            for r in opex_rows
        ]
    )
    report = counts_report(frame, 2024, 2024)
    y = report["by_year"]["2024"]
    assert y["fomc"] == 8
    assert y["witching"] == 4
    assert y["opex"] == 12
    assert y["_sanity_fomc_delta"] == 0
    assert y["_sanity_witching_delta"] == 0
    assert y["_sanity_opex_delta"] == 0
    assert set(EVENT_TYPES)


def test_events_csv_fixture_schema_if_present() -> None:
    """When data/events.csv exists (after refresh), schema must match."""
    path = Path(__file__).resolve().parents[1] / "data" / "events.csv"
    if not path.exists():
        return
    df = pd.read_csv(path, dtype=str).fillna("")
    assert list(df.columns) == ["date", "type", "source", "ticker"]
    assert set(df["type"].unique()).issubset(set(EVENT_TYPES))
