# MARCO semantic resolver protocol

Marco Translator uses MARCO as a **semantic selector**, not as a natural-language generator.

## Why the adapter reads MARCO's selected node

MARCO's public `mco` API exposes stable result status, evidence and trace. The compatibility backend records the selected graph node in the `judge` trace step (`detail.winner`) and may also expose it as `graph_node` evidence.

The runtime therefore sends the **raw source utterance** to a translator-specific `.mco` model. It does not wrap the utterance in JSON and it does not ask MARCO to generate a semantic-frame JSON document.

```text
source utterance
      |
      v
MARCO .mco model
      |
      +-- graph routing
      +-- node selection
      +-- evidence / trace
      |
      v
stable semantic node id
      |
      v
marco-frame-map-v1
      |
      v
SemanticFrame
      |
      +-- deterministic realizer
      +-- tiny neural realizer (fallback)
```

This preserves the system boundary: MARCO decides **which known meaning** is grounded; the target-language renderer decides **how to say it**.

## Accepted MARCO outcomes

A known mapped node is accepted from `answered`, `needs_input` or `observed` results. `unknown` and `rejected` are never promoted into a translation merely because a low-confidence winner happened to exist in a trace.

P1 uses `needs_input` intentionally: the semantic-routing graph is not trying to satisfy a conversational goal. It uses MARCO's matching/routing machinery to select a stable semantic node.

## Frame map

`knowledge/marco-frame-map.zh-ko.json` maps a selected MARCO node to deterministic frame metadata:

- source/target language pair
- domain scope
- intent/style
- deterministic template and slots
- upper-bound confidence

Terminology decisions remain in `knowledge/seed.zh-ko.json`, so semantic routing and target terminology are versioned separately.

## Unknown contract

If MARCO returns `unknown` / `rejected`, selects an unmapped node, or the frame is outside the request's language/domain scope, the resolver returns an unresolved frame. The neural realizer is not allowed to invent a meaning for that frame.

## Building the P1 model

With a MARCO checkout available:

```bash
pip install -e /path/to/Marco
mco compile marco -o build/zh-ko-gaming.mco \
  --name marco-translator-zh-ko-gaming \
  --graph 'graphs/graph_zh_ko_gaming_semantics.kg' \
  --marco-root /path/to/Marco
```

The committed `.kg` source is authoritative. Generated `.mco` files are build artifacts and are not committed.
