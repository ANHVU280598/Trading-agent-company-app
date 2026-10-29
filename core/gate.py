"""Promotion gate (Phase 4 / Model v3+) — no hand-tuning after peeking."""

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
    base: dict[str, Any],
    challenger: dict[str, Any],
    *,
    month_drop_limit: float = 0.10,
) -> GateResult:
    """Challenger trades only if ALL checks pass vs base.

    Accepts either (base, challenger) or legacy (v1, v2) call sites.
    """
    reasons: list[str] = []
    checks: dict[str, Any] = {}

    acc1 = float(base["accuracy"])
    acc2 = float(challenger["accuracy"])
    beat_acc = acc2 > acc1
    checks["accuracy_base"] = acc1
    checks["accuracy_challenger"] = acc2
    checks["accuracy_v1"] = acc1  # back-compat aliases for Phase 4 tests
    checks["accuracy_v2"] = acc2
    checks["accuracy_beats_base"] = beat_acc
    checks["accuracy_beats_v1"] = beat_acc
    if not beat_acc:
        reasons.append(
            f"walk-forward accuracy {acc2:.4f} does not beat base {acc1:.4f}"
        )

    bp1 = float(base.get("buy_precision") or 0.0)
    bp2 = float(challenger.get("buy_precision") or 0.0)
    buy_ok = bp2 >= bp1
    checks["buy_precision_base"] = bp1
    checks["buy_precision_challenger"] = bp2
    checks["buy_precision_v1"] = bp1
    checks["buy_precision_v2"] = bp2
    checks["buy_precision_ok"] = buy_ok
    if not buy_ok:
        reasons.append(f"buy precision {bp2:.4f} < base {bp1:.4f}")

    sp1 = float(base.get("sell_precision") or 0.0)
    sp2 = float(challenger.get("sell_precision") or 0.0)
    sell_ok = sp2 >= sp1
    checks["sell_precision_base"] = sp1
    checks["sell_precision_challenger"] = sp2
    checks["sell_precision_v1"] = sp1
    checks["sell_precision_v2"] = sp2
    checks["sell_precision_ok"] = sell_ok
    if not sell_ok:
        reasons.append(f"sell precision {sp2:.4f} < base {sp1:.4f}")

    months1 = {m["month"]: float(m["accuracy"]) for m in base.get("walk_forward") or []}
    months2 = {
        m["month"]: float(m["accuracy"]) for m in challenger.get("walk_forward") or []
    }
    bad_months: list[str] = []
    for month, a1 in months1.items():
        if month not in months2:
            continue
        a2 = months2[month]
        if a1 - a2 > month_drop_limit + 1e-12:
            bad_months.append(f"{month}: challenger {a2:.4f} vs base {a1:.4f}")
    month_ok = len(bad_months) == 0
    checks["disastrous_months"] = bad_months
    checks["month_ok"] = month_ok
    if not month_ok:
        reasons.append("month drop > 10 pts vs base: " + "; ".join(bad_months))

    passed = beat_acc and buy_ok and sell_ok and month_ok
    return GateResult(
        passed=passed,
        verdict="Kept" if passed else "Rejected",
        reasons=reasons or ["all gate checks passed"],
        checks=checks,
    )


def evaluate_gate_v5(
    base: dict[str, Any],
    challenger: dict[str, Any],
    *,
    base_original5: dict[str, Any] | None = None,
    challenger_original5: dict[str, Any] | None = None,
    continuity_limit: float = 0.02,
    month_drop_limit: float = 0.10,
) -> GateResult:
    """Model v5 gate = Phase 4 four checks + original-5 continuity guard.

    Continuity: on the original 5 tickers pooled, challenger accuracy must not
    fall more than `continuity_limit` (default 2 pts) below base.
    """
    base_gate = evaluate_gate(base, challenger, month_drop_limit=month_drop_limit)
    reasons = list(base_gate.reasons) if not base_gate.passed else []
    checks = dict(base_gate.checks)

    cont_ok = True
    if base_original5 is not None and challenger_original5 is not None:
        a1 = float(base_original5.get("accuracy") or 0.0)
        a2 = float(challenger_original5.get("accuracy") or 0.0)
        cont_ok = a2 >= a1 - continuity_limit - 1e-12
        checks["original5_accuracy_base"] = a1
        checks["original5_accuracy_challenger"] = a2
        checks["original5_continuity_ok"] = cont_ok
        if not cont_ok:
            reasons.append(
                f"original-5 continuity: accuracy {a2:.4f} is more than "
                f"{continuity_limit:.0%} below base {a1:.4f}"
            )
    else:
        checks["original5_continuity_ok"] = None

    # If base four passed, reasons may be the success message — clear before append
    if base_gate.passed:
        reasons = [r for r in reasons if r != "all gate checks passed"]

    passed = base_gate.passed and cont_ok
    if passed and not reasons:
        reasons = ["all gate checks passed"]
    return GateResult(
        passed=passed,
        verdict="Kept" if passed else "Rejected",
        reasons=reasons,
        checks=checks,
    )
