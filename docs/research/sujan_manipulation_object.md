# SUJAN_MANIPULATION_RESEARCH_PHASE_1 — object spec (SEM-033)

**Status:** CHARACTERIZED · research only · detection only
**Code:** [`src/research/sujan_manipulation/`](../../src/research/sujan_manipulation/)
**Floor:** [`tests/research/test_sujan_manipulation.py`](../../tests/research/test_sujan_manipulation.py)
**Ontology:** `configs/formulas/market_ontology.yaml` SEM-033 · founding UNK-007 (open) · proxy SEM-034 (UNVALIDATED)
**Identity lock:** [`docs/governance/SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md`](../governance/SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md)
**Drift records:** [`sujan_identity_drift_log.md`](sujan_identity_drift_log.md) Record 5 (the object) · Record 6 (the proxy)

This object detects a manipulation event and emits an alert. **Nothing else.**

---

## 1. Frozen definitions

Frozen by the human bridge 2026-08-28. `FROZEN` is a human-bridge status; this document
does not self-certify it.

### Parent Bulk Candle

> A visually dominant candle that defines a range.

**VISUAL CONCEPT. Not mechanically frozen.** No mathematical definition exists and none is
invented here. Parents arrive either supplied **externally** or as a bridge-**confirmed**
subset of the SEM-034 proxy shortlist. See §5.

### Parent Range

```text
Range High = parent candle HIGH
Range Low  = parent candle LOW
```

Full wick-to-wick extent. **Body-only interpretations are REJECTED** — `ParentRange` carries
no body fields, so the rejected reading is not constructible from the object.

### Manipulation

A **later** candle that:

1. purges the parent range high **OR** the parent range low, **AND**
2. closes back **inside** the parent range.

Then `Manipulation = TRUE`. The parent range remains the reference object. Manipulation does
not require the immediately next candle; any later candle may qualify.

---

## 2. The predicate, exactly

Purge arithmetic is **imported** from SP-001 (`src/structure/predicates.py`), never
re-derived locally — local re-derivation is the named `FC-FEATURE-NAME-COLLISION` failure
class. What SP-001 does *not* own is the founding; that stays with the caller, which is what
makes this a new object rather than a re-run of an existing one.

```python
high_purge = swept_high(bar.high, bar.close, range_high) and bar.close > range_low
low_purge  = swept_low(bar.low,  bar.close, range_low)  and bar.close < range_high
```

`swept_high` supplies `high > ref and close < ref` — closed back past the **purged** side.
The added conjunct is the bridge's **fully-inside** ruling: `range_low < close < range_high`.

| side | condition |
|---|---|
| `HIGH_SWEEP` | `high_purge` only |
| `LOW_SWEEP` | `low_purge` only |
| `BOTH` | both — an outside candle purging each boundary and closing inside |

`bar.index > parent.index` is required. The parent can never manipulate its own range.

SP-001 is **strict on both sides**: a candle that merely touches a boundary, or closes exactly
on one, is not manipulation.

**There is no threshold in this object.** No ATR, no volatility, no percentage, no body ratio,
no displacement, no magnitude gate of any kind. The predicate reads OHLC and two levels.

---

## 3. State machine

```text
IDLE -> BULK_FOUND -> WAIT_FOR_MANIPULATION -> MANIPULATION_DETECTED -> ALERT
```

Implemented as five real states (`state.py`), not a boolean, with every transition recorded
to `state_trace.jsonl` so "the machine ran" is an observation rather than a claim.

Bridge rulings encoded in the lifecycle:

- After `ALERT` the monitor returns to `WAIT_FOR_MANIPULATION` and alerts on **every** later
  qualifying candle.
- **No expiry.** A parent stays armed to the end of the corpus.
- Every supplied parent is monitored **independently and in parallel**. Monitors never
  interact and never retire one another.

---

## 4. Required output

```json
{"event": "SUJAN_MANIPULATION_DETECTED",
 "parent_timestamp": "...", "manipulation_timestamp": "...", "side": "HIGH_SWEEP"}
```

Those three fields are the specification's requirement. Each record additionally carries
`parent_index`, `manipulation_index`, `range_high`, `range_low`, `bar_high`, `bar_low`,
`bar_close`, `sem_id` and `economic_claims_allowed: false` — enough that the **alternative**
(looser, SP-001-only) close-back-inside reading is re-derivable from the artifact without a
re-run. The ambiguity is preserved in data, not resolved away.

---

## 5. BULK_CANDLE_SELECTOR = APPROVED_PROXY_UNVALIDATED

Recorded evidence for the concept, verbatim and complete:

- visually dominant
- often large-bodied
- may also be wick-dominant
- **no approved percentage threshold exists**

Until 2026-08-28 this package shipped **no selector** and the constant read `UNRESOLVED`.
On 2026-08-29 the human bridge approved a **mechanical proxy** (drift log Record 6, SEM-034):

> Top-N over the **whole corpus**, computed twice and **never merged** — by FM-002
> `candle_range` and, separately, by FM-001 `body_size`. Ties break by ascending bar index.
> **N = 50.** No window, no percentile, no volatility normalisation, no threshold.

**APPROVED is not VALIDATED.** The proxy has never been agreement-checked against a chart
reading, so it **shortlists candidates** and does not define the concept. **UNK-007 stays
OPEN.** A candidate becomes a parent only when the bridge confirms it on the rendered page
(§5b); `run_candidates` never feeds the detector.

Three selectors exist and no fourth may appear without its own recorded freeze:

| Selector | Decides? |
|---|---|
| `ExplicitTimestampSelector` | No — resolves timestamps the bridge already chose; **fails closed** on any it cannot find (no nearest-bar fallback, which would be an invented rule) |
| `TopNRangeSelector` | SEM-034, wick-inclusive reading |
| `TopNBodySelector` | SEM-034, "often large-bodied" reading |

### 5a. What the first run measured

XAUUSD M15, 47,275 bars, N=50 (`docs/research-readiness/sujan_manipulation/candidates/`):

| Measurement | Value |
|---|---|
| Overlap between the two rankings | **34 of 50** — they disagree on a third of the list |
| Corpus months represented (range / body) | **4 / 5 of 25** — 20+ months return no candidate |
| Parquet cross-check | **AGREES** — 47,166 rows, 0 mismatches at 1e-6, 109 `csv_only` as expected |

The temporal concentration is the top-N-over-corpus rule behaving exactly as specified, not
a defect — but **a shortlist is not a survey**. Months with zero candidates are not evidence
that they contain no bulk candles.

Size is measurable and the arithmetic is independently corroborated. Neither fact makes size
the concept.

### 5b. The confirmation page

`candidates.html` renders each candidate with 40 bars of context and asks one frozen question:

> **Is the marked candle a parent bulk candle — visually dominant, defining a range?**

Deliberately **not blinded** — the bridge needs timestamps because the output is a parents
file — and it says on its face that it is a **curation tool, not a measurement instrument**.
Its `yes` answers are both the runnable parents file and the hand-labelled ground truth
UNK-007's `resolution_metric` needs in order to ever validate SEM-034.

### 5c. Parquet is the check, not the source

The ranking reads `data/mt5/XAUUSD_M15.csv` — tracked, sha-pinned, complete, label-free.
`--verify-parquet` then re-reads `features.candle_range` / `features.body_size` from the
projection and asserts agreement. Parquet is not the source because: the CSV has **no
Parquet twin** (nothing exists under `data/`); the XAUUSD projections live in gitignored
trees, which the measurement contract forbids citing as evidence; their grain is one row per
(bar × direction) and is **109 bars short**; and `clean_labels` carries `y_R_net` / `y_tp1`
in the same table, which would put forward outcomes in the founding's read path.

The check **fails closed** without pyarrow rather than silently degrading to a JSONL read —
a skipped check must never be indistinguishable from a passed one.

---

## 6. Preserved ambiguities

Recorded, not resolved. None of these is closed by an implementation choice.

| Ambiguity | Status | How it is preserved |
|---|---|---|
| Which candle is "bulk" | `UNRESOLVED` (UNK-007, still open) | SEM-034 shortlists under an APPROVED-but-UNVALIDATED proxy; a candidate is not a parent until the bridge confirms it, and every manifest states the proxy status |
| Multi-candle purge/reclaim path | `MULTIPLE INTERPRETATIONS` | The spec's two numbered conditions are properties of one candle, so the single-candle reading is implemented; the path reading is recorded here and not built |
| "Closes back inside" — fully-inside vs past-the-purged-side | Bridge chose **fully inside** | The looser reading is re-derivable from every alert's `bar_close` / `range_high` / `range_low` |
| Is manipulation a bar predicate at all? | `UNKNOWN` | The identity charter warns that CRT may be path-dependent; the reduction to a bar predicate is **bridge-specified**, not model-inferred, and recorded as such in drift Record 5 |

---

## 7. What this object is NOT

Explicitly excluded by the specification and enforced by the test floor:

weekly location · monthly location · order blocks · FVGs · CRT High · CRT Low · objectives ·
expansion · distribution · C1 · C2 · C3 · repository `CRTState` · SMC feature dependencies ·
entries · targets · stops · HTF analysis.

And:

- **Not** ParentCRT `MANIPULATION_C2`. The vocabulary collision with F-077 is bridge-approved
  and recorded (drift Record 5); the objects are unrelated.
- **Not** SEM-031 and not a SEM-031 retune. `research.sujan_crt` is on the forbidden-import
  list. F-095's `REJECT` attaches to SEM-031 and does not travel here — and nothing here
  travels upward to "Sujan CRT" either.
- **Not** a trade object. No entry, stop, target, `forward_walk`, cost model, control, split
  or outcome exists anywhere in the package.

---

## 8. Isolation contract

Forbidden runtime imports (AST-enforced): `config_layer.crt_engine_v2`,
`config_layer.parent_crt`, `runtime.backtest_v2`, `core.engine_runner`,
`research.visual_crt`, `research.sujan_crt`, `research.weekly_sweep`,
`research.candle_state`, `features.feature_pipeline`.

Allowed: `structure.predicates` (SP-001), `data_ingestion.dataset_integrity`, stdlib.

---

## 9. Running it

```bash
# 1. shortlist candidates under the SEM-034 proxy
python -m research.sujan_manipulation candidates --corpus data/mt5/XAUUSD_M15.csv --top-n 50 --verify-parquet

# 2. confirm them in candidates.html, save the yes-set, then detect
python -m research.sujan_manipulation detect --corpus data/mt5/XAUUSD_M15.csv --parents confirmed_parents.json
```

`--verify-parquet` needs a venv interpreter (pyarrow). `detect --parents` is required and has no default. Artifacts: `alerts.jsonl`, `state_trace.jsonl`,
`run_manifest.json`.

**The alert count is an observation, never a result.** Nothing in Phase 1 derives a rate, a
quality, or an economic reading from it. `economic_claims_allowed` is `false` on every record.

---

## 10. Authority

None. No `MC-*`, no `F-*`, no `RF-*` row, no G001, no production config, no promotion, no
spine wiring. Registering SEM-033 does not certify that the object is Sujan's — identity
certification is a human-bridge status the coding layer cannot self-award.

The honest sentence is: *we detected SEM-033, an object the human bridge specified.*
