# Migration plan — `v3_unified_market_structure_2026_09`

**Change:** `CH-v3-unified-market-structure-v1` · **Date:** 2026-08-29 ·
**Status:** SHIPPED, register-only · **Finding:** F-097

`ACTIVE_VERSION` remains `v2_htfcrt_2026_08`. v3 exists in the registry and is reachable by
explicit research invocation; nothing about the running system changed.

---

## What shipped

| Phase | Deliverable | Gate |
|---|---|---|
| 1 | `configs/production/v3_unified_market_structure_2026_09.json` + one `REGISTERED` line in `configs/promotion_log.jsonl` | full-corpus parity vs v2 |
| 2 | `src/runtime/bar_structure_snapshot.py` (SEM-035) + 5 additive sites in `backtest_v2.py` + `ParentCRTFeed.last_range_ratio` | byte-identical ledger, emit ON vs OFF |
| 3 | Parquet projection via existing `parquet_store` + a `FAMILY_DEFAULTS` entry | `verify_projection` clean on 47,275 rows |
| 4 | `MC-CTXATTR-XAUUSD-M15-V1` sealed **before** the driver existed | contract floor green |
| 5 | `src/research/evidence/context_attribution.py` (SEM-036) + run | mt00 executed, artifacts resolve |
| 6 | Ontology SEM-035/036, claim classes, SITS, F-097 | GREEN_FLOOR |
| 7 | Data contract, diagram, objects, this plan | citations resolve |

---

## Config: three hash-neutral sections

`config_hash` covers the `params` dict **only** (`production_config.py:89-92`). v3 carries the
same five `params` keys and the same hash `7de09f62…` as v2 and v2_multi_2026_04, so
compatibility is structural rather than argued. The three new top-level sections
(`bar_structure_snapshot`, `bar_structure_parquet`, `context_attribution`) are invisible to the
hash and to `_validate_override_keys`.

### Why registration, not promotion

`PromotionManager._write_to_registry` deep-clones `v1_multi_2026_03.json` and overlays only the
nine `_METADATA_KEYS`. Running `promote_*` on a v3-shaped config would **silently strip
`parent_crt`, `feature_pipeline` and `backtest`** — the same trap `v2_htfcrt_2026_08` documents
in its own notes. So v3 was hand-written and one line was hand-appended to the promotion log.

The event is **`REGISTERED`, not `PROMOTED`**, and `score`/`score_std_dev` are null.
`config_integrity.active_version_is_governed` is the only consumer that filters on the event
value and it only inspects the version named by `ACTIVE_VERSION`; a `PROMOTED` line for a
never-activated version would be a false governance record, and a score would claim a
`ConfigValidator` run that did not happen.

---

## Compatibility, measured

`scripts/analysis/v3_config_parity.py`, full XAUUSD corpus (47,275 bars), three arms:

```
A. v2_htfcrt_2026_08  vs  v3 (emit OFF)          [requirement 9]
   OK events.jsonl         byte-identical (1,871,819 bytes)
   OK crt_telemetry.jsonl  byte-identical (1,671,551 bytes)
   OK trades.csv           identical except ['config_version']
   OK summary.json         identical

B. v3 emit OFF  vs  v3 emit ON                   [requirements 4 and 5]
   OK events.jsonl         byte-identical
   OK crt_telemetry.jsonl  byte-identical
   OK trades.csv           all columns identical
   OK summary.json         identical

   Non-vacuity: snapshot stream rows = 47,275
```

The `config_version` carve-out in arm A is not a loosened gate: the ledger stamps the config it
ran under on every trade row, and two different configs producing the same stamp would be a
provenance defect. Measured, that stamp is the **only** difference — 85 of 86 trade columns and
every non-volatile summary key match exactly. In arm B it must match too, and does.

### The harness never touches `ACTIVE_VERSION`

`PROD_VERSION` resolves once at import from a path **relative to the process working
directory**. Flipping the shared pointer for the length of a multi-minute backtest would be
visible to every other process on the machine, and this repository is routinely worked by
several concurrent sessions. Each arm therefore runs in an isolated root
(`src/utils/isolated_config_root.py`): a real copy of `configs/` with its own one-line
`ACTIVE_VERSION`, plus directory junctions to `data/`, `models/`, `src/`, `scripts/`.

---

## Emission: five additive sites

Site 0 builds the emitter (fails soft — a broken observation surface must not take a backtest
down). Site 1 captures the previously-discarded `parent_feed.push()` return. Sites 2 and 2b
emit warmup/initialise rows. Site 3 emits the full record **after** `process_candle` has
returned.

Site **2b** exists because the initialise branch `continue`s before the emit site, leaving
exactly one hole at bar 77. That was found by the `CC-CTX-RUN-SCOPED-OBSERVATION` grounding
check on the first real stream — not by any unit test — and is now pinned by
`tests/governance/test_bar_structure_grounding.py`.

---

## Rollback boundary

Delete the v3 config and its promotion-log line; delete `bar_structure_snapshot.py`,
`context_attribution.py`, `isolated_config_root.py`, the two scripts and their tests; revert the
five `backtest_v2.py` sites, the `ParentCRTFeed` property, the three optional `break_events`
parameters in `features/smc/`, and the `semantic_grounding` check; remove SEM-035/036, the
`STR-*`/`CC-*` rows, the SITS entries and F-097.

`ACTIVE_VERSION`, `params`, `config_hash`, `CANONICAL_FEATURES`, `SCHEMA_HASH` and every
existing model artifact are untouched by the change and therefore by its rollback.

---

## What activation would additionally require

Registration is not activation, and none of the following was done:

1. A `ConfigValidator.validate()` APPROVE for v3 — currently blocked by a **pre-existing**
   defect unrelated to this change: the validator does not stamp `CRTConfig` with an allowed
   construction-provenance mode before calling `BacktestRunner`, so it rejects
   `v2_multi_2026_04`'s unchanged params identically (documented in `v2_htfcrt_2026_08`'s notes).
2. Feature-layer freeze-pin re-certification.
3. A decision on emission cost: enabling the snapshot adds ≈66 s per XAUUSD corpus and 173 MB of
   JSONL per run. It is default-off precisely so activation does not silently impose that.
4. An explicit `ACTIVE_VERSION` flip with user authorization.

---

## Promotion of a context feature into decision logic

`context_attribution.promoted_families` is `[]` and stays empty. Requirement 8 is mechanical,
not a convention: a family may enter it only after `MC-CTXATTR-XAUUSD-M15-V1` produces holdout
evidence **and** a separate authorized change program wires it in.

On the first run, **0 of 22** families cleared (F-097) — a *powered* null, not an insufficient
one. So the list stays empty on evidence, not merely on procedure.

---

## Test strategy

| Test | Pins |
|---|---|
| `tests/test_bar_structure_snapshot.py` | record shape, gapless coverage, key-order stability, null semantics, all ten families present, emitter mutates nothing and returns `None`, disabled emitter is a true no-op |
| `tests/test_smc_break_event_memo.py` | memoized `_find_break_events` bit-identical over 1,785 comparisons (1,136 non-trivial), default arg unchanged, **and a wrong event list changes the answer** so the equality assertions cannot pass vacuously |
| `tests/governance/test_bar_structure_grounding.py` | the CAN class is a real check: grounds a clean stream, refuses a one-bar hole, missing identity, and two concatenated runs; the CANNOT class refuses regardless of contents |
| `tests/research/test_context_attribution_contract.py` | contract ↔ code binding (every gate constant is a module constant), 22 tests enumerable, split constants imported from the frozen calendar, the run writes the split it used, **the primary metric is numerically zero on a planted CRT proxy and non-zero on a real within-stratum effect**, abstentions excluded from both cells, BH monotone |
| `scripts/analysis/v3_config_parity.py` | the empirical requirement 4/5/9 proof on the full corpus |

Must stay green: `test_feature_layer_freeze`, `test_semantic_registry`, `test_feature_lineage`,
`test_jsonl_claim_catalog`, `test_jsonl_claim_grounding`, `test_script_registry`,
`test_script_matrix_sync`, `test_measurement_contract`, `test_measurement_result_log`,
`test_parquet_store`.

---

## Known residue

- `tests/test_current_findings.py` has **two pre-existing failures**, both naming only **F-096**
  (registered 2026-08-28 by a concurrent session): it is absent from the CLAUDE.md Truths Index
  and cites four untracked paths. Not touched here — it is another session's incomplete work,
  and F-097 is clean on both checks.
- mt00 carries two structurally INCONCLUSIVE probes
  (`E1-05-FINGERPRINT-DIGEST-COMPOSITION`, `E2-04-METRIC-GATE-TRACE`). Both are limits of the
  clean-path runner and are carried by every contract in the repository.
- mt01 is 0/27 repo-wide, so the E4 seal is unmet and no economic authority is available to any
  contract, including this one.
