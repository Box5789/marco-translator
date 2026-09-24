from __future__ import annotations

from typing import Protocol

from .models import SemanticFrame


class NeuralRealizer(Protocol):
    def realize(self, frame: SemanticFrame) -> str | None: ...


class NullNeuralRealizer:
    def realize(self, frame: SemanticFrame) -> str | None:
        return None


class RuleRealizer:
    def realize(self, frame: SemanticFrame) -> str | None:
        if frame.template:
            try:
                return frame.template.format(**frame.slots)
            except KeyError:
                return None
        # P1 conservative fallback: only emit deterministic replacement if the
        # full source is a single grounded term. Partial term substitution can
        # create fluent-looking nonsense and is intentionally rejected.
        if len(frame.terms) == 1 and frame.terms[0].source == frame.source_text:
            return frame.terms[0].target
        return None
