#!/usr/bin/env python3
"""Standing panic exam over fixed historical windows (Model v4+).

Not a fifth gate condition. Results are reported, never hidden.
v5+: rows include trained_on when the window overlaps the model's train span.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from core import db  # noqa: E402
from core.behavior_data import load_behavior_csv  # noqa: E402
from core.config import DB_PATH, DEFAULT_WATCHLIST  # noqa: E402
from core.data import get_daily_bars  # noqa: E402
from core.features import (  # noqa: E402
    FEATURE_ORDER_V1,
    FEATURE_ORDER_V4,
    build_features,
    build_features_v4,
)
from core.history_cache import load_cached  # noqa: E402
from core.model_store import load_model  # noqa: E402

PANIC_WINDOWS: list[tuple[str, str, str]] = [
    ("COVID crash", "2020-02-19", "2020-03-23"),
    ("2022 bear slide", "2022-01-03", "2022-10-14"),
    ("Aug 2024 yen-unwind", "2024-08-01", "2024-08-09"),
    ("Apr 2025 tariff drop", "2025-04-02", "2025-04-11"),
]

CALM_WINDOWS: list[tuple[str, str, str]] = [
    ("calm 2023 H1", "2023-01-03", "2023-06-30"),
    ("calm 2024 spring", "2024-03-01", "2024-05-31"),
]

REPORT_PATH = ROOT / "models" / "panic_exam_v4.json"


def _bars(ticker: str, start: str, end: str) -> pd.DataFrame:
    cached = load_cached(ticker)
    if not cached.empty:
        return cached[(cached["date"] >= start) & (cached["date"] <= end)].copy()
    return get_daily_bars(ticker, start, end)


def _feature_frame(
    tickers: list[str],
    hist_start: str,
    end: str,
    behavior: pd.DataFrame,
    *,
    feature_mode: str = "v4",
) -> pd.DataFrame:
    spy = _bars("SPY", hist_start, end)
    if spy.empty:
        return pd.DataFrame()
    spy_i = spy.set_index("date")
    spy_i.index = spy_i.index.astype(str)
    frames = []
    for t in tickers:
        bars = _bars(t, hist_start, end)
        if bars.empty:
            continue
        indexed = bars.set_index("date")
        indexed.index = indexed.index.astype(str)
        if feature_mode == "v1":
            feats = build_features(indexed)
            # Still attach crowd_mood meter columns for exam reporting
            try:
                beh = build_features_v4(indexed, spy_i, behavior=behavior)
                for col in ("crowd_mood", "capitulation_ticker"):
                    if col in beh.columns:
                        feats[col] = beh[col]
            except Exception:
                feats["crowd_mood"] = pd.NA
                feats["capitulation_ticker"] = 0.0
        else:
            feats = build_features_v4(indexed, spy_i, behavior=behavior)
        feats = feats.copy()
        feats["ticker"] = t
        feats["date"] = feats.index.astype(str)
        frames.append(feats.reset_index(drop=True))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _predict_sell_p(model, frame: pd.DataFrame, feature_mode: str) -> pd.Series:
    default_cols = FEATURE_ORDER_V1 if feature_mode == "v1" else FEATURE_ORDER_V4
    cols = list(getattr(model, "feature_names_in_", default_cols))
    use = frame.dropna(subset=[c for c in cols if c in frame.columns])
    missing = [c for c in cols if c not in use.columns]
    if missing or use.empty:
        return pd.Series(dtype=float)
    proba = model.predict_proba(use[cols])
    classes = list(model.classes_)
    if "sell" not in classes:
        return pd.Series(0.0, index=use.index)
    sell_i = classes.index("sell")
    return pd.Series(proba[:, sell_i], index=use.index)


def evaluate_window(
    model,
    frame: pd.DataFrame,
    start: str,
    end: str,
    *,
    feature_mode: str = "v4",
) -> dict:
    sub = frame[(frame["date"] >= start) & (frame["date"] <= end)].copy()
    if sub.empty:
        return {
            "avg_sell_p": None,
            "min_crowd_mood": None,
            "capitulation_days": 0,
            "rows": 0,
            "notes": "no rows in window",
        }
    sell = _predict_sell_p(model, sub, feature_mode)
    avg_sell = float(sell.mean()) if len(sell) else None
    mood = sub["crowd_mood"].dropna() if "crowd_mood" in sub.columns else pd.Series(dtype=float)
    min_mood = float(mood.min()) if len(mood) else None
    caps = 0
    if "capitulation_ticker" in sub.columns:
        caps = int(sub[sub["capitulation_ticker"].fillna(0) > 0]["date"].nunique())
    note_bits = []
    if avg_sell is not None:
        note_bits.append(f"avg sell_p={avg_sell:.3f}")
    if min_mood is not None:
        note_bits.append(f"min crowd_mood={min_mood:.1f}")
        if min_mood < 20:
            note_bits.append("meter reads Extreme fear")
        elif min_mood < 40:
            note_bits.append("meter reads Fear")
    if avg_sell is not None and avg_sell >= 0.35:
        note_bits.append("leaning sell into stress")
    elif avg_sell is not None:
        note_bits.append("sell lean weak vs calm expectation")
    return {
        "avg_sell_p": avg_sell,
        "min_crowd_mood": min_mood,
        "capitulation_days": caps,
        "rows": int(len(sub)),
        "notes": "; ".join(note_bits) if note_bits else "—",
    }


def _window_trained_on(train_start: str | None, start: str, end: str) -> bool:
    """True if the exam window overlaps the model's training date span."""
    if not train_start:
        return False
    # In-sample if window end >= train_start (model saw that calendar period)
    return end >= train_start and start >= train_start


def run_exam(
    model_version: str = "v4",
    *,
    db_path: Path = DB_PATH,
    tickers: list[str] | None = None,
    train_start: str | None = None,
    report_path: Path | None = None,
    feature_mode: str = "v4",
) -> dict:
    tickers = tickers or list(DEFAULT_WATCHLIST)
    behavior = load_behavior_csv()
    if behavior.empty:
        try:
            behavior = db.read_behavior(db_path)
        except Exception:
            behavior = pd.DataFrame()

    model, meta = load_model(model_version)
    if train_start is None:
        train_start = meta.get("train_start") or meta.get("start")
    if feature_mode == "v4" and "crowd_mood" not in list(
        getattr(model, "feature_names_in_", [])
    ):
        # Live v1-features models (incl. v5) still get v1 inference + mood meter
        if set(getattr(model, "feature_names_in_", [])) <= set(FEATURE_ORDER_V1) or set(
            getattr(model, "feature_names_in_", [])
        ) == set(FEATURE_ORDER_V1):
            feature_mode = "v1"

    hist_start = "2017-01-01"
    end = max(w[2] for w in PANIC_WINDOWS + CALM_WINDOWS)
    print(f"building feature frame {hist_start}..{end} mode={feature_mode}…")
    if feature_mode == "v4" and behavior.empty:
        raise SystemExit("behavior table empty — run scripts/refresh_behavior.py")
    frame = _feature_frame(
        tickers, hist_start, end, behavior, feature_mode=feature_mode
    )
    if frame.empty:
        raise SystemExit("empty feature frame for panic exam")

    rows = []
    panic_sells = []
    for name, start, end_w in PANIC_WINDOWS:
        stats = evaluate_window(model, frame, start, end_w, feature_mode=feature_mode)
        trained = _window_trained_on(train_start, start, end_w)
        note = stats["notes"]
        if trained:
            note = (note + "; " if note and note != "—" else "") + "trained_on=true (in-sample)"
        rows.append(
            {
                "model_version": model_version,
                "window": f"{name} ({start}→{end_w})",
                "avg_sell_p": stats["avg_sell_p"],
                "min_crowd_mood": stats["min_crowd_mood"],
                "capitulation_days": stats["capitulation_days"],
                "notes": note,
                "trained_on": int(trained),
            }
        )
        if stats["avg_sell_p"] is not None:
            panic_sells.append(stats["avg_sell_p"])

    calm_sells = []
    calm_caps = 0
    for name, start, end_w in CALM_WINDOWS:
        stats = evaluate_window(model, frame, start, end_w, feature_mode=feature_mode)
        if stats["avg_sell_p"] is not None:
            calm_sells.append(stats["avg_sell_p"])
        calm_caps += int(stats["capitulation_days"])

    avg_panic = float(np.mean(panic_sells)) if panic_sells else None
    avg_calm = float(np.mean(calm_sells)) if calm_sells else None
    summary = {
        "model_version": model_version,
        "train_start": train_start,
        "feature_mode": feature_mode,
        "avg_sell_p_panic": avg_panic,
        "avg_sell_p_calm": avg_calm,
        "sell_p_higher_in_panic": (
            avg_panic is not None and avg_calm is not None and avg_panic > avg_calm
        ),
        "calm_capitulation_days_total": calm_caps,
        "windows": rows,
        "meta_version": meta.get("version"),
    }

    out_df = pd.DataFrame(rows)
    db.init_db(db_path)
    existing = db.read_panic_exam(db_path)
    if not existing.empty:
        existing = existing[existing["model_version"] != model_version]
        combined = pd.concat([existing, out_df], ignore_index=True)
    else:
        combined = out_df
    db.replace_panic_exam(combined, db_path)

    out_path = report_path or (
        ROOT / "models" / f"panic_exam_{model_version}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["report_path"] = str(out_path)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="v4")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--train-start", default=None)
    parser.add_argument("--feature-mode", choices=["v1", "v4"], default=None)
    args = parser.parse_args()
    mode = args.feature_mode or ("v1" if args.version == "v5" else "v4")
    summary = run_exam(
        args.version,
        db_path=args.db,
        train_start=args.train_start,
        feature_mode=mode,
    )
    print(json.dumps(summary, indent=2))
    print(f"wrote {summary.get('report_path')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
