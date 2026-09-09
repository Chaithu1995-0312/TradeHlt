# Corpus Authority Doctrine

| Field | Value |
|---|---|
| Status | **FROZEN v1.0.0** (object model) · R3 v1 **implemented** (bound datasets only) |
| Status token | `DATASET_IDENTITY_STATUS = FROZEN` |
| BC-1 | `BC-1_INFRASTRUCTURE = IMPLEMENTED` · `BC-1_CLOSURE = NOT_GRANTED` |
| Date | 2026-09-02 |
| Change | [`CH-dataset-identity-star-v1`](build_manifests/CH-dataset-identity-star-v1.impact.json) · [`CH-dataset-identity-r3-v1`](build_manifests/CH-dataset-identity-r3-v1.impact.json) |
| Lane | semantic certification |
| Freeze (bytes) | [`ohlcv-corpus-mutation-freeze-2026-07-10.md`](ohlcv-corpus-mutation-freeze-2026-07-10.md) |
| Schema (CAD-* archive) | [`corpus_authority_decision.schema.json`](corpus_authority_decision.schema.json) |
| Decisions (CAD-* archive) | [`corpus_authority_decisions.jsonl`](corpus_authority_decisions.jsonl) |
| PASS-B | [`ohlcv-closure-report-2026-07-10.md`](ohlcv-closure-report-2026-07-10.md) |
| Contract | [`ohlcv-output-contract-2026-07-10.json`](ohlcv-output-contract-2026-07-10.json) |
| Layer identity | [`CANONICAL_LAYER_IDENTITY_CONTRACT.md`](CANONICAL_LAYER_IDENTITY_CONTRACT.md) — **unchanged** (L0–L5 stay CLOSED) |

`DATASET_IDENTITY_STATUS = FROZEN`

```text
one admitted artifact, projections are functions
```

---

## Frozen sentence

> **Dataset Identity is the authority. M15 is the canonical admitted artifact. H1/H4/D1/W1/MN1 are direct projections of that artifact.**
>
> one admitted artifact, projections are functions

That is the R3 object. It is not a second L0–L5. It is the missing owner of `corpus_sha256` that frozen L0 already requires.

---

## 0. What this freeze is, and is not

| This freeze does | This freeze does not |
|---|---|
| Name Dataset Identity as the corpus-authority object | Reopen Canonical Layer Identity, Storage Preservation, or Physical Storage |
| Bind one canonical admitted artifact per dataset | Auto-APPROVE any hash (XAUUSD M15 stays `FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION`) |
| Require HTF as **direct projections** (star from the canonical artifact) | Cascade `M15 → H1 → H4 → D1 → W1` |
| Formalize F-075: Parent CRT population is `derived_h4` | Invent `CalendarHTFBuilder` or a fourth aggregator |
| Classify stored H1/H4 CSVs as **FORENSIC / NOT_ADMITTED** | Delete those files; they remain for native-vs-derived studies |
| Keep CAD-* `SYMBOL_TIMEFRAME` rows as archive | Migrate the decision schema |

**Not OHLCV CLOSED.** `OHLCV_CLOSURE_STATUS` stays `BLOCKED:BC-1..BC-6`. R3 v1 is the admission gate for **one** bound dataset. It is not G-05 remediated for the corpus universe, not G001.

`Construction ≠ Closure`

---

## 0.1 Construction ≠ Closure (BC-1 status)

```text
BC-1_INFRASTRUCTURE = IMPLEMENTED
BC-1_CLOSURE        = NOT_GRANTED
```

R3 v1 put identity on the load path for bound datasets:

```text
CandleLoader → DatasetRegistry → DatasetIdentity → admitted artifact → stream
```

That is **remediation infrastructure**. It is not BC-1 adjudicated closed.

G-05 remains **CONTRADICTED** for the corpus universe (nine logical ids still resolve to different bytes with no binding). The XAUUSD Phase-1 slice has an enforcer. Contract exists ≠ evidence proven for every instrument.

Remaining PASS-B blockers now attach to a **stable object** (`XAUUSD_MT5_PHASE1_20260521` → admitted M15 @ `4d73f5ce…`), not a moving path:

| Blocker | Still open because |
|---|---|
| BC-1 closure | Universe not bound; only one dataset admitted |
| BC-2 | **RESOLVED for mt5 2026-09-03** — open-time labeling PROVEN by a live pair (see below). Still open for the binance / yfinance acquisition families |
| BC-3 | Unbound crypto root still yfinance-descent (path-governed) |
| BC-4 | **PARTIALLY ADVANCED 2026-09-03** — `H_REAL` rejected, artifact binding `BOUND` (100% over 2yr sample); semantic verdict `TICK_VOLUME_APPROXIMATE`, not `CONFIRMED` (see below). `corpus_authority_decision.schema.json`'s `volume_semantic` enum now carries `TICK_VOLUME_APPROXIMATE` (2026-09-08, expressibility parity with `dataset_identity.schema.json`) — schema-wiring alone; no CAD row's value changed (all 48 stay `UNDECLARED`). Still open: exact-match proof, and the rest of BC-4a enforcement (`is_synthetic` / SEED-OHLCV-19) |
| BC-5 | Option A/B/C/D not selected; status is frozen-candidate, not APPROVED |
| BC-6 | yfinance tz/forming-bar — scoped to that family; not this dataset's clock proof |

Before R3, XAUUSD M15 already had a one-off Phase-1 path guard. R3 made Dataset Identity the admission API and closed the native-HTF back door: `data/mt5/XAUUSD_H4.csv` via `CandleLoader` is FORENSIC-reject. Parent CRT was already `derived_h4` (`ParentCandleBuilder` on the child stream). The loader now **cannot** introduce a second H4 population by accident.

### Two load regimes (staged, not an oversight)

| Regime | Markets | Authority |
|---|---|---|
| Bound (dataset-governed) | `XAUUSD_MT5_PHASE1_20260521` | Dataset Identity + hash/range |
| Unbound (path-governed) | EURUSD, BTCUSDT, ETHUSDT, … | Call-site filepath (legacy) |

R3b is the fail-closed step for the unbound world: unknown corpus → load denied unless a Dataset Identity exists. That is a behavior change across research/backtest and needs its own authorization. R3 v1 `unbound_load_policy: path_passthrough` is the migration scaffold, not G-05 closure.

### Evidence lane (post-R3) — architecture handed off

For the XAUUSD Phase-1 slice the problem class has changed:

```text
Before R3:  What object are we measuring?
After  R3:  What does the admitted object mean?
```

Highest-ROI lane: **semantic adjudication of the admitted M15** (`4d73f5ce…`), not another resolver, dataset object, HTF authority model, or loader path.

Do **not** re-run Phase-1 G2/G4 as if they were never run. Residuals on this exact hash (`xauusd_phase1_validation_report-2026-07-10.json`):

| Gate | Already measured | Still missing |
|---|---|---|
| G2 / BC-2 | 15m-monotonic, 0 dups/OOO, STATIC fetcher uses `rates['time']` as open epoch; **`executable_open_vs_close_label_proof` PRESENT 2026-09-03 (verdict `OPEN`)** | nothing — this residual is closed for the mt5 family |
| G4 / BC-4 | `TICK_VOLUME` DECLARED; 0 zero-vol rows; min 2 / median 2001 / max 31468; **2026-09-03 live probe: `H_REAL` REJECTED, `artifact_binding` BOUND (17/17 exact), `volume_semantic_verdict` TICK_VOLUME_APPROXIMATE (0.55-0.68% consistent gap, NOT exact)**. CAD schema enum now expresses `TICK_VOLUME_APPROXIMATE` (2026-09-08) | exact-match proof (APPROXIMATE ≠ CONFIRMED per the frozen prereg §4 rule 3); BC-4a enforcement — declared ≠ enforced — `is_synthetic` + SEED-OHLCV-19 still unbuilt |
| G3 | Observed 01:00–23:45 broker pattern | independent broker calendar UNPROVEN |
| BC-5 | Frozen-candidate pin holds | A/B/C/D not selected; not APPROVED |
| BC-3 / BC-6 | Out of this slice | Unbound crypto / yfinance family |

Not yet attribution: “is this the correct corpus?” is BC-5. Not yet economic.

BC-2 probe (CH-bc2-open-close-label-probe-v1): scorer + prereg
[`docs/research/preregistration-bc2-open-close-label.md`](../research/preregistration-bc2-open-close-label.md).

```text
BC-2_STATUS = PROVEN OPEN (mt5 family, 2026-09-03)
G-06_MT5 = PROVEN
# supersedes: AUTHORIZED INSTRUMENTED PRE-REGISTERED UNPROVEN (2026-09-02)
```

```text
Probe exists ≠ Evidence exists
Scorer exists ≠ Proof exists
Synthetic PASS ≠ Live verdict
```

**SUPERSEDED 2026-09-03 — a live pair was captured.** The three inequalities above
still hold; they are why this took a live capture and not a synthetic one. History
kept per CLAUDE.md §6.2 rule 4: before this date the block read "Live `OPEN`/`CLOSE`
pair **not** captured; G-06 mt5 remains UNPROVEN", and warned that synthetic tests,
STATIC fetcher comments, a 15-minute lattice, MT5 documentation, and a stale
2026-08-07 tick are **not** `executable_open_vs_close_label_proof`. That warning was
honoured: the August terminal was never captured against.

**Live verdict `OPEN`** (`CH-bc2-open-close-emission-hardening-v2`, evidence in
[`docs/research-readiness/bc2_open_close/`](../research-readiness/bc2_open_close/README.md)):

| | |
|---|---|
| Bar T | `2026-09-02T22:30:00` broker |
| Snapshot A | `22:32:13` broker — `delta = +133s`, inside the forming bar |
| Snapshot B | `22:46:44` broker — after T closed (B's newest bar is `22:45`) |
| Mutation of T | high `4382.83 → 4388.71`, close `4382.12 → 4388.12`, volume `1117 → 7478` |
| `open` of T | `4381.17` in BOTH — fixed at bar start, the open-label signature |
| Terminal | `ICMarketsSC-Demo`, MetaTrader 5 build 6140, connected |
| Clock | `mt5_tick`, `clock_basis: broker_local`, skew `-10799s` (= UTC+3, healthy) |

Volume was 1117 of an eventual 7478 (~15%) at `delta=133s` of a 900s bar (14.8%) — an
independent consistency check that A really was mid-formation.

`rates['time']` is therefore the bar **OPEN** for this acquisition family, and the
STATIC prior is confirmed by execution rather than by belief.

**Scope — what this does NOT do.** G-06 flips for **mt5 only**. `OHLCV_CLOSURE_STATUS`
stays `BLOCKED:BC-1,BC-2[binance|yfinance],BC-3,BC-4,BC-5,BC-6[yfinance]`. No APPROVED,
no R3b, no G001, no dataset-record edit. `producer_family_match` is
`UNVERIFIED_NO_RECORDED_TERMINAL`: the frozen dataset record carries no terminal
identity, so this proves the label convention of the mt5 producer FAMILY, not that this
terminal is byte-for-byte the one that wrote `4d73f5ce…`.

Evidence queue (this slice): ~~BC-2 live pair~~ → **BC-4 (partially advanced, see below)** → BC-5 → (unbound) BC-3/BC-6.
No additional resolver work.

**BC-4 probe (`CH-bc4-volume-semantics-v1`): scorer + prereg**
[`docs/research/preregistration-bc4-volume-semantics.md`](../research/preregistration-bc4-volume-semantics.md), evidence in [`docs/research-readiness/bc4_volume_semantics/`](../research-readiness/bc4_volume_semantics/).

```text
BC4_STATUS = PARTIALLY_ADVANCED (mt5 family, 2026-09-03)
H_REAL = REJECTED
ARTIFACT_BINDING = BOUND
VOLUME_SEMANTIC_VERDICT = TICK_VOLUME_APPROXIMATE  # not CONFIRMED
```

**Test 1 (semantic identity, live, scoped to the last 60 minutes per the Phase 0 feasibility gate — deeper `copy_ticks_range` calls were observed to hang indefinitely on this terminal):** 4 bars scored, `tick_volume` vs independently counted `COPY_TICKS_ALL` ticks — `6654/6699`, `7478/7524`, `9483/9535`, `4924/4955` (diffs `45,46,52,31`; 0.55-0.68% consistent gap, `ticks_all` always ≥ `tick_volume`). `real_volume` was `0` on all 4 while `tick_volume>0` → `H_REAL` REJECTED for this family. Per the frozen prereg §4 rule 3, a small directional gap is `TICK_VOLUME_APPROXIMATE`, a DISTINCT verdict from `CONFIRMED` — not silently rounded up.

**Test 2 (artifact binding):** 20 bars sampled across the frozen corpus's full 2024-05-22 → 2026-05-21 range, re-fetched live and compared to the frozen CSV's `volume` column. 17/20 resolved (3 gaps consistent with session/holiday closures, same class as F-098's documented gaps); **17/17 exact match → `artifact_binding = BOUND`.** This is strictly more than BC-2 could establish for its column: the volume bytes in `4d73f5ce…` are reproducible from a live re-fetch on this terminal across the corpus's full span, not just a recent window.

**Residual attribution attempted and FAILED 2026-09-03 (F-100).** A pre-registered probe
(`BC4-RESIDUAL-ATTRIBUTION-XAUUSD-MT5-V1`) tried to explain the 0.55-0.68% gap. **V1
`UNATTRIBUTED`** (0 of 9 frozen candidates matched every discovery bar). A
discovery-generated hypothesis — `tick_volume == count(flags & TICK_FLAG_BID)` — matched
discovery **4/4 exactly**, then **failed an independent holdout** (`UNATTRIBUTED_V2`: 3 of 4
exact, the 07:00 bar off by −29, in the OPPOSITE direction to discovery). The holdout
requirement demonstrably prevented a false ATTRIBUTED claim.

**Newly surfaced risk:** MT5's tick FLAG VOCABULARY is **non-stationary across sessions** —
discovery bars carried `{134, 130, 4}`, holdout bars `{6, 2, 4}`, and the single failing bar
carried both at once (an encoding transition spanning one bar). Any future attribution must
treat the flag encoding as non-stationary; that is exactly how this attempt failed.

The residual is therefore **better characterised but still unexplained**: bounded at
0.55-0.68% and demonstrably NOT explained by tick class (`COPY_TICKS_INFO == COPY_TICKS_ALL`,
`COPY_TICKS_TRADE == 0`), boundary inclusion, exact duplication, price-change filtering, or
BID-flag filtering. **BC-5 remains blocked on it.**

**Scope — what this does NOT do.** `TICK_VOLUME_APPROXIMATE` does NOT close the BC-4b residual the way `CONFIRMED` would (prereg §7). BC-4 stays a blocker in `OHLCV_CLOSURE_STATUS`. No APPROVED, no R3b, no G001, no dataset-record edit yet. `producer_family_match` is unaffected by Test 1; `artifact_binding=BOUND` narrows it for the volume COLUMN specifically but does not resolve terminal identity in general.

---

## 1. Object graph (required)

```text
Dataset Identity
        │
        ▼
Canonical Admitted Artifact (M15 for XAUUSD Phase-1)
        │
        ├── H1  = ParentCandleBuilder(rule=H1)   direct
        ├── H4  = ParentCandleBuilder(rule=H4)   direct
        ├── D1  = ParentCandleBuilder(rule=D1)   direct
        ├── W1  = ParentCandleBuilder(rule=W1)   direct
        └── MN1 = ParentCandleBuilder(rule=MN1)  direct; W1 forbidden as parent
        │
        ▼
L0 Bar  (instrument, timeframe, bar_open_ts, corpus_sha256)
        ▼
L1–L5   unchanged
```

Forbidden:

```text
M15 → H1 → H4 → D1 → W1          # cascade
M15 file + H1 file + H4 file     # independently authoritative
```

---

## 2. Dataset Identity

Authority object. Not a file. Not a timeframe.

```yaml
dataset_id: XAUUSD_MT5_PHASE1_20260521
symbol: XAUUSD
source_family: mt5
clock_basis: broker_local          # F-066 default; not a UTC declaration
volume_semantic: TICK_VOLUME       # existing CAD enum; do not mint a parallel
decision_status: FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION

canonical_artifact:
  timeframe: M15
  path: data/mt5/XAUUSD_M15.csv
  sha256: 4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56
  source: native_fetch
  admitted: true                   # admitted as the Phase-1 candidate object, not APPROVED
```

`canonical_timeframe` is a field of the dataset, not a universal law that every market is M15. This dataset's native fetch is M15.

Broker name is **lineage**, not a guessed PK. Do not write `ICMarketsSC-Demo` onto the two-year candidate unless a fetch log says so.

---

## 3. Projection (not a second corpus)

A projection is a deterministic function of the admitted artifact. It is **not an artifact authority**.

```yaml
H4:
  role: projection
  producer: features.parent_candle.ParentCandleBuilder
  rule: H4
  parent: M15
  parent_sha256: 4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56
  derivation: direct
```

Identity of a projection:

```text
(dataset_id, rule, parent_sha256, producer_id)
```

H4 inherits from **dataset + M15 hash + producer + rule**, not from H1. That is the identity rule that stops BC-1 at HTF: there is no `XAUUSD_H4` logical id to bind.

`derivation: direct` is required on every coarser slot.

### Why the star is required (not merely cleaner)

1. **Tail bucket.** `resample(resample(M15,"H1"),"H4")` vs `resample(M15,"H4")` differ by one dropped partial bucket (`src/research/resample.py`, 2026-08-22 correction). Prefer the DIRECT rule.
2. **W1 ⊄ MN1.** `aggregate(M15,"MN1") ≠ aggregate(aggregate(M15,"W1"),"MN1")` is a permanent calendar inequality (`src/features/calendar_periods.py`). MN1 is always aggregated from the base stream. W1 forbidden as parent.

A stored derived CSV, if ever written, is a **cache** whose hash is checked against a rebuild. Never a second admitted corpus.

Forming-bar on projections: `ParentCandleBuilder` never exposes the in-progress parent (G-09 proven by construction for this producer). Trailing partial is dropped.

### Producers (closed)

| Producer | Slot |
|---|---|
| `features.parent_candle.ParentCandleBuilder` | Canonical derivation (streaming; Parent CRT) |
| `research.resample` | Optional batch materialization; same OHLC contract; tail-count caveat; not a second authority |
| `runtime.backtest_v2.HTFBuilder` | **Not a projection.** Count-based clock (`rolling_count_htf`, CX-OHLCV-007). Different object |

Do not mint `CalendarHTFBuilder`.

---

## 4. Authoritative vs FORENSIC

### Authoritative

```text
DatasetIdentity
  canonical_artifact (admitted M15)
  ParentCandleBuilder projections (functions of that artifact)
```

### FORENSIC / NOT_ADMITTED

```text
data/mt5/XAUUSD_H1.csv
data/mt5/XAUUSD_H4.csv          # DUP-005 twin of quarantine
data/_rejected/XAUUSD_H4.csv
data/XAUUSD_M15.csv             # extended root 486cf361… — still out of Phase-1 scope
data/mt5/_rejected/XAUUSD_M15.csv
data/yfinance/XAUUSD_M15.csv
```

FORENSIC files may be used for `native_h4` vs `derived_h4` studies, TradingView parity, and clock investigations. They **do not participate in corpus authority**. They are not what `ParentCRTFeed` reads (`src/` has zero reads of `XAUUSD_H4.csv`).

If a later measurement uses broker-native H4, it must declare `parent_timeframe_source: native_h4` and is a **different population** from `parent_timeframe_source: derived_h4`. Do not assume equivalence. F-080 already shows they can differ at the daily-open bar.

---

## 5. Parent CRT population (formalizes F-075)

Parent CRT does not consume `data/mt5/XAUUSD_H4.csv`.

```text
admitted M15
  → ParentCandleBuilder(rule="H4")
  → ParentCRTTrack
  → ParentCRTFeed.bias
  → CRTEngine.process_candle(..., parent_state=)
```

Config `parent_crt.timeframe: H4` names the **rule** applied to the child stream, not a file.

The authoritative Parent CRT population is already `derived_h4`. This freeze records that. It does not introduce a new HTF object.

---

## 6. Relation to frozen L0–L5

Canonical Layer Identity stays CLOSED:

| Frozen layer | Object |
|---|---|
| L0 | One bar `(instrument, timeframe, bar_open_ts, corpus_sha256)` |
| L1–L5 | Feature values / states / CRT occupancy / geometry / outcome |

Dataset Identity sits **upstream** of L0. It owns the `corpus_sha256` of the canonical artifact. Projection bars, when materialized, carry their own `corpus_sha256` (hash of those derived bytes, or of the identity tuple if never stored). A later identity-contract amendment **may** add `dataset_id` as L0 lineage; this freeze does not reopen that contract.

Do not remap L0–L5 onto Corpus / Timeframe / Bar / Liquidity / Structure / CRT.

---

## 7. R0–R2 substrate (retained)

Row-level OHLCV integrity (G-01…G-04) is strong. The layer still fails on identity, semantics, and provenance until R3 admits a dataset.

R0–R2 chain (still true of CAD-* archive rows):

```text
logical corpus
  → approved physical artifact
  → exact SHA-256
  → source family
  → transformation chain
  → authority decision
```

UNRESOLVED rows cannot enter binding manifest and cannot be loaded by governed research paths once R3 exists.

R3 target (this freeze):

```text
dataset_id
  → canonical admitted artifact (path + sha256)
  → direct projections (functions)
  → load-time hash check on the canonical artifact
```

**R3 v1 built (CH-dataset-identity-r3-v1):** Dataset Identity JSON + registry index + `src/data_ingestion/dataset_registry.py` + `CandleLoader` admission. Scope = bound datasets only (`unbound_load_policy: path_passthrough`). CAD schema still `SYMBOL_TIMEFRAME` archive. Global UNRESOLVED reject is **not** this slice.

### Dependency graph

```text
                    DATASET IDENTITY (this freeze)
                              │
                              ↓
                 CORPUS BINDING MANIFEST          ← R3 v1 (dataset_identity_registry.json)
                  dataset_id → canonical artifact
                              │
                              ↓
                  LOAD-TIME ADMISSION GATE        ← R3 v1 (DatasetRegistry.admit_csv_path)
                              │
                ┌─────────────┼──────────────┐
                ↓             ↓              ↓
         PROVENANCE      FIELD SEMANTICS   TEMPORAL
```

XAUUSD M15 `CandleLoader` rewrite to `data/mt5/XAUUSD_M15.csv` @ `4d73f5ce…` is the first **bound** Dataset Identity slot. Other instruments remain path-passthrough until a dataset record is added.

---

## Decision statuses

| Status | Meaning |
|---|---|
| `APPROVED` | Exact bytes may enter a binding manifest (R3) for governed load |
| `REJECTED` | Explicitly not authoritative; do not bind or load as canonical |
| `QUARANTINED` | Held out of authority; may remain on disk for forensics |
| `UNRESOLVED` | **Default seed.** No binding. R3 v1: still path-passthrough (unbound regime). R3b (not authorized): no governed load. |
| `FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION` | **Scope freeze only.** Exact path+hash+range may be used for Phase-1 validation probes — **not** AUTHORITATIVE / VALIDATED / ECONOMICALLY_ADMISSIBLE / APPROVED |

Critical rules:

```text
UNRESOLVED
  → cannot enter binding manifest
  → R3 v1: path-passthrough if the instrument is not a bound dataset
  → R3b (not authorized): cannot be loaded by governed research paths

FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION
  → Phase-1 work MUST target the frozen object only (fail-closed hash/range)
  → does NOT grant production authority or economic admissibility
  → promotion requires a later APPROVED decision on the SAME hash
```

### XAUUSD Phase-1 frozen candidate (active canonical artifact)

| Field | Value |
|---|---|
| Binding | [`xauusd_m15_phase1_frozen_candidate.json`](xauusd_m15_phase1_frozen_candidate.json) |
| Path | `data/mt5/XAUUSD_M15.csv` |
| SHA-256 | `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56` |
| Range | `2024-05-22T01:00:00` → `2026-05-21T23:45:00` (47,275 rows) |
| Enforcer | `src/data_ingestion/xauusd_phase1_candidate.py` |
| Status | `FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION` |

**Out of scope for Phase-1 XAUUSD validation:** `data/XAUUSD_M15.csv` (extended root `486cf361…`), quarantine twin, yfinance short window.

Census `authority_class` (e.g. `AUTHORITATIVE_CANONICAL` by path convention) is
**inventory evidence**, not an authority decision. Seeding never auto-APPROVEs.

This freeze does **not** select Option A/B/C/D as an APPROVED promotion. The Phase-1 candidate remains the canonical artifact of `XAUUSD_MT5_PHASE1_20260521` under frozen-candidate status.

---

## G-10 synthetic corpora (design constraint)

Guarantee G-10 (`no undeclared substitution`) is CONTRADICTED under the current
system. Remediation must **not ban synthetic corpora**. It must require:

- declared derivation lineage (`transformation_chain` / parent ids), and
- field semantics (`volume_semantic`, `volume_meta.is_synthetic`, etc.)

bound to corpus identity. Undeclared synthesis is the defect; declared synthesis
with lineage is admissible under authority rules.

HTF projections are **declared** synthesis of the admitted M15 (lineage = parent hash + producer + rule). That is the G-10-legal form. Native HTF files presented as if they were that projection, without the identity tuple, are undeclared substitution.

---

## XAUUSD golden vertical slice

See [`corpus_authority_XAUUSD_M15_adjudication-2026-07-10.md`](corpus_authority_XAUUSD_M15_adjudication-2026-07-10.md).

User must select Option A/B/C/D before any byte move or R3 **APPROVED** admission. The object model in this file does not move bytes.

---

## Enforcement today

| Layer | Mechanism |
|---|---|
| Object-model freeze | this document (`DATASET_IDENTITY_STATUS = FROZEN`) |
| Process freeze (bytes) | freeze policy doc |
| Mechanical pin | `tests/test_ohlcv_corpus_freeze.py` |
| Decision integrity | `tests/test_corpus_authority_decisions.py` |
| Load-time admission | R3 v1: `src/data_ingestion/dataset_registry.py` `admit_csv_path` (bound datasets). Phase-1 module remains the XAUUSD hash/range enforcer. Unbound = path_passthrough. |
