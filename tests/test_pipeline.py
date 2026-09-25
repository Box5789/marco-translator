from pathlib import Path

from marco_translator.knowledge import KnowledgeStore
from marco_translator.models import SemanticFrame, TranslationRequest
from marco_translator.pipeline import Translator
from marco_translator.resolver import DeterministicResolver
from marco_translator.tm import SQLiteTranslationMemory


ROOT = Path(__file__).resolve().parents[1]


def make_translator(*, neural_realizer=None):
    knowledge = KnowledgeStore.from_json(ROOT / "knowledge" / "seed.zh-ko.json")
    return Translator(
        resolver=DeterministicResolver(knowledge),
        tm=SQLiteTranslationMemory(),
        neural_realizer=neural_realizer,
    )


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


def test_neural_realizer_does_not_guess_unresolved_frame():
    class Guess:
        called = False

        def realize(self, frame):
            self.called = True
            return "추측 번역"

    neural = Guess()
    result = make_translator(neural_realizer=neural).translate(
        TranslationRequest("完全未知的新句子", domain="gaming")
    )

    assert result.path == "unresolved"
    assert result.translated_text == ""
    assert result.frame.unresolved
    assert not neural.called


def test_grounded_rule_miss_still_reaches_neural_realizer():
    class Resolver:
        def resolve(self, request):
            return SemanticFrame(
                request.source_language,
                request.target_language,
                request.text,
                domain=request.domain,
                intent="statement",
                slots={"entity": "적"},
                unresolved=[],
                confidence=0.8,
            )

    class Neural:
        def realize(self, frame):
            return "적이 보임"

    translator = Translator(resolver=Resolver(), neural_realizer=Neural())
    result = translator.translate(TranslationRequest("敌人", domain="gaming"))

    assert result.path == "neural-realizer"
    assert result.translated_text == "적이 보임"
