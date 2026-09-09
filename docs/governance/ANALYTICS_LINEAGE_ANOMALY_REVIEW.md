# Analytics Lineage Anomaly Review

**Status:** design-only review note (Phase 4 Lineage follow-on).  
**Date:** 2026-09-06 (IST)  
**Machine / repo:** `DESKTOP-UC5M671` / `D:\Tradelatest`  
**Primary target:** 12 UNKNOWN `produced_by` cells in family `opportunities` in [`ANALYTICS_LINEAGE_REGISTRY.md`](./ANALYTICS_LINEAGE_REGISTRY.md).  
**Companion:** [`ANALYTICS_SCHEMA_REGISTRY.md`](./ANALYTICS_SCHEMA_REGISTRY.md) §2.4 `opportunities`.

---

## Doctrine (provenance, not attribution)

- **Lineage answers origin before attribution.** This note classifies *who emitted / synthesized* analytics columns. It does **not** label edge, causal edge, or profit attribution.
- **Analytics never becomes authority.** No Context / ODP / PolicyOpinion / Market Ontology v2 claims. No `src/` changes. No new ontology.
- **`produced_by` fill rule (this review):** fill the lineage registry **only** with high-confidence **single producer module path**. If multi-producer, umbrella-owner ambiguity, or write-site vs semantic-origin conflict remains, keep `UNKNOWN` and record the architecture finding here.
- **Phase 5 Attribution remains blocked** until this opportunities pocket is understood (see §Verdict).

Classification vocabulary used below:

| Code | Meaning | Pure docs gap? |
|------|---------|----------------|
| **(1)** | Producer exists but was never recorded | Yes |
| **(2)** | Producer changed ownership over time | No (architectural) |
| **(3)** | Artifact is synthesized from multiple producers | No (architectural) |
| **(4)** | Artifact was created before ownership doctrine existed | No (architectural) |

---

## Scope of investigation

Investigated (read-only):

- Registry / schema headers and family `opportunities` rows (12 fields).
- Emitters / call sites: `scripts/research/opportunity_scanner.py`, `scripts/auto_train_from_opportunities.py` (subprocess wrapper), `scripts/research/ingest_live_outcomes.py` (schema-compatible twin, different filename).
- Consumers only (not writers): `src/training/*`, `src/replay/*`, `src/control_plane/dashboard_api.py`, analysis/training scripts under `scripts/`.
- Sample JSONL: `logs/BNBUSDT/**/opportunities.jsonl`, `logs/XAUUSD/xauusd_phase1_20260723/opportunities.jsonl`, `logs/{BTC,ETH}USDT/oos_*/opportunities.jsonl`.
- Projection conventions: `scripts/maintenance/jsonl_to_parquet.py` `FAMILY_DEFAULTS`, `scripts/analysis/query_trace.py` `FAMILY_GLOBS`.
- Prior measurement docs: F-022; `docs/analysis/cross-instrument-anatomy-2026-06-13.md`; lineage registry summary note that all 12 `produced_by` are UNKNOWN at module granularity.
- Git history: `opportunity_scanner.py` present across tree-restoration / tracesweep commits; no alternate `opportunities.jsonl` write-site found in current `src/` + `scripts/`.

**Not touched:** `src/` (no edits), Context/ODP, attribution claims, git commit.

---

## Opportunities UNKNOWN pocket — analysis

### What the family is

| Item | Evidence |
|------|----------|
| JSONL pattern | `opportunities.jsonl` (`FAMILY_DEFAULTS` skips `type=run_header`) |
| DuckDB / parquet globs | `logs/**/opportunities.parquet`, `results/**/opportunities.parquet` |
| Schema owner (umbrella) | `opportunities logger` / "Opportunity / phase-1 logging paths" |
| Lineage `produced_by` (today) | **UNKNOWN** × 12 |
| Population | Detection-stream opportunity rows (not engine trade ledger) |

Sample records (all inspected runs) share the same 12 data keys after `run_header`:

`timestamp`, `instrument`, `direction`, `entry`, `sl`, `tp`, `outcome`, `rr_achieved`, `duration_candles`, `mfe`, `mae`, `features`.

`run_header` carries `{type, run_id, instrument, started_at}` only — **no** `produced_by` / `emitted_by` / module pin.

### Emitter module path(s) found

| Role | Module path | Writes `**/opportunities.jsonl`? | Notes |
|------|-------------|----------------------------------|-------|
| **Primary JSONL write site** | `scripts/research/opportunity_scanner.py` (`scan()` → `out_path.open("w")`) | **Yes** | Pipeline B research scanner; CRT intentionally not consulted. Cross-instrument anatomy (2026-06-13) states all four instrument streams come from this script. |
| Orchestrator (not emitter) | `scripts/auto_train_from_opportunities.py` | No | Subprocess-calls the scanner; resolves output path only. |
| Schema-compatible twin | `scripts/research/ingest_live_outcomes.py` | **No** (CLI output e.g. `logs/live_training.jsonl`) | Same *consumer* shape for phase5, different filename and outcome vocabulary (`WIN`/`LOSS`/`BREAKEVEN` + `source=live_alerts`). Outside `FAMILY_DEFAULTS` basename match. |
| Feature value origin | `src/features/feature_pipeline.py` (+ `CANONICAL_FEATURES` in `src/features/feature_schema.py`) | No | Values packed into `features{}` by the scanner. |
| Path metrics origin | `opportunity_scanner._simulate` | N/A (same file) | Local trailing-stop forward walk; mirrored later by `src/replay/timing_reconstructor.py` for offline recompute (reader/backfill helper, not the historical writer of corpus files sampled). |
| Engine / backtest | `src/runtime/*` | **No** opportunities.jsonl writes found | `events` family is separate (`backtest_v2.py`). Dual *systems* (spine `TRADE_OPENED` vs scanner detection stream) are architectural neighbors, not alternate writers of this JSONL basename. |

**`src/` has readers only** for `opportunities.jsonl` (dashboard, replay, training, episode projectors). No `OpportunityLogger` class; the schema owner string is an umbrella label.

### Field-level origin (within the scanner record)

Even with a single file write site, row fields are not one homogeneous origin:

| Field group | Assembled by | Semantic inputs |
|-------------|--------------|-----------------|
| `timestamp`, `instrument`, `direction` | `opportunity_scanner.scan` | Candle timestamp / CLI instrument / synthetic long+short |
| `entry`, `sl`, `tp` | `scan` geometry | `close` + ATR-sized distances; **ATR from FeaturePipeline** (`atr_14_raw`) |
| `outcome`, `rr_achieved`, `duration_candles`, `mfe`, `mae` | `_simulate` | Local trailing-stop path labels (F-022: detection-stream labels, not governing trade ledger / not oracle `forward_walk`) |
| `features` | `scan` packs dict | **Values computed by FeaturePipeline**; names from `CANONICAL_FEATURES` |

So: **file emitter = one module**, **field provenance = mixed**.

### Ownership / doctrine timeline

- Corpus samples date from **2026-05 → 2026-07** (e.g. `bnbusdt_training_20260524`, `20260530_011521`, `xauusd_phase1_20260723`).
- Analytics schema + lineage registries are **2026-09-06** Phase 4 design-only inventories.
- Schema still names owner as umbrella **"opportunities logger"** / "Opportunity / phase-1 logging paths", not a module path — consistent with **(4)** and with registry’s own note that generic owners are umbrellas.

No git evidence that a different module formerly wrote `opportunities.jsonl` and later transferred ownership — **(2) is not evidenced** for this basename.

---

## Classification of the 12 fields

Pocket-level codes apply to every row; field notes call out extra **(3)** where synthesis is explicit.

| field_name | Classification | Rationale (brief) | Fill `produced_by` now? |
|------------|----------------|-------------------|-------------------------|
| timestamp | **(1)** + **(4)** | Emitted by scanner; never module-pinned in lineage; corpus predates Phase 4 doctrine | **No** — leave UNKNOWN pending write-site vs owner-module decision |
| instrument | **(1)** + **(4)** | Same | **No** |
| direction | **(1)** + **(4)** | Synthetic long/short from scanner loop | **No** |
| entry | **(1)** + **(3)** + **(4)** | Scanner geometry; depends on candle close (+ pipeline enrichment of frame) | **No** |
| sl | **(1)** + **(3)** + **(4)** | Scanner geometry sized with FeaturePipeline `atr_14_raw` | **No** |
| tp | **(1)** + **(3)** + **(4)** | Same as `sl` | **No** |
| outcome | **(1)** + **(4)** (+ F-022 semantics) | Written by `_simulate`; detection-stream label (not ledger) | **No** |
| rr_achieved | **(1)** + **(4)** (+ F-022 semantics) | Same; known internally inconsistent vs governing exits | **No** |
| duration_candles | **(1)** + **(4)** | From `_simulate` | **No** |
| mfe | **(1)** + **(4)** | From `_simulate` | **No** |
| mae | **(1)** + **(4)** | From `_simulate` | **No** |
| features | **(1)** + **(3)** + **(4)** | Explicit multi-producer: FeaturePipeline values packed by scanner | **No** |

**Pocket rollup:** not a pure documentation gap. Dominant codes = **(1)+(3)+(4)**. **(2)** not supported.

---

## Finding IDs

### L-001 — Opportunities `produced_by` UNKNOWN pocket (architectural)

- **Family:** `opportunities` (all 12 lineage rows).
- **Codes:** **(1)** + **(3)** + **(4)**.
- **Summary:** The DuckDB/Parquet family keyed by `opportunities.jsonl` has a **single evidenced JSONL write site** (`scripts/research/opportunity_scanner.py`), but lineage `produced_by` cannot be honestly collapsed to that path alone without an architecture decision: several fields are **synthesized** (ATR / feature bag from FeaturePipeline), owner remains an **umbrella**, and corpus **predates** Phase 4 ownership/lineage doctrine. Registry correctly left `UNKNOWN`; this review keeps it.
- **Candidate fill (deferred):** `scripts/research/opportunity_scanner.py` *if* doctrine defines `produced_by` = JSONL write site only (parity with how `clean_labels` → `builder.py` and `crt_construction` → `crt_construction_trace.py` are treated).
- **Must stay UNKNOWN when:** `produced_by` is interpreted as semantic value origin / sole computational owner — then at least `features` / ATR-sized `sl`/`tp` require multi-producer notation the current single-cell schema cannot express.

### L-002 — `features` (and ATR-sized geometry) multi-producer synthesis

- **Fields:** `features` (primary); `sl`, `tp` (secondary via `atr_14_raw`).
- **Code:** **(3)**.
- **Summary:** Nested feature bag is not produced by the JSONL writer’s own formulas; it snapshots `FeaturePipeline` / `CANONICAL_FEATURES`. Schema registry already warns of HOMONYM risk for bare names inside the bag (`momentum_score`, `break_of_structure`, etc.).

### L-003 — Detection-stream outcome fields vs governing path oracles (provenance boundary)

- **Fields:** `outcome`, `rr_achieved` (and path companions `mfe`/`mae`/`duration_candles`).
- **Code:** **(4)** context + governance finding F-022 (not a second emitter).
- **Summary:** These columns are *emitted* by the scanner’s local `_simulate`, but research doctrine forbids treating them as realized trade-ledger truth. That is a **provenance/semantics** constraint for Phase 5 Attribution — not a missing module path. Lineage may eventually pin the write site; attribution must still refuse stream-outcome → edge claims.

**L-003 measurement artifact now exists (2026-09-07):** `docs/governance/ANALYTICS_OUTCOME_SEMANTICS_L003.md` + `docs/governance/analytics_outcome_semantics_l003-2026-09-07.json` (run_id `l003_outcome_semantics_20260907_172143`, commit `d7c25f6e55616261b8b229b000875abd3bd315eb`). Observation/doctrine only — registries untouched; attribution still blocked.

---

## Can lineage registry `produced_by` be filled?

| Decision | Detail |
|----------|--------|
| **Registry update this pass** | **None.** All 12 remain `UNKNOWN`. |
| **Why not fill** | Pocket is **multi-producer / umbrella-owner / pre-doctrine** — not a pure **(1)** docs gap. Prefer accuracy over blanks. |
| **What would unlock a fill** | Explicit architecture decision: (A) `produced_by` = JSONL write site → fill all 12 with `scripts/research/opportunity_scanner.py` and optionally annotate L-002/L-003 in notes; or (B) allow multi-producer cells / split family → then `features` cites `src/features/feature_pipeline.py` and geometry/path fields cite scanner helpers. |
| **What must not happen** | Inventing `OpportunityLogger` as a module path; pointing `produced_by` at consumers (phase5, train_trade_net, discover_zones); collapsing live ingest twin into this family without basename/population adjudication. |

Owner column comparison: registry `owner` = umbrella `opportunities logger` vs candidate emitter module = `scripts/research/opportunity_scanner.py`. This is **not** recorded as a produced_by↔owner *conflict* in the lineage summary (umbrellas are acknowledged); it is an **identity granularity** gap — secondary anomaly S-001 below.

---

## Secondary anomalies (brief; non-blocking for this pocket)

| ID | Observation | Action |
|----|-------------|--------|
| **S-001** | Owner umbrella (`opportunities logger`) vs module-path owners used elsewhere (`crt_construction_trace`, `clean_labels builder`). | Docs-only; align owner string only after L-001 decision. |
| **S-002** | Schema-compatible twin `ingest_live_outcomes.py` → non-`opportunities.jsonl` paths; outcome vocab differs. | Keep out of this family unless FAMILY_DEFAULTS intentionally expanded. |
| **S-003** | Nested `features` HOMONYMs vs `bar_structure` / telemetry (already flagged in schema registry collision watch). | No lineage cell change; do not promote bare feature names. |
| **S-004** | Dual research systems: spine/`TRADE_OPENED` ledger vs scanner detection stream — neighbors, not alternate writers of this JSONL. | Architecture awareness only. |
| **S-005** | Other families: no additional UNKNOWN `produced_by` cells in current lineage summary (12/12 concentrated in `opportunities`). Quick scan: no owner↔producer conflicts declared for filled families. | No further UNKNOWN pocket this pass. |

---

## Verdict — Phase 5 Attribution

**Phase 5 Attribution remains blocked** until L-001 is resolved (write-site vs semantic-origin doctrine for `produced_by`) and L-003’s detection-stream boundary stays explicit: opportunities `outcome` / `rr_achieved` must not be treated as attributable realized edge without a governing exit/oracle path.

This review does **not** unblock Attribution. It only explains why the 12 cells are UNKNOWN and what evidence exists.

---

## Explicit non-goals / non-actions

- No `src/` changes.
- No Context / ODP / Policy edits.
- No attribution or causal-edge claims.
- No new ontology / schema family.
- **Lineage registry not updated** (UNKNOWN retained).
- **Not committed.**

---

## Pointers

- Lineage registry: `docs/governance/ANALYTICS_LINEAGE_REGISTRY.md` (family `opportunities`; summary UNKNOWN rates).
- Schema registry: `docs/governance/ANALYTICS_SCHEMA_REGISTRY.md` §2.4.
- Write site: `scripts/research/opportunity_scanner.py`.
- Feature values: `src/features/feature_pipeline.py`, `src/features/feature_schema.py`.
- Family conventions: `scripts/maintenance/jsonl_to_parquet.py`, `scripts/analysis/query_trace.py`.
- Prior governance: F-022 (`context/03_FINDINGS.md` / `docs/current-findings.md`); anatomy provenance note `docs/analysis/cross-instrument-anatomy-2026-06-13.md`.
