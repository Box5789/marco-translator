from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from marco_translator.knowledge import KnowledgeStore
from marco_translator.marco_adapter import MarcoResolver
from marco_translator.models import TranslationRequest
from marco_translator.pipeline import Translator


ROOT = Path(__file__).resolve().parents[1]
MODEL = os.environ.get("MARCO_TRANSLATOR_MCO")
MARCO_ROOT = os.environ.get("MCO_MARCO_ROOT")

pytestmark = pytest.mark.skipif(not MODEL, reason="MARCO_TRANSLATOR_MCO is not set")


def make_resolver() -> MarcoResolver:
    knowledge = KnowledgeStore.from_json(ROOT / "knowledge" / "seed.zh-ko.json")
    return MarcoResolver(
        MODEL,
        str(ROOT / "knowledge" / "marco-frame-map.zh-ko.json"),
        knowledge=knowledge,
        marco_root=MARCO_ROOT,
    )


def make_translator() -> Translator:
    return Translator(resolver=make_resolver())


@pytest.mark.parametrize(("source", "expected"), [
    ("西边有狙", "서쪽에 저격수 있음"),
    ("家里有人", "본진에 적 있음"),
    ("教堂需要建材", "교회에 건축 자재가 필요함"),
    ("集合一波去啊", "뭉쳐서 한 번에 밀자"),
    ("一个一个送没辙", "한 명씩 가서 죽어주면 답이 없어"),
])
def test_actual_marco_pack_resolves_seed_regressions(source: str, expected: str):
    result = make_translator().translate(TranslationRequest(source, domain="gaming"))
    if result.translated_text != expected:
        probe = make_resolver()._model.run(source)
        pytest.fail(json.dumps({
            "translation": result.to_dict(),
            "marco": probe.to_dict(include_raw=True),
        }, ensure_ascii=False, indent=2))
    assert result.path == "rule"
    assert result.confidence > 0


def test_actual_marco_pack_declines_unregistered_input():
    result = make_translator().translate(TranslationRequest("完全未知的新句子", domain="gaming"))
    assert result.path == "unresolved", result.to_dict()
    assert result.translated_text == ""


def test_actual_marco_pack_applies_and_releases_user_term(tmp_path):
    """Exercise the actual engine, SQLite overlay, TM and final realization."""
    from marco_translator.knowledge import LayeredKnowledgeStore
    from marco_translator.tm import SQLiteTranslationMemory
    from marco_translator.user_state import SQLiteUserOverlay

    base = KnowledgeStore.from_json(ROOT / "knowledge" / "seed.zh-ko.json")
    overlay = SQLiteUserOverlay(tmp_path / "overlay.db")
    tm = SQLiteTranslationMemory()
    resolver = MarcoResolver(
        MODEL, str(ROOT / "knowledge" / "marco-frame-map.zh-ko.json"),
        knowledge=LayeredKnowledgeStore(base, user_overlay=overlay),
        marco_root=MARCO_ROOT,
    )
    translator = Translator(resolver=resolver, tm=tm, user_overlay=overlay)
    request = TranslationRequest("西边有狙", domain="gaming")
    try:
        overlay.add_terminology("狙", "다른 도메인", domain="finance")
        initial = translator.translate(request)
        assert initial.path == "rule"
        assert initial.translated_text == "서쪽에 저격수 있음"

        overlay.add_terminology("狙", "스나", domain="gaming")
        changed = translator.translate(request)
        assert changed.path == "rule"
        assert changed.frame.slots["entity"] == "스나"
        assert changed.translated_text == "서쪽에 스나 있음"
        assert [(t.target, t.layer) for t in changed.frame.terms if t.source == "狙"] == [("스나", "user")]

        overlay.disable_terminology("狙", domain="gaming")
        restored = translator.translate(request)
        assert restored.path == "rule"
        assert restored.translated_text == initial.translated_text

        translator.correct(request, "서쪽 지정 번역")
        overlay.add_terminology("狙", "스나", domain="gaming")
        exact = translator.translate(request)
        assert exact.path == "tm"
        assert exact.translated_text == "서쪽 지정 번역"
        overlay.disable_terminology("狙", domain="gaming")
        assert translator.translate(request).to_dict() == exact.to_dict()
    finally:
        resolver._model.close()
        overlay.close()
        tm._db.close()
