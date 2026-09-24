from __future__ import annotations

from collections.abc import Callable
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
import zipfile


ALLOWED_PATCH_TYPES = {
    "ADD_ALIAS",
    "ADD_SENSE",
    "ADD_DOMAIN_SENSE",
    "ADD_RELATION",
    "ADD_PATTERN",
    "ADD_NEGATIVE_CONSTRAINT",
    "ADJUST_WEIGHT",
}


class PatchValidationError(ValueError):
    pass


class AnalysisExportError(ValueError):
    pass


class EvidenceIdentityError(AnalysisExportError):
    pass


_MAX_ANALYSIS_PACKAGE_BYTES = 512 * 1024 * 1024


def _canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("value must contain canonical JSON values") from exc


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _parse_finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON number")
    return parsed


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _strict_json_loads(value: str | bytes) -> object:
    return json.loads(
        value,
        parse_constant=_reject_json_constant,
        parse_float=_parse_finite_json_float,
        object_pairs_hook=_unique_json_object,
    )


def stable_evidence_id(event: dict) -> str:
    """Return an export-stable ID for one immutable translation-log event."""
    if not isinstance(event, dict):
        raise TypeError("event must be an object")
    return "ev1_" + hashlib.sha256(_canonical_json(event)).hexdigest()


def validate_patch_document(doc: object, *, known_evidence_ids: set[str] | frozenset[str],
                            current_base_kg_version: str) -> None:
    from .patches import validate_patch_document as validate_v2

    validate_v2(
        doc,
        known_evidence_ids=known_evidence_ids,
        current_base_kg_version=current_base_kg_version,
    )


def load_patch_proposal(path: str | Path, *, analysis_package: str | Path,
                        current_base_kg_version: str) -> dict:
    try:
        source = Path(path)
        if source.is_symlink() or not source.is_file():
            raise PatchValidationError("patch proposal path must name a regular file")
        contents = source.read_bytes()
    except OSError as exc:
        raise PatchValidationError("patch proposal file could not be read") from exc
    try:
        proposal = _strict_json_loads(contents)
    except (ValueError, UnicodeDecodeError) as exc:
        raise PatchValidationError("patch proposal file is invalid JSON") from exc
    package = load_analysis_package(analysis_package)
    if package["version_id"] != current_base_kg_version:
        raise PatchValidationError("analysis package does not identify the current Knowledge Version")
    validate_patch_document(
        proposal,
        known_evidence_ids=package["evidence_ids"],
        current_base_kg_version=current_base_kg_version,
    )
    return proposal


def _validate_event(event: object, line_number: int) -> tuple[str, dict | None]:
    if not isinstance(event, dict):
        raise AnalysisExportError(f"log line {line_number} must be an object")
    if not isinstance(event.get("id"), str) or not event["id"].strip():
        raise AnalysisExportError(f"log line {line_number} requires a non-empty id")
    if not isinstance(event.get("timestamp"), str):
        raise AnalysisExportError(f"log line {line_number} requires a timestamp")

    schema = event.get("schema_version")
    event_type = event.get("event_type")
    if schema == "translation-log-v1" and event_type in (None, "translation"):
        if not isinstance(event.get("request"), dict) or not isinstance(event.get("result"), dict):
            raise AnalysisExportError(f"log line {line_number} has an invalid translation record")
        return "translation", event["result"]
    if schema == "translation-feedback-v1" and event_type in (None, "correction"):
        if not isinstance(event.get("request"), dict) or not isinstance(event.get("user_correction"), str):
            raise AnalysisExportError(f"log line {line_number} has an invalid correction record")
        return "correction", event.get("generated_result")
    raise AnalysisExportError(f"log line {line_number} has an unsupported event schema")


def _read_export_events(logs: Path, *, low_confidence_threshold: float,
                        redact: Callable[[dict], dict] | None) -> tuple[dict, dict]:
    records: list[dict] = []
    subsets = {name: [] for name in ("low_confidence", "unresolved", "corrections", "candidates")}
    source_ids: dict[str, bytes] = {}
    evidence_ids: dict[str, bytes] = {}
    confidence_missing = 0

    try:
        source = logs.open("r", encoding="utf-8")
    except OSError as exc:
        raise AnalysisExportError("translation log could not be opened") from exc
    with source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                original = _strict_json_loads(line)
            except (ValueError, UnicodeDecodeError) as exc:
                raise AnalysisExportError(f"log line {line_number} is invalid JSON") from exc
            event_type, result = _validate_event(original, line_number)
            source_id = original["id"]
            original_bytes = _canonical_json(original)
            previous = source_ids.get(source_id)
            if previous is not None:
                if previous != original_bytes:
                    raise EvidenceIdentityError("one source event id has different contents")
                continue
            source_ids[source_id] = original_bytes

            exported = copy.deepcopy(original)
            if redact is not None:
                try:
                    exported = redact(exported)
                except Exception as exc:
                    raise AnalysisExportError(f"redaction failed at log line {line_number}") from exc
            if not isinstance(exported, dict):
                raise AnalysisExportError("redaction must return an object")
            exported = copy.deepcopy(exported)
            exported.pop("evidence_id", None)
            if exported.get("id") != source_id:
                raise AnalysisExportError("redaction must preserve the source event id")
            event_type, result = _validate_event(exported, line_number)
            evidence_id = stable_evidence_id({"source_event_id": source_id, "event": exported})
            exported_bytes = _canonical_json(exported)
            previous = evidence_ids.get(evidence_id)
            if previous is not None and previous != exported_bytes:
                raise EvidenceIdentityError("Evidence ID digest collision")
            evidence_ids[evidence_id] = exported_bytes
            record = {**exported, "evidence_id": evidence_id}
            records.append(record)

            if event_type == "correction":
                subsets["corrections"].append(record)
                continue
            confidence = result.get("confidence") if result is not None else None
            if (
                isinstance(confidence, (int, float))
                and not isinstance(confidence, bool)
                and math.isfinite(confidence)
            ):
                if confidence < low_confidence_threshold:
                    subsets["low_confidence"].append(record)
            else:
                confidence_missing += 1
            frame = result.get("frame") if result is not None else None
            unresolved = result.get("path") == "unresolved"
            if isinstance(frame, dict):
                unresolved = unresolved or bool(frame.get("unresolved"))
            if unresolved:
                subsets["unresolved"].append(record)
            metadata = result.get("metadata") if result is not None else None
            candidates = metadata.get("candidate_evidence") if isinstance(metadata, dict) else None
            if isinstance(candidates, list) and candidates:
                subsets["candidates"].append(record)

    return {"records": records, "subsets": subsets}, {"confidence_missing": confidence_missing}


def _jsonl_bytes(records: list[dict]) -> bytes:
    return b"".join(_canonical_json(record) + b"\n" for record in records)


def export_analysis_package(output: str | Path, *, logs: str | Path,
                            knowledge_version: dict,
                            overlay: str | Path | None = None,
                            prompt: str | Path | None = None,
                            low_confidence_threshold: float = 0.8,
                            redact: Callable[[dict], dict] | None = None) -> Path:
    if not isinstance(low_confidence_threshold, (int, float)) or isinstance(low_confidence_threshold, bool):
        raise ValueError("low_confidence_threshold must be in 0..1")
    if not math.isfinite(low_confidence_threshold) or not 0.0 <= low_confidence_threshold <= 1.0:
        raise ValueError("low_confidence_threshold must be in 0..1")

    output, logs = Path(output), Path(logs)
    if prompt is None:
        prompt = Path(__file__).resolve().parents[2] / "prompts" / "kg-maintenance.md"
    else:
        prompt = Path(prompt)
    inputs = [logs, prompt] + ([Path(overlay)] if overlay is not None else [])
    output_identity = output.resolve()
    if any(output_identity == item.resolve() for item in inputs):
        raise AnalysisExportError("package output must not replace an input file")

    evidence, diagnostics = _read_export_events(
        logs, low_confidence_threshold=float(low_confidence_threshold), redact=redact
    )
    try:
        from .knowledge_version import snapshot_document, validate_snapshot

        validate_snapshot(knowledge_version)
        snapshot_metadata = snapshot_document(knowledge_version)
        snapshot_bytes = json.dumps(snapshot_metadata, ensure_ascii=False, indent=2,
                                    sort_keys=True).encode("utf-8")
        prompt_bytes = prompt.read_bytes()
        prompt_bytes.decode("utf-8")
        overlay_bytes = Path(overlay).read_bytes() if overlay is not None else None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError, RuntimeError) as exc:
        raise AnalysisExportError("Knowledge Version, prompt, or overlay input is invalid") from exc

    version_manifest = knowledge_version["manifest"]
    snapshot_version = version_manifest["version_id"]
    subsets = evidence["subsets"]
    manifest = {
        "schema_version": "analysis-package-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "external-llm-kg-patch-proposal",
        "policy": "proposal-only; human approval required",
        "base_kg": {
            "version_id": snapshot_version,
            "canonical_sha256": hashlib.sha256(_canonical_json(snapshot_metadata)).hexdigest(),
            "snapshot": "kg_snapshot.json",
            "assets": sorted(version_manifest["assets"]),
            "derived_mco": "derived/zh-ko-gaming.mco",
        },
        "evidence_id": {
            "algorithm": "SHA-256 over canonical JSON with source event id",
            "prefix": "ev1_",
            "duplicate_policy": "exact duplicate source event collapses; reused source id with different content fails",
        },
        "evidence": {
            "total": len(evidence["records"]),
            "low_confidence": len(subsets["low_confidence"]),
            "unresolved": len(subsets["unresolved"]),
            "corrections": len(subsets["corrections"]),
            "candidates": len(subsets["candidates"]),
            "confidence_missing": diagnostics["confidence_missing"],
            "low_confidence_threshold": float(low_confidence_threshold),
        },
        "privacy": {
            "redaction": "caller-provided" if redact is not None else "none",
            "automatic_external_transfer": False,
        },
    }
    payloads = {
        "manifest.json": json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        "translation_logs.jsonl": _jsonl_bytes(evidence["records"]),
        "evidence/low_confidence.jsonl": _jsonl_bytes(subsets["low_confidence"]),
        "evidence/unresolved.jsonl": _jsonl_bytes(subsets["unresolved"]),
        "evidence/corrections.jsonl": _jsonl_bytes(subsets["corrections"]),
        "evidence/candidates.jsonl": _jsonl_bytes(subsets["candidates"]),
        "kg_snapshot.json": snapshot_bytes,
        "derived/zh-ko-gaming.mco": knowledge_version["mco"],
        "ANALYSIS_INSTRUCTIONS.md": prompt_bytes,
    }
    payloads.update(knowledge_version["assets"])
    if overlay_bytes is not None:
        payloads["user_overlay.json"] = overlay_bytes
    if len(payloads) > 2048 or sum(len(data) for data in payloads.values()) > _MAX_ANALYSIS_PACKAGE_BYTES:
        raise AnalysisExportError("analysis package exceeds the supported archive size")

    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, data in payloads.items():
                zf.writestr(name, data)
        with temporary.open("rb+") as package_file:
            os.fsync(package_file.fileno())
        os.replace(temporary, output)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return output


def load_analysis_package(path: str | Path) -> dict:
    """Validate a locally supplied v2 package without extracting its members."""
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise AnalysisExportError("analysis package path must name a regular file")
    try:
        with zipfile.ZipFile(source) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if len(names) != len(set(names)):
                raise AnalysisExportError("analysis package contains duplicate member names")
            if len(infos) > 2048 or sum(item.file_size for item in infos) > _MAX_ANALYSIS_PACKAGE_BYTES:
                raise AnalysisExportError("analysis package exceeds the supported archive size")
            for item in infos:
                member = PurePosixPath(item.filename)
                mode = item.external_attr >> 16
                if (member.is_absolute() or ".." in member.parts or "\\" in item.filename
                        or stat.S_ISLNK(mode) or item.is_dir()):
                    raise AnalysisExportError("analysis package contains an unsafe member")
            metadata = _strict_json_loads(archive.read("kg_snapshot.json"))
            if not isinstance(metadata, dict) or set(metadata) != {
                "schema_version", "manifest", "asset_digests", "derived_mco"
            }:
                raise AnalysisExportError("analysis package Knowledge Version snapshot is invalid")
            if metadata.get("schema_version") != "knowledge-snapshot-v2":
                raise AnalysisExportError("analysis package Knowledge Version schema is unsupported")
            if not isinstance(metadata.get("manifest"), dict):
                raise AnalysisExportError("analysis package Knowledge Version manifest is invalid")
            digests = metadata.get("asset_digests")
            if not isinstance(digests, dict) or not all(isinstance(name, str) for name in digests):
                raise AnalysisExportError("analysis package canonical asset list is invalid")
            required = {
                "manifest.json", "kg_snapshot.json", "translation_logs.jsonl",
                "evidence/low_confidence.jsonl", "evidence/unresolved.jsonl",
                "evidence/corrections.jsonl", "evidence/candidates.jsonl",
                "ANALYSIS_INSTRUCTIONS.md", "derived/zh-ko-gaming.mco",
                *digests.keys(),
            }
            if set(names) not in (required, required | {"user_overlay.json"}):
                raise AnalysisExportError("analysis package members do not match the v2 contract")
            manifest = _strict_json_loads(archive.read("manifest.json"))
            if not isinstance(manifest, dict) or manifest.get("schema_version") != "analysis-package-v2":
                raise AnalysisExportError("analysis package manifest schema is unsupported")
            base_kg = manifest.get("base_kg")
            if not isinstance(base_kg, dict) or base_kg.get("version_id") != metadata["manifest"].get("version_id"):
                raise AnalysisExportError("analysis package manifest and snapshot version do not match")
            if base_kg.get("snapshot") != "kg_snapshot.json" or base_kg.get("derived_mco") != "derived/zh-ko-gaming.mco":
                raise AnalysisExportError("analysis package paths do not match the v2 contract")
            if base_kg.get("assets") != sorted(digests):
                raise AnalysisExportError("analysis package asset list does not match its snapshot")
            if base_kg.get("canonical_sha256") != hashlib.sha256(_canonical_json(metadata)).hexdigest():
                raise AnalysisExportError("analysis package snapshot digest mismatch")
            assets = {name: archive.read(name) for name in digests}
            mco = archive.read("derived/zh-ko-gaming.mco")
            from .knowledge_version import validate_snapshot

            snapshot = validate_snapshot({"schema_version": "knowledge-snapshot-v2",
                                          "manifest": metadata["manifest"], "assets": assets, "mco": mco})
            records = []
            record_by_evidence_id = {}
            seen_source_ids: dict[str, bytes] = {}
            evidence_ids: set[str] = set()
            for line_number, line in enumerate(archive.read("translation_logs.jsonl").splitlines(), 1):
                try:
                    record = _strict_json_loads(line)
                    event_type, _ = _validate_event(record, line_number)
                    evidence_id = record.get("evidence_id")
                    event = copy.deepcopy(record)
                    event.pop("evidence_id", None)
                    expected_id = stable_evidence_id({"source_event_id": record["id"], "event": event})
                    if evidence_id != expected_id or evidence_id in evidence_ids:
                        raise EvidenceIdentityError("analysis package evidence identity is invalid or duplicated")
                    event_bytes = _canonical_json(event)
                    previous = seen_source_ids.get(record["id"])
                    if previous is not None and previous != event_bytes:
                        raise EvidenceIdentityError("analysis package reuses a source event ID")
                    seen_source_ids[record["id"]] = event_bytes
                    evidence_ids.add(evidence_id)
                    records.append((record, event_type))
                    record_by_evidence_id[evidence_id] = record
                except (ValueError, KeyError, TypeError) as exc:
                    if isinstance(exc, AnalysisExportError):
                        raise
                    raise AnalysisExportError(f"analysis package evidence line {line_number} is invalid") from exc
            evidence_manifest = manifest.get("evidence")
            if not isinstance(evidence_manifest, dict) or evidence_manifest.get("total") != len(records):
                raise AnalysisExportError("analysis package evidence counts are invalid")
            threshold = evidence_manifest.get("low_confidence_threshold")
            if (not isinstance(threshold, (int, float)) or isinstance(threshold, bool)
                    or not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0):
                raise AnalysisExportError("analysis package confidence threshold is invalid")
            expected_subsets = {name: [] for name in ("low_confidence", "unresolved", "corrections", "candidates")}
            confidence_missing = 0
            for record, event_type in records:
                if event_type == "correction":
                    expected_subsets["corrections"].append(record["evidence_id"])
                    continue
                result = record["result"]
                confidence = result.get("confidence")
                if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
                    if confidence < evidence_manifest.get("low_confidence_threshold", 0.8):
                        expected_subsets["low_confidence"].append(record["evidence_id"])
                else:
                    confidence_missing += 1
                frame = result.get("frame")
                if result.get("path") == "unresolved" or (isinstance(frame, dict) and frame.get("unresolved")):
                    expected_subsets["unresolved"].append(record["evidence_id"])
                candidates = (result.get("metadata") or {}).get("candidate_evidence") if isinstance(result.get("metadata"), dict) else None
                if isinstance(candidates, list) and candidates:
                    expected_subsets["candidates"].append(record["evidence_id"])
            for name, evidence in expected_subsets.items():
                subset_name = f"evidence/{name}.jsonl"
                subset_ids = []
                for line in archive.read(subset_name).splitlines():
                    item = _strict_json_loads(line)
                    if not isinstance(item, dict) or item.get("evidence_id") not in evidence_ids:
                        raise AnalysisExportError(f"analysis package subset {name} has a dangling evidence reference")
                    if _canonical_json(item) != _canonical_json(record_by_evidence_id[item["evidence_id"]]):
                        raise AnalysisExportError(f"analysis package subset {name} changes an evidence record")
                    subset_ids.append(item["evidence_id"])
                if subset_ids != evidence:
                    raise AnalysisExportError(f"analysis package subset {name} does not match the evidence manifest")
                if evidence_manifest.get(name) != len(evidence):
                    raise AnalysisExportError(f"analysis package {name} count does not match the manifest")
            if evidence_manifest.get("confidence_missing") != confidence_missing:
                raise AnalysisExportError("analysis package missing-confidence count is invalid")
            return {"version_id": snapshot["manifest"]["version_id"],
                    "evidence_ids": frozenset(evidence_ids), "manifest": manifest}
    except AnalysisExportError:
        raise
    except (OSError, zipfile.BadZipFile, KeyError, UnicodeDecodeError, ValueError, RuntimeError) as exc:
        raise AnalysisExportError("analysis package is malformed or corrupt") from exc
