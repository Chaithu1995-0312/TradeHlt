# Pre-registration: `xau_metals_protocol_v1`

**Status:** **EXECUTED** 2026-07-22/23 (run `20260722T211010Z`) — frozen JSON economic fields unchanged  
**Registered:** 2026-07-23  
**Machine file:** [`configs/research/xau_metals_protocol_v1.json`](../../configs/research/xau_metals_protocol_v1.json)  
**Loader:** [`src/research/xau_metals_protocol.py`](../../src/research/xau_metals_protocol.py)  
**Runner:** [`scripts/research/run_xau_metals_protocol_v1.py`](../../scripts/research/run_xau_metals_protocol_v1.py)  
**Result:** [`results/gaussian_xauusd_econ/xau_metals_protocol_v1/PROTOCOL_V1_RESULT.md`](../../results/gaussian_xauusd_econ/xau_metals_protocol_v1/PROTOCOL_V1_RESULT.md) · [`EXECUTION_RECORD.json`](../../results/gaussian_xauusd_econ/xau_metals_protocol_v1/EXECUTION_RECORD.json)  
**Floors:** `tests/test_xau_metals_protocol_v1.py`  
**Parent design:** [`docs/implementation_plan/xauusd-gaussian-toward-economics-2026-07-23.md`](../implementation_plan/xauusd-gaussian-toward-economics-2026-07-23.md)  
**Falsification that forced this:** [`results/gaussian_xauusd_econ/CONVERSATION_FALSIFICATION.md`](../../results/gaussian_xauusd_econ/CONVERSATION_FALSIFICATION.md)

### Execution snapshot (research-only; no economic authority)

| Field | Value |
|---|---|
| protocol_sha256 | `2a562f39e46058df0b6561bd5ba8b6d631f71144126cf3e9f6127f4af518e471` |
| RETEST scored n | 30 (train 26 / oos 4) |
| SWEEP diagnostic (not primary) | 3252 enter edges |
| Control acceptance | PASS |
| E1 kills | `NO_RELATIVE_SKILL`, `NO_ABSOLUTE_EDGE` |
| Primary M4 (`nb_top_decile`) | **INSUFFICIENT** (n=9 &lt; min_samples=30) |
| any_PROMOTE | false |
| n_permutations formal | **2000** (M4 re-run from frozen units; first execute used 200 CLI) |
| economic_authority_granted | **false** |
| E3 allowed | false |

---

## Why a new protocol

| Defect in v0 (conversation train / E0–E2) | v1 fix (frozen now) |
|---|---|
| Flat **12 bps** → often `cost_R > 1` on gold M15 | Primary **fixed USD round-trip** `0.40` |
| Entry = **SWEEP** (detection) | Entry = **RETEST enter edge** |
| Control arm double-tagged → n inflated | **Per-split size-match** + single tag + acceptance test |
| “Skill” read as economics | Absolute E gate + M4 still required; no auto authority |

**This document freezes decisions before any re-run.** Changing any primary field requires a **new `protocol_id`**.

---

## 1. Cost model for metals — `XAU_COST_V1_FIXED_USD`

### Primary (gate)

```text
cost_R = usd_round_trip / risk_distance
risk_distance = sl_atr_mult * atr_abs
usd_round_trip = 0.40   # declared prior, NOT fit on this corpus
net_R = gross_R - cost_R
```

**Rationale (pre-data for *this* protocol’s choice, not post-hoc):**  
Falsification showed ~45% of TP paths under 12 bps had `cost_R > 1` on XAU M15. Fixed USD spread is a standard metals research alternative. **0.40 USD RT** is a stated prior (~0.20/side), **not** optimized against y_rr / OOS / M4.

### Sensitivity (diagnostic only — cannot promote)

`usd_round_trip ∈ {0.20, 0.40, 0.80}` — report tables only.

### Legacy diagnostic only

12 bps flat — compare to v0 only; **never** primary under v1.

### Forbidden

- Picking USD after seeing OOS E[R]  
- Adaptive per-bar spread fit on the evaluation corpus  

---

## 2. Entry ontology — `XAU_ENTRY_V2_RETEST_EDGE`

### Primary universe

- CRT state **edge into `RETEST`** (`prev != RETEST`, `current == RETEST`)  
- Direction ∈ {long, short}  
- Entry price = bar close  
- Exclude: no direction, non-positive ATR, OOB for forward walk  

### Holdout

Trailing **2 calendar months** from corpus max timestamp (same family as v0).

### Explicitly not primary (without new protocol_id)

- SWEEP-as-entry (v0)  
- All bars  
- TRADE_OPENED-only as sole gated set if n &lt; 30 (may be diagnostic count only)  

### Model

**No retrain** under v1: score with frozen  
`xauusd_nb_20260722T194904Z` (39-dim name-anchored).  
Retrain = new protocol.

---

## 3. Fixed control arm — `XAU_CTRL_V1_RANDOM_MATCH`

```text
For split in {train, oos}:
  k = |{i in split : score_i >= p90_train}|
  draw k indices from split candidates without replacement
  seeds: sha256("xau_metals_protocol_v1|random_match_n|{split}")[:8] as u32
```

**Acceptance (hard fail if false):**

```text
len(random) == len(top)
len(random ∩ train) == len(top ∩ train)
len(random ∩ oos) == len(top ∩ oos)
```

**Membership list for M4:** single arm id `random_match_n` only  
(no inclusive union of `_train` / `_oos` tags — fixes E2 inflation).

**Quantiles:** p10/p90 on **train scores only**.

---

## 4. Exit geometry (isolated change vs cost)

Keep **1R / 1R**, `intrabar_fixed`, max_forward 40 — so v1 vs v0 isolates **cost + entry + control**, not a simultaneous SL/TP redesign.  
Planner-true SL/TP → `xau_metals_protocol_v2` (or similar).

---

## 5. M4 (formal record)

Defaults from `research_config_majors.json` qualification block:

- min_samples 30, E_min 0, PF_min 1.0, oos_retention 0.5, 2000 perm, α 0.05  
- Primary hypothesis: `nb_top_decile`  
- Control: `random_match_n` (acceptance must pass)  
- Primary cost only for gate; sensitivity grid not a gate  

**Even PROMOTE → research only** until separate human E3 + live-path ΔG001.

---

## 6. Kill criteria (pre-registered)

| Stage | Kill |
|---|---|
| E1 relative | OOS top E ≤ all AND ≤ random → `NO_RELATIVE_SKILL` |
| E1 absolute | OOS top E &lt; 0 → `NO_ABSOLUTE_EDGE` (still log M4) |
| E2 | primary ≠ PROMOTE → **no E3** |
| Any | Do not invent costs/entries after kill; bump `protocol_id` |

---

## 7. Execution order (when implemented)

1. Record `protocol_sha256` of the JSON  
2. Stream RETEST edges + journal kinds  
3. Score frozen model  
4. Label with primary USD cost (+ sensitivity diagnostic)  
5. Arms + control acceptance_test  
6. E1 tables + kills  
7. M4  
8. Manifests; `economic_authority_granted=false` unless later human E3  

**Outputs dir:** `results/gaussian_xauusd_econ/xau_metals_protocol_v1/`

---

## 8. What this pre-registration is not

- Not a claim that 0.40 USD is “true” broker cost  
- Not permission to live-wire ML  
- Not a retrain  
- ~~Not executed~~ → **Executed** 20260722T211010Z; result under `results/gaussian_xauusd_econ/xau_metals_protocol_v1/` (frozen JSON `status` field left as pre-reg stamp; authority still research-only)

---

## 9. Sign-off

| Role | Statement |
|---|---|
| Protocol | Frozen in `configs/research/xau_metals_protocol_v1.json` |
| Tests | Enforce id, cost mode, entry state, control acceptance math |
| Next build | Implement runner that **only** reads this file (no CLI override of primary cost/entry without `--protocol` pointing at a new id) |
