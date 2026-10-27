# Decisions log

Muse reviews this file every round. Every deviation from the Muse Doc Detailed Build Spec is logged here: what, why, and what was chosen instead. An unlogged deviation is treated as a bug.

| Date | What | Why | Chose instead |
|------|------|-----|---------------|
| 2026-10-27 | H step 1 uses `st.navigation` in `app.py` pointing at `pages/*.py` | Spec wants `app.py` as entry + `pages/` files; classic auto-pages would rename the home page after `app.py` | Explicit `st.Page` list with titles Dashboard / Signals / Trades / Model / Settings |
| 2026-10-27 | Prototype scripts (`train.py`, `live_signal.py`, `paper_trade.py`, `news_sentiment.py`) not in repo yet | Doc says they are ready to be added; they were not on `main` at skeleton time | Skeleton only; do not invent those scripts until Muse/Tuan provide them or a later brief asks |
| 2026-10-27 | `core/db.py` includes `signal_grades` table from addendum | Addendum says apply from the start | Schema includes `signal_grades`; UI scorecard waits for Model wiring steps |
