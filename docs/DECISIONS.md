# Decisions log

Muse reviews this file every round. Every deviation from the Muse Doc Detailed Build Spec is logged here: what, why, and what was chosen instead. An unlogged deviation is treated as a bug.

| Date | What | Why | Chose instead |
|------|------|-----|---------------|
| 2026-10-27 | H step 1 uses `st.navigation` in `app.py` pointing at `pages/*.py` | Spec wants `app.py` as entry + `pages/` files; classic auto-pages would rename the home page after `app.py` | Explicit `st.Page` list with titles Dashboard / Signals / Trades / Model / Settings |
| 2026-10-27 | Prototype scripts (`train.py`, `live_signal.py`, `paper_trade.py`, `news_sentiment.py`) not in repo yet | Doc says they are ready to be added; they were not on `main` at skeleton time | Added minimal versions in H.4–H.6 so seed/app/settings checks can pass; formulas match the Doc |
| 2026-10-27 | `core/db.py` includes `signal_grades` table from addendum | Addendum says apply from the start | Schema includes `signal_grades`; UI scorecard on Model page |
| 2026-10-27 | Seed uses `fixtures/paper_state.json` + `fixtures/paper_trades.csv` | Doc assumes root `paper_state.json` / `paper_trades.csv` from the agent; those files were absent | Fixtures mirror Doc wireframe numbers ($102,340); seed script accepts paths; swap to live agent outputs when available |
| 2026-10-27 | `XAI_API_KEY` / Alpaca / Finnhub missing in agent env | User said key available; not found in env or common secret paths | Settings show Not connected; sentiment NULL; no live API calls from UI |
