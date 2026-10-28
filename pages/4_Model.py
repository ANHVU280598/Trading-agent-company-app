"""Model — results + Phase 4 v1 vs v2 + Model v3 v1 vs v3 gates."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from core import db
from core.charts import feature_importance_bars, walk_forward_bars
from core.components import kpi_card
from core.config import MODEL_HONESTY
from core.model_store import V1_META, V2_META, V3_META
from core.repository import (
    load_active_model_meta,
    load_results,
    load_v1_v2_report,
    load_v1_v3_report,
)
from core.ui import page_heading

page_heading("Model")

st.markdown(f'<div class="tac-honesty">{MODEL_HONESTY}</div>', unsafe_allow_html=True)

with st.spinner("Loading latest data…"):
    runs = db.read_model_runs()
    results = load_results()
    compare_v2 = load_v1_v2_report()
    compare_v3 = load_v1_v3_report()
    active_meta = load_active_model_meta()
    trades = db.read_trades()
    grades = db.read_signal_grades()

active_version = str(active_meta.get("version") or "v1")
display_acc = None
display_base = None
retrain_date = "—"

# Prefer active model's own report side when present (v1 from either gate)
for compare in (compare_v2, compare_v3):
    if not compare:
        continue
    side = compare.get(active_version) or compare.get("v1") or {}
    if side and display_acc is None:
        display_acc = float(side.get("accuracy") or 0)
        display_base = float(side.get("baseline") or 0)

for meta_path in (V3_META, V2_META, V1_META):
    if meta_path.exists():
        retrain_date = str(
            json.loads(meta_path.read_text(encoding="utf-8")).get("trained_date")
            or retrain_date
        )
        break

if display_acc is None:
    if not runs.empty:
        kept = runs[runs["verdict"] == "Kept"]
        latest = kept.iloc[0] if not kept.empty else runs.iloc[0]
        display_acc = float(latest["accuracy"])
        display_base = float(latest["baseline"])
        retrain_date = str(latest["date"])
    elif results:
        display_acc = float(results["accuracy"])
        display_base = float(results["baseline"])
        retrain_date = str(results["date"])

if display_acc is None:
    c1, c2, c3, c4 = st.columns(4)
    for col in (c1, c2, c3, c4):
        with col:
            kpi_card("—", "—")
else:
    closed = trades[trades["status"] == "Closed"] if not trades.empty else trades
    wins = closed[closed["realized_pnl"].fillna(0) > 0] if not closed.empty else closed
    wr = (len(wins) / len(closed) * 100) if len(closed) else None

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card(
            "Test accuracy",
            f"{display_acc * 100:.1f}%",
            f"vs {(display_base or 0) * 100:.1f}% baseline · active {active_version}",
        )
    with c2:
        kpi_card("Paper win rate", "—" if wr is None else f"{wr:.1f}%")
    with c3:
        kpi_card("Paper trades", str(len(trades)))
    with c4:
        kpi_card("Last retrained", retrain_date)

    st.caption(
        results.get("cost_assumption", "")
        or (compare_v2.get("v1") or {}).get("cost_assumption", "")
        or (compare_v3.get("v1") or {}).get("cost_assumption", "")
    )

    def _gate_block(title: str, compare: dict, challenger_key: str) -> None:
        if not compare:
            return
        st.markdown(f'<div class="tac-section">{title}</div>', unsafe_allow_html=True)
        gate = compare.get("gate") or {}
        verdict = gate.get("verdict", "—")
        color = "#16C784" if verdict == "Kept" else "#EA3943"
        reasons = gate.get("reasons") or []
        st.markdown(
            f'<div class="tac-panel"><span style="color:{color};font-weight:600;">'
            f"Gate: {verdict}</span> · active paper model: <b>{gate.get('active_model', active_version)}</b>"
            f"<div class='tac-body' style='margin-top:8px;'>{'; '.join(reasons)}</div></div>",
            unsafe_allow_html=True,
        )
        v1 = compare.get("v1") or {}
        ch = compare.get(challenger_key) or {}
        rows = [
            ("Walk-forward accuracy", v1.get("accuracy"), ch.get("accuracy"), "pct"),
            ("Always-hold baseline", v1.get("baseline"), ch.get("baseline"), "pct"),
            ("Buy precision", v1.get("buy_precision"), ch.get("buy_precision"), "pct"),
            ("Sell precision", v1.get("sell_precision"), ch.get("sell_precision"), "pct"),
            ("Train rows", v1.get("train_rows"), ch.get("train_rows"), "int"),
        ]
        body = []
        for label, a, b, kind in rows:

            def _cell(x: object, k: str = kind) -> str:
                if x is None:
                    return "—"
                if k == "int":
                    return str(int(x))
                return f"{float(x) * 100:.1f}%"

            body.append(
                "<tr>"
                f"<td>{label}</td>"
                f"<td class='tac-num'>{_cell(a)}</td>"
                f"<td class='tac-num'>{_cell(b)}</td>"
                "</tr>"
            )
        st.markdown(
            f"""
            <div class="tac-panel">
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
              <thead><tr class="tac-muted">
                <th align="left">Metric</th><th align="right">v1 (base)</th>
                <th align="right">{challenger_key}</th>
              </tr></thead>
              <tbody>{''.join(body)}</tbody>
            </table>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if challenger_key == "v2":
            words = ch.get("sentiment_importance_rank_words")
        else:
            words = ch.get("calendar_importance_words")
        if words:
            st.caption(str(words))

    _gate_block("v1 vs v2 (Phase 4 gate)", compare_v2, "v2")
    _gate_block("v1 vs v3 (Model v3 gate)", compare_v3, "v3")

    st.markdown(
        '<div class="tac-section">Walk-forward accuracy by month</div>',
        unsafe_allow_html=True,
    )
    wf_source = None
    for compare in (compare_v2, compare_v3):
        if not compare:
            continue
        side = compare.get(active_version) or compare.get("v1") or {}
        if side.get("walk_forward"):
            wf_source = side.get("walk_forward")
            break
    wf = pd.DataFrame(wf_source or results.get("walk_forward") or [])
    if wf.empty and not runs.empty:
        tmp = runs.copy()
        tmp["month"] = tmp["date"].astype(str).str.slice(0, 7)
        wf = tmp.groupby("month", as_index=False)["accuracy"].mean()
    baseline_plot = display_base or 0.0
    if not wf.empty:
        st.plotly_chart(
            walk_forward_bars(wf, baseline_plot),
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
        fi = {}
        if compare_v3 and (compare_v3.get("v3") or {}).get("feature_importance"):
            fi = compare_v3["v3"]["feature_importance"]
        elif compare_v2 and (compare_v2.get("v2") or {}).get("feature_importance"):
            fi = compare_v2["v2"]["feature_importance"]
        else:
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
            notes = str(r["notes"]) if "notes" in r.index and r["notes"] == r["notes"] else ""
            rows.append(
                "<tr>"
                f"<td>{r['date']}</td>"
                f"<td class='tac-num'>{int(r['train_rows'])}</td>"
                f"<td class='tac-num'>{float(r['accuracy']) * 100:.1f}%</td>"
                f"<td class='tac-num'>{float(r['baseline']) * 100:.1f}%</td>"
                f"<td style='color:{color};'>{r['verdict']}</td>"
                f"<td>{notes}</td>"
                "</tr>"
            )
        st.markdown(
            f"""
            <div class="tac-panel">
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
              <thead><tr class="tac-muted">
                <th align="left">Date</th><th align="right">Train rows</th>
                <th align="right">Test accuracy</th><th align="right">Baseline</th>
                <th align="left">Verdict</th><th align="left">Notes</th>
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
