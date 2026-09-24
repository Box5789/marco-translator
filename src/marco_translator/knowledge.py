from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

from .models import TermDecision


@dataclass(frozen=True)
class KnowledgeEntry:
    source: str
    concept: str
    target: str
    source_language: str = "zh"
    target_language: str = "ko"
    domain: str | None = None
    confidence: float = 1.0
    layer: str = "base"


class KnowledgeStore:
    """Small deterministic reference store.

    This is *not* a replacement for MARCO. It implements the same boundary used
    by P1 tests so the pipeline can be exercised before a translator-specific
    .mco model exists. `MarcoResolver` can replace this component later.
    """

    def __init__(self, entries: Iterable[KnowledgeEntry] = ()) -> None:
        self.entries = list(entries)

    @classmethod
    def from_json(cls, path: str | Path) -> "KnowledgeStore":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(KnowledgeEntry(**row) for row in data.get("entries", []))

    def resolve_terms(self, text: str, source_language: str, target_language: str,
                      domain: str | None) -> list[TermDecision]:
        matches: list[TermDecision] = []
        # Domain-specific meaning wins over global meaning for the same source span.
        candidates = [e for e in self.entries if e.source_language == source_language
                      and e.target_language == target_language and e.source in text
                      and (e.domain is None or e.domain == domain)]
        candidates.sort(key=lambda e: (e.source, e.domain is not None, len(e.source)), reverse=True)
        seen_source: set[str] = set()
        for e in candidates:
            if e.source in seen_source:
                continue
            seen_source.add(e.source)
            matches.append(TermDecision(e.source, e.concept, e.target, e.confidence, e.layer))
        return matches
