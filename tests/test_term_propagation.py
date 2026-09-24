"""Term selection must reach the normal output path, not just frame.terms.

The adapter arm injects only the MARCO node-selection result. All translator,
SQLite overlay, session, TM, frame binding and realization code is real.
Actual MARCO execution belongs to test_marco_integration.py.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from marco_translator.knowledge import KnowledgeStore, LayeredKnowledgeStore
from marco_translator.marco_adapter import MarcoResolver
from marco_translator.models import TranslationRequest
from marco_translator.pipeline import Translator
from marco_translator.resolver import DeterministicResolver
from marco_translator.tm import SQLiteTranslationMemory
from marco_translator.user_state import SQLiteUserOverlay, SessionStateStore


ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "knowledge" / "seed.zh-ko.json"
FRAME_MAP = ROOT / "knowledge" / "marco-frame-map.zh-ko.json"
SOURCE = "西边有狙"
REQUEST = TranslationRequest(SOURCE, domain="gaming")


class SelectedNodeModel:
    """Only a deterministic test double for upstream graph selection."""

    def run(self, text):
        node = "ZH_GAMING_WEST_SNIPER" if text == SOURCE else None
        detail = {"winner": node, "margin": 1.0 if node else 0.0}
        return SimpleNamespace(
            status="answered" if node else "unknown", evidence=[],
            trace=SimpleNamespace(stage=lambda name: SimpleNamespace(detail=detail)),
        )


def make_translator(kind, overlay, *, tm=None, sessions=None, frame_map=FRAME_MAP):
    knowledge = LayeredKnowledgeStore(
        KnowledgeStore.from_json(SEED), user_overlay=overlay, sessions=sessions
    )
    if kind == "deterministic":
        resolver = DeterministicResolver(knowledge)
    else:
        resolver = MarcoResolver.from_model(
            SelectedNodeModel(), str(frame_map), knowledge=knowledge
        )
    return Translator(resolver=resolver, tm=tm, user_overlay=overlay, sessions=sessions)


@pytest.fixture(params=["deterministic", "marco-adapter"])
def runtime(request, tmp_path):
    overlay = SQLiteUserOverlay(tmp_path / "overlay.db")
    sessions = SessionStateStore()
    tm = SQLiteTranslationMemory()
    translator = make_translator(request.param, overlay, tm=tm, sessions=sessions)
    yield translator, overlay, sessions, request.param
    overlay.close()
    tm._db.close()


def assert_rule(result, target, layer):
    assert result.path == "rule"  # A TM hit must not count as term propagation.
    assert result.translated_text == f"서쪽에 {target} 있음"
    assert result.frame.slots == {"location": "서쪽", "entity": target}
    selected = [t for t in result.frame.terms if t.source == "狙"]
    assert len(selected) == 1
    assert (selected[0].target, selected[0].layer) == (target, layer)
    assert result.frame.unresolved == []


def test_declared_user_term_reaches_sentence_and_disable_restores_default(runtime):
    translator, overlay, _, _ = runtime
    original_files = (SEED.read_bytes(), FRAME_MAP.read_bytes())
    assert_rule(translator.translate(REQUEST), "저격수", "base")
    overlay.add_terminology("狙", "스나", domain="gaming")
    assert_rule(translator.translate(REQUEST), "스나", "user")
    overlay.disable_terminology("狙", domain="gaming")
    assert_rule(translator.translate(REQUEST), "저격수", "base")
    assert translator.tm.lookup("zh", "ko", "gaming", SOURCE) is None
    assert original_files == (SEED.read_bytes(), FRAME_MAP.read_bytes())


def test_other_domain_or_language_does_not_leak(runtime):
    translator, overlay, _, _ = runtime
    overlay.add_terminology("狙", "다른 도메인", domain="finance")
    overlay.add_terminology("狙", "다른 언어", source_language="en", domain="gaming")
    assert_rule(translator.translate(REQUEST), "저격수", "base")


def test_exact_user_correction_stays_above_term_binding_even_after_disable(runtime):
    translator, overlay, _, _ = runtime
    overlay.add_terminology("狙", "스나", domain="gaming")
    receipt = translator.correct(REQUEST, "서쪽에 있는 상대를 조심해")
    assert receipt.tm_written
    # An exact correction bypasses both resolver arms; do not change precedence.
    def must_not_resolve(_request):
        raise AssertionError("TM hit must not call resolver")
    translator.resolver.resolve = must_not_resolve
    result = translator.translate(REQUEST)
    assert result.path == "tm"
    assert result.translated_text == "서쪽에 있는 상대를 조심해"
    overlay.disable_terminology("狙", domain="gaming")
    assert translator.translate(REQUEST).to_dict() == result.to_dict()


def test_partial_session_binding_reaches_sentence_without_cross_session_leak(runtime):
    translator, overlay, _, _ = runtime
    overlay.add_terminology("狙", "스나", domain="gaming")
    translator.bind_session_entity("s1", "狙", "정찰병", domain="gaming")
    scoped = TranslationRequest(SOURCE, domain="gaming", session_id="s1")
    assert_rule(translator.translate(scoped), "정찰병", "session")
    assert_rule(translator.translate(REQUEST), "스나", "user")
    translator.clear_session("s1")
    assert_rule(translator.translate(scoped), "스나", "user")


@pytest.mark.parametrize("kind", ["deterministic", "marco-adapter"])
def test_reopened_overlay_keeps_term_effect_and_disabled_state(tmp_path, kind):
    path = tmp_path / "overlay.db"
    overlay = SQLiteUserOverlay(path)
    overlay.add_terminology("狙", "스나", domain="gaming")
    overlay.close()
    overlay = SQLiteUserOverlay(path)
    try:
        assert_rule(make_translator(kind, overlay).translate(REQUEST), "스나", "user")
        overlay.disable_terminology("狙", domain="gaming")
    finally:
        overlay.close()
    overlay = SQLiteUserOverlay(path)
    try:
        assert_rule(make_translator(kind, overlay).translate(REQUEST), "저격수", "base")
    finally:
        overlay.close()


def test_pending_correction_is_not_silently_promoted_to_sentence_term(runtime):
    translator, overlay, _, _ = runtime
    # Correcting the isolated term populates a different exact TM key.
    term_request = TranslationRequest("狙", domain="gaming")
    for _ in range(3):
        receipt = translator.correct(term_request, "스나")
    assert receipt.proposal_status == "pending"
    assert_rule(translator.translate(REQUEST), "저격수", "base")
    overlay.approve_proposal(receipt.proposal_id)
    assert_rule(translator.translate(REQUEST), "스나", "user")


def test_unbound_term_does_not_rewrite_unrelated_slot(runtime):
    translator, overlay, _, _ = runtime
    # This first change declares entity <- 狙 only, not arbitrary substitutions.
    overlay.add_terminology("西边", "동쪽", domain="gaming")
    assert_rule(translator.translate(REQUEST), "저격수", "base")


def test_frame_defaults_and_previous_results_are_not_mutated(runtime):
    translator, overlay, _, kind = runtime
    if kind == "deterministic":
        before = deepcopy(translator.resolver.patterns[0].slots)
    else:
        before = deepcopy(translator.resolver._frames)
    old = translator.translate(REQUEST)
    overlay.add_terminology("狙", "스나", domain="gaming")
    assert_rule(translator.translate(REQUEST), "스나", "user")
    assert_rule(old, "저격수", "base")
    if kind == "deterministic":
        assert translator.resolver.patterns[0].slots == before
    else:
        assert translator.resolver._frames == before


def test_legacy_frame_map_without_binding_keeps_authored_output(tmp_path):
    import json
    document = json.loads(FRAME_MAP.read_text())
    for spec in document["frames"].values():
        spec.pop("slot_terms", None)
    legacy = tmp_path / "legacy-map.json"
    legacy.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    overlay = SQLiteUserOverlay()
    try:
        overlay.add_terminology("狙", "스나", domain="gaming")
        result = make_translator("marco-adapter", overlay, frame_map=legacy).translate(REQUEST)
        assert result.path == "rule"
        assert result.translated_text == "서쪽에 저격수 있음"
        assert result.frame.terms[0].target == "스나"
    finally:
        overlay.close()


def test_binding_is_not_target_string_replacement():
    from marco_translator.knowledge import bind_term_slots
    from marco_translator.models import TermDecision
    slots = {"entity": "저격수", "classification": "저격수"}
    term = TermDecision("狙", "SNIPER", "스나", 1.0, "user")
    assert bind_term_slots(slots, {"entity": "狙"}, [term]) == {
        "entity": "스나", "classification": "저격수",
    }
    assert slots == {"entity": "저격수", "classification": "저격수"}


def test_missing_or_base_term_preserves_authored_inflection():
    from marco_translator.knowledge import bind_term_slots
    from marco_translator.models import TermDecision
    slots = {"feed": "죽어주면"}
    base = TermDecision("送", "FEED_ENEMY", "킬 헌납", 0.94, "base")
    assert bind_term_slots(slots, {"feed": "送"}, []) == slots
    assert bind_term_slots(slots, {"feed": "送"}, [base]) == slots


@pytest.mark.parametrize("binding", [None, [], {"absent": "狙"}, {"entity": ""}, {"entity": 1}])
def test_malformed_binding_fails_at_both_resolver_boundaries(tmp_path, binding):
    import json
    from marco_translator.resolver import Pattern
    with pytest.raises(ValueError, match="slot_terms"):
        DeterministicResolver(
            KnowledgeStore(),
            patterns=[Pattern(SOURCE, "{entity}", {"entity": "저격수"}, slot_terms=binding)],
        )
    document = json.loads(FRAME_MAP.read_text())
    document["frames"]["ZH_GAMING_WEST_SNIPER"]["slot_terms"] = binding
    bad_map = tmp_path / "invalid-map.json"
    bad_map.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="slot_terms"):
        MarcoResolver.from_model(SelectedNodeModel(), str(bad_map))


def test_binder_refuses_ambiguous_or_empty_personal_term():
    from marco_translator.knowledge import bind_term_slots
    from marco_translator.models import TermDecision
    first = TermDecision("狙", "SNIPER", "스나", 1.0, "user")
    other = TermDecision("狙", "SNIPER", "정찰병", 1.0, "session")
    with pytest.raises(ValueError, match="single selected meaning"):
        bind_term_slots({"entity": "저격수"}, {"entity": "狙"}, [first, other])
    blank = TermDecision("狙", "SNIPER", " ", 1.0, "user")
    with pytest.raises(ValueError, match="non-empty target"):
        bind_term_slots({"entity": "저격수"}, {"entity": "狙"}, [blank])
