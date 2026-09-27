# DC-HTF-AUTHORITY-01 — HTF clock vs M15 range ownership

| Field | Value |
|---|---|
| **ID** | DC-HTF-AUTHORITY-01 |
| **Status** | LOCKS CLOSED (D1–D3 FROZEN); W1 gate open; patch PARKED|
| **Domain** | trading-infra |
| **Sources** | `src/config_layer/m15_structural_range.py`; `ResetLogic.should_reset` in `src/config_layer/crt_engine_v2.py`; `HTFBuilder` in `src/runtime/backtest_v2.py`; `structure.predicates.swept_high/swept_low`; active prod `v2_htfcrt_2026_08` |
| **Frozen** | ownership map yes; structural-break predicate pending User confirm |

## Intention

Name who owns what so HTF / reset / sweep changes land on the right chain.

## Bridge

Config W ↔ HTFBuilder clock ↔ ResetLogic lifecycle  
≠  
child window ↔ `from_child_window` ↔ `h_ref`/`l_ref` ↔ `detect_sweep`

## Decision (ownership)

| Object | Owns | Does not own |
|---|---|---|
| `htf_candles_per_range` (W) | Clock period (how often `current_htf_id` flips) | Range geometry; sweep truth |
| `HTFBuilder.current_htf_id` / `clock_id` | **Lifecycle cadence** (partition / sync token stamped onto the range) | Structure; sweep entry |
| `h_ref` / `l_ref` | **Sweep / structure authority** (max-high / min-low of caller-chosen children) | When the narrative resets |
| `detect_sweep` / `swept_high`/`swept_low` | **Entry validation** — wick beyond ref, close back inside | Range teardown |
| `ResetLogic.should_reset` | **State-machine lifecycle transitions** → RANGE | Structural formula |

Classification follows ownership:

- Dataset / G1 W vs `parent_crt.timeframe` → validation
- `detect_sweep` → entry filter
- `ResetLogic.should_reset` → lifecycle transition
- `current_htf_id` → lifecycle clock

## Invariant — birth vs rebuild asymmetry

Characterized in `m15_structural_range.py` (not domain-certified):

| When | Child window for `h_ref`/`l_ref` |
|---|---|
| First range (`initialise_range` / HTFBuilder seed) | Completed HTFBuilder list = **W** bars |
| Later ranges (post-reset rebuild in `process_candle`) | `candle_buffer[-atr_period:]` (**default 14**) |

So **range birth authority changes after initialization**. Any reasoning that assumes “the range is the HTF window” is false after the first reset. Fixing that asymmetry is a separate authorized change from the reset-trigger policy.

## Structural-break policy (proposed — not applied until confirm)

Today: HTF branch of `should_reset` fires on `current_htf_id != active_range.clock_id` (with EXPANSION/RETEST + open-trade protects).

Proposed: teardown ownership moves onto the **structure** chain:

- **Break (reset):** `close > h_ref` OR `close < l_ref`  
  (i.e. `not active_range.is_inside(close)` — acceptance beyond the envelope)
- **Sweep (entry, unchanged):** `high > h_ref and close < h_ref` / `low < l_ref and close > l_ref`  
  (`structure.predicates.swept_high` / `swept_low`)
- **Clock:** `clock_id` remains stamped for telemetry / resolver sync; **no longer a reset cause**
- **Protects retained:** EXPANSION/RETEST; OPEN/TP1 trade block
- **W:** live active config already `htf_candles_per_range = 16` (≥ 12); no config bump required unless pointer drifts
- **Mirror:** `crt_state_resolver` lifecycle HTF arm must follow the same predicate or research/engine drift

Complementarity is deliberate: sweep = reject back inside; break = close accepts outside. Same refs, opposite ownership of the event.

## Plug script (optional)

None yet. Patch surface when confirmed:

1. `ResetLogic.should_reset` HTF branch → structural-break branch
2. Resolver `_apply_lifecycle_resets` HTF arm
3. Tests locking `"HTF changed"` / clock-flip reset (`test_shadow_ttl_lifecycle`, object-relations AST, confusion fixtures)
4. Module / prod comments that claim clock-flip is the only HTF teardown

## Out of scope

- Changing `from_child_window` geometry formula
- Unifying birth window (W) with rebuild window (`atr_period`) — track separately
- Live orders / Hot / AWS
- Claiming edge from this policy edit

## Open questions

- Confirm break predicate = close beyond `h_ref`/`l_ref` (vs wick-beyond without reclaim, vs both)
- Confirm clock-flip is removed as reset cause (vs kept as secondary)
- Whether EXPANSION/RETEST should still suppress **structural** break (today they suppress clock-flip)

---

## REOPEN — 2026-09-22 (design thread only; patch still PARKED)

**Verdict:** Mechanism link is solid. Run 1 is legitimate motivating evidence. It does **not** by itself authorize the structural-break behavior change.

**Companion audit JSON:** `multi_llm/parameter_usage_audit/DC-HTF-AUTHORITY-01_RUN1_REOPEN.json`

### Version pins (for later audit)

| Pin | Value |
|---|---|
| Reopened (IST) | 2026-09-22 |
| Motivating folder | `results/run_20260916_225925_XAUUSD` |
| Canonical content id | `run_20260916_172925` |
| Layer-trace id | `lt_20260916_172925_XAUUSD` |
| Config dump | `logs/config_dumps/XAUUSD_run_20260916_172925_config.json` |
| Config dump sha256[:12] | `b382ec24f235` |
| Active config id | `v2_htfcrt_2026_08` |
| Active config path | `configs/production/v2_htfcrt_2026_08.json` |
| Active config sha256[:12] | `3ca7549e8088` |
| W (`htf_candles_per_range`) | `16` (>=12 satisfied) |
| Fail-closed A | `09ffcb1` |
| Structural-break patch | **PARKED** |

### Evidence attached (scoped)

| Claim | Number | Population |
|---|---:|---|
| RESET_HTF candidate deaths | 1442 | candidate-lifecycle death_reason — use for death-share claims |
| RESET_HTF share | 80.2% | of candidate population |
| SWEEP->RANGE edge | 1372 | L3 state-machine transitions — different population |
| Delta | ~70 | RESET_HTF deaths without SWEEP->RANGE edge |

**Establishes:** clock-flip teardown fires a lot (mechanism).
**Does not establish:** that replacing it improves outcomes (no counterfactual; 3-trade -R pool is not healthy-survivor proof).

### Three open locks (block code)

1. **Directionality** — replace vs add clock-flip; symmetric (`close > h_ref OR close < l_ref`) vs directional.
2. **Protect parity** — keep EXPANSION / RETEST / OPEN / TP1 protects; extend; or drop.
3. **Ordering** — structural-break before / after / instead of clock check (wins when both fire; reason attribution).

Until these are answered, status is **parked pending design**, not parked pending evidence.

### Authorized sequence

1. Reopen card + attach Run 1 evidence **(this section — done)**
2. Resolve the three locks as design decisions (no code).
3. Counterfactual replay on the same corpus: fate of the 1442 under structural-break (trade vs die at later gate).
4. Only then un-park the patch — **HARD GATE:** counterfactual artifact must exist; justification = counterfactual fate table, not the death count. Locks alone do not authorize apply.

### Explicit non-authorization

- No `ResetLogic.should_reset` edit.
- No resolver mirror edit.
- No config W change (already 16).
- No claim that 80.2% implies a bug.

### HARD GATE — counterfactual required before patch

**Patch may not be applied until a counterfactual replay on the 1,442 RESET_HTF candidate deaths is recorded**, showing whether structural-break reset produces trades or merely shifts deaths to a later gate (DISPLACEMENT / EXPANSION / RETEST / post-score filters).

- Closing the three design locks is necessary but **not sufficient**.
- The 1,442 / 80.2% mechanism count is **motivation**, not authorization.
- Authorization = locks resolved **and** counterfactual artifact recorded (path + method + survivor/fate table) on this card and in the audit JSON.
- Applying the patch on death-count strength alone reopens the same motivation-vs-evidence gap that produced the original PARKED state.

---

## Parallel leaves registry (non-colliding)

Rule: each question is a **leaf** with a unique `keyword` + `formula`. Leaves run in parallel — resolving one does not rewrite another.

Machine registry: `multi_llm/parameter_usage_audit/DC-HTF-AUTHORITY-01_PARALLEL_LEAVES.json`

| leaf_id | keyword | status | formula (short) |
|---|---|---|---|
| `L-HTF-DIR` | `HTF_BREAK_DIRECTIONALITY` | **FROZEN** | `DIR := REPLACE_CLOCK × SYMMETRIC; break := (close>h_ref)∨(close<l_ref); clock_flip ∉ reset_causes` |
| `L-HTF-PROT` | `HTF_BREAK_PROTECT_PARITY` | **FROZEN** | `PROT := KEEP_BASELINE; suppressed ∈ {EXPANSION, RETEST, OPEN, TP1}` |
| `L-HTF-ORD` | `HTF_BREAK_CHECK_ORDER` | **FROZEN** | `ORD := BREAK_ONLY; clock_flip ∉ reset_predicates` |
| `L-HTF-CFGATE` | `HTF_COUNTERFACTUAL_GATE` | OPEN_GATE | `APPLY_OK ⇔ LOCKS_CLOSED ∧ CF_RECORDED where CF_RECORDED := artifact(fate_table(1442, structural_break)) sho...` |
| `L-HTF-POP` | `HTF_DEATH_POPULATION_SPLIT` | RESOLVED_DISCIPLINE | `POP_CAND := \|{c : death_reason=RESET_HTF}\| = 1442; POP_EDGE := \|{bars : L3 transition SWEEP→RANGE}\| = 1...` |
| `L-HTF-MECH` | `HTF_MECHANISM_NOT_OUTCOME` | RESOLVED_DISCIPLINE | `MECH := P(death_reason=RESET_HTF) = 0.802; OUT := Δ(expectancy \| REPLACE_CLOCK→BREAK); MECH ⇏ OUT; OUT req...` |
| `L-HTF-IDX` | `HTF_INDEX_BASIS_OFFSET` | MEASURED | `bar_idx(open_ts) = trades.candle_idx − 1; bar_idx(open_ts) = events.candle_index + 62; trades.candle_idx = ...` |
| `L-HTF-FUNNEL` | `HTF_FUNNEL_EDGE_ORDER` | CORRECTED | `PATH := RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION; ¬(EXPANSION → DISPLACEMENT); bottlen...` |

### Lock leaves (still OPEN — your policy calls)

**L-HTF-DIR · `HTF_BREAK_DIRECTIONALITY`**
- Q: Does structural-break replace the clock flip, or add to it? Symmetric or directional?
- Formula: `DIR := {mode × sense} where mode ∈ {REPLACE_CLOCK, ADD_TO_CLOCK} and sense ∈ {SYMMETRIC: close>h_ref ∨ close<l_ref, DIRECTIONAL: break only through active sweep side}`

**L-HTF-PROT · `HTF_BREAK_PROTECT_PARITY`**
- Q: Do EXPANSION / RETEST / OPEN / TP1 protects stay, extend, or drop under structural-break?
- Formula: `PROT := {p ∈ STATES_OR_TRADE_FLAGS : break_may_fire(p)} where baseline_protect = {EXPANSION, RETEST, OPEN, TP1}; choice ∈ {KEEP_BASELINE, EXTEND(S), DROP(S)}`

**L-HTF-ORD · `HTF_BREAK_CHECK_ORDER`**
- Q: Structural-break checked before, after, or instead of clock check?
- Formula: `ORD := eval_order(predicates) ∈ {BREAK_THEN_CLOCK, CLOCK_THEN_BREAK, BREAK_ONLY, CLOCK_ONLY} ; winner := first True under ORD; reason_attr := winner.label`

### Gate leaf

**L-HTF-CFGATE · `HTF_COUNTERFACTUAL_GATE`**
- Formula: `APPLY_OK ⇔ LOCKS_CLOSED ∧ CF_RECORDED where CF_RECORDED := artifact(fate_table(1442, structural_break)) showing trades_produced ∨ deaths_shifted_to_later_gate; ¬APPLY_OK from death_count alone`

### Measured / discipline leaves (not locks)

- `L-HTF-POP` `HTF_DEATH_POPULATION_SPLIT` — RESOLVED_DISCIPLINE
- `L-HTF-MECH` `HTF_MECHANISM_NOT_OUTCOME` — RESOLVED_DISCIPLINE
- `L-HTF-IDX` `HTF_INDEX_BASIS_OFFSET` — MEASURED
- `L-HTF-FUNNEL` `HTF_FUNNEL_EDGE_ORDER` — CORRECTED


---

## LOCK D1 FROZEN — 2026-09-22 (directionality)

| Field | Value |
|---|---|
| **leaf_id** | `L-HTF-DIR` |
| **keyword** | `HTF_BREAK_DIRECTIONALITY` |
| **Decision** | **REPLACE_CLOCK × SYMMETRIC** |
| **Break predicate** | `(close > h_ref) OR (close < l_ref)` |
| **Clock** | `clock_id` retained for telemetry / resolver sync; **not** a reset cause |
| **Frozen by** | User |
| **Frozen at (UTC)** | 2026-09-22T04:19:50Z |


### Options presented (for later audit)

| Option | Chosen? | Meaning |
|---|---|---|
| **REPLACE × SYMMETRIC** | **YES** | Clock out of reset; symmetric close-beyond |
| **REPLACE × DIRECTIONAL** | no | Clock out; break only on active sweep side |
| **ADD × SYMMETRIC** | no | Break or clock can reset; symmetric |
| **ADD × DIRECTIONAL** | no | Dual causes + one-sided break |

**Does not authorize:** any `should_reset` / resolver edit, or un-parking the patch.

**Still open:** D2 protect parity · D3 ordering · W1 counterfactual gate.

**Remaining lock formula (unchanged):**
- D2 `L-HTF-PROT`: keep / extend / drop EXPANSION·RETEST·OPEN·TP1 protects
- D3 `L-HTF-ORD`: BREAK_THEN_CLOCK / CLOCK_THEN_BREAK / BREAK_ONLY / CLOCK_ONLY
  (with REPLACE_CLOCK, BREAK_ONLY is the natural mate — confirm in D3)



---

## LOCK D2 FROZEN — 2026-09-22 (protect parity)

| Field | Value |
|---|---|
| **leaf_id** | `L-HTF-PROT` |
| **keyword** | `HTF_BREAK_PROTECT_PARITY` |
| **Decision** | **KEEP baseline** |
| **Protects (break suppressed)** | EXPANSION · RETEST · OPEN · TP1 |
| **Frozen by** | User |
| **Frozen at (UTC)** | 2026-09-22T04:20:56Z |
| **Audit artifact** | `multi_llm/parameter_usage_audit/DC-HTF-AUTHORITY-01_LOCK_DECISIONS.json` |

### Options presented (for later audit)

| Option | Chosen? | Meaning |
|---|---|---|
| **KEEP baseline** | **YES** | Same holds as prior clock-flip protects |
| **EXTEND** | no | Baseline + named extras |
| **DROP** | no | Break may fire mid-setup / mid-trade |

**Does not authorize:** any `should_reset` / resolver edit, or un-parking the patch.

**Still open:** D3 ordering · W1 counterfactual gate.



---

## LOCK D3 FROZEN — 2026-09-22 (check order)

| Field | Value |
|---|---|
| **leaf_id** | `L-HTF-ORD` |
| **keyword** | `HTF_BREAK_CHECK_ORDER` |
| **Decision** | **BREAK_ONLY** |
| **Eval order** | `[structural_break]` only |
| **Clock** | not a reset predicate (mates D1 REPLACE) |
| **Frozen by** | User |
| **Frozen at (UTC)** | 2026-09-22T04:26:16Z |
| **Audit artifact** | `multi_llm/parameter_usage_audit/DC-HTF-AUTHORITY-01_LOCK_DECISIONS.json` (+ `.md`) |

### Options presented (for later audit)

| Option | Chosen? | Meaning |
|---|---|---|
| **BREAK_ONLY** | **YES** | Structural break is sole HTF reset |
| **BREAK_THEN_CLOCK** | no | Break first; clock if break false |
| **CLOCK_THEN_BREAK** | no | Clock first; break if clock false |
| **CLOCK_ONLY** | no | Rejects structural break |

### Policy bundle (D1+D2+D3) — design locks closed; patch still PARKED

| Lock | Freeze | Options on record |
|---|---|---|
| D1 DIR | REPLACE_CLOCK × SYMMETRIC | 4 cells (REPLACE/ADD × SYM/DIR) |
| D2 PROT | KEEP baseline EXPANSION/RETEST/OPEN/TP1 | KEEP / EXTEND / DROP |
| D3 ORD | BREAK_ONLY | BREAK_ONLY / BREAK_THEN_CLOCK / CLOCK_THEN_BREAK / CLOCK_ONLY |

**HARD GATE still open:** W1 counterfactual fate table on the 1,442 RESET_HTF deaths. Locks alone do **not** authorize apply.

