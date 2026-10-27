"""Model — fake-data pass (H step 2) including signal scorecard addendum."""

from __future__ import annotations

import streamlit as st

from core import fake_data
from core.charts import feature_importance_bars, walk_forward_bars
from core.components import kpi_card, sample_data_line
from core.config import MODEL_HONESTY
from core.ui import page_heading

page_heading("Model")
sample_data_line()

st.markdown(f'<div class="tac-honesty">{MODEL_HONESTY}</div>', unsafe_allow_html=True)

runs = fake_data.model_runs()
kept = runs[runs["verdict"] == "Kept"].iloc[0]
c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi_card(
        "Test accuracy",
        f'{kept["accuracy"] * 100:.1f}%',
        f'vs {kept["baseline"] * 100:.1f}% baseline',
    )
with c2:
    closed = fake_data.trades()
    closed = closed[closed["status"] == "Closed"]
    wins = closed[closed["realized_pnl"].fillna(0) > 0]
    wr = (len(wins) / len(closed) * 100) if len(closed) else None
    kpi_card("Paper win rate", "—" if wr is None else f"{wr:.1f}%")
with c3:
    kpi_card("Paper trades", str(len(fake_data.trades())))
with c4:
    kpi_card("Last retrained", str(kept["date"]))

st.markdown('<div class="tac-section">Walk-forward accuracy by month</div>', unsafe_allow_html=True)
st.plotly_chart(
    walk_forward_bars(fake_data.walk_forward(), float(kept["baseline"])),
    use_container_width=True,
    config={"displayModeBar": False},
)

left, right = st.columns(2)
with left:
    st.markdown('<div class="tac-section">Confusion matrix</div>', unsafe_allow_html=True)
    cm = fake_data.confusion_matrix()
    st.markdown(
        f'<div class="tac-panel">{cm.to_html(classes="tac-num")}</div>',
        unsafe_allow_html=True,
    )
with right:
    st.markdown('<div class="tac-section">Feature importance</div>', unsafe_allow_html=True)
    st.plotly_chart(
        feature_importance_bars(fake_data.feature_importance()),
        use_container_width=True,
        config={"displayModeBar": False},
    )

st.markdown('<div class="tac-section">Retrain log</div>', unsafe_allow_html=True)
rows = []
for _, r in runs.iterrows():
    color = "#16C784" if r["verdict"] == "Kept" else "#848E9C"
    rows.append(
        "<tr>"
        f"<td>{r['date']}</td>"
        f"<td class='tac-num'>{int(r['train_rows'])}</td>"
        f"<td class='tac-num'>{r['accuracy'] * 100:.1f}%</td>"
        f"<td class='tac-num'>{r['baseline'] * 100:.1f}%</td>"
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
grades = fake_data.signal_grades()
graded_5d = grades[grades["ret_5d"].notna()]
if len(graded_5d) < 30:
    st.markdown(
        f'<div class="tac-panel-empty">Graded signals: {len(graded_5d)}. '
        "Not enough graded signals yet — the scorecard needs 30.</div>",
        unsafe_allow_html=True,
    )
else:
    st.write("Scorecard ready")  # filled in H5 when real grades exist
