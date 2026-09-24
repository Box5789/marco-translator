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

    def write(self, request: TranslationRequest, result: TranslationResult) -> str:
        event_id = str(uuid.uuid4())
        record = {
            "schema_version": "translation-log-v1",
            "id": event_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request": asdict(request),
            "result": result.to_dict(),
            "user_correction": None,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        return event_id
