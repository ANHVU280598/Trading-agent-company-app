"""Clearly fake sample rows for H step 2 layout review.

Deleted in H step 4 when pages switch to SQLite. Do not use for decisions.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from core.config import DEFAULT_WATCHLIST, STARTING_PAPER_CASH

SAMPLE_AS_OF = "2026-10-27"
SAMPLE_START = "2026-09-02"
WATCHLIST = list(DEFAULT_WATCHLIST)


def sample_banner() -> str:
    return "Sample data"


def portfolio_history() -> pd.DataFrame:
    """~40 trading days of fake agent vs benchmark equity."""
    rng = np.random.default_rng(7)
    start = date.fromisoformat(SAMPLE_START)
    days: list[date] = []
    d = start
    while d <= date.fromisoformat(SAMPLE_AS_OF):
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    n = len(days)
    agent_rets = rng.normal(0.0008, 0.006, n)
    bench_rets = rng.normal(0.0005, 0.005, n)
    agent = STARTING_PAPER_CASH * np.cumprod(1 + agent_rets)
    bench = STARTING_PAPER_CASH * np.cumprod(1 + bench_rets)
    # Pin last day to wireframe-ish numbers
    agent[-1] = 102_340.0
    bench[-1] = 100_940.0
    high = np.maximum.accumulate(agent)
    drawdown = agent / high - 1.0
    cash = np.linspace(80_000, 61_200, n)
    return pd.DataFrame(
        {
            "date": [x.isoformat() for x in days],
            "value": agent,
            "benchmark_value": bench,
            "cash": cash,
            "drawdown": drawdown,
        }
    )


def positions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"ticker": "AAPL", "shares": 42.1250, "avg_cost": 218.40, "price": 227.10},
            {"ticker": "MSFT", "shares": 18.5000, "avg_cost": 410.00, "price": 428.55},
            {"ticker": "NVDA", "shares": 12.0000, "avg_cost": 112.20, "price": 141.80},
        ]
    )


def signals_latest() -> pd.DataFrame:
    rows = [
        ("SPY", "hold", 0.35, 0.44, 0.21, 512.30, 51.0, -0.012, None, "—"),
        ("AAPL", "buy", 0.61, 0.28, 0.11, 227.10, 58.0, -0.008, 0.42, "Apple expands AI features in next OS"),
        ("MSFT", "hold", 0.22, 0.55, 0.23, 428.55, 49.0, -0.015, 0.10, "Cloud growth steady in quarterly update"),
        ("NVDA", "buy", 0.58, 0.30, 0.12, 141.80, 62.0, -0.022, 0.55, "GPU demand remains elevated"),
        ("TSLA", "sell", 0.18, 0.27, 0.55, 248.40, 41.0, -0.085, -0.35, "Delivery miss weighs on shares"),
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "ticker",
            "signal",
            "buy_p",
            "hold_p",
            "sell_p",
            "price",
            "rsi14",
            "drawdown63",
            "sentiment",
            "headline",
        ],
    ).assign(date=SAMPLE_AS_OF)


def signal_gated() -> dict[str, bool]:
    """True when raw signal was gated to HOLD for trading."""
    return {"SPY": False, "AAPL": False, "MSFT": False, "NVDA": False, "TSLA": False}


def trades() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": 1,
                "date": "2026-09-12",
                "ticker": "AAPL",
                "action": "buy",
                "shares": 42.1250,
                "price": 218.40,
                "confidence": 0.61,
                "status": "Open",
                "realized_pnl": None,
            },
            {
                "id": 2,
                "date": "2026-09-18",
                "ticker": "NVDA",
                "action": "buy",
                "shares": 15.0000,
                "price": 118.00,
                "confidence": 0.57,
                "status": "Closed",
                "realized_pnl": 420.50,
            },
            {
                "id": 3,
                "date": "2026-09-25",
                "ticker": "TSLA",
                "action": "buy",
                "shares": 20.0000,
                "price": 260.00,
                "confidence": 0.56,
                "status": "Closed",
                "realized_pnl": -312.00,
            },
            {
                "id": 4,
                "date": "2026-10-03",
                "ticker": "MSFT",
                "action": "buy",
                "shares": 18.5000,
                "price": 410.00,
                "confidence": 0.59,
                "status": "Open",
                "realized_pnl": None,
            },
            {
                "id": 5,
                "date": "2026-10-10",
                "ticker": "NVDA",
                "action": "sell",
                "shares": 3.0000,
                "price": 135.00,
                "confidence": 0.60,
                "status": "Closed",
                "realized_pnl": 51.00,
            },
            {
                "id": 6,
                "date": "2026-10-20",
                "ticker": "TSLA",
                "action": "sell",
                "shares": 20.0000,
                "price": 244.40,
                "confidence": 0.58,
                "status": "Closed",
                "realized_pnl": -312.00,
            },
        ]
    )


def model_runs() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-10-27",
                "train_rows": 4200,
                "accuracy": 0.566,
                "baseline": 0.562,
                "verdict": "Kept",
                "notes": "8 features, hindsight labels",
                "month": "2026-10",
            },
            {
                "date": "2026-10-20",
                "train_rows": 4100,
                "accuracy": 0.551,
                "baseline": 0.560,
                "verdict": "Rejected",
                "notes": "8 features, hindsight labels",
                "month": "2026-09",
            },
            {
                "date": "2026-10-13",
                "train_rows": 4000,
                "accuracy": 0.558,
                "baseline": 0.555,
                "verdict": "Kept",
                "notes": "8 features, hindsight labels",
                "month": "2026-08",
            },
            {
                "date": "2026-10-06",
                "train_rows": 3900,
                "accuracy": 0.549,
                "baseline": 0.552,
                "verdict": "Rejected",
                "notes": "8 features, hindsight labels",
                "month": "2026-07",
            },
        ]
    )


def walk_forward() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "month": ["2026-07", "2026-08", "2026-09", "2026-10"],
            "accuracy": [0.549, 0.558, 0.551, 0.566],
        }
    )


def confusion_matrix() -> pd.DataFrame:
    # rows/cols: sell, hold, buy
    return pd.DataFrame(
        [[40, 22, 8], [30, 210, 25], [12, 28, 55]],
        index=["sell", "hold", "buy"],
        columns=["sell", "hold", "buy"],
    )


def feature_importance() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "feature": [
                "ret1",
                "ret5",
                "ret21",
                "vol21",
                "rsi14",
                "dist_ma50",
                "drawdown63",
                "volz",
            ],
            "importance": [0.09, 0.14, 0.11, 0.08, 0.16, 0.13, 0.18, 0.11],
        }
    )


def price_history(ticker: str = "SPY") -> pd.DataFrame:
    rng = np.random.default_rng(abs(hash(ticker)) % (2**32))
    start = date.fromisoformat(SAMPLE_AS_OF) - timedelta(days=200)
    days: list[date] = []
    d = start
    end = date.fromisoformat(SAMPLE_AS_OF)
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    base = {"SPY": 500.0, "AAPL": 210.0, "MSFT": 400.0, "NVDA": 120.0, "TSLA": 250.0}.get(
        ticker, 100.0
    )
    rets = rng.normal(0.0004, 0.012, len(days))
    close = base * np.cumprod(1 + rets)
    return pd.DataFrame({"date": [x.isoformat() for x in days], "close": close})


def signal_history(ticker: str = "SPY") -> pd.DataFrame:
    prices = price_history(ticker)
    rng = np.random.default_rng(3)
    picks = prices.iloc[::15].copy()
    signals = rng.choice(["buy", "sell", "hold"], size=len(picks), p=[0.2, 0.15, 0.65])
    return pd.DataFrame(
        {
            "date": picks["date"].values,
            "signal": signals,
            "price": picks["close"].values,
        }
    )


def feature_values(ticker: str = "SPY") -> dict[str, float | str | None]:
    samples = {
        "SPY": {
            "ret1": 0.002,
            "ret5": 0.011,
            "ret21": 0.024,
            "vol21": 0.12,
            "rsi14": 51.0,
            "dist_ma50": 0.015,
            "drawdown63": -0.012,
            "volz": 0.40,
            "sentiment": None,
            "spy_regime": "Up",
        },
        "AAPL": {
            "ret1": 0.008,
            "ret5": 0.021,
            "ret21": 0.045,
            "vol21": 0.18,
            "rsi14": 58.0,
            "dist_ma50": 0.022,
            "drawdown63": -0.008,
            "volz": 1.10,
            "sentiment": 0.42,
            "spy_regime": "Up",
        },
    }
    return samples.get(ticker, samples["SPY"])


def settings() -> dict[str, object]:
    return {
        "watchlist": list(WATCHLIST),
        "position_size": 0.20,
        "drawdown_freeze": 0.10,
        "confidence_threshold": 0.55,
    }


def signal_grades() -> pd.DataFrame:
    """Fewer than 30 graded — scorecard shows the exact not-enough note."""
    return pd.DataFrame(
        [
            {
                "date": "2026-09-18",
                "ticker": "NVDA",
                "signal": "buy",
                "confidence": 0.57,
                "price_then": 118.0,
                "ret_1d": 0.012,
                "ret_5d": 0.041,
                "ret_20d": 0.08,
                "spy_ret_1d": 0.004,
                "spy_ret_5d": 0.015,
                "spy_ret_20d": 0.03,
            },
            {
                "date": "2026-10-20",
                "ticker": "TSLA",
                "signal": "sell",
                "confidence": 0.58,
                "price_then": 244.4,
                "ret_1d": -0.01,
                "ret_5d": -0.03,
                "ret_20d": None,
                "spy_ret_1d": 0.002,
                "spy_ret_5d": 0.01,
                "spy_ret_20d": None,
            },
        ]
    )


def dashboard_meta() -> dict[str, object]:
    hist = portfolio_history()
    last = hist.iloc[-1]
    start_val = float(hist.iloc[0]["value"])
    agent_ret = float(last["value"]) / start_val - 1.0
    bench_ret = float(last["benchmark_value"]) / float(hist.iloc[0]["benchmark_value"]) - 1.0
    high = float(hist["value"].max())
    return {
        "last_updated": f"{SAMPLE_AS_OF} 16:05 ET",
        "market_open": False,
        "portfolio_value": float(last["value"]),
        "portfolio_ret": agent_ret,
        "start_date": SAMPLE_START,
        "agent_ret": agent_ret,
        "bench_ret": bench_ret,
        "cash": float(last["cash"]),
        "cash_pct": float(last["cash"]) / float(last["value"]),
        "drawdown": float(last["drawdown"]),
        "high_water": high,
        "buys_frozen": False,
    }
