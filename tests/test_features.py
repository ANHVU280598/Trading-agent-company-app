"""Feature / label rule tests (spec section M / Phase 4)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.features import FEATURE_ORDER_V2, build_features_v2, make_labels


def _prices_from_returns(returns: list[float], start: float = 100.0) -> pd.DataFrame:
    closes = [start]
    for r in returns:
        closes.append(closes[-1] * (1.0 + r))
    return pd.DataFrame({"close": closes, "volume": [1_000_000] * len(closes)})


def _synth_bars(n: int = 80, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-02", periods=n).astype(str)
    close = 100 * np.cumprod(1 + rng.normal(0, 0.01, size=n))
    return pd.DataFrame(
        {"date": dates, "close": close, "volume": rng.integers(1e6, 2e6, size=n)}
    ).set_index("date")


def test_v2_feature_order_and_spy_regime() -> None:
    prices = _synth_bars()
    spy = _synth_bars(seed=2)
    sent = pd.Series({"2024-01-03": 0.5})
    hc = pd.Series({"2024-01-03": 4})
    feats = build_features_v2(prices, spy.reset_index(), sentiment=sent, headline_count=hc)
    assert list(feats.columns) == FEATURE_ORDER_V2
    # Missing days → 0 sentiment / 0 headlines
    assert float(feats.loc["2024-01-02", "sentiment"]) == 0.0
    assert float(feats.loc["2024-01-02", "headline_count"]) == 0.0
    assert float(feats.loc["2024-01-03", "sentiment"]) == 0.5
    assert float(feats.loc["2024-01-03", "headline_count"]) == 4.0
    assert set(feats["spy_regime"].dropna().unique()).issubset({0.0, 1.0})


def test_leakage_future_sentiment_does_not_change_day_t() -> None:
    """Day T features must ignore sentiment rows dated after T."""
    prices = _synth_bars()
    spy = _synth_bars(seed=3)
    day_t = str(prices.index[60])
    sent_clean = pd.Series({day_t: 0.2})
    hc_clean = pd.Series({day_t: 3})
    # Inject "future" news after day T — must not affect day T row
    sent_leak = sent_clean.copy()
    hc_leak = hc_clean.copy()
    for d in prices.index[61:65]:
        sent_leak.loc[str(d)] = 0.99
        hc_leak.loc[str(d)] = 99
    a = build_features_v2(prices, spy.reset_index(), sentiment=sent_clean, headline_count=hc_clean)
    b = build_features_v2(prices, spy.reset_index(), sentiment=sent_leak, headline_count=hc_leak)
    pd.testing.assert_series_equal(a.loc[day_t], b.loc[day_t])


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
