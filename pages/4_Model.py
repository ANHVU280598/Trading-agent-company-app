"""Model — empty-state skeleton (H step 1)."""

from __future__ import annotations

import streamlit as st

from core.config import MODEL_HONESTY
from core.ui import page_heading

page_heading("Model")
st.markdown(
    f'<div class="tac-honesty">{MODEL_HONESTY}</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="tac-panel-empty">—</div>',
    unsafe_allow_html=True,
)
