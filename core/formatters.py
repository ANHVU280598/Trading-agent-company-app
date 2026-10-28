"""Display formatters — USD, percents, dates (spec section C)."""

from __future__ import annotations

from typing import Optional


def money(value: Optional[float], cents: bool = True) -> str:
    if value is None:
        return "—"
    if cents:
        return f"${value:,.2f}"
    return f"${value:,.0f}"


def pct(value: Optional[float], signed: bool = True, digits: int = 1) -> str:
    if value is None:
        return "—"
    # value is a fraction (0.032 → +3.2%)
    x = value * 100.0
    if signed:
        return f"{x:+.{digits}f}%"
    return f"{x:.{digits}f}%"


def conf_pct(value: Optional[float], digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.{digits}f}%"


def dash(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float) and value != value:  # NaN
        return "—"
    return str(value)
