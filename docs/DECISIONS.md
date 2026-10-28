# Decisions log

Muse reviews this file every round. Every deviation from the Muse Doc Detailed Build Spec is logged here: what, why, and what was chosen instead. An unlogged deviation is treated as a bug.

| Date | What | Why | Chose instead |
|------|------|-----|---------------|
| 2026-10-27 | H step 1 uses `st.navigation` in `app.py` pointing at `pages/*.py` | Spec wants `app.py` as entry + `pages/` files; classic auto-pages would rename the home page after `app.py` | Explicit `st.Page` list with titles Dashboard / Signals / Trades / Model / Settings |
| 2026-10-27 | Prototype scripts (`train.py`, `live_signal.py`, `paper_trade.py`, `news_sentiment.py`) not in repo yet | Doc says they are ready to be added; they were not on `main` at skeleton time | Added minimal versions in H.4–H.6 so seed/app/settings checks can pass; formulas match the Doc |
| 2026-10-27 | `core/db.py` includes `signal_grades` table from addendum | Addendum says apply from the start | Schema includes `signal_grades`; UI scorecard on Model page |
| 2026-10-27 | Seed uses `fixtures/paper_state.json` + `fixtures/paper_trades.csv` | Doc assumes root `paper_state.json` / `paper_trades.csv` from the agent; those files were absent | Fixtures mirror Doc wireframe numbers ($102,340); seed script accepts paths; swap to live agent outputs when available |
| 2026-10-27 | `XAI_API_KEY` / Alpaca / Finnhub missing in agent env | User said key available; not found in env or common secret paths | Settings show Not connected; sentiment NULL; no live API calls from UI |
| 2026-10-27 | `.env.example` adds optional `APCA_*` / `FINNHUB_SECRET` / base URL names | Muse lists four exact keys; Anh’s Alpaca SDK uses APCA names and provided a Finnhub secret | Keep Muse’s four primary keys; document empty aliases; resolve either naming in `core/secrets.py` |
| 2026-10-27 | Alpaca client uses REST urllib, not `alpaca-py` | Avoid new dependency churn for Phase 3; paper URL asserted in code | REST against `https://paper-api.alpaca.markets` only; may adopt `alpaca-py` later if Muse asks |
| 2026-10-27 | `FINNHUB_SECRET` stored in `.env` but unused by code | Anh provided API key + secret; Finnhub company-news uses the API key token only | `FINNHUB_API_KEY` drives calls; secret kept in env for future endpoints, never logged |
| 2026-10-28 | BLS schedules fetched via Wayback when live bls.gov returns 403 | Cloud egress blocked/challenged on BLS; Fed page works live | `refresh_events.py` tries live then archive.org closest snapshot; source URL stored in `events_counts.json` |
| 2026-10-28 | Earnings history from Yahoo (`yfinance`) in addition to Finnhub | Finnhub free `calendar/earnings` returns mostly the next upcoming print, not 2021→today history | Merge: Yahoo fills history; Finnhub wins on same date+ticker; Muse earnings honesty note applies (actual report dates) |
| 2026-10-28 | 2025 CPI/NFP counts are 11 not 12 | BLS 2025 published schedule omits one month each (disrupted releases) | Keep published dates only — do not invent missing months |
| 2026-10-28 | v3 Step 1 branched from `main`, not PR #3 | PR #3 (Phase 4) still open; Doc start condition met with gate Rejected → base v1 | New PR for calendar only; do not activate rejected v2 |
