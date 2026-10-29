#!/usr/bin/env python3
"""Model v4 Steps 3–4: train v1 vs v4 walk-forward, gate, panic exam, save artifacts.

Base = live paper model (v1). Rejected v2/v3 are not activated.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from core import db  # noqa: E402
from core.behavior_data import load_behavior_csv  # noqa: E402
from core.behavior_features import BEHAVIOR_FEATURE_ORDER  # noqa: E402
from core.config import DB_PATH, DEFAULT_WATCHLIST  # noqa: E402
from core.data import get_daily_bars  # noqa: E402
from core.features import (  # noqa: E402
    FEATURE_ORDER_V1,
    FEATURE_ORDER_V4,
    build_features,
    build_features_v4,
    make_labels,
)
from core.gate import evaluate_gate  # noqa: E402
from core.model_store import save_model, set_active_model  # noqa: E402

ET = ZoneInfo("America/New_York")
HIST_START = "2017-01-01"  # SPY warm-up for 125d×252 pct; VIX table still 2019+


def _rf() -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=200,
        min_samples_leaf=50,
        random_state=7,
        n_jobs=-1,
    )


def collect(
    tickers: list[str],
    train_start: str,
    end: str,
    behavior: pd.DataFrame,
) -> pd.DataFrame:
    spy = get_daily_bars("SPY", HIST_START, end)
    if spy.empty:
        return pd.DataFrame()
    spy_i = spy.set_index("date")
    spy_i.index = spy_i.index.astype(str)
    frames = []
    for t in tickers:
        bars = get_daily_bars(t, HIST_START, end)
        if bars.empty:
            continue
        indexed = bars.set_index("date")
        indexed.index = indexed.index.astype(str)
        lab = make_labels(bars)
        lab.index = bars["date"].astype(str)
        v1 = build_features(indexed)
        v4 = build_features_v4(indexed, spy_i, behavior=behavior)
        frame = v4.copy()
        for c in FEATURE_ORDER_V1:
            frame[c] = v1[c]
        frame["action"] = lab.reindex(frame.index).values
        frame["ticker"] = t
        frame["date"] = frame.index.astype(str)
        # Training rows still start train_start (2021); history kept for warm-up only
        frame = frame[frame["date"] >= train_start]
        frames.append(frame.reset_index(drop=True))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _precision(y_true: np.ndarray, y_pred: np.ndarray, label: str) -> float:
    return float(
        precision_score(y_true, y_pred, labels=[label], average="macro", zero_division=0)
    )


def walk_forward(df: pd.DataFrame, feature_cols: list[str]) -> dict:
    data = df.dropna(subset=feature_cols + ["action"]).copy()
    data["month"] = data["date"].str.slice(0, 7)
    months = sorted(data["month"].unique())
    rows = []
    y_true_all: list[str] = []
    y_pred_all: list[str] = []
    for i, month in enumerate(months):
        if i == 0:
            continue
        train = data[data["month"] < month]
        test = data[data["month"] == month]
        if len(train) < 50 or test.empty:
            continue
        clf = _rf()
        clf.fit(train[feature_cols], train["action"])
        pred = clf.predict(test[feature_cols])
        acc = float(accuracy_score(test["action"], pred))
        baseline = float(test["action"].value_counts(normalize=True).max())
        rows.append({"month": month, "accuracy": acc, "baseline": baseline})
        y_true_all.extend(list(test["action"]))
        y_pred_all.extend(list(pred))

    y_true = np.array(y_true_all)
    y_pred = np.array(y_pred_all)
    overall_acc = float(accuracy_score(y_true, y_pred)) if len(y_true) else float("nan")
    baseline = (
        float(pd.Series(y_true).value_counts(normalize=True).max()) if len(y_true) else 0.0
    )
    return {
        "accuracy": overall_acc,
        "baseline": baseline,
        "buy_precision": _precision(y_true, y_pred, "buy") if len(y_true) else 0.0,
        "sell_precision": _precision(y_true, y_pred, "sell") if len(y_true) else 0.0,
        "walk_forward": rows,
        "train_rows_final": int(len(data)),
        "feature_cols": feature_cols,
    }


def fit_final(df: pd.DataFrame, feature_cols: list[str]):
    data = df.dropna(subset=feature_cols + ["action"])
    clf = _rf()
    clf.fit(data[feature_cols], data["action"])
    return clf, data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2021-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--skip-panic-exam", action="store_true")
    args = parser.parse_args()
    end = args.end or datetime.now(ET).strftime("%Y-%m-%d")

    behavior = load_behavior_csv()
    if behavior.empty:
        behavior = db.read_behavior(args.db)
    if behavior.empty:
        print("FAIL: behavior empty — run scripts/refresh_behavior.py")
        return 1

    print(f"collecting hist={HIST_START} train={args.start}..{end}")
    df = collect(list(DEFAULT_WATCHLIST), args.start, end, behavior)
    if df.empty:
        print("FAIL: no training frame")
        return 1

    print("walk-forward v1 (base)…")
    v1 = walk_forward(df, FEATURE_ORDER_V1)
    print("walk-forward v4…")
    v4 = walk_forward(df, FEATURE_ORDER_V4)

    clf1, data1 = fit_final(df, FEATURE_ORDER_V1)
    clf4, data4 = fit_final(df, FEATURE_ORDER_V4)

    imp = {f: float(i) for f, i in zip(FEATURE_ORDER_V4, clf4.feature_importances_)}
    ranked = sorted(imp.items(), key=lambda x: x[1], reverse=True)
    beh_set = set(BEHAVIOR_FEATURE_ORDER)
    beh_ranked = [(f, v) for f, v in ranked if f in beh_set]
    used = [f for f, v in beh_ranked if v > 1e-6]
    ignored = [f for f, v in beh_ranked if v <= 1e-6]
    beh_rank_words = []
    for f, _v in beh_ranked:
        overall_rank = next(i + 1 for i, (ff, _) in enumerate(ranked) if ff == f)
        beh_rank_words.append(f"{f}#{overall_rank}")
    ignored_words = ", ".join(ignored) if ignored else "(none)"

    meta_common = {
        "trained_date": end,
        "start": args.start,
        "end": end,
        "hist_start": HIST_START,
        "label_source": "hindsight +3%/-3% 5d",
        "cost_assumption": (
            "Universe = today's tickers only (survivorship bias). "
            "v4 adds behavior features; putcall missing post-2019 → VIX/AAII crowd_mood. "
            "Base is live paper model v1."
        ),
        "base_model": "v1",
    }
    meta_v1 = {
        **meta_common,
        "version": "v1",
        "feature_list": FEATURE_ORDER_V1,
        "train_rows": int(len(data1)),
        "walk_forward": v1["walk_forward"],
        "accuracy": v1["accuracy"],
        "baseline": v1["baseline"],
        "buy_precision": v1["buy_precision"],
        "sell_precision": v1["sell_precision"],
    }
    meta_v4 = {
        **meta_common,
        "version": "v4",
        "feature_list": FEATURE_ORDER_V4,
        "train_rows": int(len(data4)),
        "walk_forward": v4["walk_forward"],
        "accuracy": v4["accuracy"],
        "baseline": v4["baseline"],
        "buy_precision": v4["buy_precision"],
        "sell_precision": v4["sell_precision"],
        "feature_importance": imp,
        "behavior_features_used": used,
        "behavior_features_ignored": ignored,
        "behavior_importance_words": (
            "Behavior features by importance: "
            + ", ".join(beh_rank_words)
            + f". Ignored (≈0 importance): {ignored_words}."
        ),
    }

    # Muse: base model untouched as rollback — only write model_v4 artifacts.
    # v1 walk-forward metrics below are for this fair side-by-side gate only.
    _ = clf1  # fitted for parity; not persisted
    save_model(clf4, meta_v4, version="v4")

    gate = evaluate_gate(meta_v1, meta_v4)
    if gate.passed:
        set_active_model("v4", "; ".join(gate.reasons))
        active = "v4"
    else:
        set_active_model(
            "v1",
            "v2 Rejected (Phase 4); v3 Rejected (Model v3); v4 Rejected (Model v4). "
            + "; ".join(gate.reasons),
        )
        active = "v1"

    panic_summary = None
    if not args.skip_panic_exam:
        import importlib.util

        pe_path = ROOT / "scripts" / "panic_exam.py"
        spec = importlib.util.spec_from_file_location("panic_exam", pe_path)
        assert spec and spec.loader
        pe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pe)

        print("running panic exam…")
        panic_summary = pe.run_exam("v4", db_path=args.db)
        meta_v4["panic_exam"] = {
            "avg_sell_p_panic": panic_summary.get("avg_sell_p_panic"),
            "avg_sell_p_calm": panic_summary.get("avg_sell_p_calm"),
            "sell_p_higher_in_panic": panic_summary.get("sell_p_higher_in_panic"),
        }
        save_model(clf4, meta_v4, version="v4")

    db.init_db(args.db)
    panic_note = ""
    if panic_summary:
        panic_note = (
            f" | panic avg_sell={panic_summary.get('avg_sell_p_panic')} "
            f"calm={panic_summary.get('avg_sell_p_calm')} "
            f"higher_in_panic={panic_summary.get('sell_p_higher_in_panic')}"
        )
    with db.connect(args.db) as conn:
        conn.execute(
            "INSERT INTO model_runs(date, train_rows, accuracy, baseline, verdict, notes) "
            "VALUES (?,?,?,?,?,?)",
            (
                end,
                meta_v1["train_rows"],
                meta_v1["accuracy"],
                meta_v1["baseline"],
                "Kept",
                "v1 base 8 features (Model v4 comparison baseline)",
            ),
        )
        conn.execute(
            "INSERT INTO model_runs(date, train_rows, accuracy, baseline, verdict, notes) "
            "VALUES (?,?,?,?,?,?)",
            (
                end,
                meta_v4["train_rows"],
                meta_v4["accuracy"],
                meta_v4["baseline"],
                gate.verdict,
                "v4 +8 behavior features; gate: "
                + "; ".join(gate.reasons)
                + panic_note,
            ),
        )
        conn.commit()

    report = {
        "base": "v1",
        "v1": {
            k: meta_v1[k]
            for k in (
                "accuracy",
                "baseline",
                "buy_precision",
                "sell_precision",
                "train_rows",
                "walk_forward",
                "feature_list",
            )
        },
        "v4": {
            k: meta_v4[k]
            for k in (
                "accuracy",
                "baseline",
                "buy_precision",
                "sell_precision",
                "train_rows",
                "walk_forward",
                "feature_list",
                "feature_importance",
                "behavior_features_used",
                "behavior_features_ignored",
                "behavior_importance_words",
            )
            if k in meta_v4
        },
        "gate": {
            "passed": gate.passed,
            "verdict": gate.verdict,
            "reasons": gate.reasons,
            "checks": gate.checks,
            "active_model": active,
        },
        "panic_exam": panic_summary,
    }
    out = ROOT / "models" / "v1_vs_v4_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "v1": {
                    k: report["v1"][k]
                    for k in (
                        "accuracy",
                        "baseline",
                        "buy_precision",
                        "sell_precision",
                        "train_rows",
                    )
                },
                "v4": {
                    k: report["v4"][k]
                    for k in (
                        "accuracy",
                        "baseline",
                        "buy_precision",
                        "sell_precision",
                        "train_rows",
                    )
                },
                "behavior_importance_words": meta_v4["behavior_importance_words"],
                "gate": report["gate"],
                "panic_exam": {
                    k: (panic_summary or {}).get(k)
                    for k in (
                        "avg_sell_p_panic",
                        "avg_sell_p_calm",
                        "sell_p_higher_in_panic",
                    )
                },
            },
            indent=2,
        )
    )
    print(f"wrote {out}")
    print(f"GATE {gate.verdict} active={active}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
