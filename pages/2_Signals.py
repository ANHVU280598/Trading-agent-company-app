"""Signals — empty-state skeleton (H step 1)."""

from __future__ import annotations

import streamlit as st

from core.config import EMPTY_SIGNALS_COPY, SIGNAL_NOTE
from core.ui import empty_panel, page_heading

page_heading("Signals")
empty_panel(EMPTY_SIGNALS_COPY)
st.caption(SIGNAL_NOTE)
