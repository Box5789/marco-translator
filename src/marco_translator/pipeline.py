from __future__ import annotations

from .models import CorrectionReceipt, TranslationRequest, TranslationResult
from .normalizer import normalize_text
from .realizer import NullNeuralRealizer, RuleRealizer


class Translator:
    def __init__(self, *, resolver, tm=None, rule_realizer=None, neural_realizer=None,
                 logger=None, user_overlay=None, sessions=None) -> None:
        self.resolver = resolver
        self.tm = tm
        self.rule_realizer = rule_realizer or RuleRealizer()
        self.neural_realizer = neural_realizer or NullNeuralRealizer()
        self.logger = logger
        self.user_overlay = user_overlay
        self.sessions = sessions

    @staticmethod
    def _normalized_request(request: TranslationRequest) -> TranslationRequest:
        return TranslationRequest(
            text=normalize_text(request.text),
            source_language=request.source_language,
            target_language=request.target_language,
            domain=request.domain,
            style=request.style,
            session_id=request.session_id,
        )

    def translate(self, request: TranslationRequest) -> TranslationResult:
        req = self._normalized_request(request)

        if self.sessions:
            hit = self.sessions.lookup_exact(
                req.session_id, req.source_language, req.target_language, req.domain, req.text
            )
            if hit is not None:
                result = TranslationResult(req.text, hit, "session", 1.0)
                self._log(req, result)
                return result

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

    def correct(self, request: TranslationRequest, corrected_text: str, *,
                result: TranslationResult | None = None) -> CorrectionReceipt:
        """Record explicit user supervision.

        The exact correction is immediately safe to put in Translation Memory.
        Repeated corrections may create a *pending* User Overlay proposal, but
        they never mutate Base KG or auto-approve the proposal.
        """
        req = self._normalized_request(request)
        corrected = normalize_text(corrected_text)
        if not corrected:
            raise ValueError("corrected_text must be non-empty")

        tm_written = False
        if self.tm is not None:
            self.tm.put(
                req.source_language, req.target_language, req.domain,
                req.text, corrected, origin="user_correction",
            )
            tm_written = True

        proposal = None
        if self.user_overlay is not None:
            proposal = self.user_overlay.record_correction(
                req.text,
                corrected,
                source_language=req.source_language,
                target_language=req.target_language,
                domain=req.domain,
                generated_text=result.translated_text if result else None,
            )

        if self.logger and hasattr(self.logger, "write_correction"):
            self.logger.write_correction(req, corrected, result=result, proposal=proposal)

        return CorrectionReceipt(
            source_text=req.text,
            corrected_text=corrected,
            tm_written=tm_written,
            proposal_id=proposal.id if proposal else None,
            proposal_status=proposal.status if proposal else None,
        )

    def bind_session_entity(self, session_id: str, source: str, target: str, *,
                            source_language: str = "zh", target_language: str = "ko",
                            domain: str | None = None, concept: str = "SESSION_ENTITY") -> None:
        if self.sessions is None:
            raise RuntimeError("session state store is not configured")
        self.sessions.bind_entity(
            session_id, source, target, source_language=source_language,
            target_language=target_language, domain=domain, concept=concept,
        )

    def clear_session(self, session_id: str) -> None:
        if self.sessions is not None:
            self.sessions.clear_session(session_id)

    def reinforce_route(self, domain: str | None, candidate: str, delta: float, *,
                        reason: str = "explicit_user_route_choice") -> str:
        if self.user_overlay is None:
            raise RuntimeError("user overlay is not configured")
        return self.user_overlay.adjust_routing_weight(domain, candidate, delta, reason=reason)

    def rollback_route(self, event_id: str) -> float:
        if self.user_overlay is None:
            raise RuntimeError("user overlay is not configured")
        return self.user_overlay.rollback_routing_weight(event_id)

    def _log(self, request, result) -> None:
        if self.logger:
            self.logger.write(request, result)
