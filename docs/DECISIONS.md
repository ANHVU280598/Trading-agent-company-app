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
| 2026-10-28 | Cost estimate uses $0.30/$0.50 per 1M in/out tokens | xAI invoice line items may differ by model | Documented in CHAT.md; TSLA month test ~$0.0047 → full projection ~$1.62 ≪ $25 |
| 2026-10-28 | Weekly backfill scores only weekdays (ignores exchange holidays) | Spec accepts holiday limitation for market-open display; same here | Weekday calendar only for sentiment day keys |
| 2026-10-28 | Full backfill DB lives only in gitignored `data/app.db` | Sentiment rows are large and machine-local; secrets/cost stay out of git | Code + CHAT cost report in PR; re-run `scripts/sentiment_backfill.py --full` on Tuan’s laptop |
| 2026-10-28 | Parallel per-ticker Grok backfill (5 workers) | Sequential 2021→today was too slow for the cloud run | Faster wall time; accepted some HTTP 403 gaps; missing days → feature 0 / No news; no re-score |
| 2026-10-28 | Gate Rejected → active model stays v1 | Muse rule: no hand-tuning after peeking | Saved v2 artifact + report; paper agent loads v1 via `active_model.json` |
| 2026-10-28 | Signals always compute v2 display fields even when active model is v1 | Step 5 UI needs sentiment / headline_count / Market chip regardless of gate | Inference still uses only the active model’s feature columns |
| 2026-10-28 | Commit JSON sidecars + `v1_vs_v2_report.json`; keep `models/*.joblib` gitignored | Joblib blobs are large/machine-local; metrics must travel with the PR | Retrain regenerates joblib from the same script |
