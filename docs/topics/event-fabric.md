# Topic: Event Fabric

> **Topic-visibility unit.** The canonical event-envelope system every cross-component JSONL write
> flows through — the telemetry/audit backbone that makes replay comparable and auditable.
>
> Created: 2026-06-05 · Updated: 2026-06-05 · Status: living

## In plain language
Whenever any component writes a record meant for another component (telemetry, decision snapshots,
drift audits), it wraps it in **one canonical envelope** so every line carries the same metadata:
a unique id, a monotonic generation number (for total ordering within a run), the event type, the
instrument, an ISO timestamp, a parent id (for causal chains), and a **schema hash**. The rule is
"consolidate on the fabric, never fork your own logging schema." The schema hash is a *passive* drift
detector — no runtime code branches on it; offline tools compare it to the current feature hash.

## Code covered
- [`src/events/event_fabric.py:119`](../../src/events/event_fabric.py) — `make_event_envelope` — the primary API; returns the envelope dict (event_id, generation, event_type, instrument, source, timestamp, schema_hash, parent_event_id, payload).
- [`src/events/event_fabric.py:56`](../../src/events/event_fabric.py) — `EventType` — the event taxonomy (DECISION_SNAPSHOT, ENGINE_TELEMETRY, DECISION_LINEAGE, DRIFT_AUDIT, COGNITIVE_TELEMETRY, REGIME_CLASSIFICATION, STATE_TRANSITION, LLM_ADVISORY, …).
- [`src/events/event_fabric.py:73`](../../src/events/event_fabric.py) — `_GenerationCounter` — thread-safe monotonic counter (`.next()` at :83); per-process, not persisted.
- [`src/events/event_fabric.py:104`](../../src/events/event_fabric.py) — `_resolve_schema_hash` — pulls `FEATURE_ORDER_HASH`; fail-open `""`; cached for the process.

## Ins / Outs
- **Ins:** `event_type`, `instrument`, `source`, `payload` (the component's own dict), optional `parent_event_id`. Schema hash is auto-resolved from `features.feature_schema`.
- **Outs:** a JSON-serialisable envelope dict appended to the component's JSONL channel (e.g. `ENGINE_TELEMETRY`, `DECISION_LINEAGE`, `DRIFT_AUDIT`). Consumed by offline replay/audit tooling and the cognitive sidecar.

## Entry points & validations
- **Reached via:** library call, not a CLI. Producers include `core.engine_runner` (decision/engine telemetry), `config_layer.crt_engine_v2` (trade-lifecycle), `replay.replay_drift_governor` (drift audit), `utils.engine_telemetry` / `utils.trade_logger`.
- **Validated by:** the invariants in the module docstring — every cross-component write uses the envelope; `generation` strictly monotonic per process; `event_fabric` is always on (no kill switch); schema_hash is the passive drift signal.

## Tests
- [`tests/events/test_event_fabric.py`](../../tests/events/test_event_fabric.py) — envelope fields, generation monotonicity, thread safety (concurrent), schema-hash caching, parent-id chains, event-id uniqueness, JSON serialisability.

## Fits in architecture
The substrate under all telemetry in [`event-taxonomy.md`](../architecture/event-taxonomy.md) and the
replay-governance story ([`replay-governance.md`](../architecture/replay-governance.md)) — it's how
the five governance questions ("can this be audited / can an LLM reason about this event") are met. It
is the **consolidation point** named in the migration doctrine (`assistant_project.md`).

## Discussion (filled in-session)
- **Risks:** 2026-06-05 — schema_hash is passive; a drifted record is only caught if someone runs the offline audit. No runtime guard by design.
- **Ambiguities:** 2026-06-05 — `generation` is per-process and resets on restart; it orders within a run, not across runs (replay comparison deliberately ignores `event_id`/`generation`/wall-clock).
- **Enhancements:** 2026-06-05 — several consumers (cognitive bus, replay memory) are sidecar-only today (F-012); the fabric carries their telemetry but the spine doesn't consume it back.
