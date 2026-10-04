# Run Identity Governance (EFAP) — Design Authority

Status: **IMPLEMENTED (RFC `CH-run-identity-efap`, 2026-09-19)** · Stage 0/2 · Owner: `src/governance/run_identity.py`

## SYNOPSIS — phase status

```
Phase 1 (Identity Authority + Join Gate) … COMPLETE
Phase 2 (Derived Provenance Chain) ………… OPEN
Phase 3 (LLM Enforcement) …………………… PARTIALLY COMPLETE (documented, not universally enforced)
```

- **Phase 1 COMPLETE** — supersedes the README "status" line above: identity authority, manifest,
  always-on stamping, join gate, reason codes, and acceptance evidence are live.
- **Phase 2 OPEN** — `derived_from` propagation onto `results/analysis/*`, cross-tabs, funnels,
  research/LLM outputs; source→derived registry index; read-only backfill scanner; inherited
  `identity_status`; comparison-vs-strategy join distinction.
- **Phase 3 PARTIALLY COMPLETE** — the CONTEXT mandate is written
  (`docs/governance/LLM_WORKFLOW_CONTEXT_MANDATE_EFAP.md`) but not yet enforced across all LLM
  run-contexts.

Acceptance evidence: `docs/governance/build_manifests/CH-run-identity-efap.acceptance.json`
(scope recorded: proves UNVERIFIED_OPERAND denial; does_not_prove two-VERIFIED cross-run until
Phase 2 links two identity-bearing live runs).

---

## Purpose

Prevent **cross-run data contamination**: the mixing of artifacts produced by *different* backtest
runs (run A's trades joined with run B's config summary, run C's events with run D's metrics, etc.)
into a single object that is then treated as if it came from one run. Each artifact must be able to
prove **which run** it came from, and any **join** must be gated so that mismatched or identity-less
artifacts are refused rather than silently merged.

## The identity record

A run's canonical identity is a **6-field record**, minted once per run by the *single* authority
(`build_identity()`) and written verbatim as `run_identity.json` inside every run directory:

| Field | Meaning | Verified requirement |
|---|---|---|
| `run_id` | canonical output-content id, e.g. `run_20260916_101506_XAUUSD` | present, non-empty |
| `config_version` | human config version (e.g. `v2_multi_2026_04`) | present, non-empty |
| `config_hash` | sha256 from the config-registry metadata | present, non-empty |
| `dataset_hash` | sha256 of the consumed CSV/candle range (**registered formula**, see below) | present, non-empty |
| `artifact_timestamp` | UTC ISO8601 mint time | present, non-empty |
| `identity_status` | `VERIFIED` if all five data fields are present & non-empty; else `UNVERIFIED` | computed, never hand-authorable |

### `identity_status` is mandatory first-class

- **VERIFIED** requires all five data fields present and self-consistent. Anything less is **UNVERIFIED**.
- **UNVERIFIED inherits down** — a derived report is `UNVERIFIED` if the source artifact it is built on
  is `UNVERIFIED` (carried on trades/events rows and read back by derived layers).
- **RECOMPUTE != RECOVER** — a historic pre-2026-09-16 run that never recorded hashes is **never**
  backfilled or upgraded to VERIFIED. No hash is invented for it. It stays `UNVERIFIED`.

## The registered `dataset_hash` formula

The *one* place dataset hashing is defined is `run_identity.dataset_hash(path)`:
`SHA-256(bytes(file))`. It is never inlined at call sites. Because the backtest's dataset layer
already admits files via `data_ingestion.dataset_registry`, the recorded `dataset_hash` is computed
only *after* a file passes that admission gate.

## The join gate — `can_join(a, b)`

Deny order is load-bearing (verified order in tests):

1. if `a.identity_status != "VERIFIED"` → **deny** (closes the historical-run loophole);
2. if `b.identity_status != "VERIFIED"` → **deny**;
3. if `a.run_id != b.run_id` → **deny** (cross-run);
4. if `a.config_hash != b.config_hash` → **deny** (config drift).
5. else → allow, reason `JOIN ALLOWED: <run_id>`.

This makes the gate **stricter than "matching hashes"**: an UNVERIFIED artifact can never join, even
if it happens to carry a matching `run_id`/`config_hash`. Historical artifacts therefore cannot be
mixed in after the fact — exactly the guarantee the plan requires.

## Mandatory artifact stamping (always-on)

The backtest `ReportWriter` is a **pure sink**: it never recomputes status. When a caller passes an
already-minted `run_identity` dict, the writer:

- writes `run_identity.json` (full record) into the run dir;
- carries the full record on `{i}_summary.json`;
- repeats `identity_status` on every row of `{i}_trades.csv` and every line of `{i}_events.jsonl`;
- writes an `── RUN IDENTITY (EFAP) ──` header block into the report `.txt`.

The `run_identity` parameter defaults to `None`, so every pre-existing `write_all` caller is
unaffected. If identity minting degrades (config meta unavailable, no `csv_path`), the record is
stamped `UNVERIFIED` — never a fabricated VERIFIED.

### Run folder naming — one id, range + config in the name (CH-run-identity-range-folder-manifest)

The canonical id (`run_YYYYMMDD_HHMMSS`, UTC) is minted **once, before the `ReportWriter` exists**,
so the run folder name and the stamped content share the SAME id (this closed the F-101
"folder id ≠ content id" split — previously the writer minted its own naive-local id). Folder
recipe (one deterministic place: `ReportWriter._folder_stem`):

```
results/run_<UTC>_<INSTRUMENT>__<startYYYYMMDD>..<endYYYYMMDD>_<config_version>_<config_hash8>/
  e.g. results/run_20260916_172925_XAUUSD__20240522..20260521_v2_htfcrt_2026_08_3ca7549e/
```

- `start/end` = first/last `timestamp` cell of the corpus CSV (cheap pre-walk read from
  `_corpus_range_from_csv`; missing/unreadable ⇒ suffix omitted ⇒ legacy folder shape).
- The suffix makes "same time range, different configs" runs distinct and at-a-glance readable —
  the original cross-run confusion driver.
- `BacktestMetrics.corpus_start/end` (the ACTUAL walked first/last candle) flow into `{i}_summary.json`
  and `run_manifest.json`; the folder pre-walk estimate is only the folder-name fallback.

### `run_manifest.json` — one pointer to every id (CH-run-identity-range-folder-manifest)

Every run dir gains a `run_manifest.json` (schema `run_manifest_v2`) consolidating the F-101 id
family **recorded, never clock-joined or collapsed**:

```json
{
  "schema": "run_manifest_v2",
  "run_id": "<canonical run_YYYYMMDD_HHMMSS>",
  "instrument": "XAUUSD",
  "layer_trace_id": "<lt_..._XAUUSD>",
  "run_ids": {
    "utils.logging_config.RUN_ID": "<import-time local id>",
    "runtime.ReportWriter.run_id": "<= canonical>",
    "config_dump_run_id": "<config-dump mint>",
    "runtime.BacktestRunner.canonical_run_id": "<canonical>",
    "layer_trace": "<lt_..._XAUUSD>"
  },
  "fingerprint": {"config_version": "...", "config_hash": "<sha256>", "dataset_hash": "<sha256>"},
  "corpus": {"start": "...", "end": "...", "rows": 47197},
  "identity": {6-field record, may be UNVERIFIED},
  "artifacts": {"identity": "...", "summary": "...", "trades_csv": "...", "events": "...",
                "report": "...", "telemetry": "...", "config_dump": "..."}
}
```

(No `manifest` self-reference — the pointer file lists the artifacts it points at, not itself.)

The layer trace also records the canonical id in its `preexisting_run_ids`
(`runtime.BacktestRunner.canonical_run_id`), so the observation-only trace self-links back to the
core outputs it can now be joined against — identity provenance, not a decision input.

## CLI

```
python -m governance.run_identity show <run_identity.json>
python -m governance.run_identity validate-join <left-run_identity.json> <right-run_identity.json>
```

`validate-join` returns exit code 0 on ALLOW, 1 on DENY (each with a machine-parseable reason line).

## Testing

`tests/test_run_identity.py` covers: single-run VERIFIED allow, cross-run deny, config-drift deny,
dataset-mismatch deny (via distinct hashes), historic-UNVERIFIED deny-first, deterministic dataset
hashing, and record round-trips. A writer smoke test verifies `run_identity.json` + the summary
block + row/event `identity_status` + the report header are all emitted.

## Model of "who may join"

Only a derived object that can prove `VERIFIED` on **both** halves and identical `run_id` +
`config_hash` may be formed. Any other pair (one empty, one unknown, one historic) is refused —
so the "F-101 fourth identifier" problem is resolved by construction: there is now exactly **one**
identity authority, and any artifact that cannot present it is `UNVERIFIED`.