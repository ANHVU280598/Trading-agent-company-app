"""Reusable UI fragments: badges, KPI cards, banners."""

from __future__ import annotations

from typing import Optional

import streamlit as st

from core.formatters import money, pct


def sample_data_line() -> None:
    st.markdown(
        '<div class="tac-muted" style="margin-bottom:12px;">Sample data</div>',
        unsafe_allow_html=True,
    )


def signal_badge(signal: str) -> str:
    s = (signal or "hold").lower()
    cls = {"buy": "badge-buy", "sell": "badge-sell", "hold": "badge-hold"}.get(s, "badge-hold")
    return f'<span class="{cls}">{s.upper()}</span>'


def kpi_card(label: str, value_html: str, sub_html: str = "") -> None:
    st.markdown(
        f"""
        <div class="tac-panel">
          <div class="tac-muted">{label}</div>
          <div class="tac-kpi">{value_html}</div>
          <div class="tac-body">{sub_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def market_status(is_open: bool) -> str:
    if is_open:
        return (
            '<span style="color:#16C784;">●</span> '
            '<span class="tac-body">Market open</span>'
        )
    return (
        '<span style="color:#848E9C;">●</span> '
        '<span class="tac-body">Market closed</span>'
    )


def colored_pnl(value: Optional[float], as_pct: bool = False) -> str:
    if value is None:
        return "—"
    color = "#16C784" if value >= 0 else "#EA3943"
    text = pct(value) if as_pct else money(value)
    sign_ok = True
    _ = sign_ok
    return f'<span style="color:{color}; font-variant-numeric:tabular-nums;">{text}</span>'


def prob_bars(buy_p: float, hold_p: float, sell_p: float) -> str:
    def seg(p: float, color: str) -> str:
        w = max(2, int(round(p * 100)))
        return (
            f'<span style="display:inline-block;width:{w}px;height:10px;'
            f'background:{color};margin-right:2px;border-radius:2px;"></span>'
        )

    return (
        '<span style="white-space:nowrap;">'
        f"{seg(buy_p, '#16C784')}{seg(hold_p, '#E8B33D')}{seg(sell_p, '#EA3943')}"
        "</span>"
    )


def market_regime_chip(spy_regime: Optional[float | int]) -> str:
    """Phase 4 Step 5: Market up/down from spy_regime (1 / 0)."""
    if spy_regime is None or (isinstance(spy_regime, float) and spy_regime != spy_regime):
        return '<span class="tac-muted">Market: —</span>'
    up = int(spy_regime) == 1
    color = "#16C784" if up else "#EA3943"
    label = "up" if up else "down"
    return (
        f'<span style="color:{color};font-weight:600;">Market: {label}</span>'
    )


def sentiment_html(value: Optional[float]) -> str:
    if value is None:
        return "—"
    if value > 0.2:
        color = "#16C784"
    elif value < -0.2:
        color = "#EA3943"
    else:
        color = "#848E9C"
    return f'<span style="color:{color};">{value:+.2f}</span>'
