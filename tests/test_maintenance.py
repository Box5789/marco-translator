from __future__ import annotations

import json
from pathlib import Path
import socket
import zipfile

import pytest

from marco_translator.knowledge_version import (
    SNAPSHOT_SCHEMA, VERSION_SCHEMA, KnowledgeVersionStore, _version_id, sha256,
)
from marco_translator.maintenance import (
    AnalysisExportError, EvidenceIdentityError, PatchValidationError,
    export_analysis_package, load_analysis_package, load_patch_proposal,
    stable_evidence_id, validate_patch_document,
)
from marco_translator.patches import stable_target_id


ROOT = Path(__file__).resolve().parents[1]
SEED = "knowledge/seed.zh-ko.json"
BASE_VERSION = "kg2_" + "a" * 64
EVIDENCE_ID = "ev1_" + "b" * 64


def _snapshot():
    assets = KnowledgeVersionStore._source_assets(ROOT)
    digests = {name: sha256(data) for name, data in sorted(assets.items())}
    mco = b"derived test model"
    compiler_inputs = {name.removeprefix("marco/"): digest for name, digest in digests.items()
                       if name.startswith("marco/")}
    provenance = {
        "schema_version": "marco-build-provenance-v1",
        "marco": {"repository": "https://example.test/Marco", "revision": "1" * 40},
        "compiler": {"package": "mco", "version": "test", "api": "mco.compile"},
        "python": {"implementation": "cpython", "version": "3.12", "platform": "Darwin",
                   "architecture": "arm64", "platform_version": "test",
                   "zlib_version": "test", "zlib_runtime_version": "test"},
        "dependencies": {"numpy": "test"},
        "recipe": {"script": "scripts/build_marco_pack.py", "script_sha256": "2" * 64,
                   "module": "src/marco_translator/marco_pack.py", "module_sha256": "3" * 64,
                   "name": "marco-translator-zh-ko-gaming",
                   "graphs": ["graphs/graph_zh_ko_gaming_semantics.kg"],
                   "model_inputs": compiler_inputs},
        "output": {"sha256": sha256(mco), "size_bytes": len(mco)},
    }
    manifest = {
        "schema_version": VERSION_SCHEMA,
        "version_id": _version_id(digests, provenance),
        "parent_version_id": None,
        "patch_sha256": None,
        "evidence_ids": [],
        "assets": digests,
        "build_provenance": provenance,
    }
    return {"schema_version": SNAPSHOT_SCHEMA, "manifest": manifest, "assets": assets, "mco": mco}


def _translation_event(event_id, *, confidence, path="rule", candidates=None):
    metadata = {"candidate_evidence": candidates} if candidates is not None else {}
    return {
        "schema_version": "translation-log-v1", "event_type": "translation", "id": event_id,
        "timestamp": "2026-09-24T00:00:00+00:00",
        "request": {"text": "家里有人", "domain": "gaming"},
        "result": {"translated_text": "본진에 적 있음", "path": path,
                   "confidence": confidence, "metadata": metadata},
        "user_correction": None,
    }


def _write_jsonl(path: Path, events):
    path.write_text("".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events), encoding="utf-8")


def _package(tmp_path, events=None, *, redact=None):
    logs = tmp_path / "logs.jsonl"
    _write_jsonl(logs, events or [_translation_event("evidence-1", confidence=0.4, path="unresolved")])
    prompt = tmp_path / "prompt.md"
    prompt.write_text("proposal only", encoding="utf-8")
    output = tmp_path / "analysis.zip"
    export_analysis_package(output, logs=logs, knowledge_version=_snapshot(), prompt=prompt, redact=redact)
    return output


def _proposal(version: str, *, evidence_ids=None, **patch_fields):
    entry = {
        "source": "谜语", "concept": "RIDDLE", "target": "수수께끼",
        "source_language": "zh", "target_language": "ko", "domain": "gaming", "confidence": 0.8,
    }
    identity = {key: entry[key] for key in (
        "source_language", "target_language", "domain", "source", "concept", "target"
    )}
    patch = {
        "id": "patch-1", "type": "ADD_DOMAIN_SENSE", "resource": SEED,
        "target": stable_target_id(SEED, "seed_entry", identity),
        "expected_old_state": None, "proposed_new_state": entry,
        "evidence_ids": [EVIDENCE_ID] if evidence_ids is None else evidence_ids,
    }
    patch.update(patch_fields)
    return {"schema_version": "kg-patch-v2", "base_kg_version": version, "patches": [patch]}


def test_valid_patch_requires_v2_resource_identity_states_and_evidence():
    validate_patch_document(_proposal(BASE_VERSION), known_evidence_ids={EVIDENCE_ID},
                            current_base_kg_version=BASE_VERSION)
    with pytest.raises(PatchValidationError, match="v2"):
        validate_patch_document({"schema_version": "kg-patch-v1", "base_kg_version": BASE_VERSION,
                                 "patches": []}, known_evidence_ids={EVIDENCE_ID},
                                current_base_kg_version=BASE_VERSION)


def test_patch_rejects_bad_resource_target_state_and_auto_apply():
    context = {"known_evidence_ids": {EVIDENCE_ID}, "current_base_kg_version": BASE_VERSION}
    for proposal in (
        _proposal(BASE_VERSION, resource="arbitrary/path"),
        _proposal(BASE_VERSION, target="tgt1_" + "f" * 64),
        _proposal(BASE_VERSION, expected_old_state={"confidence": 0}),
        _proposal(BASE_VERSION, apply_automatically=True),
    ):
        with pytest.raises(PatchValidationError):
            validate_patch_document(proposal, **context)


def test_patch_rejects_stale_base_unknown_evidence_and_duplicate_target():
    for proposal, known in (
        (_proposal("kg2_" + "c" * 64), {EVIDENCE_ID}),
        (_proposal(BASE_VERSION, evidence_ids=["ev1_" + "c" * 64]), {EVIDENCE_ID}),
    ):
        with pytest.raises(PatchValidationError):
            validate_patch_document(proposal, known_evidence_ids=known,
                                    current_base_kg_version=BASE_VERSION)
    duplicate = _proposal(BASE_VERSION)
    duplicate["patches"].append(dict(duplicate["patches"][0], id="patch-2"))
    with pytest.raises(PatchValidationError, match="duplicates"):
        validate_patch_document(duplicate, known_evidence_ids={EVIDENCE_ID},
                                current_base_kg_version=BASE_VERSION)


def test_load_patch_uses_verified_package_evidence_and_does_not_mutate_files(tmp_path):
    package = _package(tmp_path)
    evidence_ids = load_analysis_package(package)["evidence_ids"]
    proposal = _proposal(_snapshot()["manifest"]["version_id"], evidence_ids=sorted(evidence_ids))
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal, ensure_ascii=False), encoding="utf-8")
    original = proposal_path.read_bytes()
    loaded = load_patch_proposal(proposal_path, analysis_package=package,
                                 current_base_kg_version=proposal["base_kg_version"])
    assert loaded == proposal
    assert proposal_path.read_bytes() == original
    assert len(evidence_ids) == 1


def test_load_patch_rejects_duplicate_json_keys_and_nonfiles(tmp_path):
    package = _package(tmp_path)
    with pytest.raises(PatchValidationError, match="regular file"):
        load_patch_proposal(tmp_path, analysis_package=package, current_base_kg_version=BASE_VERSION)
    proposal = tmp_path / "proposal.json"
    proposal.write_text('{"schema_version":"kg-patch-v2","schema_version":"kg-patch-v2"}', encoding="utf-8")
    with pytest.raises(PatchValidationError, match="invalid JSON"):
        load_patch_proposal(proposal, analysis_package=package, current_base_kg_version=BASE_VERSION)


def test_evidence_id_is_deterministic_and_rejects_non_json_numbers():
    first = {"id": "event-1", "request": {"text": "家里有人", "domain": "gaming"}}
    reordered = {"request": {"domain": "gaming", "text": "家里有人"}, "id": "event-1"}
    changed = {"id": "event-1", "request": {"text": "家里有人", "domain": "literal"}}
    assert stable_evidence_id(first) == stable_evidence_id(reordered)
    assert stable_evidence_id(first).startswith("ev1_")
    assert stable_evidence_id(first) != stable_evidence_id(changed)
    with pytest.raises(ValueError, match="canonical JSON"):
        stable_evidence_id({"confidence": float("nan")})


def test_analysis_package_carries_full_version_assets_mco_and_evidence_subsets(tmp_path, monkeypatch):
    events = [
        _translation_event("low-unresolved", confidence=0.4, path="unresolved"),
        _translation_event("known", confidence=0.95),
        _translation_event("candidate", confidence=0.9, path="unresolved", candidates=[{"node": "X"}]),
        {"schema_version": "translation-feedback-v1", "event_type": "correction", "id": "correction-1",
         "timestamp": "2026-09-24T00:01:00+00:00", "request": {"text": "家里有人", "domain": "gaming"},
         "user_correction": "본진에 적 있음"},
    ]
    logs = tmp_path / "logs.jsonl"
    _write_jsonl(logs, events)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("proposal only", encoding="utf-8")
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"

    def reject_network(*_args, **_kwargs):
        raise AssertionError("analysis package export attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    version = _snapshot()
    export_analysis_package(first, logs=logs, knowledge_version=version, prompt=prompt)
    export_analysis_package(second, logs=logs, knowledge_version=version, prompt=prompt)
    with zipfile.ZipFile(first) as package, zipfile.ZipFile(second) as repeated:
        names = set(package.namelist())
        assert set(version["assets"]).issubset(names)
        assert {"manifest.json", "translation_logs.jsonl", "kg_snapshot.json", "derived/zh-ko-gaming.mco",
                "ANALYSIS_INSTRUCTIONS.md", "evidence/low_confidence.jsonl", "evidence/unresolved.jsonl",
                "evidence/corrections.jsonl", "evidence/candidates.jsonl"}.issubset(names)
        manifest = json.loads(package.read("manifest.json"))
        repeated_manifest = json.loads(repeated.read("manifest.json"))
        records = [json.loads(line) for line in package.read("translation_logs.jsonl").splitlines()]
        repeat_records = [json.loads(line) for line in repeated.read("translation_logs.jsonl").splitlines()]
        assert [item["evidence_id"] for item in records] == [item["evidence_id"] for item in repeat_records]
        assert all(record["evidence_id"].startswith("ev1_") for record in records)
        assert manifest["schema_version"] == "analysis-package-v2"
        assert manifest["base_kg"]["version_id"] == version["manifest"]["version_id"]
        assert manifest["base_kg"]["version_id"] == repeated_manifest["base_kg"]["version_id"]
        assert manifest["evidence"] == {"total": 4, "low_confidence": 1, "unresolved": 2,
                                         "corrections": 1, "candidates": 1,
                                         "confidence_missing": 0, "low_confidence_threshold": 0.8}
        assert package.read("derived/zh-ko-gaming.mco") == version["mco"]
        assert package.read("ANALYSIS_INSTRUCTIONS.md") == b"proposal only"
        assert manifest["privacy"]["automatic_external_transfer"] is False
    loaded = load_analysis_package(first)
    assert len(loaded["evidence_ids"]) == 4


def test_analysis_package_redacts_only_when_caller_supplies_policy(tmp_path):
    def redact(event):
        event["request"]["text"] = "[redacted]"
        return event

    output = _package(tmp_path, [_translation_event("secret", confidence=1.0)], redact=redact)
    with zipfile.ZipFile(output) as package:
        exported = json.loads(package.read("translation_logs.jsonl"))
        manifest = json.loads(package.read("manifest.json"))
    assert exported["request"]["text"] == "[redacted]"
    assert manifest["privacy"]["redaction"] == "caller-provided"


def test_analysis_package_deduplicates_identical_source_and_rejects_reused_id(tmp_path):
    event = _translation_event("same", confidence=1.0)
    output = _package(tmp_path, [event, event])
    with zipfile.ZipFile(output) as package:
        assert json.loads(package.read("manifest.json"))["evidence"]["total"] == 1
        old_manifest = package.read("manifest.json")
    changed = {**event, "request": {"text": "changed"}}
    logs = tmp_path / "logs.jsonl"
    _write_jsonl(logs, [event, changed])
    with pytest.raises(EvidenceIdentityError, match="different contents"):
        export_analysis_package(output, logs=logs, knowledge_version=_snapshot(), prompt=tmp_path / "prompt.md")
    with zipfile.ZipFile(output) as package:
        assert package.read("manifest.json") == old_manifest


def test_analysis_package_rejects_malformed_inputs_without_replacing_output(tmp_path):
    logs = tmp_path / "logs.jsonl"
    logs.write_text("{bad json}\n", encoding="utf-8")
    prompt = tmp_path / "prompt.md"
    prompt.write_text("instructions", encoding="utf-8")
    output = tmp_path / "analysis.zip"
    output.write_bytes(b"previous package")
    with pytest.raises(AnalysisExportError, match="invalid JSON"):
        export_analysis_package(output, logs=logs, knowledge_version=_snapshot(), prompt=prompt)
    _write_jsonl(logs, [_translation_event("valid", confidence=0.9)])
    with pytest.raises(AnalysisExportError, match="Knowledge Version"):
        export_analysis_package(output, logs=logs, knowledge_version={"bad": True}, prompt=prompt)
    assert output.read_bytes() == b"previous package"


def test_analysis_package_reports_missing_confidence_and_preserves_threshold(tmp_path):
    output = _package(tmp_path, [_translation_event("boundary", confidence=0.8),
                                 _translation_event("missing", confidence=None)])
    with zipfile.ZipFile(output) as package:
        manifest = json.loads(package.read("manifest.json"))
        low_confidence = package.read("evidence/low_confidence.jsonl")
    assert manifest["evidence"]["low_confidence"] == 0
    assert manifest["evidence"]["confidence_missing"] == 1
    assert low_confidence == b""


def test_analysis_package_rejects_malicious_archive_member(tmp_path):
    path = tmp_path / "malicious.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("../escape", b"x")
    with pytest.raises(AnalysisExportError, match="unsafe member"):
        load_analysis_package(path)
