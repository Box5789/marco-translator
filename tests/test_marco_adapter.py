from dataclasses import dataclass
from pathlib import Path

import pytest

from marco_translator.knowledge import KnowledgeStore
from marco_translator.marco_adapter import MarcoResolver
from marco_translator.models import TranslationRequest
from marco_translator.pipeline import Translator
from marco_translator.user_state import SQLiteUserOverlay


ROOT = Path(__file__).resolve().parents[1]
FRAME_MAP = ROOT / "knowledge" / "marco-frame-map.zh-ko.json"
KNOWLEDGE = KnowledgeStore.from_json(ROOT / "knowledge" / "seed.zh-ko.json")


@dataclass
class FakeStep:
    detail: dict


class FakeTrace:
    def __init__(self, winner: str | None, margin: float | None = None):
        self.winner = winner
        self.margin = margin

    def stage(self, name: str):
        if name != "judge" or self.winner is None:
            raise KeyError(name)
        return FakeStep({"winner": self.winner, "margin": self.margin})


@dataclass
class FakeEvidence:
    kind: str
    text: str
    score: float | None = None


class FakeResult:
    def __init__(self, status: str, winner: str | None, *, margin: float | None = None, evidence=()):
        self.status = status
        self.trace = FakeTrace(winner, margin)
        self.evidence = list(evidence)
        self.answer = ""


class FakeModel:
    def __init__(self, result: FakeResult):
        self.result = result
        self.inputs = []

    def run(self, text: str):
        self.inputs.append(text)
        return self.result


def resolver_for(result: FakeResult) -> tuple[MarcoResolver, FakeModel]:
    model = FakeModel(result)
    return MarcoResolver.from_model(model, str(FRAME_MAP), knowledge=KNOWLEDGE), model


def test_marco_needs_input_can_still_select_grounded_semantics():
    resolver, model = resolver_for(FakeResult("needs_input", "ZH_GAMING_WEST_SNIPER"))
    frame = resolver.resolve(TranslationRequest("西边有狙", domain="gaming"))
    assert model.inputs == ["西边有狙"]
    assert frame.template == "{location}에 {entity} 있음"
    assert frame.slots == {"location": "서쪽", "entity": "저격수"}
    assert {t.concept for t in frame.terms} == {"SNIPER"}


def test_translator_realizes_marco_selected_frame_without_llm():
    resolver, _ = resolver_for(FakeResult("needs_input", "ZH_GAMING_BASE_ENEMY"))
    result = Translator(resolver=resolver).translate(TranslationRequest("家里有人", domain="gaming"))
    assert result.path == "rule"
    assert result.translated_text == "본진에 적 있음"


def test_unknown_status_with_low_margin_never_promotes_trace_winner():
    resolver, _ = resolver_for(FakeResult("unknown", "ZH_GAMING_WEST_SNIPER", margin=0.40))
    frame = resolver.resolve(TranslationRequest("完全未知的新句子", domain="gaming"))
    assert frame.unresolved == ["完全未知的新句子"]
    assert frame.template is None
    assert frame.confidence == 0.0


def test_unknown_status_can_rescue_a_strong_mapped_semantic_match():
    resolver, _ = resolver_for(FakeResult("unknown", "ZH_GAMING_WEST_SNIPER", margin=0.993))
    frame = resolver.resolve(TranslationRequest("西边有狙", domain="gaming"))
    assert frame.template == "{location}에 {entity} 있음"
    assert frame.confidence == 0.99


def test_rejected_status_is_never_rescued_even_with_high_margin():
    resolver, _ = resolver_for(FakeResult("rejected", "ZH_GAMING_WEST_SNIPER", margin=1.0))
    frame = resolver.resolve(TranslationRequest("西边有狙", domain="gaming"))
    assert frame.unresolved == ["西边有狙"]


def test_unmapped_or_wrong_domain_is_unresolved():
    resolver, _ = resolver_for(FakeResult("needs_input", "ZH_GAMING_WEST_SNIPER"))
    frame = resolver.resolve(TranslationRequest("西边有狙", domain="finance"))
    assert frame.unresolved == ["西边有狙"]


def test_graph_node_evidence_is_fallback_when_trace_has_no_mapped_winner():
    resolver, _ = resolver_for(FakeResult(
        "needs_input",
        "SOME_INTERNAL_NODE",
        evidence=[FakeEvidence("graph_node", "ZH_GAMING_CHURCH_MATERIALS", 0.88)],
    ))
    frame = resolver.resolve(TranslationRequest("教堂需要建材", domain="gaming"))
    assert frame.template == "{location}에 {object}가 필요함"
    assert frame.confidence == 0.88


def test_reversible_user_route_bias_can_rescue_borderline_mapped_unknown(tmp_path):
    overlay = SQLiteUserOverlay(tmp_path / "overlay.db")
    event = overlay.adjust_routing_weight("gaming", "ZH_GAMING_WEST_SNIPER", 0.05)
    model = FakeModel(FakeResult("unknown", "ZH_GAMING_WEST_SNIPER", margin=0.87))
    resolver = MarcoResolver.from_model(
        model, str(FRAME_MAP), knowledge=KNOWLEDGE, routing_weights=overlay
    )
    frame = resolver.resolve(TranslationRequest("西边有狙", domain="gaming"))
    assert frame.template == "{location}에 {entity} 있음"
    assert frame.confidence == pytest.approx(0.92)

    overlay.rollback_routing_weight(event)
    frame = resolver.resolve(TranslationRequest("西边有狙", domain="gaming"))
    assert frame.unresolved == ["西边有狙"]
