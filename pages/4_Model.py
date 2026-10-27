"""Model — results.json + model_runs + signal scorecard (H step 5 / addendum)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core import db
from core.charts import feature_importance_bars, walk_forward_bars
from core.components import kpi_card
from core.config import MODEL_HONESTY
from core.repository import load_results
from core.ui import page_heading

page_heading("Model")

st.markdown(f'<div class="tac-honesty">{MODEL_HONESTY}</div>', unsafe_allow_html=True)

with st.spinner("Loading latest data…"):
    runs = db.read_model_runs()
    results = load_results()
    trades = db.read_trades()
    grades = db.read_signal_grades()

if runs.empty and not results:
    c1, c2, c3, c4 = st.columns(4)
    for col in (c1, c2, c3, c4):
        with col:
            kpi_card("—", "—")
else:
    if not runs.empty:
        kept = runs[runs["verdict"] == "Kept"]
        latest = kept.iloc[0] if not kept.empty else runs.iloc[0]
        accuracy = float(latest["accuracy"])
        baseline = float(latest["baseline"])
        retrain_date = str(latest["date"])
    else:
        accuracy = float(results["accuracy"])
        baseline = float(results["baseline"])
        retrain_date = str(results["date"])

    closed = trades[trades["status"] == "Closed"] if not trades.empty else trades
    wins = closed[closed["realized_pnl"].fillna(0) > 0] if not closed.empty else closed
    wr = (len(wins) / len(closed) * 100) if len(closed) else None

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card(
            "Test accuracy",
            f"{accuracy * 100:.1f}%",
            f"vs {baseline * 100:.1f}% baseline",
        )
    with c2:
        kpi_card("Paper win rate", "—" if wr is None else f"{wr:.1f}%")
    with c3:
        kpi_card("Paper trades", str(len(trades)))
    with c4:
        kpi_card("Last retrained", retrain_date)

    st.caption(results.get("cost_assumption", ""))

    st.markdown(
        '<div class="tac-section">Walk-forward accuracy by month</div>',
        unsafe_allow_html=True,
    )
    wf = pd.DataFrame(results.get("walk_forward") or [])
    if wf.empty and not runs.empty:
        tmp = runs.copy()
        tmp["month"] = tmp["date"].astype(str).str.slice(0, 7)
        wf = tmp.groupby("month", as_index=False)["accuracy"].mean()
    if not wf.empty:
        st.plotly_chart(
            walk_forward_bars(wf, baseline),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    left, right = st.columns(2)
    with left:
        st.markdown('<div class="tac-section">Confusion matrix</div>', unsafe_allow_html=True)
        cm_data = results.get("confusion_matrix")
        if not cm_data:
            st.markdown(
                '<div class="tac-panel-empty">No test run saved yet.</div>',
                unsafe_allow_html=True,
            )
        else:
            labels = cm_data["labels"]
            cm = pd.DataFrame(cm_data["matrix"], index=labels, columns=labels)
            st.markdown(
                f'<div class="tac-panel">{cm.to_html()}</div>',
                unsafe_allow_html=True,
            )
    with right:
        st.markdown('<div class="tac-section">Feature importance</div>', unsafe_allow_html=True)
        fi = results.get("feature_importance") or {}
        if not fi:
            st.markdown(
                '<div class="tac-panel-empty">No test run saved yet.</div>',
                unsafe_allow_html=True,
            )
        else:
            imp = pd.DataFrame(
                {"feature": list(fi.keys()), "importance": list(fi.values())}
            )
            st.plotly_chart(
                feature_importance_bars(imp),
                use_container_width=True,
                config={"displayModeBar": False},
            )

    st.markdown('<div class="tac-section">Retrain log</div>', unsafe_allow_html=True)
    if runs.empty:
        st.markdown(
            '<div class="tac-panel-empty">No test run saved yet.</div>',
            unsafe_allow_html=True,
        )
    else:
        rows = []
        for _, r in runs.iterrows():
            color = "#16C784" if r["verdict"] == "Kept" else "#848E9C"
            rows.append(
                "<tr>"
                f"<td>{r['date']}</td>"
                f"<td class='tac-num'>{int(r['train_rows'])}</td>"
                f"<td class='tac-num'>{float(r['accuracy']) * 100:.1f}%</td>"
                f"<td class='tac-num'>{float(r['baseline']) * 100:.1f}%</td>"
                f"<td style='color:{color};'>{r['verdict']}</td>"
                "</tr>"
            )
        st.markdown(
            f"""
            <div class="tac-panel">
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
              <thead><tr class="tac-muted">
                <th align="left">Date</th><th align="right">Train rows</th>
                <th align="right">Test accuracy</th><th align="right">Baseline</th>
                <th align="left">Verdict</th>
              </tr></thead>
              <tbody>{''.join(rows)}</tbody>
            </table>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown('<div class="tac-section">Signal scorecard</div>', unsafe_allow_html=True)
graded = grades[grades["ret_5d"].notna()] if not grades.empty else grades
n = len(graded)
if n < 30:
    st.markdown(
        f'<div class="tac-panel-empty">Graded signals: {n}. '
        "Not enough graded signals yet — the scorecard needs 30.</div>",
        unsafe_allow_html=True,
    )
else:
    # Split BUY/SELL win rates at 5d / 20d vs SPY
    def _wins(frame: pd.DataFrame, signal: str, horizon: str) -> float | None:
        sub = frame[frame["signal"] == signal].dropna(subset=[horizon, f"spy_{horizon}"])
        if sub.empty:
            return None
        if signal == "buy":
            ok = sub[horizon] > sub[f"spy_{horizon}"]
        else:
            ok = sub[horizon] < sub[f"spy_{horizon}"]
        return float(ok.mean())

    for signal in ("buy", "sell"):
        w5 = _wins(graded, signal, "ret_5d")
        w20 = _wins(graded, signal, "ret_20d")
        st.write(
            f"{signal.upper()} win rate — 5d: "
            f"{'—' if w5 is None else f'{w5 * 100:.1f}%'}; "
            f"20d: {'—' if w20 is None else f'{w20 * 100:.1f}%'}"
        )
