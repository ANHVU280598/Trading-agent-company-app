"""Plotly chart helpers matching the dark trading-terminal theme."""

from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.graph_objects as go


PANEL = "#161B22"
TEXT = "#EAECEF"
GRID = "#242B33"
GREEN = "#16C784"
MUTED = "#848E9C"
BLUE = "#4C8DFF"
RED = "#EA3943"
AMBER = "#E8B33D"


def _layout(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        paper_bgcolor=PANEL,
        plot_bgcolor=PANEL,
        font=dict(family="Inter, sans-serif", color=TEXT, size=12),
        margin=dict(l=40, r=20, t=30, b=40),
        height=height,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        xaxis=dict(gridcolor=GRID, zeroline=False, showgrid=True),
        yaxis=dict(gridcolor=GRID, zeroline=False, showgrid=True),
    )
    fig.update_layout(modebar_remove=["lasso2d", "select2d"])
    return fig


def portfolio_vs_benchmark(history: pd.DataFrame) -> go.Figure:
    """Green solid agent line, gray dashed benchmark."""
    fig = go.Figure()
    if history is None or history.empty:
        return _layout(fig)
    fig.add_trace(
        go.Scatter(
            x=history["date"],
            y=history["value"],
            name="Agent",
            line=dict(color=GREEN, width=2),
            mode="lines",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=history["date"],
            y=history["benchmark_value"],
            name="Buy & hold",
            line=dict(color=MUTED, width=2, dash="dash"),
            mode="lines",
        )
    )
    fig.update_layout(
        xaxis=dict(
            rangeselector=dict(
                buttons=[
                    dict(count=7, label="1W", step="day", stepmode="backward"),
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(count=3, label="3M", step="month", stepmode="backward"),
                    dict(step="all", label="All"),
                ],
                bgcolor=PANEL,
                activecolor=GREEN,
                font=dict(color=TEXT),
            ),
            rangeslider=dict(visible=False),
            type="date",
        )
    )
    return _layout(fig, height=380)


def price_with_markers(
    prices: pd.DataFrame,
    signals: Optional[pd.DataFrame] = None,
) -> go.Figure:
    """6-month price (blue) with BUY/SELL markers."""
    fig = go.Figure()
    if prices is None or prices.empty:
        return _layout(fig)
    fig.add_trace(
        go.Scatter(
            x=prices["date"],
            y=prices["close"],
            name="Close",
            line=dict(color=BLUE, width=2),
            mode="lines",
        )
    )
    if signals is not None and not signals.empty:
        buys = signals[signals["signal"] == "buy"]
        sells = signals[signals["signal"] == "sell"]
        if not buys.empty:
            fig.add_trace(
                go.Scatter(
                    x=buys["date"],
                    y=buys["price"],
                    name="BUY",
                    mode="markers",
                    marker=dict(symbol="triangle-up", size=10, color=GREEN),
                )
            )
        if not sells.empty:
            fig.add_trace(
                go.Scatter(
                    x=sells["date"],
                    y=sells["price"],
                    name="SELL",
                    mode="markers",
                    marker=dict(symbol="triangle-down", size=10, color=RED),
                )
            )
    return _layout(fig, height=320)


def walk_forward_bars(rows: pd.DataFrame, baseline: float) -> go.Figure:
    fig = go.Figure()
    if rows is None or rows.empty:
        return _layout(fig, height=280)
    fig.add_trace(
        go.Bar(
            x=rows["month"],
            y=rows["accuracy"] * 100,
            name="Accuracy",
            marker_color=GREEN,
        )
    )
    fig.add_hline(
        y=baseline * 100,
        line=dict(color=AMBER, width=1, dash="dash"),
        annotation_text="Baseline",
        annotation_position="top left",
        annotation_font_color=AMBER,
    )
    fig.update_yaxes(title_text="Accuracy %")
    return _layout(fig, height=280)


def feature_importance_bars(importance: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if importance is None or importance.empty:
        return _layout(fig, height=280)
    ordered = importance.sort_values("importance", ascending=True)
    fig.add_trace(
        go.Bar(
            x=ordered["importance"] * 100,
            y=ordered["feature"],
            orientation="h",
            marker_color=BLUE,
            hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
        )
    )
    return _layout(fig, height=320)
