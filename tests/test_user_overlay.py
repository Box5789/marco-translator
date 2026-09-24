from pathlib import Path

import pytest

from marco_translator.knowledge import KnowledgeStore, LayeredKnowledgeStore
from marco_translator.models import TranslationRequest
from marco_translator.pipeline import Translator
from marco_translator.resolver import DeterministicResolver
from marco_translator.tm import SQLiteTranslationMemory
from marco_translator.user_state import SessionStateStore, SQLiteUserOverlay


ROOT = Path(__file__).resolve().parents[1]


def make_adaptive(tmp_path, *, threshold=3):
    base = KnowledgeStore.from_json(ROOT / "knowledge" / "seed.zh-ko.json")
    overlay = SQLiteUserOverlay(tmp_path / "user-overlay.db", correction_threshold=threshold)
    sessions = SessionStateStore()
    knowledge = LayeredKnowledgeStore(base, user_overlay=overlay, sessions=sessions)
    translator = Translator(
        resolver=DeterministicResolver(knowledge),
        tm=SQLiteTranslationMemory(),
        user_overlay=overlay,
        sessions=sessions,
    )
    return translator, overlay, sessions


def test_persistent_user_terminology_overrides_base_layer(tmp_path):
    translator, overlay, _ = make_adaptive(tmp_path)
    overlay.add_terminology("挂", "치터", domain="gaming", concept="CHEAT_SOFTWARE")
    result = translator.translate(TranslationRequest("挂", domain="gaming"))
    assert result.translated_text == "치터"
    assert result.path == "rule"
    assert result.frame.terms[0].layer == "user"

    overlay.close()
    reopened = SQLiteUserOverlay(tmp_path / "user-overlay.db")
    terms = reopened.resolve_terms("挂", "zh", "ko", "gaming")
    assert [(t.target, t.layer) for t in terms] == [("치터", "user")]


def test_explicit_correction_is_immediately_written_to_tm(tmp_path):
    translator, _, _ = make_adaptive(tmp_path)
    request = TranslationRequest("西边有狙", domain="gaming")
    original = translator.translate(request)
    receipt = translator.correct(request, "서쪽 스나 있음", result=original)
    assert receipt.tm_written
    assert receipt.proposal_id is None

    repeated = translator.translate(request)
    assert repeated.path == "tm"
    assert repeated.translated_text == "서쪽 스나 있음"


def test_repeated_correction_creates_pending_overlay_proposal_but_does_not_auto_apply(tmp_path):
    translator, overlay, _ = make_adaptive(tmp_path, threshold=3)
    request = TranslationRequest("全新短语", domain="gaming")
    for _ in range(2):
        receipt = translator.correct(request, "새 표현")
        assert receipt.proposal_id is None
    receipt = translator.correct(request, "새 표현")
    assert receipt.proposal_id is not None
    assert receipt.proposal_status == "pending"
    assert overlay.resolve_terms("全新短语", "zh", "ko", "gaming") == []

    pending = overlay.pending_proposals()
    assert [p.id for p in pending] == [receipt.proposal_id]
    accepted = overlay.approve_proposal(receipt.proposal_id)
    assert accepted.status == "accepted"
    terms = overlay.resolve_terms("全新短语", "zh", "ko", "gaming")
    assert terms[0].target == "새 표현"
    assert terms[0].layer == "user"


def test_session_binding_is_ephemeral_and_has_priority_over_tm(tmp_path):
    translator, _, sessions = make_adaptive(tmp_path)
    translator.tm.put("zh", "ko", "gaming", "Luka", "루카-TM")
    translator.bind_session_entity("s1", "Luka", "루카-세션", domain="gaming")

    hit = translator.translate(TranslationRequest("Luka", domain="gaming", session_id="s1"))
    assert hit.path == "session"
    assert hit.translated_text == "루카-세션"

    outside = translator.translate(TranslationRequest("Luka", domain="gaming", session_id="s2"))
    assert outside.path == "tm"
    assert outside.translated_text == "루카-TM"

    sessions.clear_session("s1")
    after_clear = translator.translate(TranslationRequest("Luka", domain="gaming", session_id="s1"))
    assert after_clear.path == "tm"


def test_routing_weight_change_is_bounded_and_reversible(tmp_path):
    _, overlay, _ = make_adaptive(tmp_path)
    event = overlay.adjust_routing_weight("gaming", "ZH_GAMING_WEST_SNIPER", 0.07)
    assert overlay.routing_weight("gaming", "ZH_GAMING_WEST_SNIPER") == pytest.approx(0.07)
    restored = overlay.rollback_routing_weight(event)
    assert restored == pytest.approx(0.0)
    assert overlay.routing_weight("gaming", "ZH_GAMING_WEST_SNIPER") == pytest.approx(0.0)
    with pytest.raises(ValueError):
        overlay.rollback_routing_weight(event)


def test_route_bias_is_clamped(tmp_path):
    _, overlay, _ = make_adaptive(tmp_path)
    overlay.adjust_routing_weight("gaming", "X", 999)
    assert overlay.routing_weight("gaming", "X") == pytest.approx(0.10)
