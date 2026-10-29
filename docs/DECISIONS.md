# Decisions log

Muse reviews this file every round. Every deviation from the Muse Doc Detailed Build Spec is logged here: what, why, and what was chosen instead. An unlogged deviation is treated as a bug.

| Date | What | Why | Chose instead |
|------|------|-----|---------------|
| 2026-10-29 | Gate Rejected → active stays v1 | v5 beats accuracy/buy/sell + original-5 continuity but fails month-drop (>10 pts) on 2022-06, 2025-06, 2026-10 | Save v5 artifact + panic_exam_v5 + report; no v5b; Live locked; paper still original 5 |
| 2026-10-29 | `data/history/` gitignored; commit `universe.csv` + `history_quality.json` | OHLCV cache is large/local; freeze + quality flags must travel with PR | Retrain/refresh regenerates cache via `refresh_history.py` |
| 2026-10-29 | Do not overwrite `model_v1.joblib` in train_compare_v5 | Muse: base untouched as rollback; v5 isolates data scale only | Persist only `model_v5.*`; base metrics computed old-way for gate |
| 2026-10-29 | panic_exam gains `trained_on` column | Doc: v5 trains through 2020/2022 so those windows are in-sample | Flag + note on exam rows; 2020/2022 = true for train_start 2015 |
| 2026-10-29 | Gate Rejected → active stays v1 | v4 accuracy + buy/sell precision below v1 | Save v4 artifact + panic exam; no hand-tuning; Live locked |
| 2026-10-29 | Put/call not forward-filled past last CBOE publish date | Stale CDN (ends 2019-10-04) must not invent 2021+ ratios | NA after last pub; feature column imputed with published median so rows train; crowd_mood ignores putcall when NA |
| 2026-10-29 | SPY hist from 2017 for feature compute; VIX table still 2019+ | COVID panic window needs SPY 125d×252 warm-up before 2020 | Doc allows price history extension for exam; training rows still ≥2021-01-01 |
| 2026-10-29 | crowd_mood uses available components during warm-up | Early sessions lack SPY 125d×252 pct | Prefer full 3-way (or 2-way without putcall); VIX-only if SPY pct still cold |
| 2026-10-29 | Do not overwrite `model_v1.joblib` in train_compare_v4 | Muse: base untouched as rollback | Persist only `model_v4.*`; v1 metrics computed for fair gate only |
| 2026-10-28 | CBOE `totalpc.csv` ends 2019-10-04 (no 2021+ put/call) | Official free CDN series is stale; Doc forbids inventing/scraping substitutes | Log failure; keep historical putcall through 2019-10-04 in table; v4 Steps 2+ use VIX/AAII only for train-era features |
| 2026-10-28 | AAII fetch prefers live aaii.com with Wayback fallback | Live often 403 from cloud egress | `fetch_aaii()` tries live then Wayback snapshot; source recorded in `behavior_counts.json` |
| 2026-10-28 | Started Model v4 Step 1 after v3 “stop for paper review” | Anh: merge then next Doc step; v3 gate in CHAT meets v4 start condition; Phase 5 is review-not-build | Step 1 behavior data + Phase 5 status harness; do not activate v2/v3; Live locked |
| 2026-10-28 | Merged PR #3 (Phase 4 v2 Rejected) + PR #4 (Model v3 Rejected) into main | Anh asked to merge both; keep rejected trees for inspection | active_model stays v1; both report JSON + UI gate blocks retained; Live locked |
| 2026-10-28 | BLS schedules fetched via Wayback when live bls.gov returns 403 | Cloud egress blocked/challenged on BLS; Fed page works live | `refresh_events.py` tries live then archive.org closest snapshot; source URL stored in `events_counts.json` |
| 2026-10-28 | Earnings history from Yahoo (`yfinance`) in addition to Finnhub | Finnhub free `calendar/earnings` returns mostly the next upcoming print, not 2021→today history | Merge: Yahoo fills history; Finnhub wins on same date+ticker; Muse earnings honesty note applies (actual report dates) |
| 2026-10-28 | 2025 CPI/NFP counts are 11 not 12 | BLS 2025 published schedule omits one month each (disrupted releases) | Keep published dates only — do not invent missing months |
| 2026-10-28 | v3 Step 1 branched from `main`, not PR #3 | PR #3 (Phase 4) still open; Doc start condition met with gate Rejected → base v1 | New PR for calendar only; do not activate rejected v2 |
| 2026-10-28 | Leakage test covers same-day/past flags, not days_to_* | Muse allows published future calendar dates for days_to_*; deleting future events would change those by design | Assert past/same-day flags unchanged when events after T are removed; days_to_* keep scheduled future |
| 2026-10-28 | Gate Rejected → active stays v1 | Buy/sell precision narrowly below v1 despite accuracy up | Save v3 artifact; no hand-tuning; no v3b unless Muse/Anh ask |
| 2026-10-28 | Commit JSON sidecars + `v1_vs_v3_report.json`; gitignore `models/*.joblib` | Joblib blobs large/local; metrics must travel with PR | Retrain regenerates joblib via `train_compare_v3.py` |
| 2026-10-28 | Cost estimate uses $0.30/$0.50 per 1M in/out tokens | xAI invoice line items may differ by model | Documented in CHAT.md; TSLA month test ~$0.0047 → full projection ~$1.62 ≪ $25 |
| 2026-10-28 | Weekly backfill scores only weekdays (ignores exchange holidays) | Spec accepts holiday limitation for market-open display; same here | Weekday calendar only for sentiment day keys |
| 2026-10-28 | Full backfill DB lives only in gitignored `data/app.db` | Sentiment rows are large and machine-local; secrets/cost stay out of git | Code + CHAT cost report in PR; re-run `scripts/sentiment_backfill.py --full` on Tuan’s laptop |
| 2026-10-28 | Parallel per-ticker Grok backfill (5 workers) | Sequential 2021→today was too slow for the cloud run | Faster wall time; accepted some HTTP 403 gaps; missing days → feature 0 / No news; no re-score |
| 2026-10-28 | Gate Rejected → active model stays v1 | Muse rule: no hand-tuning after peeking | Saved v2 artifact + report; paper agent loads v1 via `active_model.json` |
| 2026-10-28 | Signals always compute v2 display fields even when active model is v1 | Step 5 UI needs sentiment / headline_count / Market chip regardless of gate | Inference still uses only the active model’s feature columns |
| 2026-10-28 | Commit JSON sidecars + `v1_vs_v2_report.json`; keep `models/*.joblib` gitignored | Joblib blobs are large/machine-local; metrics must travel with the PR | Retrain regenerates joblib from the same script |
| 2026-10-27 | H step 1 uses `st.navigation` in `app.py` pointing at `pages/*.py` | Spec wants `app.py` as entry + `pages/` files; classic auto-pages would rename the home page after `app.py` | Explicit `st.Page` list with titles Dashboard / Signals / Trades / Model / Settings |
| 2026-10-27 | Prototype scripts (`train.py`, `live_signal.py`, `paper_trade.py`, `news_sentiment.py`) not in repo yet | Doc says they are ready to be added; they were not on `main` at skeleton time | Added minimal versions in H.4–H.6 so seed/app/settings checks can pass; formulas match the Doc |
| 2026-10-27 | `core/db.py` includes `signal_grades` table from addendum | Addendum says apply from the start | Schema includes `signal_grades`; UI scorecard on Model page |
| 2026-10-27 | Seed uses `fixtures/paper_state.json` + `fixtures/paper_trades.csv` | Doc assumes root `paper_state.json` / `paper_trades.csv` from the agent; those files were absent | Fixtures mirror Doc wireframe numbers ($102,340); seed script accepts paths; swap to live agent outputs when available |
| 2026-10-27 | `XAI_API_KEY` / Alpaca / Finnhub missing in agent env | User said key available; not found in env or common secret paths | Settings show Not connected; sentiment NULL; no live API calls from UI |
| 2026-10-27 | `.env.example` adds optional `APCA_*` / `FINNHUB_SECRET` / base URL names | Muse lists four exact keys; Anh’s Alpaca SDK uses APCA names and provided a Finnhub secret | Keep Muse’s four primary keys; document empty aliases; resolve either naming in `core/secrets.py` |
| 2026-10-27 | Alpaca client uses REST urllib, not `alpaca-py` | Avoid new dependency churn for Phase 3; paper URL asserted in code | REST against `https://paper-api.alpaca.markets` only; may adopt `alpaca-py` later if Muse asks |
| 2026-10-27 | `FINNHUB_SECRET` stored in `.env` but unused by code | Anh provided API key + secret; Finnhub company-news uses the API key token only | `FINNHUB_API_KEY` drives calls; secret kept in env for future endpoints, never logged |
