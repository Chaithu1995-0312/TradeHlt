# MSIP-1 Design Contract Correction — 2026-07-14

**Status:** CORRECTION TO PROPOSED DESIGN (not implementation; not activation)  
**Trigger:** Executable XAUUSD CRT baseline + transition traces  
**Evidence labels:** PROVEN_BY_EXECUTABLE_EVIDENCE unless noted  

---

## 1. Frozen baseline (do not overwrite)

| Field | Value |
|---|---|
| Artifact | `XAUUSD_CRT_BASELINE_TRACE_V1` |
| Selection | `FIRST_16_FINALIZED_BARS` |
| SHA-256 | `26e185b943ec5caeee31d32a0b598b543f00a48f953d9fefc9a272eb77ea72d7` |
| Status | **FROZEN_SUCCESS** |
| Pointer | `docs/governance/xauusd_crt_baseline_trace/XAUUSD_CRT_BASELINE_TRACE_V1_FREEZE.json` |

This run is mechanism proof (all-RANGE window). Later traces are **new artifacts**.

---

## 2. Material architectural finding (CORRECTED)

### Prior (incorrect design assumption)

```text
38 certified features
        ↓
CRT state machine
```

### Executable reality (PROVEN)

```text
XAUUSD OHLCV ──► FeaturePipeline ──► 38 canonical vector
                      │
                      └── attached at TRADE_OPENED (BacktestRunner journal)

XAUUSD OHLCV ──► RAW OHLC + CRT-local math + state memory + CRTConfig
                      ↓
                 CRT process_candle
                      ↓
                 guards → transitions → events/trades
```

**CRT transition guards do not consume the 38-dim FeaturePipeline vector.**

Evidence:

- Path verification: `docs/governance/XAUUSD_CRT_TRACE_PATH_VERIFICATION.md` (C-CRT-FEAT-001)
- Baseline + transition traces: `process_candle(candle, htf_id)` only
- `CRT_INPUT_AUTHORITY_MATRIX_V1.json`

---

## 3. Corrected target architecture

MSIP is **not** “add dynamic config and wire CRT to MarketStateVector tomorrow.”

```text
CURRENT (frozen observation target)

RAW MARKET DATA
      │
      ├──────────────► FeaturePipeline ──► 38 canonical vector ──► journal/models
      │
      ▼
CRT-local interpretation (private math + state + config)
      │
      ▼
CRT state machine  ──► decisions / trades


TARGET (MSIP program — multi-stage)

RAW MARKET DATA
      ↓
CERTIFIED FEATURES (+ registered CRT-local quantities where parity proven)
      ↓
STATE INTERPRETATION LAYER (MSIP)  ── shadow only at first
      ↓
MarketStateVector
      ↓
SHADOW comparison vs CURRENT CRT decisions
      ↓
(only later, Authority Ladder) optional CRT consumer migration
```

### Mandatory MSIP sequence (corrected)

1. Identify CRT-local market mathematics  
2. Map each CRT input → canonical / non-canonical / CRT-private / config / duplicate  
3. Decide authority owner  
4. Build interpretation layer  
5. **Shadow** MarketStateVector  
6. Bar-by-bar comparison vs current CRT  
7. Only then consider CRT consumer migration  

**Forbidden short-cut:** implement MarketStateVector and immediately bind CRT.

---

## 4. Transition coverage status

| Artifact | Purpose |
|---|---|
| `XAUUSD_CRT_TRANSITION_TRACE_V1` | First feature-ready RANGE→SWEEP + 8 pre + 15 post (24 bars) |
| `crt_executable_transition_coverage_corpus_v1.json` | Full-corpus first-hit family index |
| `CRT_TRANSITION_COVERAGE_MATRIX_V1.json` | Family classifications |

Observed in full Phase-1 scan (active config):  
RANGE→SWEEP, SWEEP→DISPLACEMENT, DISPLACEMENT→EXPANSION, EXPANSION→RETEST, EXPANSION→EXPIRED, RETEST→EXECUTION, TRADE_OPENED/EXIT, shadow paths, resets — see matrix.

**Gap:** dedicated 8+1+15 windows not yet captured for every family (only first-hit timestamps + one primary window).

---

## 5. Design questions — status updates

| ID | Prior | Update |
|---|---|---|
| OQ-001 | OPEN | **CONSTRAINED:** MSIP must start as shadow/sidecar; CRT remains CLOSED trade lifecycle authority until reopen conditions + Authority Ladder |
| OQ-002 | OPEN | **BIAS:** MarketStateVector may *observe* `crt_phase` as read-only; must not fork CRT edges |
| OQ-005 | shadow bias | **STRENGTHENED → REQUIRED for phase 1** |
| OQ-009 (NEW) | — | How to prove CRT-local ATR/EMA/body_ratio parity vs pipeline before any binding? |
| OQ-010 (NEW) | — | Which CRT-private quantities stay forever private (range refs, sweep_event memory)? |

---

## 6. Non-goals (reinforced)

- No CRT redesign in MSIP-1  
- No production cutover  
- No formula changes to closed CRT surface without reopen  
- No claiming 38-vector “drives” CRT transitions  
- No economic edge claims from traces  

---

## 7. Recommended next engineering steps

1. Keep baseline V1 frozen.  
2. Expand transition corpus: dedicated windows for SWEEP→DISP, DISP→EXP, EXP→RETEST, RETEST soft-conf, TRADE_OPENED.  
3. Use `CRT_INPUT_AUTHORITY_MATRIX_V1` as the migration backlog.  
4. Implement MSIP **shadow only**.  
5. Re-verify MSIP package with this correction attached.

---

## 8. Behavior-preservation policy (2026-07-14)

See [`TASK_CLASSIFICATION_BEHAVIOR_POLICY.md`](TASK_CLASSIFICATION_BEHAVIOR_POLICY.md).

- General requirement to match historical baseline transition/event/trade hashes: **SUPERSEDED**.
- MSIP shadow / observation work: **OBSERVATION_ONLY** neutrality still required.
- MSIP consumer cutover / CRT redesign: **BEHAVIOR_CHANGE_AUTHORIZED** when planned — evaluate before/after + invariants, not historical hash equality alone.

## 9. Authority

Research/governance design correction only.  
Grants **no** production wiring, CRT reopen, or model enablement (§6.5).
