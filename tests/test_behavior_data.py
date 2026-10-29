"""Model v4 Step 1 — behavior data lag + composite primitives."""

from __future__ import annotations

import pandas as pd

from core.behavior_data import (
    BEHAVIOR_COLUMNS,
    forward_fill_aaii_to_sessions,
    putcall_in_force,
)


def test_aaii_publication_lag_never_earlier() -> None:
    """AAII published on day P must not affect any feature dated before P."""
    aaii = pd.DataFrame(
        {
            "date": ["2024-01-04", "2024-01-11"],
            "aaii_bull": [40.0, 55.0],
            "aaii_bear": [30.0, 25.0],
        }
    )
    sessions = [
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
        "2024-01-08",
        "2024-01-09",
        "2024-01-10",
        "2024-01-11",
        "2024-01-12",
    ]
    filled = forward_fill_aaii_to_sessions(sessions, aaii)
    # Before first publication → NA
    assert pd.isna(filled.loc["2024-01-02", "aaii_bull"])
    assert pd.isna(filled.loc["2024-01-03", "aaii_bull"])
    # On/after 2024-01-04 → 40
    assert float(filled.loc["2024-01-04", "aaii_bull"]) == 40.0
    assert float(filled.loc["2024-01-10", "aaii_bull"]) == 40.0
    # On/after 2024-01-11 → 55
    assert float(filled.loc["2024-01-11", "aaii_bull"]) == 55.0
    assert float(filled.loc["2024-01-12", "aaii_bear"]) == 25.0


def test_putcall_one_session_lag() -> None:
    """Day T uses T-1 put/call when lag_one_session=True (post-close publish)."""
    pc = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03", "2024-01-04"],
            "putcall": [0.8, 0.9, 1.1],
        }
    )
    sessions = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
    lagged = putcall_in_force(sessions, pc, lag_one_session=True)
    assert pd.isna(lagged.loc["2024-01-02"])
    assert float(lagged.loc["2024-01-03"]) == 0.8
    assert float(lagged.loc["2024-01-04"]) == 0.9
    assert float(lagged.loc["2024-01-05"]) == 1.1


def test_behavior_columns_contract() -> None:
    assert BEHAVIOR_COLUMNS == [
        "date",
        "vix_close",
        "putcall",
        "aaii_bull",
        "aaii_bear",
    ]
