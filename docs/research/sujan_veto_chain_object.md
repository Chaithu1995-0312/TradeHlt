# Sujan nested veto chain — SEM-031 (geometry freeze)

**Status:** Lane 1 code (`P-SUJAN-01`) · `knowledge_status: CHARACTERIZED` · frozen before measurement  
**Date:** 2026-08-27 · **Change:** `CH-sujan-veto-chain-v1`  
**Code:** `src/research/sujan_crt/` · **Floor:** `tests/research/test_sujan_veto_chain.py`  
**Accepted reading:** [`.grok/SUJAN_ACCEPTED.md`](../../.grok/SUJAN_ACCEPTED.md)  
**Identity lock:** [`docs/governance/SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md`](../governance/SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md) — this object is a mechanical **projection**. Identity with Sujan-as-narrated is NOT established (F-095). Do not retune after seeing `y`. New Sujan work loads the identity lock first.

Not a production spec. Not G001. `P-SUJAN-02` sealed `MC-SUJAN-XAUUSD-M15-V1` against **this projection**.

---

## 1. Why this object exists

The two SujanTrader transcripts are one AI-side dialogue. On 2026-08-27 the user accepted a nested reading: **conjunction of vetoes**, not a 100-point score. This file freezes the geometry that code is allowed to run.

SEM-022 / SEM-023 / SEM-024 / SEM-025 stay registered as 2026-08-22 nodes. This object **does not** implement SEM-022's ParentCRTTrack ladder and **does not** admit on SEM-023.

## 2. What it is not

| Not | Why |
|---|---|
| `CRTState` 9/12-graph | Different object. Isolation AST-enforced. |
| ParentCRT C1/C2/C3 / `DISTRIBUTION_C3` | F-077. Distribution here is a reversal-warning via `HTFState`. |
| Visual CRT (SEM-012) | Different founding (pools). Import forbidden. |
| SEM-023 ≥ 90 | Comparison arm only. Never admission. |
| Romeo 1-3-5-9 | Clock unchosen. Field `romeo_clock=UNUSED`. |
| Displacement magnitude cut | Unchosen. SP-002 direction only. |
| `multi_tp_walk` | One target at the Daily parent extreme. |

## 3. Parameters (no silent defaults)

Caller must pass every field of `VetoParams` plus an `atr` series aligned 1:1 with bars.

| Field | Role |
|---|---|
| `expansion_min_range_ratio` | `HTFState` expansion cut (same classifier as `htf_state.classify_htf_state`) |
| `accumulation_max_range_ratio` | `HTFState` accumulation cut |
| `distribution_min_range_ratio` | `HTFState` distribution cut |
| `location_tolerance_atr` | SEM-024 band in ATR multiples |
| `rr_floor` | SEM-025 floor (lateness, not quality) |
| `max_sweep_age_bars` | displacement must print within this many bars after sweep |
| `max_return_age_bars` | return must print within this many bars after displacement |

Numeric values used in tests are explicit call-site literals, not function defaults. Production config ratios `1.2 / 0.7 / 1.0` are **not** read from ACTIVE_VERSION.

## 4. Veto chain (conjunction)

Evaluated on closed M15 bars only. In-progress calendar parents are dropped.

1. **MN + W bias.** Last closed MN1 and W1 share the same non-none body bias. 6M/3M excluded.
2. **Daily job.** Last closed D1 shares that bias (the named Daily job).
3. **Do not chase.** `classify_htf_state` on the last two closed W1 parents and last two closed D1 parents. If **both** current W1 and current D1 are `EXPANSION` → reject.
4. **Location.** Entry (return close) within `location_tolerance_atr * atr[i]` of a last-closed MN1/W1/D1/H4 high, low, or midpoint formed before the entry bar. This is the V1 admissible set (calendar-parent CRT high/mid/low). SMC order blocks are not in V1.
5. **Sweep.** SP-001 against a prior closed parent high/low. HIGH → short, LOW → long. Deepest pierce wins.
6. **Displacement.** First later bar within `max_sweep_age_bars` that satisfies SP-002 away from the swept side.
7. **Return / entry.** First later bar within `max_return_age_bars` whose range overlaps the displacement bar. Entry = that bar's close. Same-bar return is illegal.
8. **Stop.** Long `min(sweep_price, displacement.low)`; short `max(sweep_price, displacement.high)`.
9. **Target.** Long = last closed D1 high; short = last closed D1 low.
10. **RR floor.** `|target-entry| / |entry-stop| >= rr_floor`. Fail closed if stop distance is 0.

H4 may look opposite the last H4 impulse (Grade B pullback). H4 bias is **not** in vetoes 1–2.

**Size hint** (diagnostic, not admission): `full` if current H4 `HTFState` is `ACCUMULATION`, else `half`.

**SEM-023 score:** computed after admission from the same boolean indicators; stored on the candidate; ignored by the gate.

## 5. Isolation

Runtime imports forbidden: `config_layer.crt_engine_v2`, `config_layer.parent_crt`, `runtime.backtest_v2`, `research.visual_crt`, TradeLib.

Allowed: `structure.predicates` (SP-001/SP-002 identities), `features.calendar_periods.period_key` / `period_start`, `config_layer.htf_state.classify_htf_state` (posture only).

## 6. Measurement

`P-SUJAN-02` sealed `MC-SUJAN-XAUUSD-M15-V1` and ran it. PRIMARY = R4. SEM-023 is not a gate. Holdout R4 n=80 REJECT (F-095). Artifacts: `docs/research-readiness/sujan_crt/mc_sujan_xauusd_m15_v1/`.
