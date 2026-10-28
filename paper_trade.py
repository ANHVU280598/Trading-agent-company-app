"""Daily paper agent — reads settings from SQLite, writes signals/trades/portfolio.

Phase 3: with --broker alpaca, submits matching paper orders to Alpaca paper API.
Live trading is never enabled. Paper-only.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from dotenv import load_dotenv

from core.agent import buys_frozen, confidence_gate, position_buy_shares
from core.config import DB_PATH, ROOT, STARTING_PAPER_CASH
from core.data import get_daily_bars, get_headlines
from core.features import build_features, build_features_v2
from core.model_store import load_active_model
from core.repository import load_settings
from core import db

load_dotenv(ROOT / ".env")

ET = ZoneInfo("America/New_York")
STATE_PATH = ROOT / "paper_state.json"
TRADES_PATH = ROOT / "paper_trades.csv"
REPORT_PATH = ROOT / "paper_report.md"
MODEL_PATH = ROOT / "model.joblib"


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {
        "cash": STARTING_PAPER_CASH,
        "high_water": STARTING_PAPER_CASH,
        "positions": {},
        "start_date": None,
    }


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def log_trades(rows: list[dict]) -> None:
    frame = pd.DataFrame(rows)
    if TRADES_PATH.exists():
        prev = pd.read_csv(TRADES_PATH)
        frame = pd.concat([prev, frame], ignore_index=True)
    frame.to_csv(TRADES_PATH, index=False)


def portfolio_value(cash: float, positions: dict, prices: dict[str, float]) -> float:
    total = cash
    for t, pos in positions.items():
        total += float(pos["shares"]) * float(prices.get(t, pos.get("avg_cost", 0)))
    return total


def _normalize_positions(state: dict) -> dict[str, dict]:
    if isinstance(state.get("positions"), list):
        return {
            p["ticker"]: {"shares": p["shares"], "avg_cost": p["avg_cost"]}
            for p in state["positions"]
        }
    return dict(state.get("positions") or {})


def _submit_alpaca(side: str, ticker: str, shares: float, dry_run: bool) -> str | None:
    from core.alpaca_broker import AlpacaPaperBroker

    broker = AlpacaPaperBroker()
    result = broker.submit_market_order(ticker, shares, side, dry_run=dry_run)
    if dry_run:
        return "dry-run"
    return None if result is None else result.id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="Market date YYYY-MM-DD")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument(
        "--broker",
        choices=["local", "alpaca"],
        default="local",
        help="local = SQLite/JSON only; alpaca = also submit paper orders",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="With --broker alpaca, validate but do not submit orders",
    )
    args = parser.parse_args()

    settings = load_settings(args.db)
    as_of = args.date or datetime.now(ET).strftime("%Y-%m-%d")
    start = (datetime.strptime(as_of, "%Y-%m-%d") - timedelta(days=400)).strftime("%Y-%m-%d")

    state = load_state()
    positions = _normalize_positions(state)

    cash = float(state.get("cash", STARTING_PAPER_CASH))
    high_water = float(state.get("high_water", cash))
    prices: dict[str, float] = {}
    signal_rows: list[dict] = []
    new_trades: list[dict] = []
    broker_notes: list[str] = []

    # Phase 4: load gated artifact (v2 if Kept, else v1). Legacy model.joblib fallback.
    model = None
    model_version = "none"
    model_meta: dict = {}
    try:
        model, model_meta, model_version = load_active_model()
        if model is None and MODEL_PATH.exists():
            import joblib

            model = joblib.load(MODEL_PATH)
            model_version = "legacy"
    except Exception:
        model = None
    broker_notes.append(f"model={model_version}")

    spy_bars = get_daily_bars("SPY", start, as_of)
    spy_bars = spy_bars[spy_bars["date"] <= as_of] if not spy_bars.empty else spy_bars

    # When using Alpaca paper, seed cash from the paper account (read-only sync).
    if args.broker == "alpaca":
        from core.alpaca_broker import AlpacaPaperBroker

        acct = AlpacaPaperBroker().get_account()
        cash = float(acct.cash)
        high_water = max(high_water, float(acct.equity))
        broker_notes.append(
            f"alpaca_paper equity={acct.equity:.2f} cash={acct.cash:.2f} status={acct.status}"
        )

    for ticker in settings["watchlist"]:
        bars = get_daily_bars(ticker, start, as_of)
        if bars.empty:
            continue
        bars = bars[bars["date"] <= as_of]
        if bars.empty:
            continue
        last = bars.iloc[-1]
        price = float(last["close"])
        prices[ticker] = price

        # Phase 4 Step 1: score the day that just closed into news_sentiment (idempotent).
        sentiment: float | None = None
        headline_count = 0
        top_headline = None
        try:
            from news_sentiment import score_day

            if not db.has_news_sentiment(as_of, ticker, args.db):
                scored = score_day(ticker, as_of)
                if scored.ok and scored.days:
                    row_s = scored.days[0]
                    db.insert_news_sentiment(
                        row_s.date,
                        ticker,
                        row_s.sentiment,
                        row_s.headline_count,
                        row_s.summary,
                        row_s.source,
                        args.db,
                    )
            ns = db.read_news_sentiment(args.db)
            match = ns[(ns["date"] == as_of) & (ns["ticker"] == ticker)]
            if not match.empty:
                sentiment = float(match.iloc[0]["sentiment"])
                headline_count = int(match.iloc[0]["headline_count"] or 0)
                summary = str(match.iloc[0]["summary"] or "")
                top_headline = None if summary == "No news." else summary
        except Exception:
            headlines = get_headlines(ticker, as_of)
            top_headline = headlines[0]["headline"] if headlines else None

        indexed = bars.set_index("date")
        indexed.index = indexed.index.astype(str)
        use_v2 = model_version == "v2" or (
            model is not None
            and hasattr(model, "feature_names_in_")
            and "sentiment" in list(model.feature_names_in_)
        )
        if use_v2 and not spy_bars.empty:
            import pandas as pd

            sent_s = pd.Series(
                {as_of: sentiment if sentiment is not None else 0.0}
            )
            hc_s = pd.Series({as_of: float(headline_count)})
            # full history series for join
            ns_all = db.read_news_sentiment(args.db)
            sub = ns_all[ns_all["ticker"] == ticker] if not ns_all.empty else ns_all
            if not sub.empty:
                sent_s = sub.set_index("date")["sentiment"]
                hc_s = sub.set_index("date")["headline_count"]
                sent_s.index = sent_s.index.astype(str)
                hc_s.index = hc_s.index.astype(str)
            feats = build_features_v2(indexed, spy_bars, sentiment=sent_s, headline_count=hc_s)
        else:
            feats = build_features(indexed)

        row = feats.dropna().iloc[-1] if not feats.dropna().empty else None
        buy_p = hold_p = sell_p = 1 / 3
        raw = "hold"
        if model is not None and row is not None:
            cols = list(model.feature_names_in_)
            proba = model.predict_proba([row[cols]])[0]
            classes = list(model.classes_)
            mapping = {c: float(p) for c, p in zip(classes, proba)}
            buy_p = mapping.get("buy", 0.0)
            hold_p = mapping.get("hold", 0.0)
            sell_p = mapping.get("sell", 0.0)
            raw = max(mapping, key=mapping.get)  # type: ignore[arg-type]
        conf = max(buy_p, hold_p, sell_p)
        traded = confidence_gate(raw, conf, settings["confidence_threshold"])
        rsi_val = float(row["rsi14"]) if row is not None else None
        dd63 = float(row["drawdown63"]) if row is not None else None
        spy_regime_val = None
        if row is not None and "spy_regime" in row.index:
            spy_regime_val = int(row["spy_regime"])
        signal_rows.append(
            {
                "date": as_of,
                "ticker": ticker,
                "signal": raw,
                "buy_p": buy_p,
                "hold_p": hold_p,
                "sell_p": sell_p,
                "price": price,
                "rsi14": rsi_val,
                "drawdown63": dd63,
                "sentiment": sentiment,
                "headline": top_headline,
                "headline_count": headline_count,
                "spy_regime": spy_regime_val,
            }
        )

        value = portfolio_value(cash, positions, prices)
        dd = value / high_water - 1.0 if high_water else 0.0
        frozen = buys_frozen(dd, settings["drawdown_freeze"])

        if traded == "buy" and ticker not in positions and not frozen:
            shares = position_buy_shares(
                value, cash, price, settings["position_size"]
            )
            if shares > 0:
                if args.broker == "alpaca":
                    try:
                        oid = _submit_alpaca("buy", ticker, shares, args.dry_run)
                        broker_notes.append(f"buy {ticker} qty={shares} order={oid}")
                    except Exception as exc:
                        broker_notes.append(f"buy {ticker} SKIP: {exc}")
                        continue
                cost = shares * price
                cash -= cost
                positions[ticker] = {"shares": shares, "avg_cost": price}
                new_trades.append(
                    {
                        "date": as_of,
                        "ticker": ticker,
                        "action": "buy",
                        "shares": shares,
                        "price": price,
                        "confidence": conf,
                        "status": "Open",
                        "realized_pnl": None,
                    }
                )
            else:
                broker_notes.append(f"buy {ticker} skipped: cash under $10 or size 0")
        elif traded == "sell" and ticker in positions:
            pos = positions[ticker]
            shares = float(pos["shares"])
            if args.broker == "alpaca":
                try:
                    oid = _submit_alpaca("sell", ticker, shares, args.dry_run)
                    broker_notes.append(f"sell {ticker} qty={shares} order={oid}")
                except Exception as exc:
                    broker_notes.append(f"sell {ticker} SKIP: {exc}")
                    continue
            positions.pop(ticker)
            proceeds = shares * price
            pnl = proceeds - shares * float(pos["avg_cost"])
            cash += proceeds
            new_trades.append(
                {
                    "date": as_of,
                    "ticker": ticker,
                    "action": "sell",
                    "shares": shares,
                    "price": price,
                    "confidence": conf,
                    "status": "Closed",
                    "realized_pnl": pnl,
                }
            )

    value = portfolio_value(cash, positions, prices)
    high_water = max(high_water, value)
    dd = value / high_water - 1.0 if high_water else 0.0

    # Benchmark: equal-weight buy-and-hold from start (simplified: track cash-equivalent growth)
    bench = float(state.get("benchmark_value", STARTING_PAPER_CASH))
    if prices:
        # naive: average daily move across watchlist vs previous prices in state
        prev_prices = state.get("last_prices") or prices
        rets = []
        for t, px in prices.items():
            if t in prev_prices and prev_prices[t]:
                rets.append(px / float(prev_prices[t]) - 1.0)
        if rets:
            bench *= 1.0 + sum(rets) / len(rets)

    state.update(
        {
            "as_of": as_of,
            "cash": cash,
            "high_water": high_water,
            "portfolio_value": value,
            "benchmark_value": bench,
            "drawdown": dd,
            "positions": [
                {"ticker": t, "shares": p["shares"], "avg_cost": p["avg_cost"]}
                for t, p in positions.items()
            ],
            "last_prices": prices,
            "start_date": state.get("start_date") or as_of,
        }
    )
    save_state(state)

    db.init_db(args.db)
    with db.connect(args.db) as conn:
        for row in signal_rows:
            conn.execute(
                "INSERT OR REPLACE INTO signals(date, ticker, signal, buy_p, hold_p, sell_p, "
                "price, rsi14, drawdown63, sentiment, headline, headline_count, spy_regime) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    row["date"],
                    row["ticker"],
                    row["signal"],
                    row["buy_p"],
                    row["hold_p"],
                    row["sell_p"],
                    row["price"],
                    row["rsi14"],
                    row["drawdown63"],
                    row["sentiment"],
                    row["headline"],
                    row.get("headline_count"),
                    row.get("spy_regime"),
                ),
            )
            conn.execute(
                "INSERT OR IGNORE INTO signal_grades(date, ticker, signal, confidence, price_then) "
                "VALUES (?,?,?,?,?)",
                (
                    row["date"],
                    row["ticker"],
                    row["signal"],
                    max(row["buy_p"], row["hold_p"], row["sell_p"]),
                    row["price"],
                ),
            )
        conn.execute(
            "INSERT OR REPLACE INTO portfolio_history(date, value, benchmark_value, cash, drawdown) "
            "VALUES (?,?,?,?,?)",
            (as_of, value, bench, cash, dd),
        )
        conn.execute("DELETE FROM positions")
        for t, p in positions.items():
            conn.execute(
                "INSERT INTO positions(ticker, shares, avg_cost) VALUES (?,?,?)",
                (t, p["shares"], p["avg_cost"]),
            )
        if new_trades:
            for tr in new_trades:
                conn.execute(
                    "INSERT INTO trades(date, ticker, action, shares, price, confidence, status, realized_pnl) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        tr["date"],
                        tr["ticker"],
                        tr["action"],
                        tr["shares"],
                        tr["price"],
                        tr["confidence"],
                        tr["status"],
                        tr["realized_pnl"],
                    ),
                )
            log_trades(new_trades)
        conn.commit()

    notes_block = "\n".join(f"- {n}" for n in broker_notes) if broker_notes else "- (none)"
    REPORT_PATH.write_text(
        f"# Paper report — {as_of}\n\n"
        f"| Metric | Value |\n|--------|-------|\n"
        f"| Portfolio value | ${value:,.2f} |\n"
        f"| Benchmark value | ${bench:,.2f} |\n"
        f"| Cash | ${cash:,.2f} |\n"
        f"| Drawdown from high | {dd * 100:.1f}% |\n"
        f"| Position size setting | {settings['position_size'] * 100:.0f}% |\n"
        f"| Broker | {args.broker}{' dry-run' if args.dry_run else ''} |\n\n"
        f"## Broker notes\n{notes_block}\n",
        encoding="utf-8",
    )
    print(
        f"paper_trade {as_of}: broker={args.broker} value=${value:,.2f} "
        f"cash=${cash:,.2f} trades={len(new_trades)}"
    )
    for note in broker_notes:
        print(f"  {note}")


if __name__ == "__main__":
    main()
