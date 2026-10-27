# Muse ↔ Cursor — Team Channel

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
