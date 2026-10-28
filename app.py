"""Trading Agent Company App — Streamlit entry (H step 1 skeleton)."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
import streamlit as st

from core.ui import configure_app, render_sidebar_brand, render_sidebar_refresh

load_dotenv(Path(__file__).resolve().parent / ".env")
configure_app()
render_sidebar_brand()

dashboard = st.Page("pages/1_Dashboard.py", title="Dashboard", default=True)
signals = st.Page("pages/2_Signals.py", title="Signals")
trades = st.Page("pages/3_Trades.py", title="Trades")
model = st.Page("pages/4_Model.py", title="Model")
settings = st.Page("pages/5_Settings.py", title="Settings")

pg = st.navigation(
    [dashboard, signals, trades, model, settings],
    position="sidebar",
)
pg.run()
render_sidebar_refresh()
