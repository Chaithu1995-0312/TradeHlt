# Structure-dimension inventory — DISPLACEMENT (first pass)

> **Status:** INVENTORY CLOSED for the first pass. The authorized research
> object is the narrow evidence table in
> [`p_struct_01_displacement_evidence.md`](p_struct_01_displacement_evidence.md)
> — not a six-axis fingerprint. No new ontology node. No new FM-id. No LLM
> authority. No G001. Experiment 1 and P-VSTATE-02 are not amended.
>
> Purpose: before any “structure fingerprint” or evidence contract is
> written, map each proposed dimension onto an **existing** authority.
> If the codebase cannot answer, the cell is `UNDEFINED` — not “LLM decide.”
>
> Architecture lock (user 2026-08-18): the LLM looks for evidence of a
> **declared** structure. It does not invent the structure.

## Layers (not yet built)

| Layer | Job | Who owns it |
|---|---|---|
| 1 Ontology | What structures may exist | `market_ontology.yaml` + Semantic OS — **not** the LLM |
| 2 Deterministic evidence | Does this bar/episode satisfy each component? | Registered formula / engine event / config threshold |
| 3 LLM | Interpret **already-computed** PASS/FAIL + values | Evidence interpreter only |

Do not skip to Layer 3. Do not encode Layer 1 as prose only. Do not
assume the dimensions below are valid until this inventory says they
have an authority.

## Family identity (do not collapse these)

| Object | Authority | Same as CRT DISPLACEMENT? |
|---|---|---|
| CRT `DISPLACEMENT` state | `CRTState` + `VALID_TRANSITIONS` (`state_identity.py:85`) + `try_sweep_to_displacement` | **this family** |
| F-074 direction | impulse away from swept side (LONG: bullish close above sweep.price) | required for this family |
| Pipeline `displacement_flag` | ontology `displacement_flag` — heuristic body/range boolean, distinct from the engine gate | **no** |
| FM-020 `disp_strength` | ATR-normalized magnitude | **no** (a number, not the state) |
| SEM-012 Visual CRT | pool-founded sweep + F-074 vs H4/PDH-PDL, `src/research/visual_crt/` | **no** (different founding structure; F-081 null) |

A fingerprint that mixes these is a new object. Not done here.

## Proposed dimensions → existing authority

Status tokens: `GROUNDED` = a named implementation answers it today ·
`DERIVABLE` = can be computed from existing events without new math ·
`MIS-SCOPED` = a real quantity, but it is not a property of the
displacement **bar** · `UNDEFINED` = no contract. None of these grant
production authority.

### Direction

| Proposal | Status | Authority |
|---|---|---|
| bullish / bearish | `GROUNDED` | F-074 + `Direction` on the SWEEP event / `crt.direction` on the action bar. Engine `STATE_TRANSITION` often has `direction: null` — join the companion SWEEP or the trace. Do not guess. |

### Predecessor

| Proposal | Status | Authority |
|---|---|---|
| after_sweep | `GROUNDED` | Legal hop `SWEEP → DISPLACEMENT` (`VALID_TRANSITIONS`). Temporal distance = bar delta between those two `STATE_TRANSITION` timestamps. N is a **new** config knob if declared — not chosen here. |
| after_range | `UNDEFINED` as a CRT displacement predecessor | `RANGE → DISPLACEMENT` is **not** a legal edge. RANGE only goes to SWEEP or SHADOW_PENDING. A “displacement after range with no sweep” is a **different family**, not this one. |

### Volume context

| Proposal | Status | Authority |
|---|---|---|
| high / normal / low via `volume / volume_ma` | Feature `GROUNDED`; CRT contract `UNDEFINED` | FM-062 `volume_ratio` (`volume / SMA(volume, volume_ma_window)`, default 20). FM-063 `volume_spike` is a separate adaptive-percentile boolean. **Neither is in any CRT state's `when:` block.** F-065: `volume_ma20` is not emitted on the live/backtest decision path; `volume_spike` is declared in `market_crt_states.yaml` and unused there. A “high_volume” **dimension of CRT DISPLACEMENT** does not exist until a contract names FM-062 or FM-063 and a threshold. Threshold not chosen here. |

### Trend relation

| Proposal | Status | Authority |
|---|---|---|
| with_ema / against_ema / neutral | `UNDEFINED` as a displacement dimension | `trend_bias` and pipeline `ema_fast`/`ema_slow` exist. CRT soft-confirmation EMAs (`crt_engine.ema_fast`/`ema_slow`, spans 2/5) are a **different** pair from the pipeline 9/21 pair (F-061 / config-first exception). No registered rule `price_direction != EMA_trend_direction` attached to DISPLACEMENT. Which EMA? Which direction rule? Unanswered = `UNDEFINED`. |

### Retracement

| Proposal | Status | Authority |
|---|---|---|
| shallow / deep / none | `MIS-SCOPED` for a displacement-bar fingerprint | FM-027 `displacement_retrace` is **cross-candle**: retest close vs displacement body. It answers “how far did a later bar come back,” not “what is this displacement bar.” Using it as a dimension **of** the displacement candle conflates two times. The engine’s expansion/retest path has its own depth/ceiling knobs (`retest_atr_depth_fraction`, `retest_min_depth_atr_fraction`). Those are RETEST-stage, and RETEST is out of P-VSTATE-02. |

### Continuation

| Proposal | Status | Authority |
|---|---|---|
| immediate / delayed / none | `DERIVABLE`, not declared | Successor hop `DISPLACEMENT → EXPANSION` is legal. Six `SWEEP → EXPANSION` skips exist on the 2-year file (census). “Immediate” = bars from DISPLACEMENT timestamp to EXPANSION timestamp, or absence. No FM-id, no declared N. Declaring N is a new config key. |

## What an evidence row may look like (only for GROUNDED / DERIVABLE cells)

Example — **not** a new feature, a join of existing artifacts:

```text
event          = STATE_TRANSITION state_to=DISPLACEMENT
direction      = SWEEP.direction  (LONG|SHORT)          GROUNDED
after_sweep    = prior state_from=SWEEP                  GROUNDED
age_bars       = disp_idx - sweep_idx                    DERIVABLE (N undeclared)
volume_ratio   = FM-062 on that timestamp                GROUNDED feature, no CRT cut
expansion_age  = exp_idx - disp_idx or absent            DERIVABLE (N undeclared)
```

The LLM may be shown those values. It may not invent `after_range`,
`against_ema`, or a volume cut.

## What is forbidden in the next build

- A YAML “structure family” that lists `after_range` as an allowed CRT
  displacement predecessor.
- A high_volume PASS/FAIL that does not name FM-062 or FM-063 **and** a
  config key.
- Treating FM-027 as a property of the displacement bar.
- Asking an LLM to fill UNDEFINED cells.
- Minting FM-ids or Semantic OS ids in this inventory.
- Economic census of fingerprints (that is later, and needs a sealed
  measurement contract). P-VSTATE-02 still has no TV pixels for this
  corpus.

## Authorized next step (started 2026-08-18)

User kept this inventory boundary and authorized **only** a research
evidence table (`P-STRUCT-01`), not a fingerprint and not an ontology
addition. Spec: [`p_struct_01_displacement_evidence.md`](p_struct_01_displacement_evidence.md).
Extractor: `scripts/research/p_struct_01_displacement_evidence.py`.
`UNKNOWN_N` is data. FM-062/063 stay numeric where present. Excluded
dimensions stay excluded. No semantic promotion. The table becomes
richer only by an authoritative join or an explicit ontology-contract
change — not because a count looks interesting. Authorized join
2026-08-18: official FM-062/063 via `FeaturePipeline.run()`
(`CH-p-struct-01-official-volume-join`). Authorized contract
2026-08-18: CH-PSTRUCT-04 / SEM-013 — FM-063 as a non-state,
non-economic `volume_participation` qualifier on CRT DISPLACEMENT
(identity of official NoSpike/VolumeSpike). Not `high_volume`.
Not a CRT `when:` predicate. Named measurement 2026-08-18:
CH-PSTRUCT-05 coincidence of already-declared columns (not a new
class, not G001). P-STRUCT-06 CLOSED 2026-08-18:
`CRT_WIRE=DISPLACEMENT:VolumeSpike:ANNOTATION_ONLY`, gate UNUSED.
P-STRUCT-07 CLOSED 2026-08-18 (reviewer-resolved): 07A DO_NOT_CONSUME ·
07B DO_NOT_DECLARE_CLASS_N · 07C DO_NOT_INTRODUCE_EMA_ON_DISPLACEMENT.
