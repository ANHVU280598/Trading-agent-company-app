"""Train RandomForest walk-forward; write results.json + model_runs row."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix

from core import db
from core.config import DB_PATH, DEFAULT_WATCHLIST, ROOT
from core.data import get_daily_bars
from core.features import FEATURE_ORDER, build_features, make_labels
from core.repository import load_settings

ET = ZoneInfo("America/New_York")
RESULTS_PATH = ROOT / "results.json"
MODEL_PATH = ROOT / "model.joblib"


def collect_frame(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    frames = []
    for t in tickers:
        bars = get_daily_bars(t, start, end)
        if bars.empty:
            continue
        feat = build_features(bars.set_index("date"))
        labels = make_labels(bars)
        feat = feat.copy()
        feat["action"] = labels.values
        feat["ticker"] = t
        feat["date"] = feat.index.astype(str)
        frames.append(feat.reset_index(drop=True))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def walk_forward(df: pd.DataFrame) -> tuple[list[dict], np.ndarray, np.ndarray, float]:
    df = df.dropna(subset=FEATURE_ORDER + ["action"]).copy()
    df["month"] = df["date"].str.slice(0, 7)
    months = sorted(df["month"].unique())
    rows = []
    y_true_all: list[str] = []
    y_pred_all: list[str] = []
    for i, month in enumerate(months):
        if i == 0:
            continue
        train = df[df["month"] < month]
        test = df[df["month"] == month]
        if train.empty or test.empty:
            continue
        clf = RandomForestClassifier(
            n_estimators=200,
            min_samples_leaf=50,
            random_state=7,
            n_jobs=-1,
        )
        clf.fit(train[FEATURE_ORDER], train["action"])
        pred = clf.predict(test[FEATURE_ORDER])
        acc = float(accuracy_score(test["action"], pred))
        baseline = float(test["action"].value_counts(normalize=True).max())
        rows.append({"month": month, "accuracy": acc, "baseline": baseline})
        y_true_all.extend(list(test["action"]))
        y_pred_all.extend(list(pred))
    overall_baseline = (
        float(pd.Series(y_true_all).value_counts(normalize=True).max())
        if y_true_all
        else 0.0
    )
    return rows, np.array(y_true_all), np.array(y_pred_all), overall_baseline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    end = args.end or datetime.now(ET).strftime("%Y-%m-%d")
    settings = load_settings(args.db)
    tickers = settings["watchlist"] or list(DEFAULT_WATCHLIST)

    df = collect_frame(tickers, args.start, end)
    if df.empty:
        print("No training data — check network / yfinance")
        return

    wf, y_true, y_pred, baseline = walk_forward(df)
    train = df.dropna(subset=FEATURE_ORDER + ["action"])
    clf = RandomForestClassifier(
        n_estimators=200, min_samples_leaf=50, random_state=7, n_jobs=-1
    )
    clf.fit(train[FEATURE_ORDER], train["action"])
    joblib.dump(clf, MODEL_PATH)

    if len(y_true):
        acc = float(accuracy_score(y_true, y_pred))
        labels = ["sell", "hold", "buy"]
        cm = confusion_matrix(y_true, y_pred, labels=labels).tolist()
    else:
        acc = float("nan")
        labels = ["sell", "hold", "buy"]
        cm = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]

    prev = db.read_model_runs(args.db)
    kept_acc = None
    if not prev.empty:
        kept = prev[prev["verdict"] == "Kept"]
        if not kept.empty:
            kept_acc = float(kept.iloc[0]["accuracy"])

    beats_prev = kept_acc is None or (acc == acc and acc > kept_acc)
    beats_base = acc == acc and acc >= baseline
    verdict = "Kept" if beats_prev and beats_base else "Rejected"

    result = {
        "date": end,
        "train_rows": int(len(train)),
        "accuracy": acc,
        "baseline": baseline,
        "verdict": verdict,
        "notes": "8 features, hindsight labels; next-open fill + costs not in this train pass",
        "feature_importance": {
            f: float(i) for f, i in zip(FEATURE_ORDER, clf.feature_importances_)
        },
        "confusion_matrix": {"labels": labels, "matrix": cm},
        "walk_forward": [{"month": r["month"], "accuracy": r["accuracy"]} for r in wf],
        "cost_assumption": (
            "Universe = today's tickers only (survivorship bias). "
            "Backtests overstate live results. "
            "Fewer than 30 trades — statistically weak. Treat this as a hint, not a result."
            if len(train) < 30
            else "Universe = today's tickers only (survivorship bias). Backtests overstate live results."
        ),
    }
    RESULTS_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")

    db.init_db(args.db)
    with db.connect(args.db) as conn:
        conn.execute(
            "INSERT INTO model_runs(date, train_rows, accuracy, baseline, verdict, notes) "
            "VALUES (?,?,?,?,?,?)",
            (
                result["date"],
                result["train_rows"],
                result["accuracy"],
                result["baseline"],
                result["verdict"],
                result["notes"],
            ),
        )
        conn.commit()

    print(
        f"train: accuracy={acc:.3f} baseline={baseline:.3f} verdict={verdict} "
        f"rows={result['train_rows']}"
    )


if __name__ == "__main__":
    main()
