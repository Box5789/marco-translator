from __future__ import annotations

import argparse
import json
from pathlib import Path

from .knowledge import KnowledgeStore
from .models import TranslationRequest
from .pipeline import Translator
from .resolver import DeterministicResolver
from .tm import SQLiteTranslationMemory


def _default_knowledge() -> Path:
    return Path(__file__).resolve().parents[2] / "knowledge" / "seed.zh-ko.json"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Marco Translator reference CLI")
    parser.add_argument("text")
    parser.add_argument("--source", default="zh")
    parser.add_argument("--target", default="ko")
    parser.add_argument("--domain", default=None)
    parser.add_argument("--style", default="neutral")
    parser.add_argument("--knowledge", default=str(_default_knowledge()))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    knowledge = KnowledgeStore.from_json(args.knowledge)
    translator = Translator(resolver=DeterministicResolver(knowledge), tm=SQLiteTranslationMemory())
    result = translator.translate(TranslationRequest(
        args.text, source_language=args.source, target_language=args.target,
        domain=args.domain, style=args.style,
    ))
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.translated_text if result.translated_text else "[unresolved]")
    return 0 if result.translated_text else 2


if __name__ == "__main__":
    raise SystemExit(main())
