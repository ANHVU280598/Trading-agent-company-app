"""Settings — save to SQLite; Live locked (H step 6)."""

from __future__ import annotations

import re

import streamlit as st

from core.config import (
    SETTINGS_APPLY_NOTE,
    SETTINGS_CONFIDENCE_CAPTION,
    SETTINGS_LIVE_CAPTION,
    SETTINGS_SAVED,
)
from core.repository import keys_connected, load_settings, save_settings
from core.ui import page_heading

page_heading("Settings")

cfg = load_settings()
connected = keys_connected()

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("##### Watchlist")
    watch_text = st.text_area(
        "Watchlist (one ticker per line)",
        value="\n".join(cfg["watchlist"]),
        height=140,
        label_visibility="collapsed",
    )
    st.markdown("##### Trading mode")
    st.radio(
        "Trading mode",
        options=["Paper", "Live"],
        index=0,
        horizontal=True,
        disabled=True,
        label_visibility="collapsed",
    )
    st.caption(SETTINGS_LIVE_CAPTION)

with col_right:
    st.markdown("##### Risk")
    pos = st.slider(
        "Position size",
        min_value=5,
        max_value=50,
        value=int(round(float(cfg["position_size"]) * 100)),
        format="%d%%",
    )
    freeze = st.slider(
        "Drawdown freeze",
        min_value=5,
        max_value=25,
        value=int(round(float(cfg["drawdown_freeze"]) * 100)),
        format="%d%%",
    )
    conf = st.slider(
        "Confidence threshold",
        min_value=0.50,
        max_value=0.80,
        value=float(cfg["confidence_threshold"]),
        step=0.01,
    )
    st.caption(SETTINGS_CONFIDENCE_CAPTION)

    def _status(ok: bool) -> str:
        if ok:
            return '<span style="color:#16C784;">Connected</span>'
        return '<span style="color:#848E9C;">Not connected</span>'

    st.markdown("##### Data sources")
    st.markdown(f"Alpaca: {_status(connected['alpaca'])}", unsafe_allow_html=True)
    st.markdown(f"Finnhub: {_status(connected['finnhub'])}", unsafe_allow_html=True)
    st.markdown(f"xAI/Grok: {_status(connected['xai'])}", unsafe_allow_html=True)

if st.button("Save"):
    lines = [ln.strip().upper() for ln in watch_text.splitlines()]
    lines = [ln for ln in lines if ln]
    # dedupe keep first
    seen: set[str] = set()
    tickers: list[str] = []
    for t in lines:
        if t not in seen:
            seen.add(t)
            tickers.append(t)
    bad = [t for t in tickers if not re.fullmatch(r"[A-Z]{1,5}", t)]
    if bad:
        st.markdown(
            '<div class="tac-banner-error">Check the watchlist: tickers are 1–5 letters, '
            "one per line.</div>",
            unsafe_allow_html=True,
        )
    else:
        save_settings(
            tickers,
            position_size=pos / 100.0,
            drawdown_freeze=freeze / 100.0,
            confidence_threshold=float(conf),
        )
        st.markdown(
            f'<span style="color:#16C784;">{SETTINGS_SAVED}</span>',
            unsafe_allow_html=True,
        )

st.caption(SETTINGS_APPLY_NOTE)
