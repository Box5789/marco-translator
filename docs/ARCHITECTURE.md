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

Target for the eventual in-app model: roughly 100–300M parameters, INT4, short semantic-frame input, 10–30 token output. This is a benchmark target, not a fixed architecture.

## 4. Maintenance plane

The user explicitly exports logs. A capable external LLM analyzes the package and returns a schema-valid patch proposal. The runtime never sends logs automatically.

Validation order:

1. JSON schema
2. allowed operation type
3. referenced evidence exists
4. base KG version check
5. graph conflict / scope check
6. corpus replay
7. regression thresholds
8. human diff and approval
9. create a new KG version

## 5. MARCO integration

Use MARCO through its stable `mco` API rather than internal modules. A translator-specific `.mco` model should return a compact, grounded semantic frame. The current Python `MarcoResolver` is the integration boundary; native/mobile implementations should preserve the contract rather than embed Python internals.

No code from MARCO is vendored in this repository. MARCO is Apache-2.0 and is treated as an external engine/runtime dependency during the reference phase.
