from __future__ import annotations

import sqlite3
from pathlib import Path


class SQLiteTranslationMemory:
    """Exact-match TM for the reference runtime.

    Fuzzy matching is intentionally not in P1: an incorrect fuzzy hit is harder
    to detect than a miss, and semantic fallback is safer.
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._db = sqlite3.connect(str(path))
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS tm (
                source_language TEXT NOT NULL,
                target_language TEXT NOT NULL,
                domain TEXT NOT NULL DEFAULT '',
                source_text TEXT NOT NULL,
                target_text TEXT NOT NULL,
                origin TEXT NOT NULL DEFAULT 'observed',
                PRIMARY KEY(source_language, target_language, domain, source_text)
            )
            """
        )
        self._db.commit()

    def lookup(self, source_language: str, target_language: str, domain: str | None, text: str) -> str | None:
        row = self._db.execute(
            "SELECT target_text FROM tm WHERE source_language=? AND target_language=? AND domain=? AND source_text=?",
            (source_language, target_language, domain or "", text),
        ).fetchone()
        return None if row is None else str(row[0])

    def put(self, source_language: str, target_language: str, domain: str | None, source_text: str,
            target_text: str, origin: str = "user") -> None:
        self._db.execute(
            """
            INSERT INTO tm(source_language,target_language,domain,source_text,target_text,origin)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(source_language,target_language,domain,source_text)
            DO UPDATE SET target_text=excluded.target_text, origin=excluded.origin
            """,
            (source_language, target_language, domain or "", source_text, target_text, origin),
        )
        self._db.commit()
