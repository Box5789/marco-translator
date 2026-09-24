# Term-slot propagation — scoped correction

## Purpose and current coverage

A selected personal term must affect the normal sentence output, not only
`SemanticFrame.terms`. This first change declares `entity <- 狙` for the existing
`西边有狙` / `ZH_GAMING_WEST_SNIPER` sentence. It does not add general translation,
new graph nodes, automatic term-to-slot inference, or a shared memory service.
Other authored patterns remain unchanged; they need their own reviewed binding
before an embedded term can override an authored slot. Inflected phrases such
as `送 -> 죽어주면` are not generalized from a lexical substitution.

## Binding contract

`Pattern.slot_terms` and each MARCO frame-map entry accept an optional mapping:

```json
"slot_terms": {"entity": "狙"}
```

The key names an existing slot. The value is an exact source expression whose
term decision has already been selected by the current knowledge store.
Both resolvers call the same pure `bind_term_slots` helper before returning the
frame. Only an unambiguous selected `user` or `session` term replaces the slot
value. A missing personal term leaves the authored default intact. Base terms
do not overwrite context-specific or inflected defaults.

The realizer still only renders the resolved frame. It does not choose terms,
read a database, perform source/target substring replacement, or mutate defaults.
Layer/domain/language/session precedence remains the knowledge store's job.
Malformed binding configuration or ambiguous/blank selected personal targets
raise `ValueError`; they are not silently used to invent output.

## Compatibility and evidence

This is optional authoring metadata, not a new SemanticFrame or database schema.
Old patterns and frame-map-v1 files without `slot_terms` keep their prior output.
Older readers ignore this optional field and therefore do not provide the new
personalized slot behavior. They are readable, not behaviorally equivalent.
No migration or runtime write to Base KG/frame maps is performed.

`TranslationResult.path`, `frame.terms` (including its selected layer) and the
resolved `frame.slots` expose the observed result with no new log schema. TM and
exact session hits intentionally have no resolver frame; never count a TM hit
as evidence that slot binding ran. The authoring map supplies the slot/source
relationship; this is not a general provenance ledger.

## Reversal and limits

Disabling an Overlay term removes only that term's effect. A sentence-specific
TM correction remains authoritative and is not cleared as a side effect.
Clearing a session restores the remaining user/base selection. Reopening the
same SQLite Overlay preserves active/disabled state. Runtime files are not
rewritten, and old result objects retain their values.

P1-D transactions/rollback, neural fallback safety, general particle/inflection
handling, confidence calibration, native platforms and engineering-skill changes
are outside this fix. A selected terminology target is explicit user input,
not proof that a synonym preserves the concept in every linguistic context.
