from __future__ import annotations

import argparse
import json
from pathlib import Path

from marco_translator.marco_pack import compile_marco_pack


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build the P1 MARCO translator model")
    parser.add_argument("--source", default="marco", help="Translator MARCO source tree")
    parser.add_argument("--output", default="build/zh-ko-gaming.mco")
    parser.add_argument("--marco-root", default=None, help="Clean upstream MARCO checkout")
    args = parser.parse_args(argv)

    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    provenance = compile_marco_pack(source, output, marco_root=args.marco_root)
    print(json.dumps(provenance, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
