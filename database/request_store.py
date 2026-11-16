"""SQLite persistence for Advanced Proxy System request history."""
from pathlib import Path
import sqlite3
from datetime import datetime

DB_PATH = Path(__file__).resolve().with_name("proxy_history.db")


def _connect():
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS request_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                client_ip TEXT NOT NULL,
                url TEXT NOT NULL,
                status TEXT NOT NULL,
                latency_ms REAL NOT NULL,
                success INTEGER NOT NULL,
                bytes_downloaded INTEGER NOT NULL DEFAULT 0
            )
        """)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_request_history_created_at "
            "ON request_history(created_at DESC)"
        )


def record_request(client_ip, url, status, latency_ms, success, bytes_downloaded=0):
    initialize_database()
    with _connect() as connection:
        connection.execute("""
            INSERT INTO request_history
            (created_at, client_ip, url, status, latency_ms, success, bytes_downloaded)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(timespec="seconds"),
            str(client_ip), str(url), str(status), float(latency_ms),
            1 if success else 0, int(bytes_downloaded)
        ))


def get_recent_requests(limit=100):
    initialize_database()
    with _connect() as connection:
        rows = connection.execute("""
            SELECT id, created_at, client_ip, url, status, latency_ms,
                   success, bytes_downloaded
            FROM request_history
            ORDER BY id DESC
            LIMIT ?
        """, (int(limit),)).fetchall()
        return [dict(row) for row in rows]
