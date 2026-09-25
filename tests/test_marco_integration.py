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
    class Guess:
        called = False

        def realize(self, frame):
            self.called = True
            return "추측 번역"

    neural = Guess()
    result = Translator(resolver=make_resolver(), neural_realizer=neural).translate(
        TranslationRequest("完全未知的新句子", domain="gaming")
    )
    assert result.path == "unresolved", result.to_dict()
    assert result.translated_text == ""
    assert not neural.called
