#!/usr/bin/env python3
"""Phase 4 Steps 3–4: train v1 vs v2 walk-forward, apply gate, save artifacts."""

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
from core.config import DB_PATH, DEFAULT_WATCHLIST  # noqa: E402
from core.data import get_daily_bars  # noqa: E402
from core.features import (  # noqa: E402
    FEATURE_ORDER_V1,
    FEATURE_ORDER_V2,
    build_features,
    build_features_v2,
    make_labels,
)
from core.gate import evaluate_gate  # noqa: E402
from core.model_store import save_model, set_active_model  # noqa: E402

ET = ZoneInfo("America/New_York")


def _rf() -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=200,
        min_samples_leaf=50,
        random_state=7,
        n_jobs=-1,
    )


def collect(
    tickers: list[str],
    start: str,
    end: str,
    db_path: Path,
) -> pd.DataFrame:
    spy = get_daily_bars("SPY", start, end)
    if spy.empty:
        raise RuntimeError("SPY bars unavailable")
    news = db.read_news_sentiment(db_path)
    frames = []
    for t in tickers:
        bars = get_daily_bars(t, start, end)
        if bars.empty:
            continue
        indexed = bars.set_index("date")
        indexed.index = indexed.index.astype(str)
        labels = make_labels(bars)
        # sentiment join
        sub = news[news["ticker"] == t] if not news.empty else pd.DataFrame()
        if not sub.empty:
            sent = sub.set_index("date")["sentiment"]
            hc = sub.set_index("date")["headline_count"]
            sent.index = sent.index.astype(str)
            hc.index = hc.index.astype(str)
        else:
            sent = pd.Series(dtype=float)
            hc = pd.Series(dtype=float)

        v1 = build_features(indexed)
        v2 = build_features_v2(indexed, spy, sentiment=sent, headline_count=hc)
        frame = v2.copy()
        for c in FEATURE_ORDER_V1:
            frame[c] = v1[c]
        frame["action"] = labels.values
        frame["ticker"] = t
        frame["date"] = frame.index.astype(str)
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
        "y_true": y_true,
        "y_pred": y_pred,
        "feature_cols": feature_cols,
    }


def fit_final(df: pd.DataFrame, feature_cols: list[str]):
    data = df.dropna(subset=feature_cols + ["action"])
    clf = _rf()
    clf.fit(data[feature_cols], data["action"])
    return clf, data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    end = args.end or datetime.now(ET).strftime("%Y-%m-%d")

    print(f"collecting {args.start}..{end}")
    df = collect(list(DEFAULT_WATCHLIST), args.start, end, args.db)
    if df.empty:
        print("FAIL: no training frame")
        return 1

    print("walk-forward v1…")
    v1 = walk_forward(df, FEATURE_ORDER_V1)
    print("walk-forward v2…")
    v2 = walk_forward(df, FEATURE_ORDER_V2)

    clf1, data1 = fit_final(df, FEATURE_ORDER_V1)
    clf2, data2 = fit_final(df, FEATURE_ORDER_V2)

    imp = {
        f: float(i) for f, i in zip(FEATURE_ORDER_V2, clf2.feature_importances_)
    }
    ranked = sorted(imp.items(), key=lambda x: x[1], reverse=True)
    sentiment_rank = next(i + 1 for i, (f, _) in enumerate(ranked) if f == "sentiment")

    meta_common = {
        "trained_date": end,
        "start": args.start,
        "end": end,
        "label_source": "hindsight +3%/-3% 5d",
        "cost_assumption": (
            "Universe = today's tickers only (survivorship bias). "
            "Local paper log uncosted; Phase 4 comparison uses same labels for both."
        ),
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
    meta_v2 = {
        **meta_common,
        "version": "v2",
        "feature_list": FEATURE_ORDER_V2,
        "train_rows": int(len(data2)),
        "walk_forward": v2["walk_forward"],
        "accuracy": v2["accuracy"],
        "baseline": v2["baseline"],
        "buy_precision": v2["buy_precision"],
        "sell_precision": v2["sell_precision"],
        "feature_importance": imp,
        "sentiment_importance_rank": sentiment_rank,
        "sentiment_importance_rank_words": (
            f"sentiment ranks #{sentiment_rank} of {len(FEATURE_ORDER_V2)} features"
        ),
    }

    save_model(clf1, meta_v1, version="v1")
    save_model(clf2, meta_v2, version="v2")

    gate = evaluate_gate(meta_v1, meta_v2)
    if gate.passed:
        set_active_model("v2", "; ".join(gate.reasons))
        active = "v2"
    else:
        set_active_model("v1", "; ".join(gate.reasons))
        active = "v1"

    # model_runs rows
    db.init_db(args.db)
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
                "v1 baseline 8 features, hindsight labels",
            ),
        )
        conn.execute(
            "INSERT INTO model_runs(date, train_rows, accuracy, baseline, verdict, notes) "
            "VALUES (?,?,?,?,?,?)",
            (
                end,
                meta_v2["train_rows"],
                meta_v2["accuracy"],
                meta_v2["baseline"],
                gate.verdict,
                "v2 +sentiment/headline_count/spy_regime/rs21; gate: "
                + "; ".join(gate.reasons),
            ),
        )
        conn.commit()

    report = {
        "v1": {k: meta_v1[k] for k in (
            "accuracy", "baseline", "buy_precision", "sell_precision",
            "train_rows", "walk_forward", "feature_list",
        )},
        "v2": {k: meta_v2[k] for k in (
            "accuracy", "baseline", "buy_precision", "sell_precision",
            "train_rows", "walk_forward", "feature_list",
            "feature_importance", "sentiment_importance_rank",
            "sentiment_importance_rank_words",
        )},
        "gate": {
            "passed": gate.passed,
            "verdict": gate.verdict,
            "reasons": gate.reasons,
            "checks": gate.checks,
            "active_model": active,
        },
    }
    out = ROOT / "models" / "v1_vs_v2_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote {out}")
    print(f"GATE {gate.verdict} active={active}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
