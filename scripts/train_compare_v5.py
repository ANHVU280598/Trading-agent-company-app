#!/usr/bin/env python3
"""Model v5: same live features (v1), 50-ticker universe, train from 2015.

Base comparison = live model trained the old way (original 5, 2021+).
v5 adds/removes NO features. Base artifact untouched.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
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
from core.features import FEATURE_ORDER_V1, build_features, make_labels  # noqa: E402
from core.gate import evaluate_gate_v5  # noqa: E402
from core.history_cache import HISTORY_DIR, fetch_and_cache, load_cached  # noqa: E402
from core.model_store import save_model, set_active_model  # noqa: E402
from core.universe import (  # noqa: E402
    ORIGINAL5,
    assert_universe_frozen,
    universe_hash,
    universe_tickers,
)

ET = ZoneInfo("America/New_York")
WARM_START = "2014-01-01"
V5_TRAIN_START = "2015-01-01"
BASE_TRAIN_START = "2021-01-01"
MIN_YEARS = 5


def _rf() -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=200,
        min_samples_leaf=50,
        random_state=7,
        n_jobs=-1,
    )


def _precision(y_true: np.ndarray, y_pred: np.ndarray, label: str) -> float:
    return float(
        precision_score(y_true, y_pred, labels=[label], average="macro", zero_division=0)
    )


def years_of_history(frame: pd.DataFrame) -> float:
    if frame is None or len(frame) < 2:
        return 0.0
    d0 = pd.Timestamp(str(frame["date"].iloc[0]))
    d1 = pd.Timestamp(str(frame["date"].iloc[-1]))
    return (d1 - d0).days / 365.25


def collect(
    tickers: list[str],
    train_start: str,
    end: str,
    *,
    drop_log: list[dict] | None = None,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for t in tickers:
        bars = load_cached(t)
        if bars.empty:
            bars, _meta = fetch_and_cache(t, WARM_START, end, HISTORY_DIR)
        if bars.empty:
            if drop_log is not None:
                drop_log.append({"ticker": t, "reason": "empty history"})
            continue
        yrs = years_of_history(bars)
        if yrs < MIN_YEARS and t not in ORIGINAL5:
            if drop_log is not None:
                drop_log.append(
                    {"ticker": t, "reason": f"under {MIN_YEARS}y history ({yrs:.1f}y)"}
                )
            continue
        bars = bars[bars["date"] <= end].copy()
        indexed = bars.set_index("date")
        indexed.index = indexed.index.astype(str)
        lab = make_labels(bars)
        lab.index = bars["date"].astype(str)
        feats = build_features(indexed)
        frame = feats.copy()
        frame["action"] = lab.reindex(frame.index).values
        frame["ticker"] = t
        frame["date"] = frame.index.astype(str)
        # Warm-up prices may predate train_start; training rows start at train_start
        frame = frame[frame["date"] >= train_start]
        frames.append(frame.reset_index(drop=True))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


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
        "n_true": int(len(y_true)),
    }


def walk_forward_by_ticker(df: pd.DataFrame, feature_cols: list[str]) -> dict[str, dict]:
    """Per-ticker walk-forward metrics (for original-5 continuity table)."""
    out: dict[str, dict] = {}
    for t, sub in df.groupby("ticker"):
        out[str(t)] = walk_forward(sub, feature_cols)
    return out


def fit_final(df: pd.DataFrame, feature_cols: list[str]):
    data = df.dropna(subset=feature_cols + ["action"])
    clf = _rf()
    t0 = time.perf_counter()
    clf.fit(data[feature_cols], data["action"])
    elapsed = time.perf_counter() - t0
    return clf, data, elapsed


def class_balance(df: pd.DataFrame) -> dict[str, float]:
    data = df.dropna(subset=["action"])
    if data.empty:
        return {}
    vc = data["action"].value_counts(normalize=True)
    return {str(k): float(v) for k, v in vc.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--end", default=None)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--skip-panic-exam", action="store_true")
    args = parser.parse_args()
    end = args.end or datetime.now(ET).strftime("%Y-%m-%d")

    uinfo = assert_universe_frozen()
    tickers = universe_tickers()
    print(f"universe hash={uinfo['hash']} n={len(tickers)}")

    # Ensure history present
    for t in tickers:
        if not (HISTORY_DIR / f"{t}.csv").exists():
            print(f"fetching missing history {t}…")
            fetch_and_cache(t, WARM_START, end, HISTORY_DIR)

    drop_log: list[dict] = []
    print(f"collecting BASE old-way {BASE_TRAIN_START}..{end} tickers={ORIGINAL5}")
    t_collect0 = time.perf_counter()
    df_base = collect(list(ORIGINAL5), BASE_TRAIN_START, end, drop_log=drop_log)
    t_base_collect = time.perf_counter() - t_collect0

    print(f"collecting V5 {V5_TRAIN_START}..{end} tickers={len(tickers)}")
    t_collect1 = time.perf_counter()
    df_v5 = collect(tickers, V5_TRAIN_START, end, drop_log=drop_log)
    t_v5_collect = time.perf_counter() - t_collect1

    if df_base.empty or df_v5.empty:
        print("FAIL: empty training frame", "base", len(df_base), "v5", len(df_v5))
        return 1

    print("walk-forward base (v1 old-way)…")
    t0 = time.perf_counter()
    base_wf = walk_forward(df_base, FEATURE_ORDER_V1)
    t_base_wf = time.perf_counter() - t0

    print("walk-forward v5…")
    t0 = time.perf_counter()
    v5_wf = walk_forward(df_v5, FEATURE_ORDER_V1)
    t_v5_wf = time.perf_counter() - t0

    # Continuity: original 5 only, same walk-forward protocol on each side
    print("original-5 continuity…")
    base_o5 = walk_forward(df_base, FEATURE_ORDER_V1)  # already original 5
    v5_o5_frame = df_v5[df_v5["ticker"].isin(ORIGINAL5)]
    v5_o5 = walk_forward(v5_o5_frame, FEATURE_ORDER_V1)
    base_per = walk_forward_by_ticker(df_base, FEATURE_ORDER_V1)
    v5_per = walk_forward_by_ticker(v5_o5_frame, FEATURE_ORDER_V1)

    clf_base, data_base, t_fit_base = fit_final(df_base, FEATURE_ORDER_V1)
    clf_v5, data_v5, t_fit_v5 = fit_final(df_v5, FEATURE_ORDER_V1)
    _ = clf_base  # not persisted — base artifact untouched

    meta_common = {
        "trained_date": end,
        "label_source": "hindsight +3%/-3% 5d",
        "cost_assumption": (
            "Universe = today's 50 names (survivorship bias — documented). "
            "v5 = live features (v1) on more stocks + longer history only."
        ),
        "base_model": "v1",
        "feature_list": FEATURE_ORDER_V1,
    }
    meta_v5 = {
        **meta_common,
        "version": "v5",
        "universe_hash": uinfo["hash"],
        "universe_version": uinfo["version"],
        "universe_as_of": uinfo.get("as_of"),
        "train_start": V5_TRAIN_START,
        "warm_start": WARM_START,
        "end": end,
        "train_rows": int(len(data_v5)),
        "class_balance": class_balance(df_v5),
        "dropped_tickers": drop_log,
        "walk_forward": v5_wf["walk_forward"],
        "accuracy": v5_wf["accuracy"],
        "baseline": v5_wf["baseline"],
        "buy_precision": v5_wf["buy_precision"],
        "sell_precision": v5_wf["sell_precision"],
        "original5_accuracy": v5_o5["accuracy"],
        "original5_buy_precision": v5_o5["buy_precision"],
        "original5_sell_precision": v5_o5["sell_precision"],
        "timing": {
            "collect_base_s": t_base_collect,
            "collect_v5_s": t_v5_collect,
            "walk_forward_base_s": t_base_wf,
            "walk_forward_v5_s": t_v5_wf,
            "fit_base_s": t_fit_base,
            "fit_v5_s": t_fit_v5,
        },
        "feature_importance": {
            f: float(i) for f, i in zip(FEATURE_ORDER_V1, clf_v5.feature_importances_)
        },
    }
    save_model(clf_v5, meta_v5, version="v5")

    base_meta = {
        "accuracy": base_wf["accuracy"],
        "baseline": base_wf["baseline"],
        "buy_precision": base_wf["buy_precision"],
        "sell_precision": base_wf["sell_precision"],
        "walk_forward": base_wf["walk_forward"],
        "train_rows": int(len(data_base)),
        "class_balance": class_balance(df_base),
        "train_start": BASE_TRAIN_START,
    }

    gate = evaluate_gate_v5(
        base_meta,
        meta_v5,
        base_original5=base_o5,
        challenger_original5=v5_o5,
    )
    if gate.passed:
        set_active_model("v5", "; ".join(gate.reasons))
        active = "v5"
    else:
        set_active_model(
            "v1",
            "v2/v3/v4 Rejected; v5 Rejected. " + "; ".join(gate.reasons),
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
        print("running panic exam for v5…")
        panic_summary = pe.run_exam(
            "v5",
            db_path=args.db,
            tickers=list(DEFAULT_WATCHLIST),
            train_start=V5_TRAIN_START,
            report_path=ROOT / "models" / "panic_exam_v5.json",
            feature_mode="v1",
        )
        meta_v5["panic_exam"] = {
            "avg_sell_p_panic": panic_summary.get("avg_sell_p_panic"),
            "avg_sell_p_calm": panic_summary.get("avg_sell_p_calm"),
            "sell_p_higher_in_panic": panic_summary.get("sell_p_higher_in_panic"),
        }
        save_model(clf_v5, meta_v5, version="v5")

    continuity_rows = []
    for t in ORIGINAL5:
        continuity_rows.append(
            {
                "ticker": t,
                "base_accuracy": (base_per.get(t) or {}).get("accuracy"),
                "v5_accuracy": (v5_per.get(t) or {}).get("accuracy"),
                "base_buy_precision": (base_per.get(t) or {}).get("buy_precision"),
                "v5_buy_precision": (v5_per.get(t) or {}).get("buy_precision"),
                "base_sell_precision": (base_per.get(t) or {}).get("sell_precision"),
                "v5_sell_precision": (v5_per.get(t) or {}).get("sell_precision"),
            }
        )

    db.init_db(args.db)
    with db.connect(args.db) as conn:
        conn.execute(
            "INSERT INTO model_runs(date, train_rows, accuracy, baseline, verdict, notes) "
            "VALUES (?,?,?,?,?,?)",
            (
                end,
                base_meta["train_rows"],
                base_meta["accuracy"],
                base_meta["baseline"],
                "Kept",
                "v1 old-way baseline for Model v5 (5 tickers, 2021+)",
            ),
        )
        conn.execute(
            "INSERT INTO model_runs(date, train_rows, accuracy, baseline, verdict, notes) "
            "VALUES (?,?,?,?,?,?)",
            (
                end,
                meta_v5["train_rows"],
                meta_v5["accuracy"],
                meta_v5["baseline"],
                gate.verdict,
                "v5 data scale-up; gate: " + "; ".join(gate.reasons),
            ),
        )
        conn.commit()

    report = {
        "base": "v1_old_way",
        "survivorship_warning": (
            "Today's 50 names are survivors — delisted/failed companies are missing, "
            "which flatters backtests. Accepted at this stage, documented, eyes open."
        ),
        "universe": uinfo,
        "v1": base_meta,
        "v5": {
            "accuracy": meta_v5["accuracy"],
            "baseline": meta_v5["baseline"],
            "buy_precision": meta_v5["buy_precision"],
            "sell_precision": meta_v5["sell_precision"],
            "train_rows": meta_v5["train_rows"],
            "class_balance": meta_v5["class_balance"],
            "train_start": V5_TRAIN_START,
            "walk_forward": meta_v5["walk_forward"],
            "feature_list": FEATURE_ORDER_V1,
            "feature_importance": meta_v5["feature_importance"],
            "timing": meta_v5["timing"],
            "dropped_tickers": drop_log,
            "original5_pooled": {
                "accuracy": v5_o5["accuracy"],
                "buy_precision": v5_o5["buy_precision"],
                "sell_precision": v5_o5["sell_precision"],
            },
        },
        "continuity_original5": continuity_rows,
        "gate": {
            "passed": gate.passed,
            "verdict": gate.verdict,
            "reasons": gate.reasons,
            "checks": gate.checks,
            "active_model": active,
        },
        "panic_exam": panic_summary,
    }
    out = ROOT / "models" / "v1_vs_v5_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "v1": {
                    k: base_meta[k]
                    for k in (
                        "accuracy",
                        "baseline",
                        "buy_precision",
                        "sell_precision",
                        "train_rows",
                    )
                },
                "v5": {
                    k: meta_v5[k]
                    for k in (
                        "accuracy",
                        "baseline",
                        "buy_precision",
                        "sell_precision",
                        "train_rows",
                    )
                },
                "original5_pooled_v5": report["v5"]["original5_pooled"],
                "timing_fit_s": {"base": t_fit_base, "v5": t_fit_v5},
                "gate": report["gate"],
                "class_balance_v5": meta_v5["class_balance"],
                "dropped": drop_log,
            },
            indent=2,
        )
    )
    print(f"wrote {out}")
    print(f"GATE {gate.verdict} active={active}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
