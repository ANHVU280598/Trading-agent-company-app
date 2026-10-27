#!/usr/bin/env python3
"""Smoke-test Alpaca PAPER account connectivity (read-only).

Never prints secret values. Does not place orders.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from core.alpaca_broker import AlpacaPaperBroker  # noqa: E402
from core.secrets import alpaca_creds_present, load_alpaca_creds  # noqa: E402


def main() -> int:
    if not alpaca_creds_present():
        print("FAIL: Alpaca paper keys not found in environment")
        return 1
    creds = load_alpaca_creds()
    assert creds is not None
    # Show host only — never keys
    print(f"base_url_host_ok={('paper' in creds.base_url.lower())}")
    print(f"base_url={creds.base_url}")
    broker = AlpacaPaperBroker(creds)
    acct = broker.get_account()
    print(f"status={acct.status}")
    print(f"account={acct.account_number_masked}")
    print(f"equity={acct.equity:.2f}")
    print(f"cash={acct.cash:.2f}")
    print(f"buying_power={acct.buying_power:.2f}")
    print("OK: Alpaca paper account reachable (read-only smoke)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
