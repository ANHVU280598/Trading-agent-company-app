"""Shared Streamlit chrome: CSS inject, page shell, empty panels."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.config import APP_NAME, STYLE_CSS


def inject_css(css_path: Path = STYLE_CSS) -> None:
    """Load assets/style.css into the Streamlit page."""
    if not css_path.exists():
        return
    css = css_path.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def configure_app() -> None:
    """Call once from app.py before st.navigation."""
    st.set_page_config(
        page_title=APP_NAME,
        layout="wide",
        initial_sidebar_state="expanded",
    )


def render_sidebar_brand() -> None:
    """App name at the top of the sidebar (above Streamlit nav)."""
    inject_css()
    with st.sidebar:
        st.markdown(
            f'<div class="tac-app-name">{APP_NAME}</div>',
            unsafe_allow_html=True,
        )


def render_sidebar_refresh() -> None:
    """Refresh data button at the bottom of the sidebar."""
    with st.sidebar:
        if st.button("Refresh data", use_container_width=True, key="refresh_data"):
            st.cache_data.clear()
            st.rerun()


def page_heading(title: str) -> None:
    st.markdown(f'<h1 class="tac-title">{title}</h1>', unsafe_allow_html=True)


def empty_panel(message: str) -> None:
    st.markdown(
        f'<div class="tac-panel-empty">{message}</div>',
        unsafe_allow_html=True,
    )


def error_banner(last_date: str) -> None:
    st.markdown(
        f'<div class="tac-banner-error">Data source unreachable — showing last '
        f"saved data from {last_date}.</div>",
        unsafe_allow_html=True,
    )
