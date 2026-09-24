from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from .models import TranslationRequest, TranslationResult


class JsonlTranslationLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, record: dict) -> str:
        event_id = record.setdefault("id", str(uuid.uuid4()))
        record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        return str(event_id)

    def write(self, request: TranslationRequest, result: TranslationResult) -> str:
        return self._append({
            "schema_version": "translation-log-v1",
            "event_type": "translation",
            "request": asdict(request),
            "result": result.to_dict(),
            "user_correction": None,
        })

    def write_correction(self, request: TranslationRequest, corrected_text: str, *,
                         result: TranslationResult | None = None, proposal=None) -> str:
        return self._append({
            "schema_version": "translation-feedback-v1",
            "event_type": "correction",
            "request": asdict(request),
            "generated_result": result.to_dict() if result else None,
            "user_correction": corrected_text,
            "overlay_proposal_id": getattr(proposal, "id", None),
            "overlay_proposal_status": getattr(proposal, "status", None),
        })
