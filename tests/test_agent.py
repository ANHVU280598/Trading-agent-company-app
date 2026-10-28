"""Paper agent rule tests (spec section M)."""

from __future__ import annotations

from core.agent import buys_frozen, confidence_gate, position_buy_shares


def test_confidence_gate_at_threshold_trades() -> None:
    assert confidence_gate("buy", 0.55, 0.55) == "buy"
    assert confidence_gate("sell", 0.55, 0.55) == "sell"


def test_confidence_gate_below_threshold_holds() -> None:
    assert confidence_gate("buy", 0.54, 0.55) == "hold"
    assert confidence_gate("sell", 0.549, 0.55) == "hold"


def test_confidence_gate_hold_stays_hold() -> None:
    assert confidence_gate("hold", 0.99, 0.55) == "hold"


def test_freeze_exactly_at_threshold_freezes() -> None:
    assert buys_frozen(-0.10, 0.10) is True
    assert buys_frozen(-0.099, 0.10) is False
    assert buys_frozen(-0.11, 0.10) is True


def test_freeze_still_allows_sell_path() -> None:
    # Freeze only blocks buys; sell path is caller's responsibility.
    # Gate itself does not rewrite sell when frozen — agent script checks freeze.
    assert confidence_gate("sell", 0.70, 0.55) == "sell"
    assert buys_frozen(-0.12, 0.10) is True


def test_position_sizing_20_percent() -> None:
    shares = position_buy_shares(100_000.0, 100_000.0, 200.0, 0.20)
    assert shares == 100.0


def test_position_sizing_cash_shortfall() -> None:
    shares = position_buy_shares(100_000.0, 1_000.0, 200.0, 0.20)
    assert shares == 5.0


def test_position_sizing_skips_tiny_cash() -> None:
    assert position_buy_shares(100_000.0, 9.99, 10.0, 0.20) == 0.0
