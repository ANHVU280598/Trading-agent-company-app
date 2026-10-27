"""Settings — empty-state skeleton (H step 1). Live toggle locked."""

from __future__ import annotations

import streamlit as st

from core.config import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_DRAWDOWN_FREEZE,
    DEFAULT_POSITION_SIZE,
    DEFAULT_WATCHLIST,
    SETTINGS_APPLY_NOTE,
    SETTINGS_CONFIDENCE_CAPTION,
    SETTINGS_LIVE_CAPTION,
)
from core.ui import page_heading

page_heading("Settings")

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("##### Watchlist")
    st.text_area(
        "Watchlist (one ticker per line)",
        value="\n".join(DEFAULT_WATCHLIST),
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
        value=int(DEFAULT_POSITION_SIZE * 100),
        disabled=True,
        format="%d%%",
    )
    st.slider(
        "Drawdown freeze",
        min_value=5,
        max_value=25,
        value=int(DEFAULT_DRAWDOWN_FREEZE * 100),
        disabled=True,
        format="%d%%",
    )
    st.slider(
        "Confidence threshold",
        min_value=0.50,
        max_value=0.80,
        value=float(DEFAULT_CONFIDENCE_THRESHOLD),
        step=0.01,
        disabled=True,
    )
    st.caption(SETTINGS_CONFIDENCE_CAPTION)
    st.markdown("##### Data sources")
    st.markdown(
        '<div class="tac-muted">Alpaca: Not connected</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="tac-muted">Finnhub: Not connected</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="tac-muted">xAI/Grok: Not connected</div>',
        unsafe_allow_html=True,
    )

st.button("Save", disabled=True)
st.caption(SETTINGS_APPLY_NOTE)
st.caption("Skeleton — settings save in H step 6.")
