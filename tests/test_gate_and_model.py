"""Gate + save/load tests (Phase 4)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from core.features import FEATURE_ORDER_V1, FEATURE_ORDER_V2
from core.gate import evaluate_gate
from core.model_store import load_model, save_model


def _metrics(acc: float, buy_p: float, sell_p: float, months: list[tuple[str, float]]) -> dict:
    return {
        "accuracy": acc,
        "buy_precision": buy_p,
        "sell_precision": sell_p,
        "walk_forward": [{"month": m, "accuracy": a} for m, a in months],
    }


def test_gate_passes_when_all_checks_hold() -> None:
    v1 = _metrics(0.55, 0.40, 0.35, [("2024-01", 0.50), ("2024-02", 0.52)])
    v2 = _metrics(0.57, 0.42, 0.36, [("2024-01", 0.51), ("2024-02", 0.55)])
    gate = evaluate_gate(v1, v2)
    assert gate.passed
    assert gate.verdict == "Kept"


def test_gate_rejects_on_accuracy() -> None:
    v1 = _metrics(0.56, 0.40, 0.35, [("2024-01", 0.50)])
    v2 = _metrics(0.55, 0.50, 0.50, [("2024-01", 0.50)])
    gate = evaluate_gate(v1, v2)
    assert not gate.passed
    assert "accuracy" in gate.reasons[0]


def test_gate_rejects_disastrous_month() -> None:
    v1 = _metrics(0.55, 0.40, 0.35, [("2024-01", 0.60), ("2024-02", 0.50)])
    v2 = _metrics(0.56, 0.40, 0.35, [("2024-01", 0.45), ("2024-02", 0.55)])
    # 0.60 - 0.45 = 0.15 > 0.10
    gate = evaluate_gate(v1, v2)
    assert not gate.passed
    assert any("month drop" in r for r in gate.reasons)


def test_save_load_same_proba(tmp_path: Path, monkeypatch) -> None:
    import core.model_store as ms

    monkeypatch.setattr(ms, "MODELS_DIR", tmp_path)
    monkeypatch.setattr(ms, "V2_PATH", tmp_path / "model_v2.joblib")
    monkeypatch.setattr(ms, "V2_META", tmp_path / "model_v2.json")

    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, len(FEATURE_ORDER_V2)))
    y = rng.choice(["buy", "hold", "sell"], size=200)
    clf = RandomForestClassifier(
        n_estimators=20, min_samples_leaf=5, random_state=7
    )
    clf.fit(X, y)
    save_model(clf, {"version": "v2", "feature_list": FEATURE_ORDER_V2}, version="v2")
    loaded, meta = load_model("v2")
    assert meta["version"] == "v2"
    p0 = clf.predict_proba(X[:5])
    p1 = loaded.predict_proba(X[:5])
    assert np.allclose(p0, p1)


def test_feature_order_v2_exact() -> None:
    assert FEATURE_ORDER_V2 == FEATURE_ORDER_V1 + [
        "sentiment",
        "headline_count",
        "spy_regime",
        "rs21",
    ]
