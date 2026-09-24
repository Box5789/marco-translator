from __future__ import annotations

import json
from pathlib import Path

import pytest

from marco_translator.knowledge_version import KnowledgeVersionStore
from marco_translator.maintenance import PatchValidationError, validate_patch_document
from marco_translator.patches import (
    FRAME_MAP, GRAPH, SEED, apply_patch_operations, stable_target_id,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = "ev1_" + "b" * 64
BASE = "kg2_" + "a" * 64


def _seed_entry(source, concept, target, domain):
    return {"source": source, "concept": concept, "target": target,
            "source_language": "zh", "target_language": "ko", "domain": domain,
            "confidence": 0.8}


def _addition(kind, resource, identity, state):
    return {"id": kind.lower(), "type": kind, "resource": resource,
            "target": stable_target_id(resource, identity[0], identity[1]),
            "expected_old_state": None, "proposed_new_state": state,
            "evidence_ids": [EVIDENCE]}


def _weight(resource, kind, identity, old, new, patch_id):
    return {"id": patch_id, "type": "ADJUST_WEIGHT", "resource": resource,
            "target": stable_target_id(resource, kind, identity),
            "expected_old_state": old, "proposed_new_state": new,
            "evidence_ids": [EVIDENCE]}


def _proposal(patches):
    return {"schema_version": "kg-patch-v2", "base_kg_version": BASE, "patches": patches}


def test_all_seven_operations_mutate_their_contractual_canonical_resource():
    assets = KnowledgeVersionStore._source_assets(ROOT)
    alias = _seed_entry("狙神", "SNIPER", "저격수", "gaming")
    sense = _seed_entry("春天", "SPRING", "봄", None)
    domain_sense = _seed_entry("装甲车", "ARMORED_VEHICLE", "장갑차", "gaming")
    pattern = {"node_id": "ZH_GAMING_GROUP_PUSH", "expression": "大家集合推中路"}
    negative = {"node_id": "_잡담", "expression": "天气一般"}
    relation = {"source_node": "ZH_GAMING_WEST_SNIPER", "relation": "뜻함",
                "target_node": "ZH_GAMING_BASE_ENEMY"}
    seed_row = json.loads(assets[SEED])["entries"][0]
    seed_identity = {key: seed_row.get(key, {"source_language": "zh", "target_language": "ko"}.get(key)) for key in (
        "source_language", "target_language", "domain", "source", "concept", "target"
    )}
    frame_identity = {"node_id": "ZH_GAMING_WEST_SNIPER"}
    patches = [
        _addition("ADD_ALIAS", SEED, ("seed_entry", {
            "source_language": "zh", "target_language": "ko", "domain": "gaming",
            "source": alias["source"], "concept": alias["concept"], "target": alias["target"],
        }), alias),
        _addition("ADD_SENSE", SEED, ("seed_entry", {
            "source_language": "zh", "target_language": "ko", "domain": None,
            "source": sense["source"], "concept": sense["concept"], "target": sense["target"],
        }), sense),
        _addition("ADD_DOMAIN_SENSE", SEED, ("seed_entry", {
            "source_language": "zh", "target_language": "ko", "domain": "gaming",
            "source": domain_sense["source"], "concept": domain_sense["concept"],
            "target": domain_sense["target"],
        }), domain_sense),
        _addition("ADD_PATTERN", GRAPH, ("marco_pattern", pattern), pattern),
        _addition("ADD_NEGATIVE_CONSTRAINT", GRAPH,
                  ("marco_negative_example", {"node_id": "_잡담", "expression": negative["expression"]}), negative),
        _addition("ADD_RELATION", GRAPH, ("marco_relation", relation), relation),
        _weight(SEED, "seed_entry", seed_identity, 0.99, 0.98, "lexical-weight"),
        _weight(FRAME_MAP, "semantic_routing_weight", frame_identity, 0.0, 0.05, "routing-weight"),
    ]
    proposal = _proposal(patches)
    validate_patch_document(proposal, known_evidence_ids={EVIDENCE}, current_base_kg_version=BASE)
    updated = apply_patch_operations(assets, proposal)

    seed_doc = json.loads(updated[SEED])
    assert alias in seed_doc["entries"]
    assert sense in seed_doc["entries"]
    assert domain_sense in seed_doc["entries"]
    assert next(row for row in seed_doc["entries"] if row["source"] == "狙")["confidence"] == 0.98
    frame_doc = json.loads(updated[FRAME_MAP])
    assert frame_doc["frames"]["ZH_GAMING_WEST_SNIPER"]["routing_weight"] == 0.05
    graph = updated[GRAPH].decode("utf-8")
    assert 'ZH_GAMING_GROUP_PUSH: "集合一波去啊" | "集合一波" | "一起推一波" | "大家集合推中路"' in graph
    assert '_잡담: "天气不错" | "今天吃什么" | "天气一般"' in graph
    assert "ZH_GAMING_WEST_SNIPER -뜻함-> ZH_GAMING_BASE_ENEMY" in graph
    assert assets[SEED] == KnowledgeVersionStore._source_assets(ROOT)[SEED]


def test_patch_operations_reject_stale_old_state_duplicate_seed_and_graph_conflict():
    assets = KnowledgeVersionStore._source_assets(ROOT)
    seed_row = json.loads(assets[SEED])["entries"][0]
    identity = {key: seed_row.get(key, {"source_language": "zh", "target_language": "ko"}.get(key)) for key in (
        "source_language", "target_language", "domain", "source", "concept", "target"
    )}
    stale = _proposal([_weight(SEED, "seed_entry", identity, 0.2, 0.3, "stale")])
    with pytest.raises(PatchValidationError, match="does not match"):
        apply_patch_operations(assets, stale)

    duplicate = _seed_entry("家里", "HOME", "집", None)
    identity = {key: duplicate[key] for key in (
        "source_language", "target_language", "domain", "source", "concept", "target"
    )}
    proposal = _proposal([_addition("ADD_SENSE", SEED, ("seed_entry", identity), duplicate)])
    with pytest.raises(PatchValidationError, match="already exists"):
        apply_patch_operations(assets, proposal)

    negative = {"source_node": "ZH_GAMING_WEST_SNIPER", "relation": "배제함",
                "target_node": "ZH_GAMING_BASE_ENEMY"}
    forward = {"source_node": "ZH_GAMING_WEST_SNIPER", "relation": "뜻함",
               "target_node": "ZH_GAMING_BASE_ENEMY"}
    negative_patch = _addition("ADD_RELATION", GRAPH, ("marco_relation", negative), negative)
    forward_patch = _addition("ADD_RELATION", GRAPH, ("marco_relation", forward), forward)
    with pytest.raises(PatchValidationError, match="conflicts"):
        apply_patch_operations(assets, _proposal([negative_patch, forward_patch]))


def test_add_negative_constraint_is_an_off_topic_example_not_a_rebuttal_edge():
    assets = KnowledgeVersionStore._source_assets(ROOT)
    state = {"node_id": "_잡담", "expression": "这不是游戏"}
    patch = _addition("ADD_NEGATIVE_CONSTRAINT", GRAPH,
                      ("marco_negative_example", state), state)
    updated = apply_patch_operations(assets, _proposal([patch]))
    graph = updated[GRAPH].decode("utf-8")
    assert '[무관]' in graph and '这不是游戏' in graph
    assert '[논증]' in graph and '这不是游戏' not in graph.split('[논증]', 1)[1]
