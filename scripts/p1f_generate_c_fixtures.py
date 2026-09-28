from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "runtime" / "fixtures" / "conformance-v1.json"


def c_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: p1f_generate_c_fixtures.py OUTPUT_HEADER")
    fixture_bytes = FIXTURES.read_bytes()
    fixtures = json.loads(fixture_bytes)
    rows = []
    for case in fixtures["cases"]:
        expected = case["expected"]["result"]
        checks = {
            "source_text": expected["source_text"],
            "translated_text": expected["translated_text"],
            "path": expected["path"],
            "confidence": expected["confidence"],
            "warnings": expected["warnings"],
        }
        term_checks = []
        if expected["frame"] is not None:
            frame = expected["frame"]
            checks.update({
                "source_language": frame["source_language"],
                "target_language": frame["target_language"],
                "source_text": frame["source_text"],
                "domain": frame["domain"],
                "intent": frame["intent"],
                "style": frame["style"],
                "template": frame["template"],
                "confidence": frame["confidence"],
                "unresolved": frame["unresolved"],
                "slots": frame["slots"],
            })
            if frame["terms"]:
                for term in frame["terms"]:
                    for key in ("source", "concept", "target", "confidence", "layer", "evidence"):
                        term_checks.append((key, term[key]))
        fields = []
        for key, value in [*checks.items(), *term_checks]:
            token = f"{json.dumps(key, ensure_ascii=False)}:{json.dumps(value, ensure_ascii=False, separators=(',', ':'))}"
            fields.append(c_string(token))
        rows.append("    {" + c_string(case["id"]) + ", " + c_string(json.dumps({
            "contract_version": fixtures["contract_version"],
            "operation": "translate",
            "request": case["request"],
        }, ensure_ascii=False, separators=(",", ":"))) + ", {" + ", ".join(fields) + "}, " + str(len(fields)) + "}")

    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "#ifndef P1F_FIXTURE_CASES_H\n#define P1F_FIXTURE_CASES_H\n"
        "#define P1F_CONTRACT_VERSION " + c_string(fixtures["contract_version"]) + "\n"
        "#define P1F_FIXTURE_SHA256 " + c_string(hashlib.sha256(fixture_bytes).hexdigest()) + "\n"
        "struct p1f_case { const char *id; const char *request; const char *checks[64]; unsigned check_count; };\n"
        "static const struct p1f_case p1f_cases[] = {\n" + ",\n".join(rows) + "\n};\n"
        "#define P1F_CASE_COUNT (sizeof(p1f_cases) / sizeof(p1f_cases[0]))\n#endif\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
