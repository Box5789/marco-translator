from __future__ import annotations

from dataclasses import dataclass

from .knowledge import KnowledgeStore
from .models import SemanticFrame, TranslationRequest


@dataclass(frozen=True)
class Pattern:
    source: str
    template: str
    slots: dict[str, str]
    domain: str | None = None
    intent: str = "statement"
    style: str = "neutral"
    confidence: float = 1.0


DEFAULT_PATTERNS = (
    Pattern("西边有狙", "{location}에 {entity} 있음", {"location": "서쪽", "entity": "저격수"}, "gaming", "warning", "gaming"),
    Pattern("集合一波去啊", "{group} {push}", {"group": "뭉쳐서", "push": "한 번에 밀자"}, "gaming", "request", "gaming"),
    Pattern("一个一个送没辙", "{one_by_one} {feed} {hopeless}", {"one_by_one": "한 명씩 가서", "feed": "죽어주면", "hopeless": "답이 없어"}, "gaming", "complaint", "gaming"),
    Pattern("家里有人", "{base}에 {enemy} 있음", {"base": "본진", "enemy": "적"}, "gaming", "warning", "gaming", 0.95),
    Pattern("教堂需要建材", "{location}에 {object}가 필요함", {"location": "교회", "object": "건축 자재"}, "gaming", "request", "gaming"),
)


class DeterministicResolver:
    def __init__(self, knowledge: KnowledgeStore, patterns=DEFAULT_PATTERNS) -> None:
        self.knowledge = knowledge
        self.patterns = tuple(patterns)

    def resolve(self, request: TranslationRequest) -> SemanticFrame:
        for pattern in self.patterns:
            if pattern.source == request.text and (pattern.domain is None or pattern.domain == request.domain):
                return SemanticFrame(
                    source_language=request.source_language,
                    target_language=request.target_language,
                    source_text=request.text,
                    domain=request.domain,
                    intent=pattern.intent,
                    style=request.style if request.style != "neutral" else pattern.style,
                    terms=self.knowledge.resolve_terms(
                        request.text, request.source_language, request.target_language,
                        request.domain, session_id=request.session_id
                    ),
                    template=pattern.template,
                    slots=dict(pattern.slots),
                    confidence=pattern.confidence,
                )

        terms = self.knowledge.resolve_terms(
            request.text, request.source_language, request.target_language,
            request.domain, session_id=request.session_id
        )
        covered = set()
        for term in terms:
            covered.update(term.source)
        unresolved = [c for c in request.text if not c.isspace() and c not in covered]
        confidence = min((t.confidence for t in terms), default=0.0)
        return SemanticFrame(
            source_language=request.source_language,
            target_language=request.target_language,
            source_text=request.text,
            domain=request.domain,
            style=request.style,
            terms=terms,
            unresolved=unresolved,
            confidence=confidence,
        )
