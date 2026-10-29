"""Model v5 frozen tradable/training universe (50 tickers)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import ROOT

UNIVERSE_CSV = ROOT / "data" / "universe.csv"
UNIVERSE_VERSION = 1
UNIVERSE_COUNT = 50
ORIGINAL5 = ["SPY", "AAPL", "MSFT", "NVDA", "TSLA"]


def _header_meta(path: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    if not path.exists():
        return meta
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        # "# key=value; key2=value2"
        body = line.lstrip("# ").strip()
        for part in body.replace(",", ";").split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                meta[k.strip()] = v.strip()
    return meta


def load_universe(path: Path = UNIVERSE_CSV) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, comment="#")
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    return df


def universe_tickers(path: Path = UNIVERSE_CSV) -> list[str]:
    return load_universe(path)["ticker"].tolist()


def universe_hash(path: Path = UNIVERSE_CSV) -> str:
    raw = path.read_bytes()
    return hashlib.sha256(raw).hexdigest()[:16]


def assert_universe_frozen(
    path: Path = UNIVERSE_CSV,
    *,
    expected_count: int = UNIVERSE_COUNT,
    expected_version: int = UNIVERSE_VERSION,
    decisions_flagged: bool = False,
) -> dict[str, Any]:
    """Refuse silent universe edits. Version bump must be loud (DECISIONS)."""
    meta = _header_meta(path)
    df = load_universe(path)
    n = int(len(df))
    ver = int(meta.get("version") or 0)
    info = {
        "count": n,
        "version": ver,
        "hash": universe_hash(path),
        "as_of": meta.get("as_of"),
    }
    if n != expected_count and not decisions_flagged:
        raise RuntimeError(
            f"universe.csv ticker count {n} != recorded {expected_count}; "
            "bump version + DECISIONS.md before training"
        )
    if ver != expected_version and not decisions_flagged:
        raise RuntimeError(
            f"universe.csv version {ver} != code expected {expected_version}; "
            "bump UNIVERSE_VERSION in core/universe.py after DECISIONS.md entry"
        )
    if n != len(set(df["ticker"])):
        raise RuntimeError("universe.csv has duplicate tickers")
    return info
