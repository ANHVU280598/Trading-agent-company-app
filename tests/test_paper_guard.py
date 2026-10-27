"""Phase 3 paper-endpoint guardrail tests."""

from __future__ import annotations

import pytest

from core.agent import assert_paper_base_url


def test_paper_url_accepted() -> None:
    assert_paper_base_url("https://paper-api.alpaca.markets")


def test_live_alpaca_url_rejected() -> None:
    with pytest.raises(RuntimeError, match="paper"):
        assert_paper_base_url("https://api.alpaca.markets")


def test_random_url_without_paper_rejected() -> None:
    with pytest.raises(RuntimeError, match="paper"):
        assert_paper_base_url("https://broker.example.com")
