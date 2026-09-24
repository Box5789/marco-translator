import pytest

from marco_translator.maintenance import PatchValidationError, validate_patch_document


def test_valid_patch_proposal():
    validate_patch_document({
        "schema_version": "kg-patch-v1",
        "patches": [{
            "id": "p-1",
            "type": "ADD_DOMAIN_SENSE",
            "expression": "家里",
            "domain": "gaming",
            "concept": "OWN_BASE",
            "evidence_ids": ["log-1", "log-2"],
        }],
    })


def test_patch_cannot_request_auto_apply():
    with pytest.raises(PatchValidationError):
        validate_patch_document({
            "schema_version": "kg-patch-v1",
            "patches": [{
                "type": "ADD_SENSE",
                "evidence_ids": ["log-1"],
                "apply_automatically": True,
            }],
        })
