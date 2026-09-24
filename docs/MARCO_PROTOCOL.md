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

A known mapped node is accepted directly from `answered`, `needs_input` or `observed` results. `rejected` is never promoted into a translation.

MARCO's general input-understanding layer can currently return `unknown` for a source language it does not structurally parse even when the translator graph matcher has selected a semantic node exactly. The translator therefore has one deliberately narrow rescue path: an `unknown` result is accepted only when the public `judge` trace selects a node present in the frame map and its separation margin is at least `0.90`. The frame confidence is capped by that margin. Low-margin or unmapped `unknown` results stay unresolved.

This is not a free-form fallback: the adapter still cannot invent a node, a frame, terminology or target text. It only accepts a strongly separated node already declared in the versioned translator pack.

## Frame map

`knowledge/marco-frame-map.zh-ko.json` maps a selected MARCO node to deterministic frame metadata:

- source/target language pair
- domain scope
- intent/style
- deterministic template and slots
- upper-bound confidence

Terminology decisions remain in `knowledge/seed.zh-ko.json`, so semantic routing and target terminology are versioned separately.

The optional `routing_weight` belongs to the frame-map node. It is bounded to `-0.10..0.10`
and adjusts only the mapped-node UNKNOWN trace-rescue margin. It cannot change the selected
node, rescue a rejected result, or change lexical `confidence` in the seed. User Overlay bias
remains user-scoped and is combined under the same total bound.

## Unknown contract

If MARCO returns `rejected`, returns a low-confidence/unmapped `unknown`, selects an unmapped node, or the frame is outside the request's language/domain scope, the resolver returns an unresolved frame. The neural realizer is not allowed to invent a meaning for that frame.

## Building the P1 model

With a MARCO checkout available:

```bash
pip install -e /path/to/Marco
mco compile marco -o build/zh-ko-gaming.mco \
  --name marco-translator-zh-ko-gaming \
  --graph 'graphs/graph_zh_ko_gaming_semantics.kg' \
  --marco-root /path/to/Marco
```

The committed `.kg` source is authoritative. Generated `.mco` files are derived artifacts and
are not committed to the source tree. A canonical Knowledge Version also records the frame map,
the compiler-consumed style/axiom JSON inputs, build recipe hashes, clean MARCO checkout
revision, `mco`/Python/dependency/platform details, and the actual `.mco` digest and size.
The version store retains those `.mco` bytes as a verified derived runtime artifact.
