"""Model v5 universe freeze + gate continuity + panic trained_on."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from core.gate import evaluate_gate, evaluate_gate_v5
from core.universe import (
    ORIGINAL5,
    UNIVERSE_COUNT,
    assert_universe_frozen,
    load_universe,
    universe_tickers,
)

_pe = importlib.util.spec_from_file_location(
    "panic_exam", Path(__file__).resolve().parents[1] / "scripts" / "panic_exam.py"
)
assert _pe and _pe.loader
_panic = importlib.util.module_from_spec(_pe)
_pe.loader.exec_module(_panic)
_window_trained_on = _panic._window_trained_on


def test_universe_count_and_original5() -> None:
    tickers = universe_tickers()
    assert len(tickers) == UNIVERSE_COUNT
    for t in ORIGINAL5:
        assert t in tickers
    info = assert_universe_frozen()
    assert info["count"] == UNIVERSE_COUNT


def test_universe_freeze_refuses_silent_count_change(tmp_path) -> None:
    src = load_universe()
    bad = src.iloc[:-1].copy()
    path = tmp_path / "universe.csv"
    path.write_text(
        "# version=1; as_of=2026-10-29; count=49\n" + bad.to_csv(index=False),
        encoding="utf-8",
    )
    try:
        assert_universe_frozen(path, expected_count=UNIVERSE_COUNT)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "count" in str(exc).lower() or "ticker" in str(exc).lower()


def test_gate_v5_continuity() -> None:
    base = {
        "accuracy": 0.55,
        "buy_precision": 0.4,
        "sell_precision": 0.3,
        "walk_forward": [{"month": "2024-01", "accuracy": 0.55}],
    }
    good = {
        "accuracy": 0.56,
        "buy_precision": 0.41,
        "sell_precision": 0.31,
        "walk_forward": [{"month": "2024-01", "accuracy": 0.56}],
    }
    bad_cont = dict(good)
    assert evaluate_gate(base, good).passed
    assert evaluate_gate_v5(
        base, good, base_original5={"accuracy": 0.55}, challenger_original5={"accuracy": 0.54}
    ).passed
    fail = evaluate_gate_v5(
        base,
        good,
        base_original5={"accuracy": 0.55},
        challenger_original5={"accuracy": 0.52},  # >2 pts below
    )
    assert not fail.passed
    assert any("continuity" in r for r in fail.reasons)


def test_panic_trained_on_flag() -> None:
    # v5 trains from 2015 → 2020 and 2022 windows are in-sample
    assert _window_trained_on("2015-01-01", "2020-02-19", "2020-03-23") is True
    assert _window_trained_on("2015-01-01", "2022-01-03", "2022-10-14") is True
    assert _window_trained_on("2021-01-01", "2020-02-19", "2020-03-23") is False
