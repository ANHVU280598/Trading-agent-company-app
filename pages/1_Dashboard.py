"""Dashboard — reads SQLite via repository (H step 4)."""

from __future__ import annotations

import streamlit as st

from core.charts import portfolio_vs_benchmark
from core.components import colored_pnl, kpi_card, market_status, signal_badge
from core.formatters import money, pct
from core.repository import latest_signals, portfolio_meta, positions_with_prices
from core.ui import empty_panel, page_heading

page_heading("Dashboard")

with st.spinner("Loading latest data…"):
    meta = portfolio_meta()
    signals = latest_signals()
    positions = positions_with_prices()

top_l, top_r = st.columns([3, 2])
with top_l:
    st.markdown(market_status(bool(meta.get("market_open"))), unsafe_allow_html=True)
with top_r:
    st.markdown(
        f'<div class="tac-muted" style="text-align:right;text-transform:none;'
        f'letter-spacing:0;">Last updated {meta.get("last_updated", "—")}</div>',
        unsafe_allow_html=True,
    )

if meta.get("buys_frozen"):
    dd_pct = abs(float(meta["drawdown"]) * 100)
    st.markdown(
        f'<div class="tac-banner-frozen">Buys frozen — portfolio is down '
        f"{dd_pct:.1f}% from its high. Sells still allowed.</div>",
        unsafe_allow_html=True,
    )

if meta.get("empty"):
    empty_panel("No trades yet. The agent is watching.")
else:
    delta = float(meta["agent_ret"]) - float(meta["bench_ret"])
    if delta >= 0:
        verdict = f'<span style="color:#16C784;">Ahead by {delta * 100:.1f} pts</span>'
    else:
        verdict = (
            f'<span style="color:#EA3943;">Behind by {abs(delta) * 100:.1f} pts</span>'
        )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card(
            "Portfolio value",
            money(float(meta["portfolio_value"]), cents=False),
            f'{colored_pnl(float(meta["portfolio_ret"]), as_pct=True)} since {meta["start_date"]}',
        )
    with c2:
        kpi_card(
            "vs Benchmark",
            verdict,
            f'Agent {pct(float(meta["agent_ret"]))} · Buy &amp; hold {pct(float(meta["bench_ret"]))}',
        )
    with c3:
        kpi_card(
            "Cash",
            money(float(meta["cash"]), cents=False),
            f'{float(meta["cash_pct"]) * 100:.1f}% of portfolio',
        )
    with c4:
        dd = float(meta["drawdown"])
        dd_color = "#EAECEF"
        if dd <= -0.10:
            dd_color = "#EA3943"
        elif dd <= -0.08:
            dd_color = "#E8B33D"
        kpi_card(
            "Drawdown",
            f'<span style="color:{dd_color};">{pct(dd)}</span>',
            f'from high {money(float(meta["high_water"]), cents=False)}',
        )

    st.markdown(
        '<div class="tac-section">Portfolio vs buy-and-hold</div>',
        unsafe_allow_html=True,
    )
    st.plotly_chart(
        portfolio_vs_benchmark(meta["history"]),
        use_container_width=True,
        config={"displayModeBar": False},
    )

st.markdown('<div class="tac-section">Today\'s signals</div>', unsafe_allow_html=True)
if signals.empty:
    empty_panel("No signals yet. Run paper_trade.py once, then refresh.")
else:
    chip_cols = st.columns(len(signals))
    for i, (_, row) in enumerate(signals.iterrows()):
        with chip_cols[i]:
            st.markdown(
                f"""
                <div class="tac-panel">
                  <div class="tac-body"><strong>{row['ticker']}</strong></div>
                  <div class="tac-num">{money(float(row['price']))}</div>
                  <div style="margin:6px 0;">{signal_badge(str(row['signal']))}</div>
                  <div class="tac-muted" style="text-transform:none;letter-spacing:0;">
                    buy {float(row['buy_p']):.2f} / hold {float(row['hold_p']):.2f} / sell {float(row['sell_p']):.2f}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.markdown('<div class="tac-section">Positions</div>', unsafe_allow_html=True)
if positions.empty:
    empty_panel("No trades yet. The agent is watching.")
else:
    rows_html = []
    total_value = 0.0
    total_pnl = 0.0
    for _, p in positions.iterrows():
        price = float(p["price"]) if p["price"] == p["price"] else float(p["avg_cost"])
        value = float(p["shares"]) * price
        cost = float(p["shares"]) * float(p["avg_cost"])
        pnl = value - cost
        pnl_pct = pnl / cost if cost else 0.0
        total_value += value
        total_pnl += pnl
        rows_html.append(
            f"<tr>"
            f"<td>{p['ticker']}</td>"
            f"<td class='tac-num'>{float(p['shares']):.4f}</td>"
            f"<td class='tac-num'>{money(float(p['avg_cost']))}</td>"
            f"<td class='tac-num'>{money(price)}</td>"
            f"<td class='tac-num'>{money(value)}</td>"
            f"<td>{colored_pnl(pnl)} ({colored_pnl(pnl_pct, as_pct=True)})</td>"
            f"</tr>"
        )
    st.markdown(
        f"""
        <div class="tac-panel">
        <table style="width:100%;border-collapse:collapse;font-size:14px;">
          <thead>
            <tr class="tac-muted">
              <th align="left">Ticker</th><th align="right">Shares</th>
              <th align="right">Avg cost</th><th align="right">Price now</th>
              <th align="right">Value</th><th align="right">P/L</th>
            </tr>
          </thead>
          <tbody>
            {''.join(rows_html)}
            <tr>
              <td><strong>Total</strong></td><td></td><td></td><td></td>
              <td class="tac-num"><strong>{money(total_value)}</strong></td>
              <td>{colored_pnl(total_pnl)}</td>
            </tr>
          </tbody>
        </table>
        </div>
        """,
        unsafe_allow_html=True,
    )
