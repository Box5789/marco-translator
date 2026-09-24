# Automatic learning policy

Runtime learning is deliberately asymmetric.

## Three mutable layers

### Session state

Memory-only. It may learn temporary entity bindings and topic context, and is
discarded when the session is cleared.

Example:

```text
"Luka" -> "루카"
scope: session s1 only
```

A session binding has higher runtime precedence than exact Translation Memory,
because it is an explicit temporary instruction.

### User overlay

Persistent but user-scoped. It may contain:

- explicit terminology preferences
- approved phrase preferences proposed from repeated corrections
- OCR correction profiles
- bounded routing weights

Nothing in this layer changes another user's knowledge or Base KG.

### Translation Memory

An explicit correction is immediately safe to store as an exact-match TM entry.
This is supervised data: the user supplied the corrected target text directly.

## Repeated corrections

The same source/target correction is counted. At the configured threshold
(default: 3), the runtime creates a **pending** `ADD_USER_PHRASE` proposal.

It does not auto-apply the proposal.

```text
correction #1 -> TM only
correction #2 -> TM only
correction #3 -> TM + pending User Overlay proposal
                         |
                         +-- user accepts -> persistent overlay terminology
                         +-- user rejects -> no knowledge change
```

This is intentionally different from the external-LLM maintenance plane:
User Overlay proposals are local preference changes; Base KG semantic changes
still require the external patch workflow and regression validation.

## Routing-weight adaptation

User-specific routing bias is bounded (default ±0.10), versioned as reversible
events, and never creates a node or sense.

For MARCO's P1 adapter, a route bias can only affect the strict trace-rescue
threshold for an already-mapped semantic node. A rejected result is never
rescued. Rolling back the event removes the learned bias without changing the
Base KG or frame map.

The Base KG has a separate semantic `routing_weight` on a frame-map node, bounded
to `-0.10..0.10`. It adjusts that same UNKNOWN trace-rescue margin and is versioned
only through an approved Knowledge Version patch. It does not select a node or
change a seed entry's lexical `confidence`. When Base KG and user bias are combined,
the total applied margin bias remains within `-0.10..0.10`.

## May update automatically

- exact Translation Memory after an explicit correction
- session context
- correction counters
- bounded routing-weight events after explicit route feedback

## Requires user approval

- pending User Overlay phrase / terminology proposals

## Must not update automatically

- Base KG topology
- new global concepts
- deletion or redefinition of existing concepts
- global aliases
- domain-wide negative constraints
- changes affecting other users

The maintenance plane may propose these operations, but a user-approved
validated patch is required.
