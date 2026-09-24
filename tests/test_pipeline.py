from pathlib import Path

from marco_translator.knowledge import KnowledgeStore
from marco_translator.models import TranslationRequest
from marco_translator.pipeline import Translator
from marco_translator.resolver import DeterministicResolver
from marco_translator.tm import SQLiteTranslationMemory


ROOT = Path(__file__).resolve().parents[1]


def make_translator():
    knowledge = KnowledgeStore.from_json(ROOT / "knowledge" / "seed.zh-ko.json")
    return Translator(resolver=DeterministicResolver(knowledge), tm=SQLiteTranslationMemory())


def test_known_game_call_is_deterministic():
    result = make_translator().translate(TranslationRequest("西边有狙", domain="gaming"))
    assert result.translated_text == "서쪽에 저격수 있음"
    assert result.path == "rule"


def test_domain_specific_home_becomes_base():
    result = make_translator().translate(TranslationRequest("家里有人", domain="gaming"))
    assert result.translated_text == "본진에 적 있음"
    concepts = {t.concept for t in result.frame.terms}
    assert "OWN_BASE" in concepts
    assert "HOME" not in concepts


def test_exact_tm_has_priority():
    translator = make_translator()
    translator.tm.put("zh", "ko", "gaming", "集合一波去啊", "다 같이 모여서 한 번에 밀자")
    result = translator.translate(TranslationRequest("集合一波去啊", domain="gaming"))
    assert result.path == "tm"
    assert result.translated_text == "다 같이 모여서 한 번에 밀자"


def test_unknown_does_not_guess():
    result = make_translator().translate(TranslationRequest("完全未知的新句子", domain="gaming"))
    assert result.path == "unresolved"
    assert result.translated_text == ""
