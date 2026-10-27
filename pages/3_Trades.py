"""Trades — empty-state skeleton (H step 1)."""

from __future__ import annotations

import streamlit as st

from core.config import EMPTY_TRADES_COPY
from core.ui import empty_panel, page_heading

page_heading("Trades")
empty_panel(EMPTY_TRADES_COPY)
