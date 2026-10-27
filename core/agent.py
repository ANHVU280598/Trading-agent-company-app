"""Paper trading rules: position size, freeze, confidence gate."""

from __future__ import annotations


def confidence_gate(
    signal: str,
    confidence: float,
    threshold: float = 0.55,
) -> str:
    """BUY/SELL only trade when confidence >= threshold; else HOLD for trading."""
    raw = signal.lower()
    if raw not in {"buy", "sell", "hold"}:
        return "hold"
    if raw == "hold":
        return "hold"
    if confidence >= threshold:
        return raw
    return "hold"


def buys_frozen(drawdown: float, freeze: float = 0.10) -> bool:
    """True when drawdown from high-water is at or beyond the freeze fraction.

    drawdown is <= 0 (e.g. -0.10). Freeze is a positive fraction (0.10 = 10%).
    Exactly at the freeze level freezes buys.
    """
    if freeze < 0:
        return False
    return drawdown <= -abs(freeze)


def position_buy_shares(
    portfolio_value: float,
    cash: float,
    price: float,
    position_size: float = 0.20,
) -> float:
    """Shares to buy: position_size % of portfolio, capped by cash; 4 decimals.

    Skip (return 0.0) when cash is under $10.00 or price is non-positive.
    """
    if price <= 0 or cash < 10.0:
        return 0.0
    target = portfolio_value * position_size
    spend = min(target, cash)
    if spend < 10.0:
        return 0.0
    return round(spend / price, 4)
