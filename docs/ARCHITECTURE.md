# Architecture

## 1. Runtime plane

The runtime plane must be usable with no network connection.

```text
Source Adapter -> Normalizer -> Exact TM -> Semantic Resolver -> Realizer -> Output
                                      |             |              |
                                      |             |              +-- rule first
                                      |             |              +-- tiny neural fallback
                                      |             +-- Base KG + Overlay + Session weights
                                      +-- user-approved / user-corrected translations
```

### Semantic ownership

The neural realizer must not receive raw source text as the sole authority for meaning. Its input is a semantic frame plus constrained terminology. The source text may be included later for style preservation, but conflicts are resolved in favor of the grounded frame.

### Knowledge precedence

1. Explicit session binding
2. Explicit user correction / user terminology overlay
3. Domain-specific verified sense
4. Base sense
5. Unknown

A miss is preferable to a fluent hallucination.

## 2. Knowledge layers

### Base KG

Versioned and verified. Runtime read-only. Topology changes require an approved maintenance patch.

### User Overlay KG

May store explicit corrections, terminology preferences, OCR corrections and provisional local senses. Automatic writes must remain reversible and scoped to the user.

### Session State

Ephemeral named entities, temporary domain hints, active topic and routing weights. Safe to discard.

### Translation Memory

Exact-match cache in P1. User corrections can be written immediately because they are explicit supervision, not inferred world knowledge.

## 3. Realization

Priority:

1. exact TM
2. deterministic template / grammar
3. tiny neural realizer
4. unresolved

P1 does not call a general-purpose LLM from the runtime.

The eventual local model size/runtime is a benchmark decision. A 100–300M INT4 realizer remains a candidate target, not a fixed architecture. P1-E must measure semantic preservation, terminology compliance, latency, peak RAM, model size and neural invocation rate on the same macOS workload before a product decision.

## 4. Maintenance plane

The user explicitly exports logs. A capable external LLM analyzes the package and returns a schema-valid patch proposal. The runtime never sends logs automatically.

Validation order:

1. JSON schema
2. allowed operation type
3. referenced evidence exists
4. exact active `kg2_` Knowledge Version check
5. resource-scoped stable target and expected-old-state check
6. operation-specific seed / MARCO graph conflict and scope checks
7. rebuild the derived `.mco` from the versioned graph and compiler assets
8. replay the registered translation and literal/domain corpus
9. reject regressed or failed oracle cases
10. human approval of the exact replayed candidate version ID
11. one SQLite transaction stores the immutable asset snapshot, verified derived `.mco`, lineage and active pointer

The canonical version contains `knowledge/seed.zh-ko.json`, the translator MARCO `.kg`,
`knowledge/marco-frame-map.zh-ko.json`, all consumed `marco/styles/*.json` and
`marco/axioms/*.json`, build provenance and the actual derived `.mco` digest. The `.mco`
bytes are retained and verified as a derived runtime artifact. A local materialized directory
is a disposable cache; the SQLite snapshot is canonical.

`kg-patch-v2` retains the seven operations but requires a closed `resource`, stable target,
`expected_old_state`, `proposed_new_state` and evidence IDs on each operation. Seed
`confidence` remains lexical confidence. Frame-map `routing_weight` is semantic and only
adjusts the bounded MARCO UNKNOWN trace-rescue margin for an already mapped node.

P1-D owns the exact package, evidence identity, Knowledge Version, transaction and rollback contracts.

## 5. MARCO integration

Use MARCO through its stable `mco` API rather than internal modules. A translator-specific `.mco` model selects grounded semantic identity that the adapter maps into a `SemanticFrame`. The current Python `MarcoResolver` is the reference integration boundary.

No code from MARCO is vendored in this repository. MARCO is Apache-2.0 and is treated as an external engine/runtime dependency during the reference phase.

## 6. Cross-platform boundary

Target product platforms are:
- macOS
- Windows
- Android
- iOS

Current direct validation is macOS-first.

Shared semantic, persistence and maintenance contracts must not require platform UI types or Python object identity. Screen capture, OCR, overlay/UI, model acceleration, permissions and lifecycle are expected platform variation points.

The shared native core implementation technology is intentionally undecided until P1-F. See `docs/PLATFORM_STRATEGY.md`.
