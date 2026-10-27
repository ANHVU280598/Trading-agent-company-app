"""Settings — fake-data pass (H step 2). Live toggle locked. Save disabled until H6."""

from __future__ import annotations

import os

import streamlit as st

from core import fake_data
from core.components import sample_data_line
from core.config import (
    SETTINGS_APPLY_NOTE,
    SETTINGS_CONFIDENCE_CAPTION,
    SETTINGS_LIVE_CAPTION,
)
from core.ui import page_heading

page_heading("Settings")
sample_data_line()

cfg = fake_data.settings()

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("##### Watchlist")
    st.text_area(
        "Watchlist (one ticker per line)",
        value="\n".join(cfg["watchlist"]),  # type: ignore[arg-type]
        height=140,
        label_visibility="collapsed",
        disabled=True,
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
    st.slider(
        "Position size",
        min_value=5,
        max_value=50,
        value=int(float(cfg["position_size"]) * 100),
        disabled=True,
        format="%d%%",
    )
    st.slider(
        "Drawdown freeze",
        min_value=5,
        max_value=25,
        value=int(float(cfg["drawdown_freeze"]) * 100),
        disabled=True,
        format="%d%%",
    )
    st.slider(
        "Confidence threshold",
        min_value=0.50,
        max_value=0.80,
        value=float(cfg["confidence_threshold"]),
        step=0.01,
        disabled=True,
    )
    st.caption(SETTINGS_CONFIDENCE_CAPTION)

    def _status(ok: bool) -> str:
        if ok:
            return '<span style="color:#16C784;">Connected</span>'
        return '<span style="color:#848E9C;">Not connected</span>'

    alpaca_ok = bool(os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_API_SECRET"))
    finnhub_ok = bool(os.getenv("FINNHUB_API_KEY"))
    xai_ok = bool(os.getenv("XAI_API_KEY"))

    st.markdown("##### Data sources")
    st.markdown(f"Alpaca: {_status(alpaca_ok)}", unsafe_allow_html=True)
    st.markdown(f"Finnhub: {_status(finnhub_ok)}", unsafe_allow_html=True)
    st.markdown(f"xAI/Grok: {_status(xai_ok)}", unsafe_allow_html=True)

st.button("Save", disabled=True)
st.caption(SETTINGS_APPLY_NOTE)
st.caption("Skeleton save wiring is H step 6.")
