# Phase-1 shadow predicate bundle — SHADOW_PENDING & shadow-resume EXPANSION

**Status:** DESCRIPTIVE_ONLY · economic_claims_allowed=false · no population expansion · no economic claims · no forbidden freeze work

**Date:** 2026-09-10 (Asia/Calcutta)

**Question:** What exact predicate bundle causes the system to declare that a previous displacement still exists and is eligible to resume?

**Object (plain language):** A *deferred displacement continuation*: a displacement that was already accepted in a prior HTF window is stored as shadow memory across an HTF reset; when a same-direction confirming sweep appears in the new window while that memory is still alive, the engine declares SHADOW_PENDING and then collapses into EXPANSION by restoring the prior displacement candle and **skipping** the usual displacement strength checks.

---

## Path the Phase-1 n=6 events actually took

**Authority for the 6 collapses:** engine `crt_engine_v2` bt_run path (events/telemetry), not the YAML feature `when:` blocks alone.

From `event_census/census.json` `common_across_6`:

| Field | Value |
|---|---|
| formation_transition_path | `RANGE -> SHADOW_PENDING -> SWEEP -> EXPANSION` (same-bar SWEEP→EXPANSION) |
| formation_reason_template | `Shadow resume: displacement carried from prior HTF window — strength check skipped` |
| action_label | `SHADOW_EXPANSION_CONFIRMED` |
| shadow_used_true | true |

**Resolver vs engine:** `configs/formulas/market_crt_states.yaml` documents SHADOW_PENDING as memory-only (`when: {}`) and lists `SHADOW_PENDING: [SWEEP, EXPANSION, RANGE]` as a **resolver projection** allowance. Engine identity (`_crt_state_generated.py`) keeps `SHADOW_PENDING → [SWEEP, RANGE]` and reaches EXPANSION via the two-step `try_shadow_pending_to_expansion` (`SHADOW_PENDING→SWEEP` then `SWEEP→EXPANSION`). The 6 events’ reason/action strings match the **engine** collapse, not a FeaturePipeline `when:` match.

Companion JSON: `results/analysis/phase1_resolver_replay/event_census/predicate_bundle.json`

---

## 0. Prerequisite — what sets pending displacement memory

Memory is **created** in `StateMachine.reset_to_range` before clearing DISPLACEMENT fields. Engine has **no** field named `pending_displacement_active`; that name exists on the resolver (`CRTResolverMemory.pending_displacement_active`). Engine “active” ≡ `pending_displacement_candle is not None` and `pending_displacement_ttl > 0`.

### Engine create gate (`crt_engine_v2.py:1893–1915`)

```text
_create_shadow =
    current_state == DISPLACEMENT
    AND displacement_candle is not None
    AND "HTF" in reason
```

If true, sets:

| Field | Source |
|---|---|
| `pending_displacement_candle` | `state.displacement_candle` |
| `pending_displacement_dir` | `state.direction` |
| `pending_displacement_ttl` | `config.pending_displacement_ttl_candles` (default **4**, `state_identity.py` / YAML lifecycle) |
| `pending_displacement_source_htf` | `active_range.htf_candle_id` (or `""`) |
| `pending_displacement_formed_idx` | `state._displacement_entry_idx` |
| `pending_displacement_age_at_reset` | `candle.index - _displacement_entry_idx` |
| `pending_displacement_reason_created` | reset `reason` |
| `pending_displacement_created_idx` | creating bar index (TTL skip) |

Non-HTF reset with ttl>0 **expires** memory (`:1916–1921`).

### Resolver mirror (`crt_state_resolver.py:1030–1055`)

On HTF reset from DISPLACEMENT when `lifecycle.shadow_on_htf_displacement_reset: true`: sets `pending_displacement_active=True`, copies formed_idx / dir / ttl / created_idx. Gap/forced reset clears it.

### TTL tick (engine `process_candle` RANGE, `:2966–2977`)

While in RANGE: if `ttl > 0` and `candle.index != pending_displacement_created_idx`, decrement; at 0 clear candle/dir/created_idx.

---

## 1. Enter SHADOW_PENDING — required predicate bundle

**Site:** `CRTEngine.process_candle` while `current_state == RANGE` (`:3017–3026`) → `StateMachine.try_range_to_shadow_pending` (`:1068–1078`).

### Required conditions (ALL)

1. **Pending memory alive (engine):** `pending_displacement_candle is not None`  
   (Resolver analogue: `pending_displacement_active == True`.)
2. **Confirming sweep detected** on this bar via `RangeDetector.detect_sweep` (`:897+`):
   - `active_range is not None`
   - SP-001 geometry (`structure/predicates.py:70–87`):
     - `swept_high`: `high > h_ref AND close < h_ref` → direction SHORT
     - `swept_low`: `low < l_ref AND close > l_ref` → direction LONG
3. **Direction match:** `sweep.direction == pending_displacement_dir`
4. Then `_transition(RANGE → SHADOW_PENDING)` with reason  
   `Shadow resume: confirming sweep @ {price} dir={dir}`; stores `sweep_event`, sets `direction = sweep.direction`.

### Thresholds / formulas feeding this gate

| Item | Role | Formula / config |
|---|---|---|
| SP-001 `swept_high` / `swept_low` | founding sweep | strict reject through `h_ref`/`l_ref` (not FeaturePipeline `liquidity_sweep` when-block when engine / `htf_range`) |
| `pending_displacement_ttl_candles` | memory survival | default 4 |
| FeaturePipeline / YAML `when:` for SHADOW_PENDING | **none** | `market_crt_states.yaml` SHADOW_PENDING `when: {}` |

### Fields set / carried into SHADOW_PENDING

- `sweep_event`, `direction` (from confirming sweep)
- Prior memory still held: `pending_displacement_*` (candle, dir, ttl, source_htf, formed_idx, …) until consumed

### Code refs

- `crt_engine_v2.py:1068–1078` — `try_range_to_shadow_pending`
- `crt_engine_v2.py:3017–3026` — RANGE branch shadow gate
- `crt_engine_v2.py:897–950` — `detect_sweep`
- `structure/predicates.py:70–87` — SP-001
- `crt_state_resolver.py:1468–1478` — resolver `htf_founding_shadow` mirror
- `market_crt_states.yaml:170–179` — memory-only state note

---

## 2. Shadow-resume EXPANSION — required predicate bundle

**Site:** same candle’s next processing when already `SHADOW_PENDING` (`:3066–3124`) → `try_shadow_pending_to_expansion` (`:1081–1103`).

### Integrity gate before collapse (`:3069–3093`)

```text
_shadow_ok =
    sweep_event is not None
    AND sweep_event.direction == pending_displacement_dir
```

If false → SHADOW_LEAK → clear pending → reset RANGE.

### Collapse (`try_shadow_pending_to_expansion`)

1. Restore: `displacement_candle = pending_displacement_candle`; `direction = pending_displacement_dir`
2. `_transition(SHADOW_PENDING → SWEEP)` reason cites `pending_displacement_formed_idx`
3. `_transition(SWEEP → EXPANSION)` reason:  
   `Shadow resume: displacement carried from prior HTF window — strength check skipped`
4. On success (`:3098–3124`): `action = SHADOW_EXPANSION_CONFIRMED`; `_came_from_shadow = True`; record `shadow_source_htf` / `shadow_formed_idx` from pending; clear all pending_* fields.

### What is SKIPPED (explicit in docstring `:1087–1090`)

Relative to normal `try_sweep_to_displacement` strength path:

- `body_ratio >= body_ratio_min` (FM-010)
- `abs(close-open) >= atr_min_displacement * atr_abs`
- `wick_size/candle_range >= atr_multiplier_min * atr_abs`
- directional/away-from-sweep impulse checks on a **new** displacement bar
- Normal `try_displacement_to_expansion` extension / `expansion_atr_min_distance` gates

Confirming sweep + restored prior displacement is treated as sufficient.

### Memory fields consumed

`pending_displacement_candle`, `pending_displacement_dir`, `pending_displacement_formed_idx`, `pending_displacement_source_htf` (and ttl/age/reason/created_idx cleared after).

### Adjacent (not entry gates)

- `_shadow_htf_alignment` computed after success (`:3103–3114`) — telemetry/signal, **not** a predicate that blocks EXPANSION.
- Resolver continuous path may return EXPANSION directly from SHADOW_PENDING when `pending_displacement_active` (`crt_state_resolver.py:1459–1463`, `_expansion_entry_allowed` `:1846–1848`). Phase-1 six events’ labels still match engine `SHADOW_EXPANSION_CONFIRMED`.

### Code refs

- `crt_engine_v2.py:1081–1103` — `try_shadow_pending_to_expansion`
- `crt_engine_v2.py:3066–3124` — SHADOW_PENDING handler
- `_crt_state_generated.py:50–52` — engine edges (SHADOW→SWEEP; SWEEP→EXPANSION legal)
- `crt_identity_schema.py:259–263` — ratchet: identity must **not** list SHADOW_PENDING→EXPANSION as a direct identity edge
- `market_crt_states.yaml:247–249` — resolver allows EXPANSION as projection

---

## 3. Contrast only — normal DISPLACEMENT → EXPANSION (no shadow)

```text
RANGE + sweep (no matching pending)
  → SWEEP (try_range_to_sweep)
  → DISPLACEMENT (try_sweep_to_displacement: direction/impulse + move/ATR + age + body_ratio + wick/ATR)
  → EXPANSION (try_displacement_to_expansion: directional bar + close beyond disp_close + ATR distance)
```

Shadow path never enters DISPLACEMENT on the resume bar; it restores prior displacement and jumps SWEEP→EXPANSION with strength skipped.

---

## 4. Explicitly NOT required (code + census)

| Claimed requirement | Evidence it is NOT required |
|---|---|
| Order block (OB) | No OB check in shadow gates; census `order_block_distance_zero` for E2/E6; structure note: OB heterogeneous |
| PDH / PDL | Not read in `try_range_to_shadow_pending` / `try_shadow_pending_to_expansion`; structure note: shared “inside D1” ambient ≠ formation gate |
| T1 / T3 agree | Census `T1_T3_agree_at_timestamp` 3/6 True / 3/6 False |
| Parent class / parent track | Census `parent_track_state` C1/C2/C3 mix; `parent_bias` mostly NONE |
| Soft-conf / S_score / decision_distance | Census: null/zero approval scores; no soft-conf decision row |
| CHoCH / break_of_structure | Census `change_of_character_zero_NoCHoCH_all`; shadow YAML `when: {}` |
| FeaturePipeline SHADOW when-states | YAML `when: {}`; state is memory-only |
| Strength re-validation on resume bar | Engine docstring + EXPANSION transition reason |

---

## 5. FeaturePipeline / formula → state encoding → when-clause

For these two transitions specifically:

- **SHADOW_PENDING:** no FeaturePipeline formula → ontology state → `when:` chain. Entry is engine/resolver **memory + SP-001 sweep**.
- **Shadow EXPANSION:** no FeaturePipeline when-clause owns entry; YAML EXPANSION `when: { displacement_flag: [Displacement] }` is soft corroboration for continuous funnel — shadow resume is funnel/injection/memory (`notes` at YAML `:147–154`).
- SP-001 (`swept_high`/`swept_low`) is the only geometric formula on the founding sweep for the engine shadow path.

---

## Forbidden-work confirmation

No continuous_disp_to_expansion flip; no CHoCH wire; no occupancy reopen; no parity optimize; no April reclassify; no TV forensic adjudicator; no unit widening; no economic promotion; no population expansion.

economic_claims_allowed=false
