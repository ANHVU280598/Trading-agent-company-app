"""Signals — SQLite + optional Yahoo price chart (H step 4 / Phase 4 + Model v3)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from core.calendar_features import next_event_line
from core.charts import price_with_markers
from core.components import market_regime_chip, prob_bars, sentiment_html, signal_badge
from core.config import SIGNAL_NOTE
from core.data import get_daily_bars
from core.events_calendar import load_events_csv
from core.formatters import conf_pct, money, pct
from core.repository import latest_signals, load_settings
from core.ui import empty_panel, error_banner, page_heading
from core import db

page_heading("Signals")

with st.spinner("Loading latest data…"):
    signals = latest_signals()
    events = load_events_csv()

if signals.empty:
    empty_panel("No signals yet. Run paper_trade.py once, then refresh.")
else:
    as_of = str(signals.iloc[0]["date"])
    st.markdown(
        f'<div class="tac-muted" style="text-transform:none;letter-spacing:0;margin-bottom:12px;">'
        f"Signals for {as_of} (last close)</div>",
        unsafe_allow_html=True,
    )
    tickers = [str(t) for t in signals["ticker"].tolist()]
    selected = st.selectbox("Ticker detail", tickers, index=0)

    header = (
        "<tr class='tac-muted'>"
        "<th align='left'>Ticker</th><th align='left'>Signal</th>"
        "<th align='right'>Conf</th><th align='left'>Buy/Hold/Sell</th>"
        "<th align='right'>Price</th><th align='right'>RSI</th>"
        "<th align='right'>DD63d</th><th align='right'>Sentiment</th>"
        "<th align='right'>Headlines</th><th align='left'>Market</th>"
        "<th align='left'>Next event</th>"
        "<th align='left'>Top headline</th></tr>"
    )
    body = []
    for _, row in signals.iterrows():
        conf = max(float(row["buy_p"]), float(row["hold_p"]), float(row["sell_p"]))
        sent = row["sentiment"]
        sent_val = None if sent is None or (isinstance(sent, float) and sent != sent) else float(sent)
        headline = row["headline"] if isinstance(row["headline"], str) and row["headline"] else "—"
        hc = row["headline_count"] if "headline_count" in row.index else None
        try:
            hc_disp = "—" if hc is None or (isinstance(hc, float) and hc != hc) else str(int(hc))
        except (TypeError, ValueError):
            hc_disp = "—"
        regime = row["spy_regime"] if "spy_regime" in row.index else None
        try:
            regime_val = None if regime is None or (isinstance(regime, float) and regime != regime) else float(regime)
        except (TypeError, ValueError):
            regime_val = None
        nxt = next_event_line(as_of, str(row["ticker"]), events)
        body.append(
            "<tr>"
            f"<td>{row['ticker']}</td>"
            f"<td>{signal_badge(str(row['signal']))}</td>"
            f"<td class='tac-num'>{conf_pct(conf)}</td>"
            f"<td>{prob_bars(float(row['buy_p']), float(row['hold_p']), float(row['sell_p']))}</td>"
            f"<td class='tac-num'>{money(float(row['price']))}</td>"
            f"<td class='tac-num'>{float(row['rsi14']):.0f}</td>"
            f"<td class='tac-num'>{pct(float(row['drawdown63']))}</td>"
            f"<td>{sentiment_html(sent_val)}</td>"
            f"<td class='tac-num'>{hc_disp}</td>"
            f"<td>{market_regime_chip(regime_val)}</td>"
            f"<td>{nxt}</td>"
            f"<td>{headline}</td>"
            "</tr>"
        )
    st.markdown(
        f'<div class="tac-panel"><table style="width:100%;border-collapse:collapse;font-size:14px;">'
        f"{header}{''.join(body)}</table></div>",
        unsafe_allow_html=True,
    )
    st.caption(SIGNAL_NOTE)

    st.markdown(
        f'<div class="tac-section">Ticker detail: {selected}</div>',
        unsafe_allow_html=True,
    )
    end = as_of
    start = (datetime.strptime(as_of, "%Y-%m-%d") - timedelta(days=200)).strftime("%Y-%m-%d")
    try:
        prices = get_daily_bars(selected, start, end)
        if prices.empty:
            error_banner(as_of)
            prices = pd.DataFrame(columns=["date", "close"])
    except Exception:
        error_banner(as_of)
        prices = pd.DataFrame(columns=["date", "close"])

    hist_signals = db.read_signals()
    markers = hist_signals[
        (hist_signals["ticker"] == selected)
        & (hist_signals["signal"].isin(["buy", "sell"]))
    ][["date", "signal", "price"]]
    if not prices.empty:
        st.plotly_chart(
            price_with_markers(prices[["date", "close"]], markers),
            use_container_width=True,
            config={"displayModeBar": False},
        )
        quality = getattr(prices, "attrs", {}).get("data_quality", "")
        if quality:
            st.caption(f"Data quality: {quality}")

    row = signals[signals["ticker"] == selected].iloc[0]
    feats = {
        "ret1": None,
        "ret5": None,
        "ret21": None,
        "vol21": None,
        "rsi14": float(row["rsi14"]),
        "dist_ma50": None,
        "drawdown63": float(row["drawdown63"]),
        "volz": None,
        "sentiment": None
        if row["sentiment"] is None or (isinstance(row["sentiment"], float) and row["sentiment"] != row["sentiment"])
        else float(row["sentiment"]),
        "headline_count": None,
        "spy_regime": "—",
        "rs21": None,
    }
    if "headline_count" in row.index and row["headline_count"] == row["headline_count"]:
        try:
            feats["headline_count"] = int(row["headline_count"])
        except (TypeError, ValueError):
            pass
    if "spy_regime" in row.index and row["spy_regime"] == row["spy_regime"]:
        try:
            feats["spy_regime"] = "up" if int(row["spy_regime"]) == 1 else "down"
        except (TypeError, ValueError):
            pass

    if not prices.empty and len(prices) > 63:
        from core.data import get_daily_bars as _bars
        from core.features import build_features_v2

        try:
            spy = _bars("SPY", start, end)
        except Exception:
            spy = pd.DataFrame()
        if not spy.empty:
            ns = db.read_news_sentiment()
            sub = ns[ns["ticker"] == selected] if not ns.empty else ns
            sent = hc = None
            if not sub.empty:
                sent = sub.set_index("date")["sentiment"]
                hc = sub.set_index("date")["headline_count"]
                sent.index = sent.index.astype(str)
                hc.index = hc.index.astype(str)
            indexed = prices.set_index("date")
            indexed.index = indexed.index.astype(str)
            built = build_features_v2(indexed, spy, sentiment=sent, headline_count=hc).dropna()
            if not built.empty:
                last = built.iloc[-1]
                for k in [
                    "ret1", "ret5", "ret21", "vol21", "rsi14", "dist_ma50",
                    "drawdown63", "volz", "sentiment", "headline_count", "rs21",
                ]:
                    feats[k] = float(last[k])
                feats["spy_regime"] = "up" if int(last["spy_regime"]) == 1 else "down"

    def _fmt(name: str, value: object) -> str:
        if value is None:
            return "—"
        if name in {"ret1", "ret5", "ret21", "dist_ma50", "drawdown63", "vol21", "rs21"}:
            return pct(float(value))
        if name == "rsi14":
            return f"{float(value):.0f}"
        if name == "volz":
            return f"{float(value):.2f}"
        if name == "sentiment":
            return f"{float(value):.2f}"
        if name == "headline_count":
            return f"{int(float(value))}"
        return str(value)

    left, right = st.columns(2)
    items = list(feats.items())
    mid = (len(items) + 1) // 2
    with left:
        for k, v in items[:mid]:
            st.markdown(
                f'<div class="tac-muted">{k}</div><div class="tac-body tac-num">{_fmt(k, v)}</div>',
                unsafe_allow_html=True,
            )
    with right:
        for k, v in items[mid:]:
            st.markdown(
                f'<div class="tac-muted">{k}</div><div class="tac-body tac-num">{_fmt(k, v)}</div>',
                unsafe_allow_html=True,
            )

_ = load_settings  # settings available for watchlist order via latest_signals
