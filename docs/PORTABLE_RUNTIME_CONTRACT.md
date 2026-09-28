# Portable Runtime Contract v1

## Identity

- Contract: `marco-runtime.v1`
- Normalization: `NFKC-UCD16.0.0+PY-RE-WHITESPACE-v1`
- Conformance fixture: `runtime/fixtures/conformance-v1.json`
- Fixture SHA-256: `b099cfc595104ee80edbf5adc0b247587c9fcf1955a5f04e53a435e5748e845b`
- JSON Schema: `schemas/marco-runtime-v1.schema.json`

The fixture contains seven Python-reference outcomes: five known deterministic frames, one unresolved input, and one full-width/NFKC plus Unicode-whitespace case. Python conformance uses Python 3.14 / UCD 16.0.0. Rust embeds the same fixture and checks the complete response values. Native host smoke checks the same fixture bytes and contract identity.

## Wire behavior

Each request is one UTF-8 JSON object with `contract_version`, `operation`, and operation-specific fields. Translation requests always carry `text`, source/target languages, `domain`, `style`, and `session_id`; nullable fields are explicit JSON `null`. Unknown properties are rejected. `correct.generated_text` may be omitted or `null`.

Every successful response is an object containing `contract_version` and `result`. A translation result contains `source_text`, `translated_text`, `path`, `confidence`, nullable `frame`, and warning codes. Python-only `metadata`, dataclass identity, exception text, timestamps, and generated IDs are not conformance fields. The unresolved warning is the stable code `no_grounded_deterministic_translation`.

Supported operations are `translate`, `correct`, `bind_session_entity`, `unbind_session_entity`, `clear_session`, `add_terminology`, `disable_terminology`, `pending_proposals`, `approve_proposal`, `reject_proposal`, `routing_weight`, `adjust_routing_weight`, and `rollback_routing_weight`. Request and response shapes are defined in the JSON Schema.

## Normalization and safety

The core first applies NFKC using Unicode 16.0.0 data, then collapses each run of Python `re` `\s` characters to one ASCII space and strips the ends. The profile's whitespace set is pinned by conformance across all Unicode scalar values.

Only a grounded deterministic result is emitted by the default slice. The resolver is a replaceable interface; the shipped resolver recognizes frozen fixtures and reports other ungrounded characters as unresolved. The neural-realizer interface is replaceable but defaults to null, and orchestration never calls it while unresolved content remains. Host code does not implement normalization, semantic resolution, or realization.

The C ABI accepts a non-empty UTF-8 database path of at most 1 MiB and JSON input of at most 1 MiB. Responses are capped at 4 MiB. Boundary failures return stable numeric statuses from `runtime/include/marco_runtime.h`; they do not return an error JSON envelope. `marco_runtime_status_name` returns `unknown_status` for any unrecognized integer.

## SQLite persistence

The shared SQLite file may contain the existing `tm`, `terminology`, `corrections`, `overlay_proposals`, `routing_weights`, and `routing_weight_events` tables. Null domain is stored as an empty string. `PRAGMA user_version=0` is the pre-gate layout; a recognized table layout is upgraded transactionally to `1`. Version `1` is accepted after the same structure checks. Unknown versions, incompatible columns/primary keys, or a missing proposal identity constraint are rejected without overwriting the file.

Exact TM entries and approved User Overlay state persist. A correction writes the exact TM entry immediately. Three repeated corrections can create one pending proposal; only an explicit approval adds the user terminology. Route weights remain bounded to `[-0.1, 0.1]` and each change has one-use rollback. Session bindings are process-memory state and disappear on close. Base KG is read-only and is not stored in this runtime database contract.

The Python `SQLiteTranslationMemory` and `SQLiteUserOverlay` stores use the same table shapes and version marker. The interop smoke seeds these stores in Python, reads the file in Rust, writes from Rust, then reopens it in Python.

## C ABI lifecycle

`marco_runtime_open` returns an opaque handle on success. `marco_runtime_process_json` serializes calls on that handle and returns library-owned NUL-terminated JSON; release every non-null result exactly once with `marco_runtime_string_free`. `marco_runtime_close` releases a handle exactly once. A handle must not be closed while a call is active or reused afterward. `runtime/include/marco_runtime.h` is the host declaration.

Hosts own paths, process lifecycle, and platform API calls. The semantic and persistence rules remain behind this C ABI. The core performs no network calls and has no Python or MARCO-module dependency at runtime.
