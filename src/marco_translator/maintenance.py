from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
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


def validate_patch_document(doc: dict) -> None:
    if doc.get("schema_version") != "kg-patch-v1":
        raise PatchValidationError("unsupported schema_version")
    patches = doc.get("patches")
    if not isinstance(patches, list):
        raise PatchValidationError("patches must be an array")
    for idx, patch in enumerate(patches):
        if not isinstance(patch, dict):
            raise PatchValidationError(f"patches[{idx}] must be an object")
        if patch.get("type") not in ALLOWED_PATCH_TYPES:
            raise PatchValidationError(f"patches[{idx}].type is not allowed")
        evidence = patch.get("evidence_ids", [])
        if not isinstance(evidence, list) or not evidence:
            raise PatchValidationError(f"patches[{idx}] requires evidence_ids")
        if patch.get("apply_automatically") is True:
            raise PatchValidationError("external patches may never request automatic application")


def export_analysis_package(output: str | Path, *, logs: str | Path,
                            kg_snapshot: str | Path | None = None,
                            overlay: str | Path | None = None,
                            prompt: str | Path | None = None) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "analysis-package-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "external-llm-kg-patch-proposal",
        "policy": "proposal-only; human approval required",
    }
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        zf.write(logs, "translation_logs.jsonl")
        if kg_snapshot:
            zf.write(kg_snapshot, "kg_snapshot.json")
        if overlay:
            zf.write(overlay, "user_overlay.json")
        if prompt:
            zf.write(prompt, "ANALYSIS_INSTRUCTIONS.md")
    return output
