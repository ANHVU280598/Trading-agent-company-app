# Trading Agent Company App

Paper-first AI trading dashboard for Tuan. Streamlit UI over a Python agent core. **No live trading in v1.**

## Setup

- Python 3.11 or newer
- Create a virtualenv and install deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` only when you have keys (Alpaca paper, Finnhub, xAI). Missing keys are fine for the skeleton — the app runs on empty SQLite / Yahoo later.

## Run

```bash
streamlit run app.py
```

Binds to localhost by default. Do not add `--server.address 0.0.0.0` in v1.

## Daily flow (once agent scripts land)

1. Run `paper_trade.py` (after US market close).
2. Open the app and review Dashboard / Signals / Trades / Model.
3. Change Settings only when you intend the next agent run to pick them up.

## Tests

```bash
pytest
```

## Folder map

| Path | Role |
|------|------|
| `app.py` | Entry + sidebar navigation |
| `pages/` | Dashboard, Signals, Trades, Model, Settings |
| `core/` | data, features, model, agent, db, config, ui |
| `assets/style.css` | Dark trading-terminal theme tokens |
| `data/` | `app.db` (gitignored) |
| `tests/` | pytest for core rules |
| `.streamlit/config.toml` | Streamlit dark theme |
| `docs/DECISIONS.md` | Spec deviations log |
| `CHAT.md` | Muse ↔ Cursor channel replies |

## Status

H step 1 (skeleton) — empty states + theme. Fake data is step 2 (needs Tuan look approval before real wiring).
