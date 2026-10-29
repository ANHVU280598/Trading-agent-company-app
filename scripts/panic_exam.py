#!/usr/bin/env python3
"""Model v4 Step 3 — standing panic exam over fixed historical windows.

Not a fifth gate condition. Results are reported, never hidden.
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
from core.features import FEATURE_ORDER_V4, build_features_v4  # noqa: E402
from core.model_store import load_model  # noqa: E402

# Fixed windows — never edited to make a model look good (Muse Doc).
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


def _feature_frame(
    tickers: list[str],
    hist_start: str,
    end: str,
    behavior: pd.DataFrame,
) -> pd.DataFrame:
    spy = get_daily_bars("SPY", hist_start, end)
    if spy.empty:
        return pd.DataFrame()
    spy_i = spy.set_index("date")
    spy_i.index = spy_i.index.astype(str)
    frames = []
    for t in tickers:
        bars = get_daily_bars(t, hist_start, end)
        if bars.empty:
            continue
        indexed = bars.set_index("date")
        indexed.index = indexed.index.astype(str)
        feats = build_features_v4(indexed, spy_i, behavior=behavior)
        feats = feats.copy()
        feats["ticker"] = t
        feats["date"] = feats.index.astype(str)
        frames.append(feats.reset_index(drop=True))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _predict_sell_p(model, frame: pd.DataFrame) -> pd.Series:
    cols = list(getattr(model, "feature_names_in_", FEATURE_ORDER_V4))
    use = frame.dropna(subset=cols)
    if use.empty:
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
    sell = _predict_sell_p(model, sub)
    avg_sell = float(sell.mean()) if len(sell) else None
    mood = sub["crowd_mood"].dropna()
    min_mood = float(mood.min()) if len(mood) else None
    # Unique session-days with any ticker capitulation
    caps = sub[sub["capitulation_ticker"].fillna(0) > 0]["date"].nunique()
    # Crowd-like note
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
        "capitulation_days": int(caps),
        "rows": int(len(sub)),
        "notes": "; ".join(note_bits) if note_bits else "—",
    }


def run_exam(
    model_version: str = "v4",
    *,
    db_path: Path = DB_PATH,
    tickers: list[str] | None = None,
) -> dict:
    tickers = tickers or list(DEFAULT_WATCHLIST)
    behavior = load_behavior_csv()
    if behavior.empty:
        try:
            behavior = db.read_behavior(db_path)
        except Exception:
            behavior = pd.DataFrame()
    if behavior.empty:
        raise SystemExit("behavior table empty — run scripts/refresh_behavior.py")

    model, meta = load_model(model_version)
    hist_start = "2017-01-01"  # SPY warm-up for crowd_mood; VIX series from 2019
    end = max(w[2] for w in PANIC_WINDOWS + CALM_WINDOWS)
    print(f"building feature frame {hist_start}..{end} for panic exam…")
    frame = _feature_frame(tickers, hist_start, end, behavior)
    if frame.empty:
        raise SystemExit("empty feature frame for panic exam")

    rows = []
    panic_sells = []
    for name, start, end_w in PANIC_WINDOWS:
        stats = evaluate_window(model, frame, start, end_w)
        rows.append(
            {
                "model_version": model_version,
                "window": f"{name} ({start}→{end_w})",
                "avg_sell_p": stats["avg_sell_p"],
                "min_crowd_mood": stats["min_crowd_mood"],
                "capitulation_days": stats["capitulation_days"],
                "notes": stats["notes"],
            }
        )
        if stats["avg_sell_p"] is not None:
            panic_sells.append(stats["avg_sell_p"])

    calm_sells = []
    calm_caps = 0
    for name, start, end_w in CALM_WINDOWS:
        stats = evaluate_window(model, frame, start, end_w)
        if stats["avg_sell_p"] is not None:
            calm_sells.append(stats["avg_sell_p"])
        calm_caps += int(stats["capitulation_days"])

    avg_panic = float(np.mean(panic_sells)) if panic_sells else None
    avg_calm = float(np.mean(calm_sells)) if calm_sells else None
    summary = {
        "model_version": model_version,
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
    # Keep other model versions' rows; replace this version
    existing = db.read_panic_exam(db_path)
    if not existing.empty:
        existing = existing[existing["model_version"] != model_version]
        combined = pd.concat([existing, out_df], ignore_index=True)
    else:
        combined = out_df
    db.replace_panic_exam(combined, db_path)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="v4")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args()
    summary = run_exam(args.version, db_path=args.db)
    print(json.dumps(summary, indent=2))
    print(f"wrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
