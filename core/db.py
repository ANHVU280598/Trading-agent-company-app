"""SQLite access for app.db. Schema created on first use (H step 3)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from core.config import DB_PATH

SIGNAL_COLUMNS = [
    "date",
    "ticker",
    "signal",
    "buy_p",
    "hold_p",
    "sell_p",
    "price",
    "rsi14",
    "drawdown63",
    "sentiment",
    "headline",
]
TRADE_COLUMNS = [
    "id",
    "date",
    "ticker",
    "action",
    "shares",
    "price",
    "confidence",
    "status",
    "realized_pnl",
]
PORTFOLIO_COLUMNS = ["date", "value", "benchmark_value", "cash", "drawdown"]
POSITION_COLUMNS = ["ticker", "shares", "avg_cost"]
MODEL_RUN_COLUMNS = ["date", "train_rows", "accuracy", "baseline", "verdict", "notes"]
SETTINGS_COLUMNS = ["key", "value"]
SIGNAL_GRADE_COLUMNS = [
    "date",
    "ticker",
    "signal",
    "confidence",
    "price_then",
    "ret_1d",
    "ret_5d",
    "ret_20d",
    "spy_ret_1d",
    "spy_ret_5d",
    "spy_ret_20d",
]


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Open app.db with a short busy timeout. Creates parent dir if needed."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """CREATE TABLE IF NOT EXISTS for all v1 tables (incl. signal_grades addendum)."""
    schema = """
    CREATE TABLE IF NOT EXISTS signals (
        date TEXT NOT NULL,
        ticker TEXT NOT NULL,
        signal TEXT NOT NULL,
        buy_p REAL,
        hold_p REAL,
        sell_p REAL,
        price REAL,
        rsi14 REAL,
        drawdown63 REAL,
        sentiment REAL,
        headline TEXT,
        PRIMARY KEY (date, ticker)
    );
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY,
        date TEXT NOT NULL,
        ticker TEXT NOT NULL,
        action TEXT NOT NULL,
        shares REAL,
        price REAL,
        confidence REAL,
        status TEXT,
        realized_pnl REAL
    );
    CREATE TABLE IF NOT EXISTS portfolio_history (
        date TEXT PRIMARY KEY,
        value REAL,
        benchmark_value REAL,
        cash REAL,
        drawdown REAL
    );
    CREATE TABLE IF NOT EXISTS positions (
        ticker TEXT PRIMARY KEY,
        shares REAL,
        avg_cost REAL
    );
    CREATE TABLE IF NOT EXISTS model_runs (
        date TEXT,
        train_rows INTEGER,
        accuracy REAL,
        baseline REAL,
        verdict TEXT,
        notes TEXT
    );
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    CREATE TABLE IF NOT EXISTS signal_grades (
        date TEXT NOT NULL,
        ticker TEXT NOT NULL,
        signal TEXT,
        confidence REAL,
        price_then REAL,
        ret_1d REAL,
        ret_5d REAL,
        ret_20d REAL,
        spy_ret_1d REAL,
        spy_ret_5d REAL,
        spy_ret_20d REAL,
        PRIMARY KEY (date, ticker)
    );
    """
    with connect(db_path) as conn:
        conn.executescript(schema)
        conn.commit()


def _empty(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def read_signals(db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    try:
        with connect(db_path) as conn:
            df = pd.read_sql_query("SELECT * FROM signals ORDER BY date, ticker", conn)
    except sqlite3.OperationalError:
        return _empty(SIGNAL_COLUMNS)
    if df.empty:
        return _empty(SIGNAL_COLUMNS)
    return df


def read_trades(db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    try:
        with connect(db_path) as conn:
            df = pd.read_sql_query("SELECT * FROM trades ORDER BY date DESC, id DESC", conn)
    except sqlite3.OperationalError:
        return _empty(TRADE_COLUMNS)
    if df.empty:
        return _empty(TRADE_COLUMNS)
    return df


def read_portfolio_history(db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    try:
        with connect(db_path) as conn:
            df = pd.read_sql_query(
                "SELECT * FROM portfolio_history ORDER BY date", conn
            )
    except sqlite3.OperationalError:
        return _empty(PORTFOLIO_COLUMNS)
    if df.empty:
        return _empty(PORTFOLIO_COLUMNS)
    return df


def read_positions(db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    try:
        with connect(db_path) as conn:
            df = pd.read_sql_query("SELECT * FROM positions ORDER BY ticker", conn)
    except sqlite3.OperationalError:
        return _empty(POSITION_COLUMNS)
    if df.empty:
        return _empty(POSITION_COLUMNS)
    return df


def read_model_runs(db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    try:
        with connect(db_path) as conn:
            df = pd.read_sql_query(
                "SELECT * FROM model_runs ORDER BY date DESC", conn
            )
    except sqlite3.OperationalError:
        return _empty(MODEL_RUN_COLUMNS)
    if df.empty:
        return _empty(MODEL_RUN_COLUMNS)
    return df


def read_settings(db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    try:
        with connect(db_path) as conn:
            df = pd.read_sql_query("SELECT * FROM settings", conn)
    except sqlite3.OperationalError:
        return _empty(SETTINGS_COLUMNS)
    if df.empty:
        return _empty(SETTINGS_COLUMNS)
    return df


def read_signal_grades(db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    try:
        with connect(db_path) as conn:
            df = pd.read_sql_query(
                "SELECT * FROM signal_grades ORDER BY date DESC, ticker", conn
            )
    except sqlite3.OperationalError:
        return _empty(SIGNAL_GRADE_COLUMNS)
    if df.empty:
        return _empty(SIGNAL_GRADE_COLUMNS)
    return df


def upsert_setting(key: str, value: str, db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()


def get_settings_map(db_path: Path = DB_PATH) -> dict[str, str]:
    df = read_settings(db_path)
    if df.empty:
        return {}
    return {str(r["key"]): str(r["value"]) for _, r in df.iterrows()}


def replace_table(table: str, frame: pd.DataFrame, db_path: Path = DB_PATH) -> None:
    """Replace all rows in a table with the given frame (same columns)."""
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(f"DELETE FROM {table}")
        if not frame.empty:
            frame.to_sql(table, conn, if_exists="append", index=False)
        conn.commit()
