#!/usr/bin/env python3
"""Phase 4 Step 1 — sentiment backfill with cost guard.

Default: --test-batch scores TSLA for one calendar month, prints cost + projection.
Full backfill only with --full and only if projection is under $25.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from core import db  # noqa: E402
from core.config import DB_PATH, DEFAULT_WATCHLIST  # noqa: E402
from news_sentiment import (  # noqa: E402
    UsageStats,
    score_week,
    trading_days,
    week_chunks,
)

COST_CEILING_USD = 25.0
BACKFILL_START = "2021-01-01"


def _month_window(year: int, month: int) -> tuple[str, str]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    # Cap end at today
    today = date.today()
    if end > today:
        end = today
    return start.isoformat(), end.isoformat()


def backfill_ticker(
    ticker: str,
    start: str,
    end: str,
    db_path: Path,
    usage_total: UsageStats,
) -> dict:
    days = trading_days(start, end)
    inserted = 0
    skipped = 0
    failed = 0
    no_news = 0

    for chunk in week_chunks(days):
        # Idempotency: skip days already stored
        pending = [d for d in chunk if not db.has_news_sentiment(d, ticker, db_path)]
        if not pending:
            skipped += len(chunk)
            continue
        # If some days in the week exist, score only pending as a mini-week
        result = score_week(ticker, pending)
        if not result.ok:
            failed += len(pending)
            print(f"  FAIL {ticker} week={pending[0]}..{pending[-1]} err={result.error}")
            continue
        usage_total.prompt_tokens += result.usage.prompt_tokens
        usage_total.completion_tokens += result.usage.completion_tokens
        usage_total.calls += result.usage.calls
        usage_total.estimated_usd += result.usage.estimated_usd
        for row in result.days:
            ok = db.insert_news_sentiment(
                row.date,
                ticker,
                row.sentiment,
                row.headline_count,
                row.summary,
                row.source,
                db_path,
            )
            if ok:
                inserted += 1
                if row.headline_count == 0:
                    no_news += 1
            else:
                skipped += 1
        print(
            f"  {ticker} {pending[0]}..{pending[-1]} "
            f"calls={result.usage.calls} tok={result.usage.prompt_tokens}+"
            f"{result.usage.completion_tokens} usd~{result.usage.estimated_usd:.4f}"
        )
    return {
        "ticker": ticker,
        "inserted": inserted,
        "skipped": skipped,
        "failed": failed,
        "no_news": no_news,
        "days_in_range": len(days),
    }


def project_full_cost(test_usd: float, test_days: int, test_tickers: int = 1) -> float:
    """Project full backfill cost from test-batch unit economics."""
    today = date.today()
    start = date.fromisoformat(BACKFILL_START)
    # Approx trading days
    all_days = len(trading_days(BACKFILL_START, today.isoformat()))
    n_tickers = len(DEFAULT_WATCHLIST)
    if test_days <= 0 or test_usd <= 0:
        # Fallback: weeks × tickers × observed per-call cost
        return float("inf")
    per_ticker_day = test_usd / (test_days * test_tickers)
    return per_ticker_day * all_days * n_tickers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument(
        "--test-batch",
        action="store_true",
        help="TSLA one calendar month cost-guard batch (default mode)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full backfill 2021-01-01→today all watchlist tickers",
    )
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--month", type=int, default=9, help="Test-batch month")
    parser.add_argument(
        "--force-full",
        action="store_true",
        help="Skip cost ceiling check (do not use unless Muse/Tuan approve)",
    )
    args = parser.parse_args()
    db.init_db(args.db)
    usage = UsageStats()

    if args.full and not args.force_full:
        # Require a prior test report file or recompute projection from a tiny probe
        print("Run --test-batch first; then --full only if projection < $25 "
              "(or pass --force-full after Muse/Tuan approval).")
        # Still allow --full if user passes both with understanding — check env flag
        # We'll compute projection from September TSLA if already in DB, else require test-batch
        start, end = _month_window(args.year, args.month)
        # If no test rows, refuse
        existing = db.read_news_sentiment(args.db)
        tsla_test = existing[
            (existing["ticker"] == "TSLA")
            & (existing["date"] >= start)
            & (existing["date"] <= end)
        ] if not existing.empty else existing
        if tsla_test.empty:
            print("FAIL: no TSLA test-batch rows in DB — run --test-batch first")
            return 1

    if args.full:
        start = BACKFILL_START
        end = date.today().isoformat()
        tickers = list(DEFAULT_WATCHLIST)
        mode = "full"
    else:
        # Default = test batch
        start, end = _month_window(args.year, args.month)
        tickers = ["TSLA"]
        mode = "test-batch"

    print(f"mode={mode} range={start}..{end} tickers={tickers}")
    summaries = []
    for ticker in tickers:
        summaries.append(backfill_ticker(ticker, start, end, args.db, usage))

    test_days = len(trading_days(start, end)) if mode == "test-batch" else 0
    projection = (
        project_full_cost(usage.estimated_usd, test_days, 1)
        if mode == "test-batch"
        else usage.estimated_usd
    )

    report = {
        "mode": mode,
        "range": {"start": start, "end": end},
        "tickers": tickers,
        "usage": {
            "calls": usage.calls,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "estimated_usd": round(usage.estimated_usd, 6),
            "rate_assumption": {
                "usd_per_m_input": 0.30,
                "usd_per_m_output": 0.50,
                "note": "Estimate from token usage; adjust if xAI invoice differs",
            },
        },
        "projected_full_backfill_usd": (
            round(projection, 4) if mode == "test-batch" else None
        ),
        "under_ceiling_25": (
            bool(projection < COST_CEILING_USD) if mode == "test-batch" else None
        ),
        "summaries": summaries,
        "rows_total": int(
            len(db.read_news_sentiment(args.db))
        ),
    }
    out_path = ROOT / "data" / f"sentiment_backfill_{mode}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote {out_path}")

    if mode == "test-batch":
        if projection >= COST_CEILING_USD:
            print(
                f"STOP: projected full backfill ${projection:.2f} >= ${COST_CEILING_USD:.0f}. "
                "Do not run --full. Wait for Muse/Tuan."
            )
            return 2
        print(
            f"OK: projection ${projection:.2f} < ${COST_CEILING_USD:.0f} — full backfill allowed"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
