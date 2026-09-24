from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any
import uuid

from .models import TermDecision


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _domain(value: str | None) -> str:
    return value or ""


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


@dataclass(frozen=True)
class OverlayProposal:
    id: str
    type: str
    source_language: str
    target_language: str
    domain: str | None
    source: str
    target: str
    evidence_count: int
    status: str


class SQLiteUserOverlay:
    """Persistent, user-scoped adaptive state.

    This database is deliberately separate from the Base KG. Runtime learning
    may write explicit user preferences and reversible routing weights here,
    but it cannot mutate verified Base KG topology.
    """

    def __init__(self, path: str | Path = ":memory:", *, correction_threshold: int = 3,
                 max_route_bias: float = 0.10) -> None:
        if correction_threshold < 2:
            raise ValueError("correction_threshold must be >= 2")
        if not 0 < max_route_bias <= 0.25:
            raise ValueError("max_route_bias must be in (0, 0.25]")
        self.path = str(path)
        self.correction_threshold = int(correction_threshold)
        self.max_route_bias = float(max_route_bias)
        self._db = sqlite3.connect(self.path)
        self._db.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS terminology (
                source_language TEXT NOT NULL,
                target_language TEXT NOT NULL,
                domain TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL,
                concept TEXT NOT NULL,
                target TEXT NOT NULL,
                confidence REAL NOT NULL,
                origin TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(source_language, target_language, domain, source)
            );

            CREATE TABLE IF NOT EXISTS corrections (
                source_language TEXT NOT NULL,
                target_language TEXT NOT NULL,
                domain TEXT NOT NULL DEFAULT '',
                source_text TEXT NOT NULL,
                target_text TEXT NOT NULL,
                count INTEGER NOT NULL,
                last_generated TEXT,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                PRIMARY KEY(source_language, target_language, domain, source_text, target_text)
            );

            CREATE TABLE IF NOT EXISTS overlay_proposals (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                source_language TEXT NOT NULL,
                target_language TEXT NOT NULL,
                domain TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                evidence_count INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(type, source_language, target_language, domain, source, target)
            );

            CREATE TABLE IF NOT EXISTS routing_weights (
                domain TEXT NOT NULL DEFAULT '',
                candidate TEXT NOT NULL,
                weight REAL NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(domain, candidate)
            );

            CREATE TABLE IF NOT EXISTS routing_weight_events (
                id TEXT PRIMARY KEY,
                domain TEXT NOT NULL DEFAULT '',
                candidate TEXT NOT NULL,
                before_weight REAL NOT NULL,
                after_weight REAL NOT NULL,
                delta REAL NOT NULL,
                reason TEXT NOT NULL,
                reverted INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                reverted_at TEXT
            );
            """
        )
        self._db.commit()

    def add_terminology(self, source: str, target: str, *, source_language: str = "zh",
                        target_language: str = "ko", domain: str | None = None,
                        concept: str = "USER_TERM", confidence: float = 1.0,
                        origin: str = "user") -> None:
        source, target = source.strip(), target.strip()
        if not source or not target:
            raise ValueError("source and target must be non-empty")
        now = _now()
        self._db.execute(
            """
            INSERT INTO terminology(
                source_language,target_language,domain,source,concept,target,
                confidence,origin,active,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,1,?,?)
            ON CONFLICT(source_language,target_language,domain,source)
            DO UPDATE SET concept=excluded.concept,target=excluded.target,
                          confidence=excluded.confidence,origin=excluded.origin,
                          active=1,updated_at=excluded.updated_at
            """,
            (source_language, target_language, _domain(domain), source, concept, target,
             _clamp(confidence, 0.0, 1.0), origin, now, now),
        )
        self._db.commit()

    def disable_terminology(self, source: str, *, source_language: str = "zh",
                            target_language: str = "ko", domain: str | None = None) -> None:
        self._db.execute(
            """
            UPDATE terminology SET active=0,updated_at=?
            WHERE source_language=? AND target_language=? AND domain=? AND source=?
            """,
            (_now(), source_language, target_language, _domain(domain), source),
        )
        self._db.commit()

    def resolve_terms(self, text: str, source_language: str, target_language: str,
                      domain: str | None, session_id: str | None = None) -> list[TermDecision]:
        rows = self._db.execute(
            """
            SELECT source,concept,target,confidence,domain
            FROM terminology
            WHERE source_language=? AND target_language=? AND active=1
              AND (domain='' OR domain=?)
            """,
            (source_language, target_language, _domain(domain)),
        ).fetchall()
        candidates = [row for row in rows if row["source"] in text]
        candidates.sort(
            key=lambda row: (
                row["source"],
                row["domain"] == _domain(domain) and bool(row["domain"]),
                len(row["source"]),
                float(row["confidence"]),
            ),
            reverse=True,
        )
        out: list[TermDecision] = []
        seen: set[str] = set()
        for row in candidates:
            source = str(row["source"])
            if source in seen:
                continue
            seen.add(source)
            out.append(TermDecision(
                source=source,
                concept=str(row["concept"]),
                target=str(row["target"]),
                confidence=float(row["confidence"]),
                layer="user",
            ))
        return out

    def record_correction(self, source_text: str, target_text: str, *,
                          source_language: str = "zh", target_language: str = "ko",
                          domain: str | None = None, generated_text: str | None = None) -> OverlayProposal | None:
        source_text, target_text = source_text.strip(), target_text.strip()
        if not source_text or not target_text:
            raise ValueError("source_text and target_text must be non-empty")
        dom, now = _domain(domain), _now()
        self._db.execute(
            """
            INSERT INTO corrections(
                source_language,target_language,domain,source_text,target_text,
                count,last_generated,first_seen,last_seen
            ) VALUES(?,?,?,?,?,1,?,?,?)
            ON CONFLICT(source_language,target_language,domain,source_text,target_text)
            DO UPDATE SET count=count+1,last_generated=excluded.last_generated,last_seen=excluded.last_seen
            """,
            (source_language, target_language, dom, source_text, target_text,
             generated_text, now, now),
        )
        row = self._db.execute(
            """
            SELECT count FROM corrections
            WHERE source_language=? AND target_language=? AND domain=?
              AND source_text=? AND target_text=?
            """,
            (source_language, target_language, dom, source_text, target_text),
        ).fetchone()
        count = int(row["count"])
        proposal: OverlayProposal | None = None
        if count >= self.correction_threshold:
            self._db.execute(
                """
                INSERT INTO overlay_proposals(
                    id,type,source_language,target_language,domain,source,target,
                    evidence_count,status,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?, 'pending',?,?)
                ON CONFLICT(type,source_language,target_language,domain,source,target)
                DO UPDATE SET evidence_count=excluded.evidence_count,updated_at=excluded.updated_at
                """,
                (str(uuid.uuid4()), "ADD_USER_PHRASE", source_language, target_language,
                 dom, source_text, target_text, count, now, now),
            )
            proposal = self._proposal_for(
                "ADD_USER_PHRASE", source_language, target_language, dom, source_text, target_text
            )
        self._db.commit()
        return proposal

    def _proposal_for(self, type_: str, source_language: str, target_language: str,
                      domain: str, source: str, target: str) -> OverlayProposal | None:
        row = self._db.execute(
            """
            SELECT * FROM overlay_proposals
            WHERE type=? AND source_language=? AND target_language=? AND domain=?
              AND source=? AND target=?
            """,
            (type_, source_language, target_language, domain, source, target),
        ).fetchone()
        return self._proposal_from_row(row) if row else None

    @staticmethod
    def _proposal_from_row(row: sqlite3.Row) -> OverlayProposal:
        return OverlayProposal(
            id=str(row["id"]),
            type=str(row["type"]),
            source_language=str(row["source_language"]),
            target_language=str(row["target_language"]),
            domain=str(row["domain"]) or None,
            source=str(row["source"]),
            target=str(row["target"]),
            evidence_count=int(row["evidence_count"]),
            status=str(row["status"]),
        )

    def pending_proposals(self) -> list[OverlayProposal]:
        rows = self._db.execute(
            "SELECT * FROM overlay_proposals WHERE status='pending' ORDER BY created_at,id"
        ).fetchall()
        return [self._proposal_from_row(row) for row in rows]

    def approve_proposal(self, proposal_id: str) -> OverlayProposal:
        row = self._db.execute("SELECT * FROM overlay_proposals WHERE id=?", (proposal_id,)).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        proposal = self._proposal_from_row(row)
        if proposal.status != "pending":
            raise ValueError("proposal is not pending")
        if proposal.type != "ADD_USER_PHRASE":
            raise ValueError("unsupported proposal type")
        self.add_terminology(
            proposal.source,
            proposal.target,
            source_language=proposal.source_language,
            target_language=proposal.target_language,
            domain=proposal.domain,
            concept="USER_PHRASE",
            confidence=1.0,
            origin="approved_repeated_correction",
        )
        self._db.execute(
            "UPDATE overlay_proposals SET status='accepted',updated_at=? WHERE id=?",
            (_now(), proposal_id),
        )
        self._db.commit()
        return OverlayProposal(**{**proposal.__dict__, "status": "accepted"})

    def reject_proposal(self, proposal_id: str) -> None:
        row = self._db.execute("SELECT status FROM overlay_proposals WHERE id=?", (proposal_id,)).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        if row["status"] != "pending":
            raise ValueError("proposal is not pending")
        self._db.execute(
            "UPDATE overlay_proposals SET status='rejected',updated_at=? WHERE id=?",
            (_now(), proposal_id),
        )
        self._db.commit()

    def routing_weight(self, domain: str | None, candidate: str) -> float:
        row = self._db.execute(
            "SELECT weight FROM routing_weights WHERE domain=? AND candidate=?",
            (_domain(domain), candidate),
        ).fetchone()
        return 0.0 if row is None else float(row["weight"])

    def adjust_routing_weight(self, domain: str | None, candidate: str, delta: float, *,
                              reason: str = "explicit_user_feedback") -> str:
        candidate = candidate.strip()
        if not candidate:
            raise ValueError("candidate must be non-empty")
        if not reason.strip():
            raise ValueError("reason must be non-empty")
        dom = _domain(domain)
        before = self.routing_weight(domain, candidate)
        after = _clamp(before + float(delta), -self.max_route_bias, self.max_route_bias)
        actual = after - before
        event_id, now = str(uuid.uuid4()), _now()
        self._db.execute(
            """
            INSERT INTO routing_weights(domain,candidate,weight,updated_at)
            VALUES(?,?,?,?)
            ON CONFLICT(domain,candidate)
            DO UPDATE SET weight=excluded.weight,updated_at=excluded.updated_at
            """,
            (dom, candidate, after, now),
        )
        self._db.execute(
            """
            INSERT INTO routing_weight_events(
                id,domain,candidate,before_weight,after_weight,delta,reason,reverted,created_at
            ) VALUES(?,?,?,?,?,?,?,0,?)
            """,
            (event_id, dom, candidate, before, after, actual, reason, now),
        )
        self._db.commit()
        return event_id

    def rollback_routing_weight(self, event_id: str) -> float:
        row = self._db.execute(
            "SELECT * FROM routing_weight_events WHERE id=?", (event_id,)
        ).fetchone()
        if row is None:
            raise KeyError(event_id)
        if int(row["reverted"]):
            raise ValueError("routing weight event is already reverted")
        dom, candidate = str(row["domain"]), str(row["candidate"])
        current = self.routing_weight(dom or None, candidate)
        restored = _clamp(
            current - float(row["delta"]), -self.max_route_bias, self.max_route_bias
        )
        now = _now()
        self._db.execute(
            "UPDATE routing_weights SET weight=?,updated_at=? WHERE domain=? AND candidate=?",
            (restored, now, dom, candidate),
        )
        self._db.execute(
            "UPDATE routing_weight_events SET reverted=1,reverted_at=? WHERE id=?",
            (now, event_id),
        )
        self._db.commit()
        return restored

    def close(self) -> None:
        self._db.close()


class SessionStateStore:
    """Ephemeral session bindings. Nothing here is persisted."""

    def __init__(self) -> None:
        self._bindings: dict[str, dict[tuple[str, str, str, str], TermDecision]] = {}

    def bind_entity(self, session_id: str, source: str, target: str, *,
                    source_language: str = "zh", target_language: str = "ko",
                    domain: str | None = None, concept: str = "SESSION_ENTITY") -> None:
        if not session_id:
            raise ValueError("session_id is required")
        source, target = source.strip(), target.strip()
        if not source or not target:
            raise ValueError("source and target must be non-empty")
        key = (source_language, target_language, _domain(domain), source)
        self._bindings.setdefault(session_id, {})[key] = TermDecision(
            source, concept, target, 1.0, "session"
        )

    def unbind_entity(self, session_id: str, source: str, *,
                      source_language: str = "zh", target_language: str = "ko",
                      domain: str | None = None) -> None:
        bucket = self._bindings.get(session_id)
        if not bucket:
            return
        bucket.pop((source_language, target_language, _domain(domain), source), None)
        if not bucket:
            self._bindings.pop(session_id, None)

    def clear_session(self, session_id: str) -> None:
        self._bindings.pop(session_id, None)

    def lookup_exact(self, session_id: str | None, source_language: str, target_language: str,
                     domain: str | None, text: str) -> str | None:
        if not session_id:
            return None
        bucket = self._bindings.get(session_id, {})
        exact = bucket.get((source_language, target_language, _domain(domain), text))
        if exact:
            return exact.target
        global_binding = bucket.get((source_language, target_language, "", text))
        return global_binding.target if global_binding else None

    def resolve_terms(self, text: str, source_language: str, target_language: str,
                      domain: str | None, session_id: str | None = None) -> list[TermDecision]:
        if not session_id:
            return []
        bucket = self._bindings.get(session_id, {})
        candidates = []
        for (src_lang, tgt_lang, dom, source), decision in bucket.items():
            if src_lang != source_language or tgt_lang != target_language or source not in text:
                continue
            if dom not in ("", _domain(domain)):
                continue
            candidates.append((dom == _domain(domain) and bool(dom), len(source), decision))
        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        out: list[TermDecision] = []
        seen: set[str] = set()
        for _domain_exact, _length, decision in candidates:
            if decision.source in seen:
                continue
            seen.add(decision.source)
            out.append(decision)
        return out
