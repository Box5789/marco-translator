# Marco Translator — external KG maintenance instructions

You review exported translation evidence and return a proposal only. You cannot apply a patch or modify the active Knowledge Version.

Return one `kg-patch-v2` JSON document that conforms to `schemas/kg-patch.schema.json`. Set `base_kg_version` to the exact `manifest.base_kg.version_id` from this package. Keep all seven operation names:

- `ADD_ALIAS`: add a seed entry that reuses an existing concept, target, language pair, and domain.
- `ADD_SENSE`: add a global seed entry with `domain: null`.
- `ADD_DOMAIN_SENSE`: add a seed entry with a non-empty domain.
- `ADD_PATTERN`: add an example to an existing MARCO graph node in `[개념]`.
- `ADD_NEGATIVE_CONSTRAINT`: add an off-topic example to the existing `[무관]` node `_잡담`. This is not a `부정관계` edge.
- `ADD_RELATION`: add one `[논증]` edge between existing graph nodes, using a relation declared in the graph header.
- `ADJUST_WEIGHT`: change either a seed entry's lexical `confidence` (0..1) or a frame-map node's semantic `routing_weight` (-0.10..0.10). Do not use it for a MARCO edge or global threshold.

Each patch must include `id`, `type`, exact `resource`, stable `target`, `expected_old_state`, `proposed_new_state`, and one or more exact `evidence_ids` from `translation_logs.jsonl`.

Resources are fixed:

- Seed operations use `knowledge/seed.zh-ko.json`.
- `ADD_PATTERN`, `ADD_NEGATIVE_CONSTRAINT`, and `ADD_RELATION` use `marco/graphs/graph_zh_ko_gaming_semantics.kg`.
- Semantic `ADJUST_WEIGHT` uses `knowledge/marco-frame-map.zh-ko.json`.

`target` is `tgt1_` plus the lowercase SHA-256 of canonical UTF-8 JSON with sorted keys and no insignificant whitespace. Hash this object:

```json
{"resource":"RESOURCE","kind":"KIND","identity":{}}
```

Use these exact kinds and identities:

- Seed entry (including lexical weight): kind `seed_entry`; identity fields are `source_language`, `target_language`, `domain`, `source`, `concept`, `target`.
- Pattern: kind `marco_pattern`; identity fields are `node_id`, `expression`.
- Off-topic example: kind `marco_negative_example`; identity fields are `node_id: "_잡담"`, `expression`.
- Relation: kind `marco_relation`; identity fields are `source_node`, `relation`, `target_node`.
- Semantic route weight: kind `semantic_routing_weight`; identity field is `node_id`.

For additions, `expected_old_state` must be `null`; `proposed_new_state` contains the complete added entry/example/edge. For `ADJUST_WEIGHT`, both states are numbers and `expected_old_state` must exactly match the current value shown by the package snapshot. An absent frame-map `routing_weight` has old value `0`.

Rules:

1. Cite only evidence IDs present in the package. Preserve the exact base version.
2. Prefer an existing concept to creating a new concept. Keep literal and domain-specific senses separate.
3. Do not infer a durable meaning from one occurrence unless the user explicitly corrected it and the operation remains appropriately scoped.
4. Never request automatic application. Omit `apply_automatically` or set it to `false`.
5. Do not rewrite the graph. Propose the smallest evidence-backed patch.
6. If evidence is contradictory or insufficient, omit that change.
7. `ADJUST_WEIGHT` changes lexical confidence or the bounded adapter trace-rescue margin only. It never changes MARCO's selected node.
