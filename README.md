# Marco Translator

A deterministic-first, offline translation engine built around **MARCO** as the semantic memory / terminology resolver, with a **tiny in-app neural realizer** used only when rule-based realization is insufficient.

The project is intentionally split into two planes:

- **Runtime plane**: offline, fast, read-mostly knowledge, small model, mobile-friendly.
- **Maintenance plane**: logs are exported by the user and analyzed by an external capable LLM; the LLM can only propose a schema-valid KG patch. The app validates, previews and applies patches only after explicit user approval.

## Core principles

1. The in-app model does **not** decide meaning. It only renders an already-resolved semantic frame naturally in the target language.
2. Base knowledge is not self-modified at runtime.
3. Safe adaptive state is allowed: translation memory, user terminology, OCR corrections, session context and routing weights.
4. New concepts / senses / relations are maintenance operations, not runtime learning.
5. Every important decision can be logged and replayed for regression testing.
6. Mobile constraints are first-class: short contexts, INT4-friendly realizer target, local-only runtime, low neural invocation rate.

## Initial target

P1 proves the architecture with **Chinese → Korean** and a gaming domain pack (WARDOGS chat samples are used as the first regression corpus). The design itself is language-agnostic.

## Pipeline

```text
Input / OCR / Clipboard
        |
        v
   Normalizer
        |
        v
Translation Memory ---- hit ---> result
        |
       miss
        v
MARCO Semantic Resolver
        |
        v
 Universal Semantic Frame
        |
        +----> Rule Realizer ----> result
        |
        +----> Tiny Neural Realizer (fallback only)
        |
        v
  Translation Log
```

## Knowledge layers

```text
Base KG (versioned, verified, runtime read-only)
   ^
   | user-approved validated patch
User Overlay KG (preferences / explicit corrections / provisional local knowledge)
   ^
   |
Session State (temporary context, expires automatically)
```

## Maintenance workflow

```text
translation logs
      |
      v
[Export analysis package]
      |
      v
external LLM chosen by user
      |
      v
kg-patch.json (proposal only)
      |
      v
schema + reference + conflict + regression validation
      |
      v
human diff / approval
      |
      v
new KG version
```

See `docs/ARCHITECTURE.md` and `docs/P1.md`.

## Prototype CLI

```bash
python -m marco_translator.cli "西边有狙" --domain gaming
python -m marco_translator.cli "家里有人" --domain gaming --json
```

The current prototype is a **reference implementation** of the runtime boundaries. MARCO's stable `mco` API is wrapped behind an adapter so the mobile/native runtime can later replace the Python reference without changing the contracts.

## MARCO adapter contract

The P1 adapter uses MARCO as a **semantic selector**. Raw source text is sent to the `.mco` model; the selected graph node is read from the public `mco.Result` trace/evidence contract and deterministically mapped to a `SemanticFrame`. MARCO is not asked to generate Korean or free-form semantic JSON.

See `docs/MARCO_PROTOCOL.md` and `marco/graphs/graph_zh_ko_gaming_semantics.kg`.


## Adaptive user state

P1-C keeps personal adaptation outside the verified Base KG.

```python
from marco_translator import (
    KnowledgeStore, LayeredKnowledgeStore, SessionStateStore,
    SQLiteUserOverlay, TranslationRequest, Translator,
)
from marco_translator.resolver import DeterministicResolver
from marco_translator.tm import SQLiteTranslationMemory

base = KnowledgeStore.from_json("knowledge/seed.zh-ko.json")
overlay = SQLiteUserOverlay("user-overlay.db")
sessions = SessionStateStore()
knowledge = LayeredKnowledgeStore(base, user_overlay=overlay, sessions=sessions)

translator = Translator(
    resolver=DeterministicResolver(knowledge),
    tm=SQLiteTranslationMemory("translation-memory.db"),
    user_overlay=overlay,
    sessions=sessions,
)

request = TranslationRequest("西边有狙", domain="gaming")
result = translator.translate(request)
translator.correct(request, "서쪽 스나 있음", result=result)
```

Explicit corrections go straight to exact Translation Memory. Repeated identical
corrections create a **pending** local overlay proposal; the runtime does not
auto-approve it. Session entity bindings are memory-only. User routing bias is
bounded and reversible. See `docs/AUTOMATIC_LEARNING.md`.
