from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path("finance.db")


@contextmanager
def connect(db_path: Path = DB_PATH):
    """Context manager returning a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    """Create tables for categories and transactions if they do not exist."""
    with connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                category_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                type TEXT CHECK(type IN ('expense','income')) NOT NULL,
                FOREIGN KEY(category_id) REFERENCES categories(id)
            )
            """
        )


def create_category(name: str, db_path: Path = DB_PATH) -> int:
    """Insert a new category and return its id."""
    with connect(db_path) as conn:
        cur = conn.execute("INSERT INTO categories(name) VALUES (?)", (name,))
        return cur.lastrowid


def update_category(category_id: int, name: str, db_path: Path = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.execute("UPDATE categories SET name=? WHERE id=?", (name, category_id))


def delete_category(category_id: int, db_path: Path = DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.execute("DELETE FROM categories WHERE id=?", (category_id,))


def list_categories(db_path: Path = DB_PATH) -> list[sqlite3.Row]:
    with connect(db_path) as conn:
        return conn.execute("SELECT id, name FROM categories ORDER BY id").fetchall()


def add_transaction(
    amount: float,
    category_id: int,
    type: str,
    timestamp: datetime | None = None,
    db_path: Path = DB_PATH,
) -> int:
    """Add a transaction and purge records older than six months."""
    if type not in {"expense", "income"}:
        raise ValueError("type must be 'expense' or 'income'")
    ts = timestamp or datetime.utcnow()
    with connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO transactions(amount, category_id, timestamp, type) VALUES (?, ?, ?, ?)",
            (amount, category_id, ts.isoformat(), type),
        )
        cutoff = datetime.utcnow() - timedelta(days=180)
        conn.execute("DELETE FROM transactions WHERE timestamp < ?", (cutoff.isoformat(),))
        return cur.lastrowid


def get_transactions_for_month(year: int, month: int, db_path: Path = DB_PATH) -> list[sqlite3.Row]:
    """Return transactions with category names for the specified month."""
    start = datetime(year, month, 1)
    end = datetime(year + (month // 12), (month % 12) + 1, 1)
    with connect(db_path) as conn:
        return conn.execute(
            (
                "SELECT t.id, t.amount, t.timestamp, t.type, c.name as category "
                "FROM transactions t JOIN categories c ON t.category_id = c.id "
                "WHERE t.timestamp >= ? AND t.timestamp < ? ORDER BY t.timestamp"
            ),
            (start.isoformat(), end.isoformat()),
        ).fetchall()


def get_balance(db_path: Path = DB_PATH) -> float:
    """Return current balance: incomes minus expenses."""
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE -amount END), 0) as balance FROM transactions"
        ).fetchone()
        return float(row["balance"])
