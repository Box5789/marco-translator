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
                      domain: str | None, session_id: str | None = None) -> list[TermDecision]:
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


class LayeredKnowledgeStore:
    """Compose session, user-overlay and verified base terminology.

    Precedence is explicit and deterministic:
      session > user overlay > base.

    Routing weights only adjust confidence; they never create a concept or a
    translation. Semantic topology remains in the Base KG / approved overlay.
    """

    _LAYER_PRIORITY = {"session": 3, "user": 2, "base": 1}

    def __init__(self, base: KnowledgeStore, *, user_overlay=None, sessions=None) -> None:
        self.base = base
        self.user_overlay = user_overlay
        self.sessions = sessions

    def resolve_terms(self, text: str, source_language: str, target_language: str,
                      domain: str | None, session_id: str | None = None) -> list[TermDecision]:
        candidates: list[TermDecision] = []
        candidates.extend(self.base.resolve_terms(
            text, source_language, target_language, domain, session_id=session_id
        ))
        if self.user_overlay is not None:
            candidates.extend(self.user_overlay.resolve_terms(
                text, source_language, target_language, domain, session_id=session_id
            ))
        if self.sessions is not None:
            candidates.extend(self.sessions.resolve_terms(
                text, source_language, target_language, domain, session_id=session_id
            ))

        adjusted: list[TermDecision] = []
        for item in candidates:
            bias = 0.0
            if self.user_overlay is not None:
                bias = self.user_overlay.routing_weight(domain, item.concept)
            adjusted.append(TermDecision(
                source=item.source,
                concept=item.concept,
                target=item.target,
                confidence=max(0.0, min(1.0, item.confidence + bias)),
                layer=item.layer,
                evidence=item.evidence,
            ))

        adjusted.sort(
            key=lambda item: (
                item.source,
                self._LAYER_PRIORITY.get(item.layer, 0),
                item.confidence,
                len(item.source),
            ),
            reverse=True,
        )
        out: list[TermDecision] = []
        seen: set[str] = set()
        for item in adjusted:
            if item.source in seen:
                continue
            seen.add(item.source)
            out.append(item)
        return out
