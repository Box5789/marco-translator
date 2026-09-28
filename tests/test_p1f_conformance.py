import hashlib
import json
import sys
import unicodedata
from pathlib import Path

from jsonschema import Draft202012Validator
from marco_translator.knowledge import KnowledgeStore
from marco_translator.models import TranslationRequest
from marco_translator.pipeline import Translator
from marco_translator.portable_contract import (
    CONTRACT_VERSION,
    NORMALIZATION_PROFILE,
    response_document,
)
from marco_translator.resolver import DeterministicResolver
from marco_translator.tm import SQLiteTranslationMemory


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "runtime" / "fixtures" / "conformance-v1.json"


def test_python_reference_matches_frozen_p1f_contract():
    assert sys.version_info[:2] == (3, 14)
    assert unicodedata.unidata_version == "16.0.0"
    fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert fixtures["contract_version"] == CONTRACT_VERSION
    assert fixtures["normalization_profile"] == NORMALIZATION_PROFILE
    fixture_hash = hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest()
    assert fixture_hash == (FIXTURE_PATH.with_suffix(".sha256").read_text(encoding="ascii").split()[0])
    schema = json.loads((ROOT / "schemas" / "marco-runtime-v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    resolver = DeterministicResolver(
        KnowledgeStore.from_json(ROOT / "knowledge" / "seed.zh-ko.json")
    )
    translator = Translator(resolver=resolver, tm=SQLiteTranslationMemory())
    for case in fixtures["cases"]:
        request = {"contract_version": CONTRACT_VERSION, "operation": "translate", "request": case["request"]}
        validator.validate(request)
        result = response_document(translator.translate(TranslationRequest(**case["request"])))
        validator.validate(result)
        assert result == case["expected"], case["id"]
