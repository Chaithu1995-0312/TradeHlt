# MC-JOINT-01 — Measurement Authority Contract (Y_joint freeze)

| Field | Value |
|---|---|
| **ID** | MC-JOINT-01 |
| **Status** | **FROZEN** |
| **Frozen (UTC+5:30)** | 2026-09-20 |
| **Domain** | measurement-authority (not strategy) |
| **Evidence** | [`JOINT_STATE_CENSUS_01.json`](../parameter_usage_audit/JOINT_STATE_CENSUS_01.json) · n=94,332 XAU clean_labels 2026-07-23 |
| **Specimen** | entry=3430.37 → `JOINT_STATE_SL_TP` (verified in census) |
| **L-003 alignment** | Joint state is primary measured object; mismatch ≠ error; no causal upgrade |

## Intention

Elevate `Y_joint` from forensic hypothesis to **measured ontology object** after census showed `JOINT_STATE_SL_TP ≈ 31%` (#2 lifecycle state, ≈ entire mismatch mass).

## Layer placement

```
Market Data
  → Dataset Integrity
  → Feature Authority
  → Measurement Authority   ← THIS CONTRACT
  → Semantic Authority
```

Scanner walk / oracle walk / joint state are **measurement objects**, not strategy objects.

## Frozen measurement objects

| Object | Source | Role |
|---|---|---|
| `Y_scanner` | stream / opportunity_scanner trail walk (`trail_mult=0.5`) | component |
| `Y_oracle` | path / `forward_walk(exit_model=intrabar_fixed)` | component |
| `Y_joint` | `(Y_scanner, Y_oracle)` → state_id | **primary measured object** |

Components are not rivals. The ontology **describes disagreement**; it does **not** resolve it.

## Frozen joint-state set (exactly six)

Aligned:

1. `BOTH_SL`
2. `BOTH_TP`
3. `BOTH_TIMEOUT`

Disjoint:

4. `JOINT_STATE_SL_TP`   ← scanner SL × oracle TP
5. `JOINT_STATE_TP_SL`   ← scanner TP × oracle SL
6. `JOINT_STATE_SL_TIMEOUT`

**Nothing else** until a new census shows a seventh state at material rate.

### Census rates (evidence, not re-litigation)

| State | n | % |
|---|---:|---:|
| BOTH_SL | 62,077 | 65.81% |
| JOINT_STATE_SL_TP | 29,294 | 31.05% |
| JOINT_STATE_SL_TIMEOUT | 1,566 | 1.66% |
| BOTH_TP | 1,231 | 1.31% |
| JOINT_STATE_TP_SL | 113 | 0.12% |
| BOTH_TIMEOUT | 51 | 0.05% |

Asymmetry `JOINT_STATE_SL_TP` (31%) ≫ `JOINT_STATE_TP_SL` (0.12%) supports trail-early-exit structure, not symmetric candle-order noise.

## Authority rule (frozen separately from ontology)

```yaml
authority_outcome:
  source: path          # F-022 — stream never primary
  fields:
    - path_outcome      # == Y_oracle terminal label
    - y_R_net
```

| May | Must not |
|---|---|
| Use `Y_joint` for population / diagnostics / AB | Treat `Y_scanner` as PnL truth |
| Report mismatch as state membership | Decide “who is correct” inside the ontology |
| Attach `authority_outcome` for money semantics | Collapse joint state into a single winner label |

Optional emit for future engine (not built yet):

```yaml
authority_outcome:   # always points at path
  path_outcome: ...
  y_R_net: ...
```

## Naming / exit mechanism (deferred emit, not new states)

When an emitter exists, prefer mechanism tags under the state — do **not** expand the six-state set:

- `FIXED_SL_HIT` / `TRAIL_HIT` / `TP_HIT` / `TIMEOUT`

`SL_HIT` on stream with `rr_achieved > 0` is known overloaded (trail); census shows ~100% of `JOINT_STATE_SL_TP` have stream `rr_achieved > 0`.

## Out of scope (explicit)

- TradeLifecycleEngine v0 implementation
- Arithmetic Layer
- Causal claims (“trail causes mismatch”)
- Promoting scanner labels to training targets
- HTF structural-break ResetLogic

## Promotion gate for engine v0

Authorized only after this freeze. Engine job is **emit only**:

`Y_scanner`, `Y_oracle`, `Y_joint`, `authority_outcome`, (+ optional exit_mechanism, rr_*, duration, mfe/mae)

No new exit semantics.

## Freeze statement

**FROZEN:** six-state `Y_joint` ontology + path `authority_outcome` contract, evidenced by `JOINT_STATE_CENSUS_01.json`.

**NOT FROZEN / NOT AUTHORIZED:** TradeLifecycleEngine code until User explicitly unblocks v0 against this contract.

## Engine v0 (shipped)

- Module: `src/research/measurement/trade_lifecycle_engine.py`
- API: `measure(entry, sl, tp, side, forward_bars) -> LifecycleMeasurement`
- Emit-only: `Y_scanner` / `Y_oracle` / `Y_joint` / `authority_outcome`
- Specimen `ac95cf287cbdfa3b` → `JOINT_STATE_SL_TP` (certified)
- No new exit semantics; mismatch remains state membership
