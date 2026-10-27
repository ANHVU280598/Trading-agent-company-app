"""Feature / label rule tests (spec section M)."""

from __future__ import annotations

import pandas as pd

from core.features import make_labels


def _prices_from_returns(returns: list[float], start: float = 100.0) -> pd.DataFrame:
    closes = [start]
    for r in returns:
        closes.append(closes[-1] * (1.0 + r))
    return pd.DataFrame({"close": closes, "volume": [1_000_000] * len(closes)})


def test_label_exact_plus_3_percent_is_hold() -> None:
    # Forward 5d return exactly +3.0% → hold (not buy).
    closes = [100.0] * 10
    closes[5] = 103.0
    prices = pd.DataFrame({"close": closes, "volume": [1.0] * 10})
    labels = make_labels(prices)
    assert labels.iloc[0] == "hold"


def test_label_above_3_percent_is_buy() -> None:
    closes = [100.0] * 10
    closes[5] = 103.1
    prices = pd.DataFrame({"close": closes, "volume": [1.0] * 10})
    labels = make_labels(prices)
    assert labels.iloc[0] == "buy"


def test_label_exact_minus_3_percent_is_hold() -> None:
    closes = [100.0] * 10
    closes[5] = 97.0
    prices = pd.DataFrame({"close": closes, "volume": [1.0] * 10})
    labels = make_labels(prices)
    assert labels.iloc[0] == "hold"


def test_label_below_minus_3_percent_is_sell() -> None:
    closes = [100.0] * 10
    closes[5] = 96.9
    prices = pd.DataFrame({"close": closes, "volume": [1.0] * 10})
    labels = make_labels(prices)
    assert labels.iloc[0] == "sell"
