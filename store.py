"""SQLite store for preference pairs."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any, Iterable, Optional

STATUSES = ("pending", "kept", "shared", "discarded")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pairs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at REAL NOT NULL,
    session_id TEXT, turn_id TEXT, platform TEXT, model TEXT,
    kind TEXT NOT NULL, confidence TEXT, reason TEXT,
    prompt TEXT NOT NULL, rejected TEXT NOT NULL, accepted TEXT NOT NULL, feedback TEXT,
    category TEXT,
    scrub_counts TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    updated_at REAL,
    uploaded_at REAL, share_url TEXT
);
CREATE INDEX IF NOT EXISTS pairs_status ON pairs(status);
CREATE INDEX IF NOT EXISTS pairs_session ON pairs(session_id, status);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""

_FIELDS = ("session_id", "turn_id", "platform", "model", "kind", "confidence", "reason",
           "prompt", "rejected", "accepted", "feedback", "category")


class Store:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    @classmethod
    def open_default(cls) -> "Store":
        from plugins.plugin_storage import plugin_db

        return cls(plugin_db("ichor", "ichor.db"))

    # writes

    def add(self, pair: dict[str, Any]) -> int:
        values = [pair.get(f) for f in _FIELDS]
        scrub = json.dumps(pair.get("scrub_counts") or {})
        now = time.time()
        with self._lock, self._conn:
            cur = self._conn.execute(
                f"INSERT INTO pairs (created_at, {', '.join(_FIELDS)}, scrub_counts, status, updated_at) "
                f"VALUES (?, {', '.join('?' for _ in _FIELDS)}, ?, 'pending', ?)",
                [now, *values, scrub, now],
            )
            return int(cur.lastrowid or 0)

    def set_status(self, pair_id: int, status: str) -> bool:
        """Idempotent. Returns False if the id does not exist or status is invalid."""
        if status not in STATUSES:
            return False
        with self._lock, self._conn:
            if status == "discarded":  # a dropped pair keeps no text
                cur = self._conn.execute(
                    "UPDATE pairs SET status = ?, updated_at = ?, prompt = '', rejected = '', accepted = '', "
                    "feedback = '' WHERE id = ?", (status, time.time(), pair_id))
            else:
                cur = self._conn.execute("UPDATE pairs SET status = ?, updated_at = ? WHERE id = ? "
                                         "AND status != 'discarded'", (status, time.time(), pair_id))
            return cur.rowcount == 1

    def set_category(self, pair_id: int, category: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("UPDATE pairs SET category = ? WHERE id = ?", (category, pair_id))

    def backfill_categories(self, labeler) -> int:
        rows = self._all("SELECT * FROM pairs WHERE category IS NULL")
        n = 0
        for row in rows:
            cat = labeler(dict(row))
            if cat:
                self.set_category(row["id"], cat)
                n += 1
        return n

    def mark_uploaded(self, ids: Iterable[int], url: str) -> None:
        now = time.time()
        with self._lock, self._conn:
            self._conn.executemany("UPDATE pairs SET uploaded_at = ?, share_url = ? WHERE id = ?",
                                   [(now, url, i) for i in ids])

    def forget_all(self) -> int:
        with self._lock, self._conn:
            return self._conn.execute("DELETE FROM pairs").rowcount

    # reads (the connection is shared across threads, so reads take the lock too)

    def _all(self, sql: str, args: tuple = ()) -> list:
        with self._lock:
            return self._conn.execute(sql, args).fetchall()

    def _one(self, sql: str, args: tuple = ()):
        with self._lock:
            return self._conn.execute(sql, args).fetchone()

    def get(self, pair_id: int) -> Optional[dict[str, Any]]:
        return _row(self._one("SELECT * FROM pairs WHERE id = ?", (pair_id,)))

    def latest_pending(self, session_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        if session_id:
            row = self._one("SELECT * FROM pairs WHERE status='pending' AND session_id=? ORDER BY id DESC LIMIT 1",
                            (session_id,))
        else:
            row = self._one("SELECT * FROM pairs WHERE status='pending' ORDER BY id DESC LIMIT 1")
        return _row(row)

    def oldest_pending(self) -> Optional[dict[str, Any]]:
        return _row(self._one("SELECT * FROM pairs WHERE status='pending' ORDER BY id ASC LIMIT 1"))

    def counts(self) -> dict[str, int]:
        out = {s: 0 for s in STATUSES}
        for row in self._all("SELECT status, COUNT(*) AS n FROM pairs GROUP BY status"):
            out[row["status"]] = row["n"]
        return out

    def top_categories(self, limit: int = 3) -> list[tuple[str, int]]:
        rows = self._all(
            "SELECT COALESCE(category, kind) AS c, COUNT(*) AS n FROM pairs "
            "WHERE status IN ('kept','shared','pending') GROUP BY c ORDER BY n DESC, c ASC LIMIT ?", (limit,))
        return [(r["c"], r["n"]) for r in rows]

    def exportable(self) -> list[dict[str, Any]]:
        rows = self._all("SELECT * FROM pairs WHERE status IN ('kept','shared') ORDER BY id")
        return [d for r in rows if (d := _row(r)) is not None]

    def to_upload(self) -> list[dict[str, Any]]:
        rows = self._all("SELECT * FROM pairs WHERE status='shared' AND uploaded_at IS NULL ORDER BY id")
        return [d for r in rows if (d := _row(r)) is not None]

    # settings

    def setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self._one("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("INSERT INTO settings(key, value) VALUES(?, ?) "
                               "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


def _row(row: Optional[sqlite3.Row]) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    d = dict(row)
    try:
        d["scrub_counts"] = json.loads(d.get("scrub_counts") or "{}")
    except ValueError:
        d["scrub_counts"] = {}
    return d
