# CRT Input & Formula Contract — Phase 2

**Program:** CRT Closure (audit-first)  
**Phase:** 2 of 8  
**Status:** **PASS** — all CRT quantities accounted; **F-050 emission remediated (CH-002)**  
**Twin:** [`crt_formula_contract.json`](crt_formula_contract.json)  
**SM authority:** `crt_engine_v2.CRTEngine` (Phase 1)  
**Config:** `v2_multi_2026_04`

---

## Verdict

| Field | Value |
|---|---|
| **CRT_FORMULA_CONTRACT_STATUS** | **ACCOUNTED_EMISSION_REMEDIATED_CH002** |
| Unaccounted CRT derivations | **0** |
| F-050 emission keys | **REMEDIATED** → FM-027 / FM-028 |

Every raw/derived value CRT reads or computes is classified. CH-002 renamed CRT cache emission keys to match Formula Registry identities.

---

## F-050 boundary (CH-002 remediated)

CRT `cached_features` at RETEST now emit **governed keys**:

| Emission key (CRT) | Math | FM-id | Pipeline (unchanged) |
|---|---|---|---|
| **`displacement_retrace`** | `\|retest.close − disp.open\| / \|disp.body\|` via `derived_math` | **FM-027** | FM-021 still named `retest_depth` |
| **`displacement_atr_ratio`** | `candle_range / atr` via `derived_math` | **FM-028** | FM-020 still named `disp_strength` |
| `body_ratio` | `body/range` via `candle_math` | **FM-010** | same |

**Legacy keys `retest_depth` / `disp_strength` / `disp_str` are no longer emitted** on the CRT cache. BitNet call-site maps FM-027/028 → legacy model input names only when `use_bitnet` is on.

**Third retest concept (policy, not a feature name):** range-boundary `depth_abs` for EXPANSION→RETEST guards.

---

## Classification map (summary)

| Class | Count | Meaning |
|---|---:|---|
| RAW_INPUT | 1 | OHLCV passthrough |
| CANONICAL_ROUTED | 3 | body_size, candle_range, body_ratio → Formula Registry |
| CANONICAL_PRIMITIVE + policy threshold | 1 | range/ATR gate |
| CRT_LOCAL_POLICY | 12 | range, sweep, ATR kernel, G-score, soft-conf, SL/TP, resets, … |
| CRT_LOCAL_POLICY_VARIANT | 1 | f_mom vs FM-022 |
| DOMAIN_POLICY_VARIANT | 1 | sweep wick ratios (eps floor) |
| NAME_COLLISION_F050 | 2 | retest_depth / disp_strength emissions |
| EXTERNAL_BOUNDARY | 1 | BitNet hook (off on prod) |
| BOUNDARY_NON_CRT | 1 | FeaturePipeline 38-dim (adjacent, not SM-owned) |

Full rows: JSON `values[]` (CRT-IN-*, CRT-DER-*, CRT-EXT-*).

---

## What CRT routes through the Formula Registry

| Quantity | FM | Path |
|---|---|---|
| body_size | FM-001 | `Candle.body_size` → `candle_math` |
| candle_range (as `wick_size`) | FM-002 | `Candle.wick_size` → `candle_math.candle_range` |
| body_ratio | FM-010 | `Candle.body_ratio` → `candle_math` |

These are **ALIGNED** (F-046).

## What CRT owns as local policy (not FM features)

Examples (not exhaustive — see JSON):

- HTF range construction (`h_ref`/`l_ref`/`equilibrium`)
- Sweep boundary cross-back rule
- CRT ATR = simple mean of true ranges (not pipeline ATR feature)
- Displacement move / body_ratio_min / atr_multiplier_min gates
- Range-boundary retest `depth_abs` + adaptive ceiling
- Soft-conf manifold C and fusion S
- Structural G-score with **hardcoded** 0.35/0.25/0.20/0.20 weights
- SL/TP from displacement extreme + risk-distance multiples
- Reset retrace % and fib extension
- Shadow age decay

These are **intentional CRT state-machine policy**, not registry violations — unless they **emit under foreign feature names** (F-050).

---

## Contradictions registered (no silent fix)

| ID | Issue | Action |
|---|---|---|
| CX-F050-RETEST | FM-027 math as `retest_depth` | Confirm F-050; defer rename |
| CX-F050-DISP | FM-028 math as `disp_strength` | Confirm F-050 sibling; defer rename |
| CX-THREE-RETEST-CONCEPTS | FM-021 vs FM-027 vs range depth_abs | Documented clarity |
| CX-G-WEIGHTS-HARDCODED | G weights hardcoded; conf_weights config | Defer Phase 5 |

---

## Confirmed findings (no new F-ids)

| F-id | Role in Phase 2 |
|---|---|
| **F-046** | body_ratio canonical via candle_math — **confirmed ALIGNED** on CRT path |
| **F-047** | feature-math / GD ledger context for collisions |
| **F-050** | retest_depth / disp_strength name collisions — **confirmed at CRT boundary** |

**NEW_FINDINGS:** none. Existing F-ids already carry this durable evidence; Phase 2 freezes the CRT-side contract rather than opening a fourth F-id for the same collision.

---

## Out of scope (preserved)

- EngineRunner / journal admission (OI-ER-001)
- Gate 6 rename remediation
- Formula code changes
- Broad backtests

---

## Phase 2 return

```text
CRT_FORMULA_CONTRACT_STATUS = ACCOUNTED_WITH_KNOWN_COLLISIONS
F050_BOUNDARY = DOCUMENTED (no remediation)
UNACCOUNTED_DERIVATIONS = 0
CONFIRMED_FINDINGS = F-046, F-047, F-050
NEW_FINDINGS = none
PHASE2_STATUS = PASS
NEXT = await Phase 3 authorization (9-state executable graph)
```

## Artifacts

| Path | Role |
|---|---|
| `docs/governance/crt_formula_contract.json` | Machine-readable contract |
| `docs/governance/crt_formula_contract.md` | Human companion |
