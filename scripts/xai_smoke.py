#!/usr/bin/env python3
"""Cheap Grok sentiment smoke (no secrets printed). Fails soft on rate limits."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from core.secrets import xai_key_present  # noqa: E402
from news_sentiment import score_headlines  # noqa: E402


def main() -> int:
    if not xai_key_present():
        print("FAIL: XAI_API_KEY missing")
        return 1
    # One short, cheap headline — public market news style
    headlines = [
        "Apple reports quarterly revenue in line with analyst estimates; "
        "services segment grows modestly."
    ]
    score = score_headlines("AAPL", headlines)
    if score is None:
        print("WARN: sentiment returned null (rate-limit, model, or network) — fail soft")
        return 0
    print(f"score={score:.4f}")
    print("OK: xAI/Grok sentiment reachable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
