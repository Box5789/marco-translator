"""Versioned wire representation for the P1-F cross-runtime reference."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .models import SemanticFrame, TranslationRequest, TranslationResult


CONTRACT_VERSION = "marco-runtime.v1"
NORMALIZATION_PROFILE = "NFKC-UCD16.0.0+PY-RE-WHITESPACE-v1"
MAX_INPUT_BYTES = 1024 * 1024


def request_document(request: TranslationRequest) -> dict[str, Any]:
    return {
        "text": request.text,
        "source_language": request.source_language,
        "target_language": request.target_language,
        "domain": request.domain,
        "style": request.style,
        "session_id": request.session_id,
    }


def _frame_document(frame: SemanticFrame | None) -> dict[str, Any] | None:
    if frame is None:
        return None
    value = asdict(frame)
    value["terms"] = [
        {**asdict(term), "evidence": list(term.evidence)} for term in frame.terms
    ]
    value["slots"] = dict(sorted(frame.slots.items()))
    return value


def response_document(result: TranslationResult) -> dict[str, Any]:
    """Remove Python-only representation details and stabilize warning codes."""
    warnings = []
    if result.warnings:
        warnings.append("no_grounded_deterministic_translation")
    return {
        "contract_version": CONTRACT_VERSION,
        "result": {
            "source_text": result.source_text,
            "translated_text": result.translated_text,
            "path": result.path,
            "confidence": result.confidence,
            "frame": _frame_document(result.frame),
            "warnings": warnings,
        },
    }
