from __future__ import annotations

import json
from typing import Any

from .models import SemanticFrame, TermDecision, TranslationRequest


class MarcoUnavailable(RuntimeError):
    pass


class MarcoResolver:
    """Adapter boundary for a translator-specific MARCO `.mco` model.

    The translator model is expected to return a compact JSON semantic frame as
    its grounded answer. The adapter never accepts free-form text as semantics.
    This keeps the in-app neural realizer downstream from the deterministic
    meaning decision.
    """

    def __init__(self, model_path: str, *, marco_root: str | None = None) -> None:
        try:
            import mco  # type: ignore
        except ImportError as exc:
            raise MarcoUnavailable("mco is not installed") from exc
        kwargs: dict[str, Any] = {}
        if marco_root:
            kwargs["marco_root"] = marco_root
        self._model = mco.load(model_path, **kwargs)

    def resolve(self, request: TranslationRequest) -> SemanticFrame:
        # This protocol is deliberately explicit. The translator-specific MCO
        # pack owns the vocabulary and must answer with grounded JSON only.
        query = json.dumps({
            "task": "resolve_translation_semantics",
            "source_language": request.source_language,
            "target_language": request.target_language,
            "domain": request.domain,
            "style": request.style,
            "text": request.text,
        }, ensure_ascii=False, separators=(",", ":"))
        result = self._model.run(query)
        if str(result.status) != "answered" or not result.answer:
            return SemanticFrame(request.source_language, request.target_language, request.text,
                                 domain=request.domain, style=request.style,
                                 unresolved=[request.text], confidence=0.0)
        try:
            raw = json.loads(result.answer)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("MARCO translator model returned non-JSON semantics") from exc
        terms = [TermDecision(**t) for t in raw.get("terms", [])]
        return SemanticFrame(
            source_language=request.source_language,
            target_language=request.target_language,
            source_text=request.text,
            domain=request.domain,
            intent=raw.get("intent", "statement"),
            style=raw.get("style", request.style),
            terms=terms,
            template=raw.get("template"),
            slots=raw.get("slots", {}),
            unresolved=raw.get("unresolved", []),
            confidence=float(raw.get("confidence", 0.0)),
        )
