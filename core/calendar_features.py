"""Model v3 Step 2 — 18 calendar features from the events table (no leakage from prices)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd

from core.events_calendar import load_events_csv

CALENDAR_FEATURE_ORDER: list[str] = [
    "days_to_fomc",
    "fomc_day",
    "days_to_cpi",
    "cpi_day",
    "nfp_day",
    "days_to_earnings",
    "earnings_soon",
    "just_reported",
    "witching_day",
    "opex_day",
    "quarter_turn",
    "santa_window",
    "january_flag",
    "september_flag",
    "may_oct_flag",
    "december_flag",
    "pre_holiday",
    "day_of_week",
]


def trading_days_index(
    start: date,
    end: date,
    holidays: set[str],
) -> list[date]:
    """Weekdays minus NYSE holiday dates (ISO strings in holidays)."""
    out: list[date] = []
    d = start
    while d <= end:
        if d.weekday() < 5 and d.isoformat() not in holidays:
            out.append(d)
        d += timedelta(days=1)
    return out


def _as_dates(series: pd.Series) -> list[date]:
    return sorted({date.fromisoformat(str(x)[:10]) for x in series.tolist()})


def build_calendar_features(
    session_dates: list[date] | pd.DatetimeIndex | pd.Index,
    events: pd.DataFrame,
    ticker: str,
) -> pd.DataFrame:
    """Build the 18 Muse calendar features for one ticker on trading sessions.

    Future *scheduled* event dates are allowed (published calendars). Features
    never read prices.
    """
    if hasattr(session_dates, "tolist"):
        raw = list(session_dates)
    else:
        raw = list(session_dates)
    sessions: list[date] = []
    for x in raw:
        if isinstance(x, date) and not isinstance(x, pd.Timestamp):
            sessions.append(x)
        else:
            sessions.append(pd.Timestamp(x).date())
    sessions = sorted(set(sessions))
    if not sessions:
        return pd.DataFrame(columns=CALENDAR_FEATURE_ORDER)

    ev = events.copy() if events is not None else pd.DataFrame()
    if ev.empty:
        ev = pd.DataFrame(columns=["date", "type", "source", "ticker"])
    ev["date"] = ev["date"].astype(str).str.slice(0, 10)
    ev["type"] = ev["type"].astype(str)
    ev["ticker"] = ev.get("ticker", "").fillna("").astype(str).str.upper()

    holidays = set(ev.loc[ev["type"] == "holiday", "date"].tolist())
    fomc = _as_dates(ev.loc[ev["type"] == "fomc", "date"])
    cpi = _as_dates(ev.loc[ev["type"] == "cpi", "date"])
    nfp = _as_dates(ev.loc[ev["type"] == "nfp", "date"])
    witch = set(ev.loc[ev["type"] == "witching", "date"].tolist())
    opex = set(ev.loc[ev["type"] == "opex", "date"].tolist())
    earn_all = ev.loc[ev["type"] == "earnings"]
    if ticker and ticker.upper() != "SPY":
        earn = _as_dates(earn_all.loc[earn_all["ticker"] == ticker.upper(), "date"])
    else:
        earn = []

    # Trading-day list spanning sessions ± cushion for days_to / santa / quarter
    cushion_start = sessions[0] - timedelta(days=40)
    cushion_end = sessions[-1] + timedelta(days=40)
    tdays = trading_days_index(cushion_start, cushion_end, holidays)
    tpos = {d: i for i, d in enumerate(tdays)}

    rows: list[dict] = []
    for t in sessions:
        iso = t.isoformat()
        # days_to_fomc — trading days until next FOMC (0 if today), cap 30
        days_to_fomc = 30.0
        if t in tpos:
            ti = tpos[t]
            for f in fomc:
                if f < t:
                    continue
                if f in tpos:
                    days_to_fomc = float(min(30, tpos[f] - ti))
                    break
                # FOMC on non-session (shouldn't happen) — calendar days proxy
                days_to_fomc = float(min(30, (f - t).days))
                break

        fomc_day = 1.0 if t in set(fomc) else 0.0

        # days_to_cpi — calendar days until next CPI, cap 31
        days_to_cpi = 31.0
        for c in cpi:
            if c >= t:
                days_to_cpi = float(min(31, (c - t).days))
                break
        cpi_day = 1.0 if t in set(cpi) else 0.0
        nfp_day = 1.0 if t in set(nfp) else 0.0

        # earnings — trading days to next, cap 63; default 63 if unknown
        days_to_earnings = 63.0
        if t in tpos and earn:
            ti = tpos[t]
            for e in earn:
                if e < t:
                    continue
                if e in tpos:
                    days_to_earnings = float(min(63, tpos[e] - ti))
                else:
                    # map to next session on/after earnings date
                    for td in tdays:
                        if td >= e:
                            days_to_earnings = float(min(63, tpos[td] - ti))
                            break
                break
        earnings_soon = 1.0 if days_to_earnings <= 5.0 else 0.0

        just_reported = 0.0
        if t in tpos and earn:
            ti = tpos[t]
            for e in earn:
                if e >= t:
                    continue
                if e in tpos:
                    lag = ti - tpos[e]
                else:
                    # last session on/before e
                    lag = None
                    for td in reversed(tdays):
                        if td <= e:
                            lag = ti - tpos[td]
                            break
                if lag in (1, 2):
                    just_reported = 1.0
                    break

        witching_day = 1.0 if iso in witch else 0.0
        opex_day = 1.0 if iso in opex else 0.0

        quarter_turn = 1.0 if _is_quarter_turn(t, tdays, tpos) else 0.0
        santa_window = 1.0 if _is_santa(t, tdays, tpos) else 0.0

        january_flag = 1.0 if t.month == 1 else 0.0
        september_flag = 1.0 if t.month == 9 else 0.0
        may_oct_flag = 1.0 if 5 <= t.month <= 10 else 0.0
        december_flag = 1.0 if t.month == 12 else 0.0

        pre_holiday = 0.0
        if t in tpos:
            ti = tpos[t]
            if ti + 1 < len(tdays):
                nxt = tdays[ti + 1]
                # holiday strictly between T and next session
                d = t + timedelta(days=1)
                while d < nxt:
                    if d.isoformat() in holidays:
                        pre_holiday = 1.0
                        break
                    d += timedelta(days=1)

        day_of_week = float(t.weekday())  # Mon=0 .. Fri=4

        rows.append(
            {
                "date": iso,
                "days_to_fomc": days_to_fomc,
                "fomc_day": fomc_day,
                "days_to_cpi": days_to_cpi,
                "cpi_day": cpi_day,
                "nfp_day": nfp_day,
                "days_to_earnings": days_to_earnings,
                "earnings_soon": earnings_soon,
                "just_reported": just_reported,
                "witching_day": witching_day,
                "opex_day": opex_day,
                "quarter_turn": quarter_turn,
                "santa_window": santa_window,
                "january_flag": january_flag,
                "september_flag": september_flag,
                "may_oct_flag": may_oct_flag,
                "december_flag": december_flag,
                "pre_holiday": pre_holiday,
                "day_of_week": day_of_week,
            }
        )

    frame = pd.DataFrame(rows).set_index("date")
    return frame[CALENDAR_FEATURE_ORDER]


def _quarter_bounds_trading_days(
    year: int, tdays: list[date], tpos: dict[date, int]
) -> list[date]:
    """Last 3 + first 2 trading days around each quarter boundary in ``year``."""
    marked: list[date] = []
    # Quarter starts: Jan 1, Apr 1, Jul 1, Oct 1 — and next Jan for year-end last-3
    starts = [
        date(year, 1, 1),
        date(year, 4, 1),
        date(year, 7, 1),
        date(year, 10, 1),
        date(year + 1, 1, 1),
    ]
    for qs in starts:
        # first 2 trading days on/after qs
        firsts = [d for d in tdays if d >= qs][:2]
        marked.extend(firsts)
        # last 3 trading days strictly before qs
        befores = [d for d in tdays if d < qs][-3:]
        marked.extend(befores)
    return marked


def _is_quarter_turn(t: date, tdays: list[date], tpos: dict[date, int]) -> bool:
    marked = set(_quarter_bounds_trading_days(t.year, tdays, tpos))
    # also need previous year's Dec last-3 when t is early Jan — covered by year-1
    marked |= set(_quarter_bounds_trading_days(t.year - 1, tdays, tpos))
    return t in marked


def _is_santa(t: date, tdays: list[date], tpos: dict[date, int]) -> bool:
    # last 5 trading days of year Y, first 2 of Y+1
    for y in (t.year - 1, t.year):
        last5 = [d for d in tdays if d.year == y][-5:]
        first2 = [d for d in tdays if d.year == y + 1][:2]
        if t in last5 or t in first2:
            return True
    return False


def next_event_line(
    as_of: str,
    ticker: str,
    events: Optional[pd.DataFrame] = None,
) -> str:
    """Display-only next-event blurb: Earnings / FOMC / CPI / Witching."""
    if events is None:
        events = load_events_csv()
    if events is None or events.empty:
        return "—"
    t = date.fromisoformat(as_of[:10])
    ev = events.copy()
    ev["date"] = ev["date"].astype(str).str.slice(0, 10)
    ev["type"] = ev["type"].astype(str)
    ev["ticker"] = ev.get("ticker", "").fillna("").astype(str).str.upper()

    holidays = set(ev.loc[ev["type"] == "holiday", "date"].tolist())
    tdays = trading_days_index(t - timedelta(days=5), t + timedelta(days=120), holidays)
    tpos = {d: i for i, d in enumerate(tdays)}
    if t not in tpos:
        prior = [d for d in tdays if d <= t]
        if not prior:
            return "—"
        t = prior[-1]

    def fmt(name: str, day: date, trading: bool) -> tuple[int, str] | None:
        if day < t:
            return None
        if day == t:
            if name == "Witching":
                return (0, "Witching day")
            return (0, f"{name} today")
        if trading and t in tpos and day in tpos:
            dist = tpos[day] - tpos[t]
        else:
            dist = (day - t).days
        if dist <= 0:
            return None
        if dist == 1:
            return (1, f"{name} tomorrow")
        return (dist, f"{name} in {dist}d")

    candidates: list[tuple[int, str]] = []
    for typ, name, trading, ticker_match in (
        ("earnings", "Earnings", True, True),
        ("fomc", "FOMC", True, False),
        ("cpi", "CPI", False, False),
        ("witching", "Witching", True, False),
    ):
        sub = ev[ev["type"] == typ]
        if ticker_match:
            sub = sub[sub["ticker"] == ticker.upper()]
        for ds in sorted(sub["date"].tolist()):
            d = date.fromisoformat(str(ds)[:10])
            if d < t:
                continue
            item = fmt(name, d, trading)
            if item:
                candidates.append(item)
            break  # nearest of this type

    if not candidates:
        return "—"
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]
