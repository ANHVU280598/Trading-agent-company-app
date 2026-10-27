"""Trades — fake-data pass (H step 2)."""

from __future__ import annotations

import streamlit as st

from core import fake_data
from core.components import colored_pnl, kpi_card, sample_data_line, signal_badge
from core.formatters import conf_pct, money
from core.ui import empty_panel, page_heading

page_heading("Trades")
sample_data_line()

trades = fake_data.trades().copy()
tickers = ["All"] + fake_data.WATCHLIST
actions = ["All", "Buy", "Sell"]

f1, f2, f3, f4 = st.columns(4)
with f1:
    ticker_f = st.selectbox("Ticker", tickers)
with f2:
    action_f = st.selectbox("Action", actions)
with f3:
    date_from = st.date_input("From", value=None)
with f4:
    date_to = st.date_input("To", value=None)

filtered = trades
if ticker_f != "All":
    filtered = filtered[filtered["ticker"] == ticker_f]
if action_f != "All":
    filtered = filtered[filtered["action"] == action_f.lower()]
if date_from is not None:
    filtered = filtered[filtered["date"] >= date_from.isoformat()]
if date_to is not None:
    filtered = filtered[filtered["date"] <= date_to.isoformat()]

if trades.empty:
    empty_panel("No trades yet. The agent is watching.")
elif filtered.empty:
    empty_panel("No trades match these filters.")
    s1, s2, s3, s4, s5 = st.columns(5)
    with s1:
        kpi_card("Trades", "0")
    with s2:
        kpi_card("Win rate", "—")
    with s3:
        kpi_card("Realized P/L", "$0.00")
    with s4:
        kpi_card("Best", "—")
    with s5:
        kpi_card("Worst", "—")
else:
    closed = filtered[filtered["status"] == "Closed"]
    wins = closed[closed["realized_pnl"].fillna(0) > 0]
    win_rate = (len(wins) / len(closed)) if len(closed) else None
    total_pnl = float(closed["realized_pnl"].fillna(0).sum()) if len(closed) else 0.0
    best = closed.loc[closed["realized_pnl"].idxmax()] if len(closed) else None
    worst = closed.loc[closed["realized_pnl"].idxmin()] if len(closed) else None

    s1, s2, s3, s4, s5 = st.columns(5)
    with s1:
        kpi_card("Trades", str(len(filtered)))
    with s2:
        kpi_card("Win rate", "—" if win_rate is None else f"{win_rate * 100:.1f}%")
    with s3:
        kpi_card("Realized P/L", colored_pnl(total_pnl))
    with s4:
        if best is None:
            kpi_card("Best", "—")
        else:
            kpi_card("Best", f"{best['ticker']} {colored_pnl(float(best['realized_pnl']))}")
    with s5:
        if worst is None:
            kpi_card("Worst", "—")
        else:
            kpi_card("Worst", f"{worst['ticker']} {colored_pnl(float(worst['realized_pnl']))}")

    show = filtered.sort_values(["date", "id"], ascending=[False, False])
    rows = []
    for _, t in show.iterrows():
        pnl = t["realized_pnl"]
        pnl_html = "—" if pnl is None or (isinstance(pnl, float) and pnl != pnl) else colored_pnl(float(pnl))
        rows.append(
            "<tr>"
            f"<td>{t['date']}</td>"
            f"<td>{t['ticker']}</td>"
            f"<td>{signal_badge(str(t['action']))}</td>"
            f"<td class='tac-num'>{float(t['shares']):.4f}</td>"
            f"<td class='tac-num'>{money(float(t['price']))}</td>"
            f"<td class='tac-num'>{conf_pct(float(t['confidence']))}</td>"
            f"<td>{t['status']}</td>"
            f"<td>{pnl_html}</td>"
            "</tr>"
        )
    st.markdown(
        f"""
        <div class="tac-panel">
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <thead><tr class="tac-muted">
            <th align="left">Date</th><th align="left">Ticker</th>
            <th align="left">Action</th><th align="right">Shares</th>
            <th align="right">Price</th><th align="right">Conf</th>
            <th align="left">Status</th><th align="right">P/L</th>
          </tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
        </div>
        """,
        unsafe_allow_html=True,
    )
