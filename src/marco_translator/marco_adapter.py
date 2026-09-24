from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import SemanticFrame, TranslationRequest


class MarcoUnavailable(RuntimeError):
    pass


_ACCEPTABLE_STATUSES = {"answered", "needs_input", "observed"}


class MarcoResolver:
    """Resolve a source utterance through a translator-specific MARCO model.

    MARCO is used as a semantic selector. The adapter reads the stable selected
    node from the public ``mco.Result`` trace/evidence contract and maps that
    node to a deterministic ``SemanticFrame``. MARCO is never asked to generate
    target-language prose or a free-form JSON meaning document.
    """

    def __init__(self, model_path: str, frame_map_path: str, *, knowledge=None,
                 marco_root: str | None = None) -> None:
        try:
            import mco  # type: ignore
        except ImportError as exc:
            raise MarcoUnavailable("mco is not installed") from exc
        kwargs: dict[str, Any] = {}
        if marco_root:
            kwargs["marco_root"] = marco_root
        model = mco.load(model_path, **kwargs)
        self._init(model, frame_map_path, knowledge)

    @classmethod
    def from_model(cls, model, frame_map_path: str, *, knowledge=None) -> "MarcoResolver":
        """Dependency-injection constructor used by tests and alternate runtimes."""
        obj = cls.__new__(cls)
        obj._init(model, frame_map_path, knowledge)
        return obj

    def _init(self, model, frame_map_path: str, knowledge) -> None:
        self._model = model
        self._knowledge = knowledge
        doc = json.loads(Path(frame_map_path).read_text(encoding="utf-8"))
        if doc.get("schema_version") != "marco-frame-map-v1":
            raise ValueError("unsupported MARCO frame-map schema")
        frames = doc.get("frames")
        if not isinstance(frames, dict):
            raise ValueError("MARCO frame map requires an object 'frames'")
        self._source_language = str(doc.get("source_language") or "")
        self._target_language = str(doc.get("target_language") or "")
        self._frames = frames

    @staticmethod
    def _status(result) -> str:
        return str(getattr(result, "status", ""))

    @staticmethod
    def _winner_from_trace(result) -> str | None:
        trace = getattr(result, "trace", None)
        if trace is None:
            return None
        try:
            step = trace.stage("judge")
        except (AttributeError, KeyError, IndexError, TypeError):
            return None
        detail = getattr(step, "detail", None)
        if isinstance(detail, dict):
            winner = detail.get("winner")
            return str(winner) if winner else None
        return None

    @staticmethod
    def _winner_from_evidence(result) -> tuple[str | None, float | None]:
        evidence = getattr(result, "evidence", ()) or ()
        for item in evidence:
            kind = getattr(item, "kind", None)
            if kind != "graph_node":
                continue
            text = getattr(item, "text", None)
            if not text:
                continue
            score = getattr(item, "score", None)
            try:
                score = float(score) if score is not None else None
            except (TypeError, ValueError):
                score = None
            return str(text), score
        return None, None

    def _unresolved(self, request: TranslationRequest, reason: str) -> SemanticFrame:
        return SemanticFrame(
            request.source_language,
            request.target_language,
            request.text,
            domain=request.domain,
            style=request.style,
            unresolved=[request.text],
            confidence=0.0,
        )

    def resolve(self, request: TranslationRequest) -> SemanticFrame:
        # Raw text is essential: MARCO's graph matcher must see the actual
        # utterance and its examples, not a JSON wrapper around it.
        result = self._model.run(request.text)
        if self._status(result) not in _ACCEPTABLE_STATUSES:
            return self._unresolved(request, "marco_status")

        winner = self._winner_from_trace(result)
        evidence_winner, evidence_score = self._winner_from_evidence(result)
        node = winner if winner in self._frames else evidence_winner
        spec = self._frames.get(node) if node else None
        if not isinstance(spec, dict):
            return self._unresolved(request, "unmapped_marco_node")

        if self._source_language and request.source_language != self._source_language:
            return self._unresolved(request, "source_language_mismatch")
        if self._target_language and request.target_language != self._target_language:
            return self._unresolved(request, "target_language_mismatch")
        expected_domain = spec.get("domain")
        if expected_domain is not None and request.domain != expected_domain:
            return self._unresolved(request, "domain_mismatch")

        confidence = float(spec.get("confidence", 0.0))
        if evidence_score is not None:
            confidence = min(confidence, max(0.0, min(1.0, evidence_score)))
        terms = []
        if self._knowledge is not None:
            terms = self._knowledge.resolve_terms(
                request.text, request.source_language, request.target_language, request.domain
            )

        return SemanticFrame(
            source_language=request.source_language,
            target_language=request.target_language,
            source_text=request.text,
            domain=request.domain,
            intent=str(spec.get("intent") or "statement"),
            style=request.style if request.style != "neutral" else str(spec.get("style") or "neutral"),
            terms=terms,
            template=spec.get("template") if isinstance(spec.get("template"), str) else None,
            slots={str(k): str(v) for k, v in (spec.get("slots") or {}).items()},
            unresolved=[],
            confidence=confidence,
        )
