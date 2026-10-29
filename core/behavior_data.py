"""Model v4 Step 1 — crowd behavior series (VIX, CBOE put/call, AAII).

Publication-lag rules (hard):
- AAII is weekly: forward-fill from the publication date only; never earlier.
- Put/call: if the file posts after the close, day T uses the T-1 value
  (implemented as shift(1) on the trading calendar when applying features;
  the stored table keeps the published file date as-is for audit).
"""

from __future__ import annotations

import io
import json
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from core.config import ROOT
from core.data import get_daily_bars

BEHAVIOR_CSV = ROOT / "data" / "behavior.csv"
BEHAVIOR_COUNTS_JSON = ROOT / "data" / "behavior_counts.json"
BEHAVIOR_COLUMNS = ["date", "vix_close", "putcall", "aaii_bull", "aaii_bear"]

CBOE_TOTAL_PC_URL = (
    "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpc.csv"
)
AAII_LIVE_URL = "https://www.aaii.com/files/surveys/sentiment.xls"
AAII_WAYBACK_URL = (
    "https://web.archive.org/web/20261022203215id_/"
    "https://www.aaii.com/files/surveys/sentiment.xls"
)

UA = {"User-Agent": "Mozilla/5.0 (compatible; MuseTradingAgent/1.0)"}


def _http_get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_vix(start: str = "2019-01-01", end: Optional[str] = None) -> pd.DataFrame:
    """Daily VIX close via the same Yahoo path as prices (`^VIX`)."""
    end = end or date.today().isoformat()
    bars = get_daily_bars("^VIX", start, end)
    if bars.empty:
        return pd.DataFrame(columns=["date", "vix_close"])
    out = bars[["date", "close"]].copy()
    out = out.rename(columns={"close": "vix_close"})
    out["date"] = out["date"].astype(str)
    out["vix_close"] = out["vix_close"].astype(float)
    return out.dropna(subset=["vix_close"]).sort_values("date").reset_index(drop=True)


def fetch_cboe_putcall() -> tuple[pd.DataFrame, dict[str, Any]]:
    """CBOE total put/call daily series from the official CDN CSV.

    Returns (frame with date, putcall) and meta. On failure, empty frame + error note.
    """
    meta: dict[str, Any] = {"source": CBOE_TOTAL_PC_URL, "ok": False}
    try:
        raw = _http_get(CBOE_TOTAL_PC_URL).decode("utf-8", "replace")
        lines = raw.splitlines()
        skip = 0
        for i, line in enumerate(lines):
            if line.startswith("DATE,"):
                skip = i
                break
        df = pd.read_csv(io.StringIO(raw), skiprows=skip)
        if "DATE" not in df.columns or "P/C Ratio" not in df.columns:
            meta["error"] = f"unexpected columns: {list(df.columns)}"
            return pd.DataFrame(columns=["date", "putcall"]), meta
        out = pd.DataFrame(
            {
                "date": pd.to_datetime(df["DATE"]).dt.strftime("%Y-%m-%d"),
                "putcall": pd.to_numeric(df["P/C Ratio"], errors="coerce"),
            }
        ).dropna(subset=["putcall"])
        out = out.sort_values("date").drop_duplicates("date").reset_index(drop=True)
        meta["ok"] = True
        meta["rows"] = int(len(out))
        meta["min_date"] = str(out["date"].iloc[0]) if len(out) else None
        meta["max_date"] = str(out["date"].iloc[-1]) if len(out) else None
        # Official free file historically stalls ~2019 — flag for DECISIONS / Step 2.
        if meta["max_date"] and meta["max_date"] < "2021-01-01":
            meta["stale_for_train_window"] = True
            meta["note"] = (
                f"CBOE totalpc.csv ends {meta['max_date']}; no coverage for "
                "2021+ training window — treat putcall as unavailable for v4 train."
            )
        return out, meta
    except Exception as exc:  # noqa: BLE001 — soft-fail per Muse brief
        meta["error"] = f"{type(exc).__name__}: {exc}"
        return pd.DataFrame(columns=["date", "putcall"]), meta


def fetch_aaii() -> tuple[pd.DataFrame, dict[str, Any]]:
    """AAII weekly bull/bear percentages from the official spreadsheet.

    Live aaii.com often 403s from cloud egress → Wayback snapshot fallback.
    """
    meta: dict[str, Any] = {"ok": False}
    raw: Optional[bytes] = None
    for label, url in (("live", AAII_LIVE_URL), ("wayback", AAII_WAYBACK_URL)):
        try:
            raw = _http_get(url, timeout=90)
            meta["source"] = url
            meta["source_kind"] = label
            break
        except Exception as exc:  # noqa: BLE001
            meta[f"{label}_error"] = f"{type(exc).__name__}: {exc}"
    if raw is None:
        meta["error"] = "AAII download failed (live + wayback)"
        return pd.DataFrame(columns=["date", "aaii_bull", "aaii_bear"]), meta

    # Persist temp for xlrd
    tmp = ROOT / "data" / ".aaii_cache.xls"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(raw)
    try:
        sheet = pd.read_excel(tmp, engine="xlrd", header=None)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass

    # Row 3 = headers; data from row 5+
    rows: list[dict[str, Any]] = []
    for i in range(5, len(sheet)):
        d = sheet.iloc[i, 0]
        bull = sheet.iloc[i, 1]
        bear = sheet.iloc[i, 3]
        if pd.isna(d):
            continue
        try:
            d_str = pd.Timestamp(d).strftime("%Y-%m-%d")
        except Exception:
            continue
        if pd.isna(bull) or pd.isna(bear):
            continue
        try:
            bull_f = float(bull)
            bear_f = float(bear)
        except (TypeError, ValueError):
            continue
        # Spreadsheet stores fractions (0.36) not percents
        if bull_f <= 1.5 and bear_f <= 1.5:
            bull_f *= 100.0
            bear_f *= 100.0
        rows.append({"date": d_str, "aaii_bull": bull_f, "aaii_bear": bear_f})

    out = pd.DataFrame(rows)
    if out.empty:
        meta["error"] = "AAII parse produced 0 rows"
        return pd.DataFrame(columns=["date", "aaii_bull", "aaii_bear"]), meta
    out = out.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    meta["ok"] = True
    meta["rows"] = int(len(out))
    meta["min_date"] = str(out["date"].iloc[0])
    meta["max_date"] = str(out["date"].iloc[-1])
    return out, meta


def forward_fill_aaii_to_sessions(
    sessions: list[str],
    aaii: pd.DataFrame,
) -> pd.DataFrame:
    """Map weekly AAII onto trading sessions with publication-lag rule.

    An AAII row published on day P may only affect sessions with date >= P.
    Forward-fill after that; never look ahead.
    """
    idx = pd.Index(sorted(sessions), name="date")
    empty = pd.DataFrame({"aaii_bull": pd.NA, "aaii_bear": pd.NA}, index=idx)
    if aaii is None or aaii.empty:
        return empty
    weekly = aaii[["date", "aaii_bull", "aaii_bear"]].copy()
    weekly["_d"] = pd.to_datetime(weekly["date"])
    weekly = weekly.drop(columns=["date"]).sort_values("_d")
    sess = pd.DataFrame({"date": list(idx)})
    sess["_d"] = pd.to_datetime(sess["date"])
    merged = pd.merge_asof(
        sess.sort_values("_d"),
        weekly,
        on="_d",
        direction="backward",
    )
    return merged.set_index("date")[["aaii_bull", "aaii_bear"]].reindex(idx)


def putcall_in_force(
    sessions: list[str],
    putcall: pd.DataFrame,
    *,
    lag_one_session: bool = True,
) -> pd.Series:
    """Put/call value in force at session T.

    Muse: if the file posts after the close, day T uses T-1.
    Default applies a one-session lag on the trading calendar.

    Do **not** forward-fill past the last published CBOE date — a stale CDN
    file (e.g. ending 2019) must not invent 2021+ putcall values. Missing → NA
    so crowd_mood falls back to VIX+SPY only.
    """
    idx = pd.Index(sorted(sessions), name="date")
    if putcall is None or putcall.empty:
        return pd.Series(pd.NA, index=idx, name="putcall")
    pub = putcall[["date", "putcall"]].copy()
    pub["date"] = pub["date"].astype(str)
    last_pub = str(pub["date"].max())
    # Align published values onto matching session dates only
    s = pub.drop_duplicates("date").set_index("date")["putcall"]
    aligned = s.reindex(idx)
    # Also allow as-of within the published span (holidays): merge_asof but clip
    pub["_d"] = pd.to_datetime(pub["date"])
    pub2 = pub.drop(columns=["date"]).sort_values("_d")
    sess = pd.DataFrame({"date": list(idx)})
    sess["_d"] = pd.to_datetime(sess["date"])
    merged = pd.merge_asof(
        sess.sort_values("_d"),
        pub2,
        on="_d",
        direction="backward",
    ).set_index("date")["putcall"]
    # Null out anything after last publication date
    merged = merged.where(pd.Index(merged.index.astype(str)) <= last_pub)
    if lag_one_session:
        merged = merged.shift(1)
    return merged.reindex(idx).rename("putcall")


def build_behavior_table(
    start: str = "2019-01-01",
    end: Optional[str] = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Assemble the behavior table on the VIX/trading calendar."""
    end = end or date.today().isoformat()
    meta: dict[str, Any] = {"start": start, "end": end}

    vix = fetch_vix(start, end)
    meta["vix"] = {
        "ok": not vix.empty,
        "rows": int(len(vix)),
        "min_date": str(vix["date"].iloc[0]) if len(vix) else None,
        "max_date": str(vix["date"].iloc[-1]) if len(vix) else None,
        "source": "yahoo:^VIX",
    }

    pc, pc_meta = fetch_cboe_putcall()
    meta["putcall"] = pc_meta

    aaii, aaii_meta = fetch_aaii()
    meta["aaii"] = aaii_meta

    if vix.empty:
        meta["error"] = "VIX fetch empty — cannot build session calendar"
        return pd.DataFrame(columns=BEHAVIOR_COLUMNS), meta

    sessions = vix["date"].astype(str).tolist()
    aaii_ff = forward_fill_aaii_to_sessions(sessions, aaii)
    # Store raw published putcall on its file date (audit). Lag applied at feature time.
    # For the committed table Muse asked: date, vix_close, putcall, aaii_bull, aaii_bear
    # with AAII already publication-safe via forward-fill from pub date.
    pc_on = (
        pc.set_index("date")["putcall"]
        if not pc.empty
        else pd.Series(dtype=float)
    )
    out = vix.set_index("date")[["vix_close"]].copy()
    out["putcall"] = pc_on.reindex(out.index)
    out["aaii_bull"] = aaii_ff["aaii_bull"]
    out["aaii_bear"] = aaii_ff["aaii_bear"]
    out = out.reset_index()
    out = out[BEHAVIOR_COLUMNS]

    meta["rows"] = int(len(out))
    meta["putcall_non_null"] = int(out["putcall"].notna().sum())
    meta["aaii_non_null"] = int(out["aaii_bull"].notna().sum())
    meta["vix_non_null"] = int(out["vix_close"].notna().sum())
    meta["cnn_fear_greed_scraped"] = False  # deliberate non-source
    return out, meta


def save_behavior_csv(frame: pd.DataFrame, path: Path = BEHAVIOR_CSV) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return path


def save_counts(meta: dict[str, Any], path: Path = BEHAVIOR_COUNTS_JSON) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return path


def load_behavior_csv(path: Path = BEHAVIOR_CSV) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=BEHAVIOR_COLUMNS)
    df = pd.read_csv(path)
    for c in BEHAVIOR_COLUMNS:
        if c not in df.columns:
            df[c] = pd.NA
    df["date"] = df["date"].astype(str)
    return df[BEHAVIOR_COLUMNS]
