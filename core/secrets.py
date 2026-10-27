"""Resolve API credentials from env. Never log or return secret values to UI."""

from __future__ import annotations

# Load .env file early to ensure environment variables are available
from pathlib import Path as _Path
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(_Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass  # dotenv not available


import os
from dataclasses import dataclass


DEFAULT_PAPER_BASE_URL = "https://paper-api.alpaca.markets"


@dataclass(frozen=True)
class AlpacaCreds:
    key_id: str
    secret_key: str
    base_url: str


def _first_env(*names: str) -> str:
    for name in names:
        val = os.getenv(name, "").strip()
        if val:
            return val
    return ""


def alpaca_creds_present() -> bool:
    return bool(
        _first_env("ALPACA_API_KEY", "APCA_API_KEY_ID")
        and _first_env("ALPACA_API_SECRET", "ALPACA_SECRET_KEY", "APCA_API_SECRET_KEY")
    )


def load_alpaca_creds() -> AlpacaCreds | None:
    key = _first_env("ALPACA_API_KEY", "APCA_API_KEY_ID")
    secret = _first_env("ALPACA_API_SECRET", "ALPACA_SECRET_KEY", "APCA_API_SECRET_KEY")
    if not key or not secret:
        return None
    base = _first_env("ALPACA_BASE_URL", "APCA_API_BASE_URL") or DEFAULT_PAPER_BASE_URL
    return AlpacaCreds(key_id=key, secret_key=secret, base_url=base.rstrip("/"))


def xai_key_present() -> bool:
    return bool(os.getenv("XAI_API_KEY", "").strip())


def finnhub_key_present() -> bool:
    return bool(os.getenv("FINNHUB_API_KEY", "").strip())
