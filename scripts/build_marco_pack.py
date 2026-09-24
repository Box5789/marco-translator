from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build the P1 MARCO translator model")
    parser.add_argument("--source", default="marco", help="Translator MARCO source tree")
    parser.add_argument("--output", default="build/zh-ko-gaming.mco")
    parser.add_argument("--marco-root", default=None, help="Upstream MARCO checkout")
    args = parser.parse_args(argv)

    try:
        import mco
    except ImportError as exc:
        raise SystemExit("mco is not installed; install the upstream MARCO checkout first") from exc

    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    options = {}
    if args.marco_root:
        options["marco_root"] = str(Path(args.marco_root).resolve())
    report = mco.compile(
        source,
        output,
        name="marco-translator-zh-ko-gaming",
        graphs=["graphs/graph_zh_ko_gaming_semantics.kg"],
        **options,
    )
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
