from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import math
import re

from .maintenance import ALLOWED_PATCH_TYPES, PatchValidationError, _canonical_json, _strict_json_loads


SEED = "knowledge/seed.zh-ko.json"
GRAPH = "marco/graphs/graph_zh_ko_gaming_semantics.kg"
FRAME_MAP = "knowledge/marco-frame-map.zh-ko.json"
MAX_SEMANTIC_ROUTING_WEIGHT = 0.10

_RESOURCE_BY_TYPE = {
    "ADD_ALIAS": {SEED},
    "ADD_SENSE": {SEED},
    "ADD_DOMAIN_SENSE": {SEED},
    "ADD_PATTERN": {GRAPH},
    "ADD_NEGATIVE_CONSTRAINT": {GRAPH},
    "ADD_RELATION": {GRAPH},
    "ADJUST_WEIGHT": {SEED, FRAME_MAP},
}
_PATCH_KEYS = {
    "id", "type", "resource", "target", "expected_old_state",
    "proposed_new_state", "evidence_ids", "reason", "apply_automatically",
}
_TARGET_RE = re.compile(r"tgt1_[0-9a-f]{64}\Z")
_KG_QUOTED = re.compile(r'"(?:\\.|[^"\\])*"')
_KG_EDGE = re.compile(r"\s*(\S+)\s+-([^\s]+)->\s*(.+?)\s*\Z")


def stable_target_id(resource: str, kind: str, identity: Mapping[str, object]) -> str:
    payload = {"resource": resource, "kind": kind, "identity": dict(identity)}
    return "tgt1_" + hashlib.sha256(_canonical_json(payload)).hexdigest()


def _number(value: object, label: str, minimum: float, maximum: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise PatchValidationError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise PatchValidationError(f"{label} must be in {minimum}..{maximum}")
    return result


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise PatchValidationError(f"{label} must be a non-empty trimmed string")
    if any(ord(char) < 32 for char in value):
        raise PatchValidationError(f"{label} must not contain control characters")
    return value


def _seed_entry(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise PatchValidationError(f"{label} must be a seed entry object")
    allowed = {
        "source", "concept", "target", "source_language", "target_language",
        "domain", "confidence",
    }
    required = {"source", "concept", "target", "source_language", "target_language", "domain", "confidence"}
    if set(value) - allowed or required - set(value):
        raise PatchValidationError(f"{label} has invalid seed entry fields")
    entry = dict(value)
    for field in ("source", "concept", "target", "source_language", "target_language"):
        _text(entry[field], f"{label}.{field}")
    if entry["domain"] is not None:
        _text(entry["domain"], f"{label}.domain")
    entry["confidence"] = _number(entry["confidence"], f"{label}.confidence", 0.0, 1.0)
    return entry


def _state_identity(patch_type: str, state: dict) -> tuple[str, dict, dict]:
    if patch_type in {"ADD_ALIAS", "ADD_SENSE", "ADD_DOMAIN_SENSE"}:
        entry = _seed_entry(state, "proposed_new_state")
        if patch_type == "ADD_SENSE" and entry["domain"] is not None:
            raise PatchValidationError("ADD_SENSE requires a global seed entry")
        if patch_type == "ADD_DOMAIN_SENSE" and not entry["domain"]:
            raise PatchValidationError("ADD_DOMAIN_SENSE requires a domain")
        key = {field: entry[field] for field in (
            "source_language", "target_language", "domain", "source", "concept", "target"
        )}
        return "seed_entry", key, entry
    if patch_type == "ADD_PATTERN":
        if set(state) != {"node_id", "expression"}:
            raise PatchValidationError("ADD_PATTERN proposed_new_state requires node_id and expression")
        node_id = _text(state["node_id"], "proposed_new_state.node_id")
        expression = _text(state["expression"], "proposed_new_state.expression")
        if any(char.isspace() or char == "," for char in node_id):
            raise PatchValidationError("ADD_PATTERN node_id is invalid")
        return "marco_pattern", {"node_id": node_id, "expression": expression}, state
    if patch_type == "ADD_NEGATIVE_CONSTRAINT":
        if set(state) != {"node_id", "expression"} or state.get("node_id") != "_잡담":
            raise PatchValidationError("ADD_NEGATIVE_CONSTRAINT must target the MARCO [무관] node _잡담")
        expression = _text(state["expression"], "proposed_new_state.expression")
        return "marco_negative_example", {"node_id": "_잡담", "expression": expression}, state
    if patch_type == "ADD_RELATION":
        if set(state) != {"source_node", "relation", "target_node"}:
            raise PatchValidationError("ADD_RELATION proposed_new_state requires source_node, relation, and target_node")
        source = _text(state["source_node"], "proposed_new_state.source_node")
        relation = _text(state["relation"], "proposed_new_state.relation")
        target = _text(state["target_node"], "proposed_new_state.target_node")
        if (any(c.isspace() or c == "," for c in source + target)
                or any(c.isspace() for c in relation)):
            raise PatchValidationError("ADD_RELATION node or relation identifier is invalid")
        return "marco_relation", {"source_node": source, "relation": relation, "target_node": target}, state
    raise PatchValidationError(f"unsupported patch type: {patch_type}")


def validate_patch_document(doc: object, *, known_evidence_ids: set[str] | frozenset[str],
                            current_base_kg_version: str) -> None:
    if not isinstance(known_evidence_ids, (set, frozenset)) or any(
        not isinstance(item, str) or not item for item in known_evidence_ids
    ):
        raise PatchValidationError("known evidence IDs must be a set of non-empty strings")
    if not isinstance(current_base_kg_version, str) or not current_base_kg_version.startswith("kg2_"):
        raise PatchValidationError("current canonical Knowledge Version is required")
    if not isinstance(doc, dict) or set(doc) != {"schema_version", "base_kg_version", "patches"}:
        raise PatchValidationError("patch proposal must contain only schema_version, base_kg_version, and patches")
    if doc.get("schema_version") != "kg-patch-v2":
        raise PatchValidationError("unsupported schema_version; kg-patch-v2 is required")
    if doc.get("base_kg_version") != current_base_kg_version:
        raise PatchValidationError("patch base KG version does not match the active version")
    patches = doc.get("patches")
    if not isinstance(patches, list) or not patches:
        raise PatchValidationError("patches must be a non-empty array")

    patch_ids: set[str] = set()
    patch_targets: set[tuple[str, str]] = set()
    for index, patch in enumerate(patches):
        label = f"patches[{index}]"
        if not isinstance(patch, dict) or set(patch) - _PATCH_KEYS:
            raise PatchValidationError(f"{label} has unsupported fields")
        required = {"id", "type", "resource", "target", "expected_old_state", "proposed_new_state", "evidence_ids"}
        if required - set(patch):
            raise PatchValidationError(f"{label} is missing required fields")
        patch_id = _text(patch["id"], f"{label}.id")
        if patch_id in patch_ids:
            raise PatchValidationError(f"{label}.id must be unique")
        patch_ids.add(patch_id)
        patch_type = patch["type"]
        if not isinstance(patch_type, str) or patch_type not in ALLOWED_PATCH_TYPES:
            raise PatchValidationError(f"{label}.type is not allowed")
        resource = patch["resource"]
        if not isinstance(resource, str) or resource not in _RESOURCE_BY_TYPE[patch_type]:
            raise PatchValidationError(f"{label}.resource is not allowed for {patch_type}")
        target = patch["target"]
        if not isinstance(target, str) or not _TARGET_RE.fullmatch(target):
            raise PatchValidationError(f"{label}.target must be a stable tgt1 identity")
        if (resource, target) in patch_targets:
            raise PatchValidationError(f"{label} duplicates a resource target")
        patch_targets.add((resource, target))
        evidence = patch["evidence_ids"]
        if not isinstance(evidence, list) or not evidence or any(
            not isinstance(item, str) or not item or item not in known_evidence_ids for item in evidence
        ):
            raise PatchValidationError(f"{label} requires known evidence IDs")
        if len(set(evidence)) != len(evidence):
            raise PatchValidationError(f"{label}.evidence_ids must not contain duplicates")
        if "reason" in patch:
            _text(patch["reason"], f"{label}.reason")
        if patch.get("apply_automatically", False) is not False:
            raise PatchValidationError("external patches may never request automatic application")
        try:
            _canonical_json(patch["expected_old_state"])
            _canonical_json(patch["proposed_new_state"])
        except ValueError as exc:
            raise PatchValidationError(f"{label} state must be finite canonical JSON") from exc

        if patch_type == "ADJUST_WEIGHT":
            minimum, maximum = (0.0, 1.0) if resource == SEED else (
                -MAX_SEMANTIC_ROUTING_WEIGHT, MAX_SEMANTIC_ROUTING_WEIGHT
            )
            _number(patch["expected_old_state"], f"{label}.expected_old_state", minimum, maximum)
            _number(patch["proposed_new_state"], f"{label}.proposed_new_state", minimum, maximum)
            if patch["expected_old_state"] == patch["proposed_new_state"]:
                raise PatchValidationError(f"{label} does not change its weight")
        else:
            if patch["expected_old_state"] is not None:
                raise PatchValidationError(f"{label}.expected_old_state must be null for an addition")
            if not isinstance(patch["proposed_new_state"], dict):
                raise PatchValidationError(f"{label}.proposed_new_state must be an object")
            kind, identity, _ = _state_identity(patch_type, patch["proposed_new_state"])
            if stable_target_id(resource, kind, identity) != target:
                raise PatchValidationError(f"{label}.target does not identify proposed_new_state")


def _load_object(assets: Mapping[str, bytes], resource: str) -> dict:
    try:
        value = _strict_json_loads(assets[resource].decode("utf-8"))
    except (KeyError, UnicodeDecodeError, ValueError) as exc:
        raise PatchValidationError(f"canonical resource is invalid: {resource}") from exc
    if not isinstance(value, dict):
        raise PatchValidationError(f"canonical resource must be an object: {resource}")
    return value


def _encode_object(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _seed_key(entry: Mapping[str, object]) -> dict:
    return {
        "source_language": entry.get("source_language", "zh"),
        "target_language": entry.get("target_language", "ko"),
        "domain": entry.get("domain"),
        "source": entry.get("source"),
        "concept": entry.get("concept"),
        "target": entry.get("target"),
    }


def _seed_rows(doc: dict) -> list[dict]:
    if doc.get("schema_version") != "knowledge-seed-v1" or not isinstance(doc.get("entries"), list):
        raise PatchValidationError("unsupported canonical seed schema")
    rows = doc["entries"]
    if any(not isinstance(row, dict) for row in rows):
        raise PatchValidationError("canonical seed entries must be objects")
    return rows


def _assert_seed_target_absent(rows: list[dict], entry: dict) -> None:
    key = _seed_key(entry)
    for row in rows:
        existing = _seed_key(row)
        if existing == key:
            raise PatchValidationError("seed target already exists")
        if (existing["source_language"], existing["target_language"], existing["domain"], existing["source"]) == (
            key["source_language"], key["target_language"], key["domain"], key["source"]
        ):
            raise PatchValidationError("seed source already maps to another concept in this scope")


def _graph_lines(assets: Mapping[str, bytes]) -> list[str]:
    try:
        return assets[GRAPH].decode("utf-8").splitlines()
    except (KeyError, UnicodeDecodeError) as exc:
        raise PatchValidationError("canonical MARCO graph is invalid UTF-8") from exc


def _sections(lines: list[str]) -> list[tuple[str, int, int]]:
    starts = [(match.group(1).strip(), index) for index, line in enumerate(lines)
              if (match := re.fullmatch(r"\s*\[([^\]]+)\]\s*", line))]
    return [
        (name, start, starts[position + 1][1] if position + 1 < len(starts) else len(lines))
        for position, (name, start) in enumerate(starts)
    ]


def _section_range(lines: list[str], name: str) -> tuple[int, int]:
    matches = [(start, end) for section, start, end in _sections(lines) if section == name]
    if len(matches) != 1:
        raise PatchValidationError(f"MARCO graph must contain exactly one [{name}] section")
    return matches[0]


def _quoted_examples(line: str) -> tuple[str, list[str]]:
    prefix, separator, rest = line.partition(":")
    if not separator:
        raise PatchValidationError("MARCO graph entry has no colon")
    matches = list(_KG_QUOTED.finditer(rest))
    if not matches:
        raise PatchValidationError("MARCO graph entry has no quoted examples")
    residue = _KG_QUOTED.sub("", rest).replace("|", "").strip()
    if residue:
        raise PatchValidationError("MARCO graph entry uses unsupported inline syntax")
    try:
        examples = [json.loads(match.group(0)) for match in matches]
    except json.JSONDecodeError as exc:
        raise PatchValidationError("MARCO graph example is malformed") from exc
    if any(not isinstance(item, str) for item in examples):
        raise PatchValidationError("MARCO graph examples must be strings")
    return prefix.strip(), examples


def _replace_node_examples(lines: list[str], section: str, node_id: str, expression: str) -> None:
    start, end = _section_range(lines, section)
    found: list[int] = []
    for index in range(start + 1, end):
        left = lines[index].partition(":")[0].strip().lstrip("*")
        if left == node_id:
            found.append(index)
    if len(found) != 1:
        raise PatchValidationError(f"MARCO graph node must occur exactly once in [{section}]: {node_id}")
    index = found[0]
    label, examples = _quoted_examples(lines[index])
    if expression in examples:
        raise PatchValidationError("MARCO graph example already exists")
    examples.append(expression)
    lines[index] = label + ": " + " | ".join(json.dumps(value, ensure_ascii=False) for value in examples)


def _all_graph_examples(lines: list[str]) -> set[str]:
    examples: set[str] = set()
    for section, start, end in _sections(lines):
        if section not in {"개념", "사례", "무관", "공리"}:
            continue
        for line in lines[start + 1:end]:
            if ":" not in line or line.lstrip().startswith("#"):
                continue
            _, row_examples = _quoted_examples(line)
            examples.update(row_examples)
    return examples


def _graph_nodes(lines: list[str]) -> set[str]:
    nodes: set[str] = set()
    for section, start, end in _sections(lines):
        if section not in {"개념", "사례", "무관", "공리"}:
            continue
        for line in lines[start + 1:end]:
            if ":" not in line or line.lstrip().startswith("#"):
                continue
            left = line.partition(":")[0].strip()
            node = left.lstrip("*").split(" ", 1)[0]
            if node:
                nodes.add(node)
    for line in lines:
        if line.startswith("목표:"):
            nodes.add(line.split(":", 1)[1].strip())
    return nodes


def _header_relations(lines: list[str]) -> tuple[set[str], set[str], set[str]]:
    headers: dict[str, set[str]] = {"전진관계": set(), "부정관계": set(), "근거관계": set()}
    for line in lines:
        if line.lstrip().startswith("["):
            break
        for key in headers:
            prefix = key + ":"
            if line.startswith(prefix):
                headers[key].update(value.strip() for value in line[len(prefix):].split(",") if value.strip())
    return headers["전진관계"], headers["부정관계"], headers["근거관계"]


def _existing_edges(lines: list[str]) -> list[tuple[str, str, str]]:
    start, end = _section_range(lines, "논증")
    edges = []
    for line in lines[start + 1:end]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _KG_EDGE.fullmatch(stripped)
        if not match:
            raise PatchValidationError("MARCO graph contains an invalid [논증] edge")
        source, relation, targets = match.groups()
        for target in targets.split(","):
            target = target.strip()
            if target:
                edges.append((source, relation, target))
    return edges


def _append_relation(lines: list[str], source: str, relation: str, target: str) -> None:
    forward, negative, evidence = _header_relations(lines)
    if relation not in forward | negative | evidence:
        raise PatchValidationError("ADD_RELATION relation must be declared in MARCO graph headers")
    nodes = _graph_nodes(lines)
    if source not in nodes or target not in nodes:
        raise PatchValidationError("ADD_RELATION endpoints must exist in the MARCO graph")
    edges = _existing_edges(lines)
    if (source, relation, target) in edges:
        raise PatchValidationError("MARCO relation already exists")
    if relation in forward and any(s == source and t == target and r in negative for s, r, t in edges):
        raise PatchValidationError("MARCO relation conflicts with an existing negative relation")
    if relation in negative and any(s == source and t == target and r in forward for s, r, t in edges):
        raise PatchValidationError("MARCO negative relation conflicts with an existing forward relation")
    start, end = _section_range(lines, "논증")
    insert_at = end
    while insert_at > start + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    lines.insert(insert_at, f"{source} -{relation}-> {target}")


def _apply_adjust_weight(assets: dict[str, bytes], patch: dict) -> None:
    resource, target = patch["resource"], patch["target"]
    new = float(patch["proposed_new_state"])
    if resource == SEED:
        doc = _load_object(assets, SEED)
        rows = _seed_rows(doc)
        matches = [row for row in rows if stable_target_id(SEED, "seed_entry", _seed_key(row)) == target]
        if len(matches) != 1:
            raise PatchValidationError("ADJUST_WEIGHT seed target is missing or ambiguous")
        row = matches[0]
        old = _number(row.get("confidence", 1.0), "canonical lexical confidence", 0.0, 1.0)
        if old != patch["expected_old_state"]:
            raise PatchValidationError("ADJUST_WEIGHT expected lexical confidence does not match")
        row["confidence"] = new
        assets[SEED] = _encode_object(doc)
        return

    doc = _load_object(assets, FRAME_MAP)
    frames = doc.get("frames")
    if doc.get("schema_version") != "marco-frame-map-v1" or not isinstance(frames, dict):
        raise PatchValidationError("unsupported canonical frame-map schema")
    matches = [
        (node_id, spec) for node_id, spec in frames.items()
        if isinstance(spec, dict) and stable_target_id(FRAME_MAP, "semantic_routing_weight", {"node_id": node_id}) == target
    ]
    if len(matches) != 1:
        raise PatchValidationError("ADJUST_WEIGHT frame-map target is missing or ambiguous")
    _, spec = matches[0]
    old = _number(spec.get("routing_weight", 0.0), "canonical semantic routing weight",
                  -MAX_SEMANTIC_ROUTING_WEIGHT, MAX_SEMANTIC_ROUTING_WEIGHT)
    if old != patch["expected_old_state"]:
        raise PatchValidationError("ADJUST_WEIGHT expected semantic routing weight does not match")
    spec["routing_weight"] = new
    assets[FRAME_MAP] = _encode_object(doc)


def apply_patch_operations(assets: Mapping[str, bytes], proposal: dict) -> dict[str, bytes]:
    result = dict(assets)
    used_targets: set[tuple[str, str]] = set()
    for patch in proposal["patches"]:
        patch_type, resource, target = patch["type"], patch["resource"], patch["target"]
        target_key = (resource, target)
        if target_key in used_targets:
            raise PatchValidationError("proposal repeats a canonical resource target")
        used_targets.add(target_key)
        if patch_type in {"ADD_ALIAS", "ADD_SENSE", "ADD_DOMAIN_SENSE"}:
            kind, identity, entry = _state_identity(patch_type, patch["proposed_new_state"])
            if stable_target_id(resource, kind, identity) != target:
                raise PatchValidationError("seed target identity does not match proposed state")
            doc = _load_object(result, SEED)
            rows = _seed_rows(doc)
            _assert_seed_target_absent(rows, entry)
            if patch_type == "ADD_ALIAS":
                matches = [row for row in rows if row.get("concept") == entry["concept"]
                           and row.get("target") == entry["target"]
                           and row.get("source_language", "zh") == entry["source_language"]
                           and row.get("target_language", "ko") == entry["target_language"]
                           and row.get("domain") == entry["domain"]]
                if not matches:
                    raise PatchValidationError("ADD_ALIAS must reuse an existing concept and target")
            rows.append(entry)
            result[SEED] = _encode_object(doc)
        elif patch_type in {"ADD_PATTERN", "ADD_NEGATIVE_CONSTRAINT"}:
            kind, identity, state = _state_identity(patch_type, patch["proposed_new_state"])
            if stable_target_id(resource, kind, identity) != target:
                raise PatchValidationError("MARCO example target identity does not match proposed state")
            expression, node_id = state["expression"], state["node_id"]
            if any(char in expression for char in ('"', "|", "\n", "\r", "\\")):
                raise PatchValidationError("MARCO graph example contains unsupported syntax characters")
            lines = _graph_lines(result)
            if expression in _all_graph_examples(lines):
                raise PatchValidationError("MARCO graph expression already exists")
            _replace_node_examples(lines, "개념" if patch_type == "ADD_PATTERN" else "무관", node_id, expression)
            result[GRAPH] = ("\n".join(lines) + "\n").encode("utf-8")
        elif patch_type == "ADD_RELATION":
            kind, identity, state = _state_identity(patch_type, patch["proposed_new_state"])
            if stable_target_id(resource, kind, identity) != target:
                raise PatchValidationError("MARCO relation target identity does not match proposed state")
            lines = _graph_lines(result)
            _append_relation(lines, state["source_node"], state["relation"], state["target_node"])
            result[GRAPH] = ("\n".join(lines) + "\n").encode("utf-8")
        elif patch_type == "ADJUST_WEIGHT":
            if resource == FRAME_MAP and not _TARGET_RE.fullmatch(target):
                raise PatchValidationError("semantic routing target is invalid")
            _apply_adjust_weight(result, patch)
        else:
            raise PatchValidationError(f"unsupported patch type: {patch_type}")
    return result
