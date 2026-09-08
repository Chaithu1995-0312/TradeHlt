# JOINT_STATE_EXPLAINABILITY — research episode

**Status:** `EPISODE_ACTIVE` (JSE-001 errata; JSE-002 measured; JSE-003 measured)  
**Opened by:** L-003 package freeze `l003_package_freeze_20260907_201945` (`L-003-FREEZE.v1`)  
**Date (UTC):** `2026-09-07T20:19:45.454186Z`  
**Branch pin:** `feature/trace-parquet-duckdb-query` @ `d7c25f6e55616261b8b229b000875abd3bd315eb`  
**Measurements this pass:** **JSE-001** (engine_state_asof -> Y_joint) · **JSE-002** (engine_state_asof -> path geometry) · **JSE-003** (engine_context_history -> path geometry)

Machine pin (optional): `docs/research/joint_state_explainability_pin.json`.

## Observation hierarchy

> **Entry weak (L-003G) · Current engine_state_asof weak (JSE-001) · Path geometry strong (L-003C–E)**

## Objective

Observe **`Y_joint` populations**.

**Not** determine which outcome is correct.

Explicitly disappeared question: **"Which outcome is right?"**

## Candidate populations

Populations use set notation (Leak-2 freeze):

| Coordinate `s ∈ Σ_joint` | Population |
|---|---|
| `STATE_SL_TP` | `{ x : Y_joint(x) = STATE_SL_TP }` |
| `STATE_SL_SL` | `{ x : Y_joint(x) = STATE_SL_SL }` |
| `STATE_TP_TP` | `{ x : Y_joint(x) = STATE_TP_TP }` |

Do **not** write "JOINT" as if it were already a population without `{ x : Y_joint(x) = s }`.

## Measurement questions only

1. Can state membership be **predicted**?
2. Can state membership be **explained**?
3. Can state membership be **automated**?
4. Does **context** (engine_state_asof now; richer CRT later if declared) explain state membership / path geometry?

## Priors from L-003 (frozen package)

> **ARCH-REVIEW wording errata (`arch_review_falsify_pack_20260908_023341`):** Downgrade "path-defined" → **path-geometry-associated**. L-003C–E show association of path-geometry descriptors with joint membership; that does **not** define the population by path, nor replace the set notation `{ x : Y_joint(x)=s }`.

| Prior | Status / note |
|---|---|
| L-003G entry-time on available anatomy fields | **Falsified** (AUC≈0.516); **path-geometry-associated**, not entry-defined on available fields |
| L-003C–E path geometry | **Associates** with joint membership |
| L-003H/I exit-ordering | **Associates**; trail not sufficient; canonical noun `scanner_exit_precedes_oracle_tp` (`exit_ordering_relation`) |
| CRT / HTF | **Not** on anatomy join historically; joining richer CRT is in-scope later **if declared** — current MeasurementObject is **engine_state_asof**, which is **not** CRT Context |

## Identity reminders (frozen)

- `OutcomeLabel` ∈ {SL_HIT, TP_HIT, TIMEOUT} is value-domain only
- `Y_scanner` / `Y_oracle` emit labels via `f_scanner(path)` / `f_oracle(path)` — same token ≠ same event
- MeasurementObjects remain `REGISTERED_IDENTITY` — not edge; attribution still blocked

## Explicit non-goals / non-promotions

- No "which outcome is correct" adjudication
- No edge claim / no attribution unlock from episode open alone
- No L-003 doctrine reopen (errata only under freeze)
- Never upgrade engine_state_asof negatives to "**CRT falsified**" (ontology: CRT Context ≠ engine_state_asof)

## Cross-links

- Freeze: `docs/governance/ANALYTICS_L003_PACKAGE_FREEZE.md`
- Registry: `docs/governance/MEASUREMENT_OBJECT_REGISTRY.md`
- State space: `docs/governance/ANALYTICS_JOINT_STATE_SPACE_L003L.md`
- Noun parity: `docs/governance/ANALYTICS_NOUN_PARITY_L003M.md`


## JSE-001 — engine_state_asof vs joint-state membership (BNB-only)

**version:** `JSE-001.v1`  
**run_id:** `jse001_crt_context_bnbusdt_20260908_020033` (preserved)  
**generated_at_utc:** `2026-09-07T20:31:37Z`  
**Machine JSON:** `docs/research/jse001_crt_context_bnbusdt-2026-09-07.json`  
**Script:** `scripts/research/jse001_crt_context_join.py`  
**Summary dir:** `results/research/jse001_crt_context_bnbusdt/`

### Ontology / wording errata (required)

**CRT Context ≠ engine_state_asof** unless declared equivalent (it is not).

User rejects upgrading JSE-001 to "CRT falsified".

**Allowed conclusion only:**

```
H0: engine_state_asof explains {x: Y_joint(x)=STATE_SL_TP}
Result: AUC ≈ 0.500
Status: FALSIFIED for this specific join surface (BNBUSDT, one runtime events run)
```

**Not allowed:** "CRT does not explain Y_joint" / "CRT/engine context falsified"

### Question

Does **engine_state_asof** explain / predict joint-state membership on this join?

Scope: **BNB-only** (honest). MeasurementProcess name: **`engine_state_asof`** — piecewise-constant `state_to` from **one** runtime `BNBUSDT_events.jsonl` (GT-3), as-of joined to anatomy entry timestamps. **Not** a claim of full CRT ontology / HTF / parent without evidence.

### Limitations (explicit)

- one instrument (BNBUSDT)
- one runtime events run
- predictor = categorical `state_to` (`engine_state_asof`) only
- not Parent / HTF / manipulation / liquidity / range / transition history

### Data / join

| Item | Value |
|---|---|
| Anatomy | `results/research/bnbusdt_trade_anatomy/trade_dataset_BNBUSDT.csv` (n=139942; 2024-05-23 → 2026-05-21) |
| Y_scanner / Y_oracle cols | `art_outcome` / `outcome` → L-003M `STATE_*` |
| Events population (GT-3) | `results/run_20260603_122112_BNBUSDT/BNBUSDT_events.jsonl` (largest single BNB runtime events file) |
| Series rule | `STATE_TRANSITION` updates to `state_to`; **RESET → RANGE** (clears engine path state to RANGE; documented) |
| Join coverage | **1.000** (139942/139942 non-null) — not `CRT_JOIN_WEAK` |

### Results (joined subset)

**Base rates (Y_joint):** STATE_SL_SL ≈ 0.657 · STATE_SL_TP ≈ 0.320 · STATE_TP_TP ≈ 0.0128

**engine_state marginals (top):** RANGE 104872 · SWEEP 18342 · EXPANSION 12322 · DISPLACEMENT 2552 · EXECUTION 1272

**STATE_SL_TP rate by engine_state (n≥500) vs base 0.320:**

| engine_state | n | rate_SL_TP | lift_SL_TP | rate_SL_SL | rate_TP_TP | lift_TP_TP |
|---|---:|---:|---:|---:|---:|---:|
| RANGE | 104872 | 0.320 | 0.998 | 0.657 | 0.0129 | 1.005 |
| SWEEP | 18342 | 0.326 | 1.019 | 0.652 | 0.0120 | 0.938 |
| EXPANSION | 12322 | 0.319 | 0.995 | 0.659 | 0.0113 | 0.882 |
| DISPLACEMENT | 2552 | 0.317 | 0.992 | 0.658 | 0.0200 | 1.563 |
| EXECUTION | 1272 | 0.292 | 0.911 | 0.683 | 0.0204 | 1.599 |

**Predictability (chronological holdout 70/30 within BNB joined):**

| Model | Target | AUC test |
|---|---|---:|
| engine_state only (one-hot → LR) | STATE_SL_TP ovr | **0.5004** |
| same | STATE_SL_SL ovr | 0.5008 |
| same | STATE_TP_TP ovr | 0.5019 |
| macro ovr (focus three) | — | 0.5010 |
| engine_state + hour (secondary) | STATE_SL_TP | 0.5109 |

**vs L-003G prior** (entry-time AUC ≈ 0.516): engine_state_asof is **not better** (≈0.500 ≈ chance; not > prior+0.02).

Chi-square (engine_state n≥500 × focus joint states) is significant at large N (χ²≈26.6, dof=8, p≈8.4e-4), driven in part by small absolute TP_TP rate bumps in DISPLACEMENT/EXECUTION — **without** useful STATE_SL_TP discrimination (AUC≈0.5; SL_TP lifts ≈ null).

### Lean / falsification (errata-compliant)

**FALSIFY** for this specific join surface only:

```
H0: engine_state_asof explains {x: Y_joint(x)=STATE_SL_TP}
Result: AUC ≈ 0.500
Status: FALSIFIED for this specific join surface (BNBUSDT, one runtime events run)
```

Does **not** promote edge, attribution, or “which outcome is right.” Does **not** claim full CRT/HTF ontology. Does **not** say CRT falsified.

### Populations reminder

| Coordinate | Population |
|---|---|
| STATE_SL_TP | `{ x : Y_joint(x) = STATE_SL_TP }` |
| STATE_SL_SL | `{ x : Y_joint(x) = STATE_SL_SL }` |
| STATE_TP_TP | `{ x : Y_joint(x) = STATE_TP_TP }` |


## JSE-002 — Does engine_state_asof predict path geometry? (BNB-only)

**version:** `JSE-002.v1`  
**run_id:** `jse002_engine_state_path_geometry_20260908_021500`  
**generated_at_utc:** `2026-09-07T20:44:23Z`  
**Machine JSON:** `docs/research/jse002_engine_state_path_geometry_bnbusdt-2026-09-07.json`  
**Script:** `scripts/research/jse002_engine_state_path_geometry.py`  
**Summary dir:** `results/research/jse002_engine_state_path_geometry_bnbusdt/`

### Title / ontology

**Context = `engine_state_asof`** (same join construction as JSE-001). **Do not call it CRT.**

Hypothesis framing (**not** a claim):  
`engine_state_asof` / richer CRT later → ? → path geometry descriptors → `Y_joint`

### Question

Does **engine_state_asof** predict / associate with path geometry descriptors on BNB?

Targets: `bars_to_peak_within_trade` (L-003D buckets), `mfe_r` (L-003D buckets), `time_to_bottom_path` / T_MAE (L-003E buckets), optional `scanner_exit_precedes_oracle_tp` (L-003H BNB events alias of `scanner_exit_before_oracle_tp`).

### Data / join

Same anatomy + same GT-3 events population as JSE-001. Coverage **1.000**.  
L-003H exit-ordering join: matched fraction **1.0**.

### Effect sizes (continuous means/medians by engine_state, n≥500)

**bars_to_peak_within_trade**

| engine_state | n | mean | median | Δmean | Δmedian |
|---|---:|---:|---:|---:|---:|
| RANGE | 101301 | 4.652 | 2.000 | +0.053 | +0.000 |
| SWEEP | 17732 | 4.486 | 2.000 | -0.113 | +0.000 |
| EXPANSION | 11886 | 4.566 | 2.000 | -0.033 | +0.000 |
| DISPLACEMENT | 2466 | 3.699 | 2.000 | -0.900 | +0.000 |
| EXECUTION | 1232 | 4.339 | 2.000 | -0.260 | +0.000 |

**mfe_r**

| engine_state | n | mean | median | Δmean | Δmedian |
|---|---:|---:|---:|---:|---:|
| RANGE | 104872 | 3.871 | 2.768 | -0.009 | -0.013 |
| SWEEP | 18342 | 3.893 | 2.830 | +0.013 | +0.048 |
| EXPANSION | 12322 | 3.791 | 2.763 | -0.088 | -0.019 |
| DISPLACEMENT | 2552 | 4.122 | 2.998 | +0.243 | +0.217 |
| EXECUTION | 1272 | 4.861 | 3.045 | +0.981 | +0.264 |

Absolute Δmean/Δmedian remain small relative to within-bucket L-003C–E separators (path geometry strong as a *descriptor of Y_joint*, weak as a *target of engine_state_asof*).

### Predictability (chrono holdout 70/30, engine_state one-hot → LR)

| Target | Metric | Value |
|---|---|---:|
| peak_bucket multiclass | macro AUC ovr (test) | **0.5045** |
| peak_bucket multiclass | balanced accuracy (test) | 0.2500 |
| mfe_bucket multiclass | macro AUC ovr (test) | **0.5033** |
| mfe_bucket multiclass | balanced accuracy (test) | 0.2500 |
| t_mae_dist_bucket multiclass | macro AUC ovr (test) | **0.4978** |
| binary peak >10 | AUC test | 0.5038 |
| binary mfe 6+ | AUC test | 0.5102 |
| binary T_MAE ≤5 | AUC test | 0.4992 |
| binary scanner_exit_precedes_oracle_tp | AUC test | 0.5006 |

### Comparison vs JSE-001 (Y_joint null)

| Quantity | Value |
|---|---:|
| JSE-001 AUC test STATE_SL_TP (recorded) | 0.5004 |
| JSE-001 STATE_SL_TP replay this run | 0.5004 |
| Best path-geometry macro AUC ovr | 0.5045 |
| Best path-geometry binary AUC | 0.5102 |
| Path better than Y_joint by +0.02? | False |

**engine_state_asof does not separate path geometry meaningfully better than chance, nor meaningfully better than it separates STATE_SL_TP.**

### Lean / falsification

**FALSIFY_PATH_AND_YJOINT**

Path-geometry AUCs also ≈0.5 on this join => engine_state_asof is weak for both direct Y_joint membership and path geometry descriptors (BNB-only; this join surface).

Observation hierarchy remains: **Entry weak (L-003G) · Current engine_state_asof weak (JSE-001) · Path geometry strong (L-003C–E)**

Limitations: one instrument; one events run; categorical `state_to` only; not Parent/HTF/manipulation/liquidity/range/transition history. **Never say CRT falsified.**

### Non-promotions

No edge, no attribution, no “which outcome is right,” no L-003 doctrine reopen, no CRT ontology claim.


## JSE-003 — engine_context_history vs path geometry (BNB-only)

**version:** `JSE-003.v1`  
**run_id:** `jse003_engine_context_history_path_geometry_20260908_021900`  
**generated_at_utc:** `2026-09-07T20:49:00Z`  
**Machine JSON:** `docs/research/jse003_engine_context_history_path_geometry-2026-09-07.json`  
**Script:** `scripts/research/jse003_engine_context_history_path_geometry.py`  
**Summary dir:** `results/research/jse003_engine_context_history_path_geometry/`

### Title / ontology

**Predictor family = `engine_context_history`** (NOT CRT Context). Built from the same GT-3-clean events run as JSE-001/JSE-002.

Never call this CRT unless measuring declared CRT objects. No Parent/HTF/manipulation invented.

### Question

Do **history features** from the BNB runtime events timeline predict path geometry descriptors better than chance / better than single as-of `state_to`?

### History feature definitions (mechanical)

| Feature | Definition |
|---|---|
| `engine_state_asof` | Baseline; piecewise `state_to` as-of entry (should ~0.50) |
| `dwell_bars_in_current_state` | M15 bars since last STATE_TRANSITION/RESET |
| `n_transitions_lookback_W` | Count of update bars in last W∈{4,16,64} M15 bars |
| `frac_time_in_state_W64` | Fraction of last 64 M15 bars in RANGE/SWEEP/EXPANSION/DISPLACEMENT/EXECUTION |
| `last_k_states` | Previous 1–3 distinct states (categorical + hash%97 of triple) |
| `bars_since_last_sweep` | Optional: M15 bars since last SWEEP event |

Bar = 15 minutes (M15 time-equivalent).

### Data / join

Same anatomy + same events: `results/run_20260603_122112_BNBUSDT/BNBUSDT_events.jsonl` (preferred path unchanged). Coverage **1.000**. Expanded history feature count ≈ 48.

### Predictability (chrono holdout 70/30)

| Target | asof-only macro AUC | history-set macro AUC | Δ |
|---|---:|---:|---:|
| peak_bucket | **0.5045** | **0.5146** | +0.010 |
| mfe_bucket | **0.5033** | **0.5081** | +0.005 |
| t_mae_dist_bucket | 0.4978 | 0.4953 | −0.002 |

Binary (history-set): peak>10 AUC **0.5217**; mfe 6+ AUC **0.5114**.

Chrono 50/50 sensitivity: history peak macro ≈0.513; mfe ≈0.508 — still near chance.

### Top history features (mean univariate macro AUC over peak+mfe)

1. `last_2_state` ≈ 0.507  
2. `n_transitions_lookback_16` ≈ 0.505  
3. `engine_state` (asof) ≈ 0.504  
4. `n_transitions_lookback_64` ≈ 0.504  
5. `frac_time_in_SWEEP_W64` ≈ 0.503  

All univariate features remain ≈0.50–0.51.

### Lean / falsification

**FALSIFY** for `engine_context_history → path_geometry` on this join (BNB-only; one events run).

History AUC still ≈0.50–0.55 (best macro 0.515; best binary 0.522); does not meet SUPPORT_ASSOCIATION threshold (AUC≥0.58 + chrono stability). Modest lift over asof (+0.01 peak) is not material.

**Not** a CRT claim. **Not** causal. No edge / attribution / L-003 doctrine reopen.

### Observation hierarchy (updated)

> **Entry weak (L-003G) · engine_state_asof weak (JSE-001/002) · engine_context_history weak (JSE-003) · Path geometry strong as Y_joint descriptor (L-003C–E)**

