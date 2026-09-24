from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import zipfile

import pytest

from marco_translator.knowledge_version import KnowledgeVersionError, KnowledgeVersionStore, _version_id, sha256
from marco_translator.maintenance import AnalysisExportError, PatchValidationError, export_analysis_package, load_analysis_package
from marco_translator.models import TranslationRequest
from marco_translator.patches import GRAPH, SEED, stable_target_id
from marco_translator.pipeline import Translator
from marco_translator.tm import SQLiteTranslationMemory
from marco_translator.user_state import SQLiteUserOverlay


ROOT = Path(__file__).resolve().parents[1]
MARCO_ROOT = os.environ.get("MCO_MARCO_ROOT")
pytestmark = pytest.mark.skipif(not MARCO_ROOT, reason="MCO_MARCO_ROOT is not set")


def _store(tmp_path):
    store = KnowledgeVersionStore(tmp_path / "versions.sqlite", marco_root=MARCO_ROOT,
                                  cache_dir=tmp_path / "materialized")
    return store, store.initialize(ROOT)


def _package(store, tmp_path):
    logs = tmp_path / "logs.jsonl"
    logs.write_text(json.dumps({
        "schema_version": "translation-log-v1", "event_type": "translation", "id": "event-1",
        "timestamp": "2026-09-24T00:00:00+00:00",
        "request": {"text": "狙神", "domain": "gaming"},
        "result": {"translated_text": "저격수", "path": "rule", "confidence": 0.9},
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    path = tmp_path / "analysis.zip"
    export_analysis_package(path, logs=logs, knowledge_version=store.snapshot())
    return path, load_analysis_package(path)


def _alias_proposal(version_id, evidence_ids):
    state = {"source": "狙神", "concept": "SNIPER", "target": "저격수",
             "source_language": "zh", "target_language": "ko", "domain": "gaming",
             "confidence": 0.8}
    identity = {key: state[key] for key in (
        "source_language", "target_language", "domain", "source", "concept", "target"
    )}
    return {"schema_version": "kg-patch-v2", "base_kg_version": version_id,
            "patches": [{"id": "alias-sniper", "type": "ADD_ALIAS", "resource": SEED,
                         "target": stable_target_id(SEED, "seed_entry", identity),
                         "expected_old_state": None, "proposed_new_state": state,
                         "evidence_ids": sorted(evidence_ids)}]}


def _pattern_proposal(version_id, evidence_ids):
    state = {"node_id": "ZH_GAMING_GROUP_PUSH", "expression": "大家集合推中路"}
    return {"schema_version": "kg-patch-v2", "base_kg_version": version_id,
            "patches": [{"id": "group-push-pattern", "type": "ADD_PATTERN", "resource": GRAPH,
                         "target": stable_target_id(GRAPH, "marco_pattern", state),
                         "expected_old_state": None, "proposed_new_state": state,
                         "evidence_ids": sorted(evidence_ids)}]}


def _version_count(database):
    with sqlite3.connect(database) as connection:
        return connection.execute("SELECT COUNT(*) FROM versions").fetchone()[0]


def test_mac_version_bootstrap_reopens_and_materializes_verified_model(tmp_path):
    store, initial = _store(tmp_path)
    snapshot = store.snapshot()
    assert initial.startswith("kg2_")
    assert "marco/styles/translator.json" in snapshot["assets"]
    assert snapshot["manifest"]["build_provenance"]["output"]["sha256"]
    assert len(snapshot["mco"]) == snapshot["manifest"]["build_provenance"]["output"]["size_bytes"]
    materialized = tmp_path / "materialized" / initial
    assert (materialized / "derived/zh-ko-gaming.mco").read_bytes() == snapshot["mco"]

    reopened = KnowledgeVersionStore(tmp_path / "versions.sqlite", marco_root=MARCO_ROOT,
                                     cache_dir=tmp_path / "materialized")
    assert reopened.active_version_id() == initial
    assert reopened.snapshot()["assets"] == snapshot["assets"]
    assert reopened.snapshot()["mco"] == snapshot["mco"]


def test_dry_run_replays_actual_marco_without_persisting_or_activating(tmp_path):
    store, initial = _store(tmp_path)
    package, package_data = _package(store, tmp_path)
    proposal = _alias_proposal(initial, package_data["evidence_ids"])
    before_assets = store.snapshot()["assets"]
    result = store.preview_patch(proposal, analysis_package=package)

    assert result["base_version_id"] == initial
    assert result["candidate_version_id"].startswith("kg2_")
    assert result["deterministic"] is True
    assert result["eligible"] is True
    assert result["counts"]["regressed"] == 0
    assert result["counts"]["unchanged"] == 8
    assert result["operations"][0]["type"] == "ADD_ALIAS"
    assert result["asset_diff"][0]["resource"] == SEED
    assert result["derived_mco"]["before_sha256"] == result["derived_mco"]["after_sha256"]
    assert store.active_version_id() == initial
    assert store.snapshot()["assets"] == before_assets
    assert _version_count(tmp_path / "versions.sqlite") == 1
    assert len(list((tmp_path / "materialized").iterdir())) == 1

    invalid = _alias_proposal(initial, package_data["evidence_ids"])
    invalid["patches"][0]["expected_old_state"] = {"confidence": 0.5}
    with pytest.raises(PatchValidationError):
        store.preview_patch(invalid, analysis_package=package)
    assert store.active_version_id() == initial


def test_candidate_graph_is_rebuilt_into_a_new_verified_derived_mco(tmp_path):
    store, initial = _store(tmp_path)
    package, package_data = _package(store, tmp_path)
    preview = store.preview_patch(_pattern_proposal(initial, package_data["evidence_ids"]),
                                  analysis_package=package)
    assert preview["eligible"] is True
    assert preview["asset_diff"][0]["resource"] == GRAPH
    assert preview["derived_mco"]["before_sha256"] != preview["derived_mco"]["after_sha256"]
    assert store.active_version_id() == initial


def test_style_config_is_part_of_identity_and_compiler_provenance(tmp_path):
    base_store, base_version = _store(tmp_path / "base")
    source = tmp_path / "style-variant"
    for name, content in KnowledgeVersionStore._source_assets(ROOT).items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    style = source / "marco/styles/translator.json"
    style_doc = json.loads(style.read_text(encoding="utf-8"))
    style_doc["인코더"]["route_threshold"] += 0.01
    style.write_text(json.dumps(style_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    variant = KnowledgeVersionStore(tmp_path / "variant" / "versions.sqlite", marco_root=MARCO_ROOT)
    variant_version = variant.initialize(source)
    base = base_store.snapshot()
    changed = variant.snapshot()
    assert variant_version != base_version
    assert changed["manifest"]["assets"]["marco/styles/translator.json"] != base["manifest"]["assets"]["marco/styles/translator.json"]
    assert changed["manifest"]["build_provenance"]["recipe"]["model_inputs"]["styles/translator.json"] == \
        changed["manifest"]["assets"]["marco/styles/translator.json"]
    assert changed["manifest"]["build_provenance"]["output"]["sha256"] == \
        sha256(changed["mco"])


def test_explicit_approval_is_atomic_and_rollback_survives_restart_without_touching_user_state(tmp_path):
    store, initial = _store(tmp_path)
    package, package_data = _package(store, tmp_path)
    proposal = _alias_proposal(initial, package_data["evidence_ids"])
    overlay = SQLiteUserOverlay(tmp_path / "overlay.sqlite")
    overlay.add_terminology("X", "엑스", domain="gaming")
    overlay.adjust_routing_weight("gaming", "ZH_GAMING_WEST_SNIPER", 0.05)
    tm = SQLiteTranslationMemory(tmp_path / "tm.sqlite")
    tm.put("zh", "ko", "gaming", "테스트", "test", origin="user_correction")
    overlay_state = overlay.resolve_terms("X", "zh", "ko", "gaming")[0].target
    tm_state = tm.lookup("zh", "ko", "gaming", "테스트")

    preview = store.preview_patch(proposal, analysis_package=package)
    assert store.active_version_id() == initial
    approved = store.approve_patch(proposal, analysis_package=package,
                                   approved_candidate_version_id=preview["candidate_version_id"])
    assert approved == preview["candidate_version_id"]
    assert store.active_version_id() == approved
    assert _version_count(tmp_path / "versions.sqlite") == 2
    manifest = store.snapshot()["manifest"]
    assert manifest["parent_version_id"] == initial
    assert manifest["patch_sha256"] == preview["patch_sha256"]
    assert manifest["evidence_ids"] == sorted(package_data["evidence_ids"])
    assert overlay.resolve_terms("X", "zh", "ko", "gaming")[0].target == overlay_state
    assert tm.lookup("zh", "ko", "gaming", "테스트") == tm_state

    restarted = KnowledgeVersionStore(tmp_path / "versions.sqlite", marco_root=MARCO_ROOT,
                                      cache_dir=tmp_path / "materialized")
    assert restarted.active_version_id() == approved
    active_result = Translator(resolver=restarted.load_active_resolver()).translate(
        TranslationRequest("家里有人", domain="gaming")
    )
    assert active_result.translated_text == "본진에 적 있음"
    assert restarted.rollback(initial) == initial
    restored = KnowledgeVersionStore(tmp_path / "versions.sqlite", marco_root=MARCO_ROOT,
                                     cache_dir=tmp_path / "materialized")
    assert restored.active_version_id() == initial
    assert restored.snapshot()["assets"] == store.snapshot(initial)["assets"]
    assert restored.snapshot()["mco"] == store.snapshot(initial)["mco"]
    rolled_back_result = Translator(resolver=restored.load_active_resolver()).translate(
        TranslationRequest("家里有人", domain="gaming")
    )
    assert rolled_back_result.translated_text == "본진에 적 있음"
    assert [event["action"] for event in restored.activation_history()] == [
        "initialize", "approve_patch", "rollback"
    ]


def test_activation_failure_and_mismatched_approval_leave_active_snapshot_unchanged(tmp_path, monkeypatch):
    store, initial = _store(tmp_path)
    package, package_data = _package(store, tmp_path)
    proposal = _alias_proposal(initial, package_data["evidence_ids"])
    preview = store.preview_patch(proposal, analysis_package=package)
    with pytest.raises(KnowledgeVersionError, match="approval"):
        store.approve_patch(proposal, analysis_package=package,
                            approved_candidate_version_id="kg2_" + "f" * 64)
    assert store.active_version_id() == initial
    assert _version_count(tmp_path / "versions.sqlite") == 1

    def fail_after_pointer_update(*_args):
        raise RuntimeError("injected activation log failure")

    monkeypatch.setattr(store, "_activation_event", fail_after_pointer_update)
    with pytest.raises(RuntimeError, match="injected"):
        store.approve_patch(proposal, analysis_package=package,
                            approved_candidate_version_id=preview["candidate_version_id"])
    assert store.active_version_id() == initial
    assert _version_count(tmp_path / "versions.sqlite") == 1
    restarted = KnowledgeVersionStore(tmp_path / "versions.sqlite", marco_root=MARCO_ROOT,
                                      cache_dir=tmp_path / "materialized")
    assert restarted.active_version_id() == initial


def test_replay_regression_blocks_approval_and_wrong_package_version_is_rejected(tmp_path, monkeypatch):
    store, initial = _store(tmp_path)
    package, package_data = _package(store, tmp_path)
    proposal = _alias_proposal(initial, package_data["evidence_ids"])
    outputs = ["서쪽에 저격수 있음", "본진에 적 있음", "교회에 건축 자재가 필요함",
               "뭉쳐서 한 번에 밀자", "한 명씩 가서 죽어주면 답이 없어", "", "집", "본진"]
    expected = [{"output": output, "path": "unresolved" if not output else (
        "lexical" if index >= 6 else "rule"), "confidence": 1.0}
        for index, output in enumerate(outputs)]
    regressed = [dict(item) for item in expected]
    regressed[0] = {"output": "", "path": "unresolved", "confidence": 0.0}
    monkeypatch.setattr(store, "_replay", lambda snapshot: expected if
                        snapshot["manifest"]["version_id"] == initial else regressed)
    preview = store.preview_patch(proposal, analysis_package=package)
    assert preview["eligible"] is False
    assert preview["counts"]["regressed"] == 1
    with pytest.raises(KnowledgeVersionError, match="regression"):
        store.approve_patch(proposal, analysis_package=package,
                            approved_candidate_version_id=preview["candidate_version_id"])
    assert store.active_version_id() == initial

    other_snapshot = store.snapshot()
    other_snapshot["assets"][SEED] += b"\n"
    other_digests = {name: sha256(data) for name, data in sorted(other_snapshot["assets"].items())}
    other_snapshot["manifest"]["assets"] = other_digests
    other_snapshot["manifest"]["version_id"] = _version_id(
        other_digests, other_snapshot["manifest"]["build_provenance"]
    )
    logs = tmp_path / "other-logs.jsonl"
    logs.write_text(json.dumps({"schema_version": "translation-log-v1", "event_type": "translation",
                                "id": "event-2", "timestamp": "2026-09-24T00:00:00+00:00",
                                "request": {"text": "狙神"}, "result": {"path": "rule", "confidence": 0.9}},
                               ensure_ascii=False) + "\n", encoding="utf-8")
    other_package = tmp_path / "other-version.zip"
    export_analysis_package(other_package, logs=logs, knowledge_version=other_snapshot)
    with pytest.raises(PatchValidationError, match="active Knowledge Version"):
        store.preview_patch(proposal, analysis_package=other_package)


def test_unsupported_database_schema_is_rejected_without_migration(tmp_path):
    database = tmp_path / "legacy.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA user_version=1")
    with pytest.raises(KnowledgeVersionError, match="unsupported"):
        KnowledgeVersionStore(database, marco_root=MARCO_ROOT)
