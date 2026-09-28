"""Shared SQLite file contract for the portable translation runtime."""

from __future__ import annotations

import sqlite3


_TABLES = {
    "tm": (
        ("source_language", "TEXT", 1, 1),
        ("target_language", "TEXT", 1, 2),
        ("domain", "TEXT", 1, 3),
        ("source_text", "TEXT", 1, 4),
        ("target_text", "TEXT", 1, 0),
        ("origin", "TEXT", 1, 0),
    ),
    "terminology": (
        ("source_language", "TEXT", 1, 1),
        ("target_language", "TEXT", 1, 2),
        ("domain", "TEXT", 1, 3),
        ("source", "TEXT", 1, 4),
        ("concept", "TEXT", 1, 0),
        ("target", "TEXT", 1, 0),
        ("confidence", "REAL", 1, 0),
        ("origin", "TEXT", 1, 0),
        ("active", "INTEGER", 1, 0),
        ("created_at", "TEXT", 1, 0),
        ("updated_at", "TEXT", 1, 0),
    ),
    "corrections": (
        ("source_language", "TEXT", 1, 1),
        ("target_language", "TEXT", 1, 2),
        ("domain", "TEXT", 1, 3),
        ("source_text", "TEXT", 1, 4),
        ("target_text", "TEXT", 1, 5),
        ("count", "INTEGER", 1, 0),
        ("last_generated", "TEXT", 0, 0),
        ("first_seen", "TEXT", 1, 0),
        ("last_seen", "TEXT", 1, 0),
    ),
    "overlay_proposals": (
        ("id", "TEXT", 0, 1),
        ("type", "TEXT", 1, 0),
        ("source_language", "TEXT", 1, 0),
        ("target_language", "TEXT", 1, 0),
        ("domain", "TEXT", 1, 0),
        ("source", "TEXT", 1, 0),
        ("target", "TEXT", 1, 0),
        ("evidence_count", "INTEGER", 1, 0),
        ("status", "TEXT", 1, 0),
        ("created_at", "TEXT", 1, 0),
        ("updated_at", "TEXT", 1, 0),
    ),
    "routing_weights": (
        ("domain", "TEXT", 1, 1),
        ("candidate", "TEXT", 1, 2),
        ("weight", "REAL", 1, 0),
        ("updated_at", "TEXT", 1, 0),
    ),
    "routing_weight_events": (
        ("id", "TEXT", 0, 1),
        ("domain", "TEXT", 1, 0),
        ("candidate", "TEXT", 1, 0),
        ("before_weight", "REAL", 1, 0),
        ("after_weight", "REAL", 1, 0),
        ("delta", "REAL", 1, 0),
        ("reason", "TEXT", 1, 0),
        ("reverted", "INTEGER", 1, 0),
        ("created_at", "TEXT", 1, 0),
        ("reverted_at", "TEXT", 0, 0),
    ),
}
_PROPOSAL_KEY = ("type", "source_language", "target_language", "domain", "source", "target")


def _validate_existing_tables(db: sqlite3.Connection) -> None:
    for table, expected in _TABLES.items():
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            continue
        actual = tuple(
            (row["name"], row["type"].upper(), row["notnull"], row["pk"])
            if isinstance(row, sqlite3.Row)
            else (row[1], row[2].upper(), row[3], row[5])
            for row in db.execute(f"PRAGMA table_info({table})")
        )
        if actual != expected:
            raise sqlite3.DatabaseError(f"incompatible runtime table: {table}")
        if table == "overlay_proposals":
            unique_keys = {
                tuple(row[0] for row in db.execute(
                    "SELECT name FROM pragma_index_info(?) ORDER BY seqno", (name,)
                ))
                for _, name, unique, *_ in db.execute("PRAGMA index_list(overlay_proposals)")
                if unique
            }
            if _PROPOSAL_KEY not in unique_keys:
                raise sqlite3.DatabaseError("incompatible runtime index: overlay_proposals")


def initialize_runtime_schema(db: sqlite3.Connection, schema_sql: str) -> None:
    """Create/upgrade compatible v0 files transactionally; reject other contracts."""
    try:
        db.executescript(f"BEGIN IMMEDIATE;\n{schema_sql}")
        version = int(db.execute("PRAGMA user_version").fetchone()[0])
        if version not in (0, 1):
            raise sqlite3.DatabaseError(f"unsupported runtime schema version: {version}")
        _validate_existing_tables(db)
        db.execute("PRAGMA user_version=1")
        db.commit()
    except Exception:
        db.rollback()
        raise
