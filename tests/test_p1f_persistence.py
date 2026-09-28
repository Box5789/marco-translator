import sqlite3

import pytest

from marco_translator.tm import SQLiteTranslationMemory
from marco_translator.user_state import SQLiteUserOverlay


def test_python_stores_share_the_versioned_sqlite_contract(tmp_path):
    path = tmp_path / "runtime.sqlite"
    tm = SQLiteTranslationMemory(path)
    overlay = SQLiteUserOverlay(path)
    tm.put("zh", "ko", "gaming", "来源", "기억 번역", origin="user_correction")
    overlay.add_terminology("术语", "용어", domain="gaming", concept="TERM")

    assert tm.lookup("zh", "ko", "gaming", "来源") == "기억 번역"
    assert overlay.resolve_terms("术语", "zh", "ko", "gaming")[0].target == "용어"
    assert tm._db.execute("PRAGMA user_version").fetchone()[0] == 1

    overlay.close()
    tm._db.close()
    reopened_tm = SQLiteTranslationMemory(path)
    reopened_overlay = SQLiteUserOverlay(path)
    assert reopened_tm.lookup("zh", "ko", "gaming", "来源") == "기억 번역"
    assert reopened_overlay.resolve_terms("术语", "zh", "ko", "gaming")[0].target == "용어"
    reopened_overlay.close()
    reopened_tm._db.close()


def test_legacy_v0_store_migrates_without_losing_tm_rows(tmp_path):
    path = tmp_path / "legacy.sqlite"
    db = sqlite3.connect(path)
    db.execute(
        """CREATE TABLE tm (
            source_language TEXT NOT NULL,
            target_language TEXT NOT NULL,
            domain TEXT NOT NULL DEFAULT '',
            source_text TEXT NOT NULL,
            target_text TEXT NOT NULL,
            origin TEXT NOT NULL DEFAULT 'observed',
            PRIMARY KEY(source_language,target_language,domain,source_text)
        )"""
    )
    db.execute("INSERT INTO tm VALUES('zh','ko','gaming','旧词','오래된 번역','user')")
    db.commit()
    db.close()

    tm = SQLiteTranslationMemory(path)
    assert tm.lookup("zh", "ko", "gaming", "旧词") == "오래된 번역"
    assert tm._db.execute("PRAGMA user_version").fetchone()[0] == 1
    tm._db.close()


def test_unknown_or_incompatible_runtime_store_is_rejected_without_downgrade(tmp_path):
    unknown = tmp_path / "unknown.sqlite"
    db = sqlite3.connect(unknown)
    db.execute("PRAGMA user_version=42")
    db.commit()
    db.close()
    with pytest.raises(sqlite3.DatabaseError, match="unsupported runtime schema version"):
        SQLiteTranslationMemory(unknown)
    db = sqlite3.connect(unknown)
    assert db.execute("PRAGMA user_version").fetchone()[0] == 42
    assert db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tm'").fetchone() is None
    db.close()

    incompatible = tmp_path / "incompatible.sqlite"
    db = sqlite3.connect(incompatible)
    db.execute("CREATE TABLE tm(source_language TEXT)")
    db.commit()
    db.close()
    with pytest.raises(sqlite3.DatabaseError, match="incompatible runtime table: tm"):
        SQLiteTranslationMemory(incompatible)
