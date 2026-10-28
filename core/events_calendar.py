"""Model v3 Step 1 — events calendar builders (Fed / BLS / NYSE / earnings).

Event rows: date, type, source, ticker (ticker only for earnings).
Types: fomc, cpi, nfp, witching, opex, holiday, earnings.

No calendar *features* here — that is Step 2. This module only builds the table.
"""

from __future__ import annotations

import calendar
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd
from bs4 import BeautifulSoup

from core.config import DATA_DIR, DEFAULT_WATCHLIST, ROOT

EVENT_TYPES = ("fomc", "cpi", "nfp", "witching", "opex", "holiday", "earnings")
EVENT_COLUMNS = ["date", "type", "source", "ticker"]

EVENTS_CSV = DATA_DIR / "events.csv"
EVENTS_COUNTS_JSON = DATA_DIR / "events_counts.json"

FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
BLS_ICS_URL = "https://www.bls.gov/schedule/news_release/bls.ics"
BLS_YEAR_URL = "https://www.bls.gov/schedule/{year}/home.htm"
WAYBACK = "https://web.archive.org/web/{ts}/{url}"

# Sanity frequencies from Muse Doc (Step 1 review / Step 2 feature counts)
SANITY_PER_YEAR = {
    "fomc": 8,
    "witching": 4,
    "opex": 12,
}

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


@dataclass(frozen=True)
class EventRow:
    date: str
    type: str
    source: str
    ticker: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "date": self.date,
            "type": self.type,
            "source": self.source,
            "ticker": self.ticker,
        }


def _http_get(url: str, timeout: int = 45) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; TradingAgentCalendar/1.0; "
                "+https://github.com/ANHVU280598/Trading-agent-company-app)"
            ),
            "Accept": "text/html,application/xhtml+xml,text/calendar,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _wayback_closest(url: str) -> Optional[str]:
    api = (
        "https://archive.org/wayback/available?"
        + urllib.parse.urlencode({"url": url})
    )
    try:
        raw = _http_get(api, timeout=30)
        data = json.loads(raw)
        closest = (data.get("archived_snapshots") or {}).get("closest") or {}
        if closest.get("available") and closest.get("url"):
            return str(closest["url"]).replace("http://", "https://")
    except Exception:
        return None
    return None


def _get_with_wayback(url: str) -> tuple[str, str]:
    """Return (body, source_label). Prefer live; fall back to Wayback."""
    try:
        return _http_get(url), url
    except Exception:
        pass
    wb = _wayback_closest(url)
    if not wb:
        raise RuntimeError(f"unable to fetch {url} (live + wayback failed)")
    return _http_get(wb), wb


def _third_friday(year: int, month: int) -> date:
    c = calendar.Calendar(firstweekday=calendar.MONDAY)
    fridays = [
        d
        for d in c.itermonthdates(year, month)
        if d.month == month and d.weekday() == calendar.FRIDAY
    ]
    return fridays[2]


def build_opex(start: date, end: date) -> list[EventRow]:
    rows: list[EventRow] = []
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        d = _third_friday(y, m)
        if start <= d <= end:
            rows.append(
                EventRow(d.isoformat(), "opex", "calendar_rule:third_friday")
            )
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return rows


def build_witching(start: date, end: date) -> list[EventRow]:
    rows: list[EventRow] = []
    for y in range(start.year, end.year + 1):
        for m in (3, 6, 9, 12):
            d = _third_friday(y, m)
            if start <= d <= end:
                rows.append(
                    EventRow(
                        d.isoformat(),
                        "witching",
                        "calendar_rule:quarterly_triple_witching",
                    )
                )
    return rows


def _easter_sunday(year: int) -> date:
    """Anonymous Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _observed(d: date) -> date:
    """NYSE Saturday → Friday before; Sunday → Monday after."""
    if d.weekday() == calendar.SATURDAY:
        return d - timedelta(days=1)
    if d.weekday() == calendar.SUNDAY:
        return d + timedelta(days=1)
    return d


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    c = calendar.Calendar(firstweekday=calendar.MONDAY)
    days = [
        d
        for d in c.itermonthdates(year, month)
        if d.month == month and d.weekday() == weekday
    ]
    return days[n - 1]


def _last_weekday(year: int, month: int, weekday: int) -> date:
    c = calendar.Calendar(firstweekday=calendar.MONDAY)
    days = [
        d
        for d in c.itermonthdates(year, month)
        if d.month == month and d.weekday() == weekday
    ]
    return days[-1]


def build_nyse_holidays(start: date, end: date) -> list[EventRow]:
    """NYSE full-day holidays (observed). Juneteenth from 2021 onward."""
    rows: list[EventRow] = []
    for y in range(start.year, end.year + 1):
        candidates = [
            _observed(date(y, 1, 1)),  # New Year's
            _nth_weekday(y, 1, calendar.MONDAY, 3),  # MLK
            _nth_weekday(y, 2, calendar.MONDAY, 3),  # Presidents
            _easter_sunday(y) - timedelta(days=2),  # Good Friday
            _last_weekday(y, 5, calendar.MONDAY),  # Memorial
            _observed(date(y, 7, 4)),  # Independence
            _nth_weekday(y, 9, calendar.MONDAY, 1),  # Labor
            _nth_weekday(y, 11, calendar.THURSDAY, 4),  # Thanksgiving
            _observed(date(y, 12, 25)),  # Christmas
        ]
        if y >= 2021:
            candidates.append(_observed(date(y, 6, 19)))  # Juneteenth
        for d in candidates:
            if start <= d <= end:
                rows.append(EventRow(d.isoformat(), "holiday", "nyse_rules"))
    # de-dupe (rare overlaps)
    uniq = {(r.date, r.type): r for r in rows}
    return sorted(uniq.values(), key=lambda r: r.date)


def _parse_fomc_decision_days(html: str) -> list[date]:
    """Parse Fed FOMC calendars page; decision day = last day of each meeting."""
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    decisions: list[date] = []

    # Split by year headings like "2024 FOMC Meetings"
    parts = re.split(r"(\d{4})\s+FOMC Meetings", text)
    # parts: preamble, year, body, year, body, ...
    for i in range(1, len(parts), 2):
        year = int(parts[i])
        body = parts[i + 1] if i + 1 < len(parts) else ""
        # Month line then day range on next line(s): "January\n30-31" or "Apr/May\n30-1"
        # Also "* " for projection meetings.
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        j = 0
        while j < len(lines):
            line = lines[j]
            # stop at next section-ish noise
            if re.match(r"^\d{4}\s+FOMC", line):
                break
            month_key = None
            month2_key = None
            m = re.match(
                r"^(January|February|March|April|May|June|July|August|"
                r"September|October|November|December)"
                r"(?:/(January|February|March|April|May|June|July|August|"
                r"September|October|November|December))?$",
                line,
                re.I,
            )
            if not m:
                # compact "Apr/May"
                m2 = re.match(
                    r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
                    r"(?:/(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))?$",
                    line,
                    re.I,
                )
                if m2:
                    month_key = m2.group(1).lower()
                    month2_key = (m2.group(2) or "").lower() or None
                else:
                    j += 1
                    continue
            else:
                month_key = m.group(1).lower()
                month2_key = (m.group(2) or "").lower() or None

            # look ahead for day range
            day_line = lines[j + 1] if j + 1 < len(lines) else ""
            dm = re.match(r"^(\d{1,2})\s*[-–]\s*(\d{1,2})\*?", day_line)
            if not dm:
                j += 1
                continue
            d1, d2 = int(dm.group(1)), int(dm.group(2))
            m1 = MONTHS[month_key]
            if month2_key:
                m2n = MONTHS[month2_key]
                # end day is in second month
                end = date(year if m2n >= m1 else year + 1, m2n, d2)
            else:
                end = date(year, m1, d2)
            decisions.append(end)
            j += 2
    return sorted(set(decisions))


def build_fomc(start: date, end: date) -> tuple[list[EventRow], str]:
    body, src = _get_with_wayback(FOMC_URL)
    days = _parse_fomc_decision_days(body)
    rows = [
        EventRow(d.isoformat(), "fomc", "federalreserve.gov")
        for d in days
        if start <= d <= end
    ]
    return rows, src


def _parse_bls_year_page(html: str, year: int) -> list[EventRow]:
    """Parse BLS yearly schedule tables (space-joined row text)."""
    rows: list[EventRow] = []
    soup = BeautifulSoup(html, "lxml")
    pat = re.compile(
        r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
        r"(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+(\d{1,2}),\s+(\d{4})\s+"
        r"\d{1,2}:\d{2}\s*[AP]M\s+"
        r"(Consumer Price Index|Employment Situation)\s+for\b",
        re.I,
    )
    # Prefer <tr> text (date + title on one line). Also scan full page with spaces.
    blobs: list[str] = [
        tr.get_text(" ", strip=True) for tr in soup.find_all("tr")
    ]
    blobs.append(soup.get_text(" ", strip=True))
    for blob in blobs:
        if "Veterans" in blob and "Employment Situation of Veterans" in blob:
            # Still allow other releases on a huge blob; filter per-match below.
            pass
        for m in pat.finditer(blob):
            window = blob[m.start() : m.start() + 140]
            if "Veterans" in window:
                continue
            mon = MONTHS[m.group(2).lower()]
            day = int(m.group(3))
            y = int(m.group(4))
            label = m.group(5).lower()
            d = date(y, mon, day)
            if "consumer price" in label:
                rows.append(EventRow(d.isoformat(), "cpi", "bls.gov"))
            else:
                rows.append(EventRow(d.isoformat(), "nfp", "bls.gov"))
    uniq = {(r.date, r.type): r for r in rows}
    return sorted(uniq.values(), key=lambda r: (r.date, r.type))


def _parse_bls_ics(ics: str) -> list[EventRow]:
    rows: list[EventRow] = []
    # Wayback sometimes returns gzip; require plaintext VCALENDAR header.
    if "BEGIN:VCALENDAR" not in ics:
        return []
    for block in ics.split("BEGIN:VEVENT")[1:]:
        summary_m = re.search(r"SUMMARY:(.+)", block)
        dt_m = re.search(r"DTSTART(?:;[^:]*)?:(\d{8})", block)
        if not summary_m or not dt_m:
            continue
        summary = summary_m.group(1).strip()
        raw = dt_m.group(1)
        d = date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
        if summary == "Consumer Price Index" or summary.startswith(
            "Consumer Price Index"
        ):
            rows.append(EventRow(d.isoformat(), "cpi", "bls.gov"))
        elif summary == "Employment Situation":
            rows.append(EventRow(d.isoformat(), "nfp", "bls.gov"))
    uniq = {(r.date, r.type): r for r in rows}
    return sorted(uniq.values(), key=lambda r: (r.date, r.type))


def build_bls(start: date, end: date) -> tuple[list[EventRow], list[str]]:
    """CPI + NFP from BLS yearly schedules (+ ICS for near-term)."""
    sources: list[str] = []
    rows: list[EventRow] = []
    for y in range(start.year, end.year + 1):
        url = BLS_YEAR_URL.format(year=y)
        try:
            body, src = _get_with_wayback(url)
            sources.append(src)
            rows.extend(_parse_bls_year_page(body, y))
        except Exception as exc:
            sources.append(f"FAIL {url}: {exc}")
    try:
        body, src = _get_with_wayback(BLS_ICS_URL)
        sources.append(src)
        rows.extend(_parse_bls_ics(body))
    except Exception as exc:
        sources.append(f"FAIL ics: {exc}")

    # Clip + dedupe
    clipped = [
        r
        for r in rows
        if start <= date.fromisoformat(r.date) <= end
    ]
    uniq = {(r.date, r.type): r for r in clipped}
    return sorted(uniq.values(), key=lambda r: (r.date, r.type)), sources


def build_earnings_finnhub(
    tickers: Iterable[str],
    start: date,
    end: date,
) -> tuple[list[EventRow], str]:
    """Upcoming earnings from Finnhub calendar (free tier: mostly future)."""
    key = os.getenv("FINNHUB_API_KEY", "").strip()
    if not key:
        return [], "finnhub:missing_key"
    rows: list[EventRow] = []
    note = "finnhub.io/calendar/earnings"
    for ticker in tickers:
        if ticker.upper() == "SPY":
            continue  # ETF — no earnings
        params = urllib.parse.urlencode(
            {
                "symbol": ticker.upper(),
                "from": start.isoformat(),
                "to": end.isoformat(),
                "token": key,
            }
        )
        url = f"https://finnhub.io/api/v1/calendar/earnings?{params}"
        try:
            raw = _http_get(url, timeout=30)
            data = json.loads(raw)
            for item in data.get("earningsCalendar") or []:
                d = str(item.get("date") or "")[:10]
                if not d:
                    continue
                dd = date.fromisoformat(d)
                if start <= dd <= end:
                    rows.append(
                        EventRow(d, "earnings", "finnhub", ticker.upper())
                    )
        except Exception as exc:
            note = f"finnhub:error:{exc}"
    uniq = {(r.date, r.ticker): r for r in rows}
    return sorted(uniq.values(), key=lambda r: (r.date, r.ticker)), note


def build_earnings_yahoo(
    tickers: Iterable[str],
    start: date,
    end: date,
) -> tuple[list[EventRow], str]:
    """Historical (+ near) earnings announcement dates via yfinance.

    Finnhub free calendar often returns only the next print. Yahoo fills history
    with actual report dates (accepted noise per Muse earnings honesty note).
    """
    import yfinance as yf

    rows: list[EventRow] = []
    for ticker in tickers:
        if ticker.upper() == "SPY":
            continue
        try:
            ed = yf.Ticker(ticker).get_earnings_dates(limit=80)
        except Exception:
            continue
        if ed is None or ed.empty:
            continue
        for ts in ed.index:
            try:
                d = ts.tz_convert("America/New_York").date() if getattr(ts, "tzinfo", None) else ts.date()
            except Exception:
                d = pd.Timestamp(ts).date()
            if start <= d <= end:
                rows.append(
                    EventRow(d.isoformat(), "earnings", "yahoo_finance", ticker.upper())
                )
    uniq = {(r.date, r.ticker): r for r in rows}
    return sorted(uniq.values(), key=lambda r: (r.date, r.ticker)), "yahoo_finance:get_earnings_dates"


def merge_earnings(
    finnhub_rows: list[EventRow],
    yahoo_rows: list[EventRow],
) -> list[EventRow]:
    """Prefer Finnhub when both have the same date+ticker; else keep both sources' uniques by date."""
    by_key: dict[tuple[str, str], EventRow] = {}
    for r in yahoo_rows:
        by_key[(r.date, r.ticker)] = r
    for r in finnhub_rows:
        by_key[(r.date, r.ticker)] = r  # finnhub wins on conflict
    return sorted(by_key.values(), key=lambda r: (r.date, r.ticker))


def build_all_events(
    start: date,
    end: date,
    tickers: Optional[list[str]] = None,
) -> tuple[pd.DataFrame, dict]:
    tickers = list(tickers or DEFAULT_WATCHLIST)
    meta: dict = {"start": start.isoformat(), "end": end.isoformat(), "sources": {}}

    fomc, fomc_src = build_fomc(start, end)
    meta["sources"]["fomc"] = fomc_src

    bls, bls_srcs = build_bls(start, end)
    meta["sources"]["bls"] = bls_srcs

    holidays = build_nyse_holidays(start, end)
    opex = build_opex(start, end)
    witching = build_witching(start, end)

    fh, fh_note = build_earnings_finnhub(tickers, start, end)
    yh, yh_note = build_earnings_yahoo(tickers, start, end)
    earnings = merge_earnings(fh, yh)
    meta["sources"]["earnings_finnhub"] = fh_note
    meta["sources"]["earnings_yahoo"] = yh_note
    meta["earnings_finnhub_rows"] = len(fh)
    meta["earnings_yahoo_rows"] = len(yh)

    all_rows = fomc + bls + holidays + opex + witching + earnings
    frame = pd.DataFrame([r.as_dict() for r in all_rows], columns=EVENT_COLUMNS)
    if not frame.empty:
        frame = (
            frame.drop_duplicates(subset=["date", "type", "ticker"], keep="last")
            .sort_values(["date", "type", "ticker"])
            .reset_index(drop=True)
        )
    meta["counts"] = counts_report(frame, start.year, end.year)
    return frame, meta


def counts_report(frame: pd.DataFrame, year_from: int, year_to: int) -> dict:
    """Per-type totals + per-year breakdown for Anh's sanity review."""
    out: dict = {
        "by_type": {},
        "by_year": {},
        "sanity": SANITY_PER_YEAR,
        "date_min": None,
        "date_max": None,
        "total_rows": int(len(frame)),
    }
    if frame.empty:
        return out
    out["date_min"] = str(frame["date"].min())
    out["date_max"] = str(frame["date"].max())
    out["by_type"] = {t: int((frame["type"] == t).sum()) for t in EVENT_TYPES}
    # earnings by ticker
    earn = frame[frame["type"] == "earnings"]
    out["earnings_by_ticker"] = (
        earn.groupby("ticker").size().astype(int).to_dict() if not earn.empty else {}
    )
    frame = frame.copy()
    frame["year"] = frame["date"].astype(str).str.slice(0, 4).astype(int)
    for y in range(year_from, year_to + 1):
        sub = frame[frame["year"] == y]
        year_counts = {t: int((sub["type"] == t).sum()) for t in EVENT_TYPES}
        # sanity deltas for Doc frequencies that are event-table types
        year_counts["_sanity_fomc_delta"] = year_counts["fomc"] - SANITY_PER_YEAR["fomc"]
        year_counts["_sanity_witching_delta"] = (
            year_counts["witching"] - SANITY_PER_YEAR["witching"]
        )
        year_counts["_sanity_opex_delta"] = year_counts["opex"] - SANITY_PER_YEAR["opex"]
        out["by_year"][str(y)] = year_counts
    return out


def save_events_csv(frame: pd.DataFrame, path: Path = EVENTS_CSV) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    for c in EVENT_COLUMNS:
        if c not in out.columns:
            out[c] = ""
    out = out[EVENT_COLUMNS].fillna("")
    out.to_csv(path, index=False)
    return path


def save_counts(meta: dict, path: Path = EVENTS_COUNTS_JSON) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return path


def load_events_csv(path: Path = EVENTS_CSV) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=EVENT_COLUMNS)
    return pd.read_csv(path, dtype=str, keep_default_na=False)
