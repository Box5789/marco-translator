from __future__ import annotations

from .models import TranslationRequest, TranslationResult
from .normalizer import normalize_text
from .realizer import NullNeuralRealizer, RuleRealizer


class Translator:
    def __init__(self, *, resolver, tm=None, rule_realizer=None, neural_realizer=None, logger=None) -> None:
        self.resolver = resolver
        self.tm = tm
        self.rule_realizer = rule_realizer or RuleRealizer()
        self.neural_realizer = neural_realizer or NullNeuralRealizer()
        self.logger = logger

    def translate(self, request: TranslationRequest) -> TranslationResult:
        normalized = normalize_text(request.text)
        req = TranslationRequest(
            text=normalized,
            source_language=request.source_language,
            target_language=request.target_language,
            domain=request.domain,
            style=request.style,
            session_id=request.session_id,
        )

        if self.tm:
            hit = self.tm.lookup(req.source_language, req.target_language, req.domain, req.text)
            if hit is not None:
                result = TranslationResult(req.text, hit, "tm", 1.0)
                self._log(req, result)
                return result

        frame = self.resolver.resolve(req)
        deterministic = self.rule_realizer.realize(frame)
        if deterministic:
            result = TranslationResult(req.text, deterministic, "rule", frame.confidence, frame=frame)
            self._log(req, result)
            return result

        generated = self.neural_realizer.realize(frame)
        if generated:
            result = TranslationResult(req.text, generated, "neural-realizer", frame.confidence, frame=frame)
            self._log(req, result)
            return result

        result = TranslationResult(
            req.text,
            "",
            "unresolved",
            frame.confidence,
            frame=frame,
            warnings=["No grounded deterministic translation and no neural realizer output."],
        )
        self._log(req, result)
        return result

    def _log(self, request, result) -> None:
        if self.logger:
            self.logger.write(request, result)
