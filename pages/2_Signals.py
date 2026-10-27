"""Signals — fake-data pass (H step 2)."""

from __future__ import annotations

import streamlit as st

from core import fake_data
from core.charts import price_with_markers
from core.components import (
    prob_bars,
    sample_data_line,
    sentiment_html,
    signal_badge,
)
from core.config import SIGNAL_NOTE
from core.formatters import conf_pct, money, pct
from core.ui import empty_panel, page_heading

page_heading("Signals")
sample_data_line()

signals = fake_data.signals_latest()
st.markdown(
    f'<div class="tac-muted" style="text-transform:none;letter-spacing:0;margin-bottom:12px;">'
    f'Signals for {fake_data.SAMPLE_AS_OF} (last close)</div>',
    unsafe_allow_html=True,
)

if signals.empty:
    empty_panel("No signals yet. Run paper_trade.py once, then refresh.")
else:
    tickers = [str(t) for t in signals["ticker"].tolist()]
    selected = st.selectbox("Ticker detail", tickers, index=0)

    header = (
        "<tr class='tac-muted'>"
        "<th align='left'>Ticker</th><th align='left'>Signal</th>"
        "<th align='right'>Conf</th><th align='left'>Buy/Hold/Sell</th>"
        "<th align='right'>Price</th><th align='right'>RSI</th>"
        "<th align='right'>DD63d</th><th align='right'>Sentiment</th>"
        "<th align='left'>Top headline</th></tr>"
    )
    body = []
    for _, row in signals.iterrows():
        conf = max(float(row["buy_p"]), float(row["hold_p"]), float(row["sell_p"]))
        body.append(
            "<tr>"
            f"<td>{row['ticker']}</td>"
            f"<td>{signal_badge(str(row['signal']))}</td>"
            f"<td class='tac-num'>{conf_pct(conf)}</td>"
            f"<td>{prob_bars(float(row['buy_p']), float(row['hold_p']), float(row['sell_p']))}</td>"
            f"<td class='tac-num'>{money(float(row['price']))}</td>"
            f"<td class='tac-num'>{float(row['rsi14']):.0f}</td>"
            f"<td class='tac-num'>{pct(float(row['drawdown63']))}</td>"
            f"<td>{sentiment_html(None if row['sentiment'] is None else float(row['sentiment']))}</td>"
            f"<td>{row['headline']}</td>"
            "</tr>"
        )
    st.markdown(
        f'<div class="tac-panel"><table style="width:100%;border-collapse:collapse;font-size:14px;">'
        f"{header}{''.join(body)}</table></div>",
        unsafe_allow_html=True,
    )

    st.caption(SIGNAL_NOTE)

    st.markdown(f'<div class="tac-section">Ticker detail: {selected}</div>', unsafe_allow_html=True)
    prices = fake_data.price_history(selected)
    markers = fake_data.signal_history(selected)
    st.plotly_chart(
        price_with_markers(prices, markers),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    feats = fake_data.feature_values(selected)
    left, right = st.columns(2)

    def _fmt_feat(name: str, value: object) -> str:
        if value is None:
            return "—"
        if name in {"ret1", "ret5", "ret21", "dist_ma50", "drawdown63", "vol21"}:
            return pct(float(value))
        if name == "rsi14":
            return f"{float(value):.0f}"
        if name == "volz":
            return f"{float(value):.2f}"
        if name == "sentiment":
            return f"{float(value):.2f}"
        return str(value)

    items = list(feats.items())
    mid = (len(items) + 1) // 2
    with left:
        for k, v in items[:mid]:
            st.markdown(
                f'<div class="tac-muted">{k}</div><div class="tac-body tac-num">{_fmt_feat(k, v)}</div>',
                unsafe_allow_html=True,
            )
    with right:
        for k, v in items[mid:]:
            st.markdown(
                f'<div class="tac-muted">{k}</div><div class="tac-body tac-num">{_fmt_feat(k, v)}</div>',
                unsafe_allow_html=True,
            )
