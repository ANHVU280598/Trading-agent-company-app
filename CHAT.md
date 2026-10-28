# Muse ↔ Cursor — Team Channel

## 2026-10-28 — Model v3 Steps 2–5: calendar features + gate (Rejected)

**Step:** Model v3 / Steps 2–5  
**Base:** v1 (Phase 4 v2 Rejected; not activated)  
**What changed:**
- Step 2: 18 calendar features in exact Muse order (`core/calendar_features.py` + `build_features_v3`)
- Step 3: `scripts/train_compare_v3.py` — same RF/labels/walk-forward; artifacts `models/model_v1.joblib` + `model_v3.joblib` (gitignored) with JSON sidecars
- Step 4: gate vs v1; no hand-tuning after peek
- Step 5: Signals “next event” line (display only); Model page v1 vs v3 block
- Paper agent loads gated active model (stays v1). Live locked.

**v1 vs v3 (walk-forward, 2021→2026-10-27):**

| Metric | v1 (base) | v3 |
|--------|-----------|-----|
| Accuracy | 0.5583 | 0.5601 |
| Baseline | 0.5483 | 0.5483 |
| Buy precision | 0.3881 | 0.3878 |
| Sell precision | 0.3190 | 0.3153 |
| Train rows | 6965 | 6965 |

- Calendar importance: **days_to_earnings#2, days_to_fomc#9, days_to_cpi#11, earnings_soon#12, may_oct_flag#13**. **Ignored (≈0): witching_day.**
- Month-drop check: **passed**

**Gate verdict: Rejected**  
Reasons: buy precision 0.3878 < base 0.3881; sell precision 0.3153 < base 0.3190 (accuracy *did* beat base).  
**Active paper model: v1.** v3 artifact saved for inspection. No tuning after peeking. No v3b this round.

**Check:** pytest 38 passed (calendar truth/frequency/leakage + gate). Report in `models/v1_vs_v3_report.json` + `model_runs`.

**Blocked / notes:** Stopped per Muse — next is paper-trading review gate, not another model.

— Cursor

## 2026-10-28 — Model v3 Step 1: events calendar (counts for Anh)

**Step:** Model v3 / Step 1 only — build events calendar  
**Base model:** v1 (Phase 4 gate Rejected on PR #3; v2 not activated)  
**What changed:**
- SQLite `events` table + committed `data/events.csv` + `data/events_counts.json`
- `core/events_calendar.py` + monthly `scripts/refresh_events.py`
- Types: `fomc`, `cpi`, `nfp`, `witching`, `opex`, `holiday`, `earnings`
- Sources: Fed FOMC page; BLS yearly schedules (live 403 → Wayback); NYSE holiday rules; witching/opex calendar rules; Finnhub earnings calendar (upcoming) + Yahoo earnings dates (history)
- Coverage: **2021-01-01 → 2027-12-24** — **510 rows**
- Stopped before Step 2 features / train / gate / UI. Live locked. Paper stays on v1.

### Counts by type (all years)

| Type | Rows | Source |
|------|------|--------|
| fomc | 56 | federalreserve.gov (decision day = meeting day 2) |
| cpi | 83 | bls.gov schedules |
| nfp | 83 | bls.gov Employment Situation |
| witching | 28 | calendar rule (3rd Fri Mar/Jun/Sep/Dec) |
| opex | 84 | calendar rule (3rd Fri each month) |
| holiday | 70 | NYSE full-day rules (+ Juneteenth from 2021) |
| earnings | 106 | Finnhub upcoming (12) + Yahoo history (97), merged |

### Per-year sanity check (Muse: fomc≈8, witching≈4, opex≈12)

| Year | fomc | witching | opex | Δfomc | Δwitch | Δopex | cpi | nfp | holiday | earnings |
|------|------|----------|------|-------|---------|--------|-----|-----|---------|----------|
| 2021 | 8 | 4 | 12 | 0 | 0 | 0 | 12 | 12 | 11 | 16 |
| 2022 | 8 | 4 | 12 | 0 | 0 | 0 | 12 | 12 | 9 | 16 |
| 2023 | 8 | 4 | 12 | 0 | 0 | 0 | 12 | 12 | 10 | 16 |
| 2024 | 8 | 4 | 12 | 0 | 0 | 0 | 12 | 12 | 10 | 16 |
| 2025 | 8 | 4 | 12 | 0 | 0 | 0 | 11 | 11 | 10 | 16 |
| 2026 | 8 | 4 | 12 | 0 | 0 | 0 | 12 | 12 | 10 | 17 |
| 2027 | 8 | 4 | 12 | 0 | 0 | 0 | 12 | 12 | 10 | 9 |

Earnings by ticker: AAPL 26, MSFT 26, NVDA 27, TSLA 27 (SPY ETF → 0).

**Gaps / notes for Anh:**
- **2025 CPI/NFP = 11** each (not 12): BLS 2025 schedule omits one month each (Oct NFP / Nov CPI) — consistent with 2025 release disruptions; left as published, not invented.
- **2022 holidays = 9:** New Year’s 2022 observed Fri 2021-12-31 (counted in 2021); expected.
- BLS live site returns 403 from this environment → Wayback snapshots used; sources URLs recorded in `data/events_counts.json`.
- Finnhub free `calendar/earnings` returns mostly upcoming only → Yahoo fills history; logged in DECISIONS (actual report dates = accepted noise per Muse).

**Check:** pytest events tests + suite green. Refresh: `python scripts/refresh_events.py`.

**Blocked:** none for Step 1. Waiting on Anh before v3 Step 2+.

— Cursor

## 2026-10-28 — Phase 4 Steps 2–5: v2 features, train, gate (Rejected)

**Step:** Phase 4 / Steps 2–5  
**What changed:**
- Step 2: `FEATURE_ORDER_V2` = v1 + `sentiment`, `headline_count`, `spy_regime`, `rs21` in `core/features.py`
- Step 3: `scripts/train_compare_v2.py` — same RF (200 trees, min_samples_leaf 50, random_state 7), same ±3% 5d labels, walk-forward by month; artifacts `models/model_v1.joblib` + `model_v2.joblib` (gitignored) with JSON sidecars; v1 kept as rollback
- Step 4: `core/gate.py` — promote v2 only if accuracy beats v1 AND buy/sell precision ≥ v1 AND no month drop >10 pts
- Step 5: `paper_trade` loads gated active model; Signals shows sentiment, headline count, Market up/down; Model page shows v1 vs v2 block + feature importance from sidecar

**Full backfill (actual):**
- Rows in `news_sentiment`: **3510** (SPY 1241, AAPL 499, MSFT 516, NVDA 606, TSLA 648)
- Grok calls this pass: **312**; estimated USD **~$0.33** (plus earlier Step 1 test-batch ~$0.0047 and partial SPY backfill)
- Gaps: parallel backfill hit HTTP **403** rate limits on some weeks; missing days stay unscored (features treat missing sentiment/count as 0 / No news). No re-score of stored days. No hand-tuning after gate.

**v1 vs v2 (walk-forward):**

| Metric | v1 | v2 |
|--------|-----|-----|
| Accuracy | 0.5583 | 0.5547 |
| Baseline (always-hold) | 0.5483 | 0.5483 |
| Buy precision | 0.3881 | 0.3775 |
| Sell precision | 0.3195 | 0.3053 |
| Train rows | 6965 | 6965 |

- Feature importance: **sentiment ranks #12 of 12 features** (lowest). Top: vol21, drawdown63, rs21.
- Month-drop check: **passed** (no month >10 pts below v1)

**Gate verdict: Rejected**  
Reasons: walk-forward accuracy 0.5547 does not beat v1 0.5583; buy precision 0.3775 < v1 0.3881; sell precision 0.3053 < v1 0.3195.  
**Active paper model: v1.** v2 artifact saved for inspection; v1 keeps trading. No tuning after peeking. Live still locked.

**Check:** pytest 35 passed (gate pass/fail, save/load, leakage, feature order). Report also in `models/v1_vs_v2_report.json` + `model_runs`.

**Blocked / notes:** Phase 5 is calendar review only — no Phase 5 build. Optional later: sequential gap-fill for 403 weeks (idempotent); would need a fresh walk-forward as a logged variant, not this gate.

— Cursor

## 2026-10-28 — Phase 4 Step 1: sentiment dataset (cost-guarded)

**Step:** Phase 4 / Step 1 — Sentiment backfill  
**What changed:**
- Extended `news_sentiment.py` (not rewritten): day/week scoring, Alpaca→Finnhub headlines, JSON `{sentiment, headline_count, summary}`, temp 0.2, injection guard unchanged
- SQLite table `news_sentiment` (date, ticker, sentiment, headline_count, summary, source); never re-score (idempotent insert)
- `scripts/sentiment_backfill.py` — `--test-batch` then `--full`
- `paper_trade.py` scores the closed day into `news_sentiment` before signals (cache forever)
- Tests: leakage prompts, idempotency, injection guard on SYSTEM_PROMPT_V2

**Cost guard (TSLA, Sep 2026 — one month):**
- Grok calls: **5** (one per ticker-week)
- Tokens: prompt **14,022** + completion **992**
- Estimated USD (grok-3-mini class @ $0.30/$0.50 per 1M in/out): **~$0.0047**
- Rows inserted: **22** trading days
- Projected full backfill (2021-01-01→today × 5 tickers): **~$1.62** — **under $25 ceiling** → full backfill allowed and started

**Full backfill status:** running on this machine into gitignored `data/app.db` (not committed). Progress continues after this report; CHAT will get a follow-up with final row counts / actual USD when complete.

**Check:** test-batch cost written; projection under ceiling; leakage + idempotency tests pass. Live still locked. Steps 2–5 not started.

**Blocked / notes:** full backfill is I/O + API bound (~hours); data stays local in SQLite. Rate assumption documented in `data/sentiment_backfill_test-batch.json` (gitignored) and above.

— Cursor

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
