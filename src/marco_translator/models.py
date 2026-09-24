from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class TermDecision:
    source: str
    concept: str
    target: str
    confidence: float
    layer: str = "base"
    evidence: tuple[str, ...] = ()


@dataclass
class SemanticFrame:
    source_language: str
    target_language: str
    source_text: str
    domain: str | None = None
    intent: str = "statement"
    style: str = "neutral"
    terms: list[TermDecision] = field(default_factory=list)
    template: str | None = None
    slots: dict[str, str] = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TranslationRequest:
    text: str
    source_language: str = "zh"
    target_language: str = "ko"
    domain: str | None = None
    style: str = "neutral"
    session_id: str | None = None


@dataclass
class TranslationResult:
    source_text: str
    translated_text: str
    path: str
    confidence: float
    frame: SemanticFrame | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CorrectionReceipt:
    source_text: str
    corrected_text: str
    tm_written: bool
    proposal_id: str | None = None
    proposal_status: str | None = None
