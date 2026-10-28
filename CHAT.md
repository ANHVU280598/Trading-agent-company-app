# Muse ↔ Cursor — Team Channel

## 2026-10-27 — xAI/Grok sentiment wired

**Step:** Wire Grok news sentiment (addendum §6)  
**What changed:**
- Gitignored `.env` now includes `XAI_API_KEY` (never committed; value not written here)
- `news_sentiment.py`: Grok-only chat completions, `<external>` wrap, system-prompt injection guard, soft-fail on 429
- `paper_trade.py` scores Finnhub headlines via Grok when key present; stores sentiment on signals
- `scripts/xai_smoke.py` cheap one-headline check
- Settings xAI/Grok Connected via existence check

**Check:** Smoke sentiment call returned a score in [-1, 1]. keys_connected alpaca/finnhub/xai all true. Live toggle still locked.

**Tests:** pytest incl. injection wrap + missing-key → None. **Passed.**

**Blocked:** none for connectivity; Phase 4 (sentiment as model feature + regime) still a later brief.

— Cursor

## 2026-10-27 — Phase 3: Alpaca paper execution + Finnhub data

**Step:** Phase 3 (execution) + data-layer Finnhub/Alpaca fallbacks  
**What changed:**
- Gitignored `.env` on laptop holds Alpaca paper + Finnhub keys (never committed)
- `.env.example` lists name-only aliases: `ALPACA_*`, `APCA_*`, `FINNHUB_API_KEY`, `FINNHUB_SECRET`
- `core/alpaca_broker.py` + `assert_paper_base_url` (refuses non-paper hosts)
- `paper_trade.py --broker alpaca [--dry-run]` submits matching paper orders; default remains `local`
- `core/data.py`: prices Yahoo → Alpaca → Stooq; headlines Finnhub
- Smoke scripts: `scripts/alpaca_smoke.py` (account read), `scripts/finnhub_smoke.py`
- Settings Connected flags via `core.secrets` (existence only)

**Check:** Alpaca paper account ACTIVE, equity readable; Finnhub returned headlines for AAPL; dry-run paper_trade synced cash from paper account without placing orders. Live toggle still locked.

**Tests:** pytest incl. paper URL guard — passed.

**Blocked:**
- `XAI_API_KEY` still missing — sentiment stays NULL / Grok skipped
- No live orders placed in this pass (smoke was read-only + dry-run)

— Cursor

## 2026-10-27 — H step 6: Settings wiring

**Step:** H.6 Settings  
**What changed:**
- Settings page saves watchlist + risk sliders to `settings` table
- Live toggle remains disabled (Paper only)
- Agent reads via `core.repository.load_settings` (used by `paper_trade.py` / `train.py`)
- Test: save position_size=0.25 → agent settings map returns 0.25

**Check (H.6):** Change position size to 25%, confirm next agent read uses 25%. **Passed** (unit test + manual save path).

**Blocked:** Alpaca / Finnhub / xAI still Not connected in this env.

— Cursor

## 2026-10-27 — H step 5: Model page wiring

**Step:** H.5 Model page  
**What changed:**
- Model page reads `model_runs` + `results.json` (accuracy 56.6% vs 56.2% baseline in seed)
- Walk-forward chart, confusion matrix, feature importance, retrain log
- Signal scorecard section (addendum) — shows “needs 30” until graded
- Added `train.py` (walk-forward RandomForest, writes results + model_runs)

**Check (H.5):** Accuracy/baseline on Model page equal `results.json` (0.566 / 0.562). **Passed** after seed.

**Blocked:** Fresh `train.py` run needs network/Yahoo; seed results used for UI parity check.

— Cursor

## 2026-10-27 — H step 4: Real data from SQLite

**Step:** H.4 Real data  
**What changed:**
- Dashboard / Signals / Trades read SQLite via `core/repository.py`
- Deleted `core/fake_data.py` (not bypassed — removed)
- Added minimal `paper_trade.py`, `live_signal.py`, `news_sentiment.py` (prompt-injection guard)
- `core/data.py`: Yahoo → Stooq fallback + data-quality flags

**Check (H.4):** After `python scripts/seed_db.py`, Dashboard portfolio = $102,340.00 matching fixtures/paper_report.md. **Passed.**

**Tests:** pytest including news wrap + seed.  

**Blocked:** No XAI/Alpaca/Finnhub keys in agent env — sentiment/headlines stay empty; no broker calls.

— Cursor

## 2026-10-27 — H step 3: Database + seed

**Step:** H.3 Database  
**What changed:**
- `core/db.py` write helpers (`upsert_setting`, `get_settings_map`, `replace_table`, `read_signal_grades`)
- Fixtures: `fixtures/paper_state.json`, `fixtures/paper_trades.csv`, `fixtures/paper_report.md`, `results.json`
- `scripts/seed_db.py` imports fixtures into `data/app.db`
- Tests: seed totals + settings round-trip

**Check (H.3):** Dashboard portfolio after seed = paper_report.md **$102,340.00**. **Passed.**

**Tests:** `pytest` 15 passed.

**Blocked / notes:**
- Real `paper_state.json` / `paper_trades.csv` from the prototype agent are not in the repo; fixtures stand in (logged in DECISIONS.md). Replace when Tuan adds the live agent outputs.
- Fake-data module still present until H.4 deletes it.

— Cursor

## 2026-10-27 — H step 2: Fake-data pass

**Step:** H.2 Fake-data pass  
**What changed:**
- Added `core/fake_data.py` (single sample-data module)
- Wired Dashboard / Signals / Trades / Model / Settings with sample rows, badges, charts, KPIs
- Each page shows muted “Sample data” line; Model includes scorecard stub (needs 30 graded)
- Shared helpers: `core/charts.py`, `core/components.py`, `core/formatters.py`

**Check (H.2):** Every page filled with clearly fake sample rows for layout/colors/badges/charts. Anh approved H.1 look and said keep going — treating that as green light to continue past visual review. **Passed.**

**Tests:** `pytest` still green (label / freeze / confidence / sizing).

**Blocked / questions:**
- `XAI_API_KEY` / Alpaca / Finnhub not present in this agent env (checked env + common secret paths). Sentiment stays “—” / Not connected.
- Prototype scripts still absent from repo; H.3+ will add fixtures + minimal agent scripts and log in DECISIONS.md.
- Fake data will be deleted in H.4 (not just bypassed).

— Cursor

## 2026-10-27 — H step 1: Skeleton

**Step:** H.1 Skeleton  
**What changed:**
- Added Streamlit app entry (`app.py`), five pages under `pages/`, dark theme (`.streamlit/config.toml`, `assets/style.css`)
- Added `core/` stubs: `config`, `ui`, `data`, `features`, `model`, `agent`, `db` (schema includes addendum `signal_grades`)
- Added `requirements.txt`, `.env.example`, `.gitignore`, `README.md`, `tests/` for label / freeze / confidence / sizing rules
- Addendum files: `.cursor/rules/project.mdc`, `docs/DECISIONS.md`

**Check (H.1):** App runs with `streamlit run app.py`; dark theme hex values match section C (`#0B0E11` bg, `#161B22` panel, `#16C784` / `#EA3943` / `#E8B33D`). Five pages render empty-state panels. **Passed** (local run).

**Tests:** `pytest` — label boundaries, freeze-at-threshold, confidence gate, position sizing. **Passed.**

**Blocked / questions:**
- Prototype scripts (`train.py`, `live_signal.py`, `paper_trade.py`, `news_sentiment.py`) are not on `main` yet — not inventing them; need Muse/Tuan to add or point to the source.
- Still need from Tuan (for later steps): `XAI_API_KEY`, Alpaca paper keys, Finnhub key — via `.env` only.
- H step 2 (fake-data pass) is next and needs Tuan visual approval before real SQLite wiring.
- Not starting Phase 3 Alpaca execution until Muse writes that brief and keys exist.

— Cursor

## Cursor handshake — 2026-10-27

Hi Muse —

**1. Doc access.** Confirmed: I can read the Muse Google Doc (Team Channel export).

**2. Project summary.** This is a paper-first AI trading stack for Tuan's own capital only—no customers. A RandomForest prototype (price/volume features on SPY, AAPL, MSFT, NVDA, TSLA) drives a daily paper agent on a fake $100k book; labels are a hindsight rule, test accuracy ~56.6% vs a ~56.2% always-hold baseline, so there is no proven edge yet. The immediate goal is pipeline discipline and paper validation before any real money.

**3. What I need before coding.**
- From **Tuan**: xAI/Grok API key for `news_sentiment.py` (do not commit secrets to the repo).
- From **Tuan**: Alpaca paper API keys when we connect the paper broker (paper-only; no live keys in the repo).
- Confirm **repo access** and which **branch** to treat as default for this work (main vs a dedicated develop/paper branch).
- Explicit confirmation: **paper-only until Tuan says go** on live capital; I will not place real trades.
- From **Muse**: the full brief for connecting paper-agent signals to a broker paper account (e.g. Alpaca) before that build starts.
- Prefer secrets via env / secret store, never checked into GitHub.

Standing by for the next brief. No trading or broker coding until you and Tuan green-light it.

— Cursor  
2026-10-27
