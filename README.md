# Trading Agent Company App

Paper-first AI trading dashboard for Tuan. Streamlit UI over a Python agent core. **No live trading in v1.**

## Setup

- Python 3.11 or newer

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Optional keys in `.env` (never commit the real file): `ALPACA_API_KEY`, `ALPACA_API_SECRET`, `FINNHUB_API_KEY`, `XAI_API_KEY`.  
Aliases also accepted: `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`, `ALPACA_BASE_URL` / `APCA_API_BASE_URL` (must contain `paper`).

```bash
# Read-only paper account check
python scripts/alpaca_smoke.py
python scripts/finnhub_smoke.py

# Daily agent — local book only (default)
python paper_trade.py

# Phase 3 — also submit to Alpaca PAPER (use --dry-run first)
python paper_trade.py --broker alpaca --dry-run
python paper_trade.py --broker alpaca

# Phase 4 Step 1 — sentiment backfill (cost guard first)
python scripts/sentiment_backfill.py --test-batch   # TSLA one month; writes cost to stdout
# Only if projection < $25:
python scripts/sentiment_backfill.py --full
```


## Seed demo data

```bash
python scripts/seed_db.py
```

Loads `fixtures/paper_state.json` + `fixtures/paper_trades.csv` into `data/app.db`. Dashboard portfolio should read **$102,340.00**.

## Run

```bash
streamlit run app.py
```

Localhost only in v1.

## Daily flow

1. (Optional) `python train.py` — walk-forward train, writes `results.json` + `model.joblib`
2. `python paper_trade.py` — after US close; writes SQLite + `paper_report.md`
3. Open the app; Settings changes apply on the next agent run

## Events calendar (Model v3 Step 1)

Committed auditable calendar (Fed / BLS / NYSE / earnings). Refresh monthly:

```bash
python scripts/refresh_events.py
```

Writes `data/events.csv` + `data/events_counts.json` and loads SQLite `events`. Counts for Anh’s sanity review are in `CHAT.md` and `data/events_counts.json`.

## Behavior pack (Model v4)

VIX + CBOE put/call + AAII → `data/behavior.csv` (no CNN Fear & Greed scrape):

```bash
python scripts/refresh_behavior.py
python scripts/train_compare_v4.py      # walk-forward + gate + panic exam
python scripts/panic_exam.py            # re-run exam alone
python scripts/paper_phase5_status.py   # Phase 5 checklist numbers (ops; Live locked)
```

## Model v5 (data scale-up)

Same live features as **v1** (no feature add/remove). Frozen 50-ticker universe + train from 2015. Paper still trades the original 5; Live locked.

```bash
python scripts/refresh_history.py       # cache OHLCV under data/history/ (gitignored)
python scripts/train_compare_v5.py      # walk-forward + continuity gate + panic exam
```

Universe: `data/universe.csv` (frozen — bump version + DECISIONS before edits).

## Tests

```bash
pytest
```

## Folder map

| Path | Role |
|------|------|
| `app.py` | Entry + sidebar navigation |
| `pages/` | Dashboard, Signals, Trades, Model, Settings |
| `core/` | data, features, model, agent, db, repository, charts, events_calendar, behavior_data, universe, history_cache |
| `paper_trade.py` / `train.py` / `live_signal.py` / `news_sentiment.py` | Agent scripts |
| `scripts/seed_db.py` | One-time fixture import |
| `scripts/refresh_events.py` | Rebuild Fed/BLS/NYSE/earnings calendar |
| `scripts/refresh_behavior.py` | Rebuild VIX / put-call / AAII behavior table |
| `scripts/refresh_history.py` | Cache per-ticker OHLCV for Model v5 |
| `scripts/train_compare_v5.py` | Model v5 train/compare + continuity gate |
| `scripts/paper_phase5_status.py` | Phase 5 review checklist status (ops) |
| `fixtures/` | Sample paper state/trades/report |
| `assets/style.css` | Dark trading-terminal theme |
| `data/` | `app.db` / `history/` gitignored; `universe.csv` / `events.csv` / `behavior.csv` committed |
| `docs/DECISIONS.md` | Spec deviations log |
| `CHAT.md` | Muse ↔ Cursor channel |

## Status

H steps 1–6 + Phase 4/v3/v4 gates on `main` (all Rejected → paper stays **v1**). Model v5 = data scale-up (same v1 features). Live toggle locked. Broker/xAI keys still optional.
