"""Phase 4 Step 4 — v2 promotion gate (no hand-tuning after peeking)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class GateResult:
    passed: bool
    verdict: str  # Kept | Rejected
    reasons: list[str]
    checks: dict[str, Any]


def evaluate_gate(
    v1: dict[str, Any],
    v2: dict[str, Any],
    *,
    month_drop_limit: float = 0.10,
) -> GateResult:
    """v2 trades only if ALL checks pass.

    (1) walk-forward accuracy beats v1
    (2) buy precision >= v1
    (3) sell precision >= v1
    (4) no month more than ``month_drop_limit`` accuracy points below v1's same month
    """
    reasons: list[str] = []
    checks: dict[str, Any] = {}

    acc1 = float(v1["accuracy"])
    acc2 = float(v2["accuracy"])
    beat_acc = acc2 > acc1
    checks["accuracy_v1"] = acc1
    checks["accuracy_v2"] = acc2
    checks["accuracy_beats_v1"] = beat_acc
    if not beat_acc:
        reasons.append(
            f"walk-forward accuracy {acc2:.4f} does not beat v1 {acc1:.4f}"
        )

    bp1 = float(v1.get("buy_precision") or 0.0)
    bp2 = float(v2.get("buy_precision") or 0.0)
    buy_ok = bp2 >= bp1
    checks["buy_precision_v1"] = bp1
    checks["buy_precision_v2"] = bp2
    checks["buy_precision_ok"] = buy_ok
    if not buy_ok:
        reasons.append(f"buy precision {bp2:.4f} < v1 {bp1:.4f}")

    sp1 = float(v1.get("sell_precision") or 0.0)
    sp2 = float(v2.get("sell_precision") or 0.0)
    sell_ok = sp2 >= sp1
    checks["sell_precision_v1"] = sp1
    checks["sell_precision_v2"] = sp2
    checks["sell_precision_ok"] = sell_ok
    if not sell_ok:
        reasons.append(f"sell precision {sp2:.4f} < v1 {sp1:.4f}")

    months1 = {m["month"]: float(m["accuracy"]) for m in v1.get("walk_forward") or []}
    months2 = {m["month"]: float(m["accuracy"]) for m in v2.get("walk_forward") or []}
    bad_months: list[str] = []
    for month, a1 in months1.items():
        if month not in months2:
            continue
        a2 = months2[month]
        if a1 - a2 > month_drop_limit + 1e-12:
            bad_months.append(f"{month}: v2 {a2:.4f} vs v1 {a1:.4f}")
    month_ok = len(bad_months) == 0
    checks["disastrous_months"] = bad_months
    checks["month_ok"] = month_ok
    if not month_ok:
        reasons.append(
            "month drop > 10 pts vs v1: " + "; ".join(bad_months)
        )

    passed = beat_acc and buy_ok and sell_ok and month_ok
    return GateResult(
        passed=passed,
        verdict="Kept" if passed else "Rejected",
        reasons=reasons or ["all gate checks passed"],
        checks=checks,
    )
