# FC1-A Implementation Contract — Centered Swing → Causal Delayed Publication

_Frozen: 2026-07-11 · Prerequisite: PIT Phase A decision record + F-051 · ACTIVE_VERSION=`v2_multi_2026_04`._  
_Machine-readable twin: [`feature_pipeline_change_contracts/FC1-A-SWING-CAUSAL.json`](feature_pipeline_change_contracts/FC1-A-SWING-CAUSAL.json)._

**Status:** `IMPLEMENTED` (2026-07-11 · change_id `CH-fc1a-swing-causal` · construction completion COMPLETE)  
**Authority:** architecture/governance PIT correctness. Grants **no** economic promotion authority.  
**Parent evidence:** F-051 · `docs/governance/pit_phaseA_centered_swing_decision_record-2026-07-11.md`  
**Post-impl note:** `docs/governance/fc1a_post_implementation_measurement-2026-07-11.md`

---

## 1. Exact intervention

### Producer binding change
| Surface | Before (production) | After (production) |
|---|---|---|
| Swing detection math | Unchanged: local max/min of high/low over window `w=2·k+1`, `k=SWING_WINDOW=2` | Unchanged |
| **Publication time** | Centered: flag written at pivot bar `t` using bars `t-k..t+k` (lookahead) | **Causal delayed:** flag published only when confirmed — production columns bind to centered pivot **shifted by `k`** (i.e. `available_at = t+k`) |
| Production columns `swing_high` / `swing_low` | `swing_*_centered_batch` | `swing_*_causal_confirmed` |
| Structure graph refs | `last_swing_*_price` from centered ffill | `last_swing_*_price` from **causal** ffill (`last_swing_*_price_causal` semantics) |

### Canonical outputs that become causal (production binding)
The **10-feature dependency closure** measured in Phase A (plus any strictly derived members of the same coherent graph — §2):

1. `swing_high`  
2. `swing_low`  
3. `higher_high`  
4. `lower_low`  
5. `break_of_structure`  
6. `liquidity_sweep`  
7. `sweep_detected`  
8. `double_sweep`  
9. `liquidity_distance`  
10. `liquidity_pressure_score`  

**Second-order (must stay coherent with causal `liquidity_sweep`, §2):**  
`retest_flag` → `retest_depth` · `candles_since_retest` (pipeline already derives these from `liquidity_sweep`; they must not remain on a centered sweep while production sweep is causal).

**Out of scope for this change:** body/range/wick geometry, EMA/ATR, volregime, volume family, RR fusion re-enable, model retrain.

---

## 2. No hybrid graph

**Invariant:** every **production** consumer of the structure family receives a **coherent causal closure**.

Forbidden:
- Production `liquidity_sweep` causal while `higher_high` / BOS still use centered `last_swing_*_price`
- Causal swing flags with centered liquidity distance
- Causal sweep with retest_* still keyed off centered sweep history

Required:
- Single publication semantic for the production structure graph
- Research/legacy centered path only via **explicit** `*_centered_batch` (and optional research_view) columns — never as silent production defaults

---

## 3. Research preservation

| Column / identity | Required after FC1-A |
|---|---|
| `swing_high_centered_batch` / `swing_low_centered_batch` | **Remain**, byte-stable vs pre-change centered math |
| Optional research env | May dual-emit research views; must **not** mutate production identity columns |
| Feature IDs | Centered and causal remain **distinct** identities (Phase-1 discipline) |

---

## 4. Prefix-invariance acceptance

Production-bound 10-feature closure (and coherent retest secondaries) **must** pass prefix-equivalence tests:

1. Run pipeline on prefix of N bars vs full corpus.  
2. On the safe interior (bars with confirmation already available under delay `k`), production structure columns are **bit-identical** between prefix and full runs.  
3. Centered-batch columns may still differ at the tail (that is the leakage we are removing from production).  
4. Permanent pytest(s) — not one-off probe only.

---

## 5. Live contract

| Topic | Contract |
|---|---|
| Publication | Live / online path publishes the **same delayed confirmed** structure semantics as batch production (not centered batch; not silent all-zeros as a substitute for structure). |
| Confirmation latency | `SWING_WINDOW = 2` M15 bars → structure flags/refs become available **2 bars after** the pivot bar. Representation: document in code comment + contract; feature values at bar `t` use only information ≤ `t`. |
| Default-absent path | If a feeder still omits structure keys, defaults remain fail-safe zeros — but the **intended** live path is causal computation (or explicit pass-through of causally computed fields), not “train on centered / serve zeros.” |
| Out of scope this PR if blocked | If online causal computation cannot land in the same change, **STOP** and adjudicate rather than ship batch-causal + live-zero as “done.” |

---

## 6. Artifact policy

| Artifact class | Status after Phase A | FC1-A action |
|---|---|---|
| `models/rr_model.json` (+ instrument RR datasets trained on FeaturePipeline vectors) | **`PIT_UNCLEAN_CENTERED_SWINGS`** | Provenance annotation only; **no automatic retrain** |
| `models/zone_registry.json` | **`PIT_UNCLEAN_CENTERED_SWINGS`** | Provenance annotation only; **no automatic retrain** |
| opportunities / stage1 / master training JSONL | Centered-era embeddings | Annotate era; rebuild only when a consumer is re-authorized |

**Operational rule (non-negotiable):**
> PIT-unclean RR/Zone artifacts **must not be promoted, re-enabled, or used as economic evidence** without causal re-dataset → retrain → revalidation.  
> No immediate retrain is justified: RR path inactive (`rr_fusion.enabled=false`) and marginal value unproven (F-038/F-044/F-045).  
> “No retrain now” ≠ “artifact remains valid.”

---

## 7. Behavior measurement (post-change)

Rerun (read-only measurement arms, or CI tests where cheap):

| Arm | Purpose |
|---|---|
| Gate-OFF BNB (and optional SOL) | Confirm F-029-class trade-generation still documented; **byte-identical ledger is NOT required** — FC1-A intentionally changes production semantics |
| Gate-ON BNB (and optional SOL) | Differential report: trades added/removed/changed, decision overlap % |
| Prefix-invariance suite | Acceptance gate for the production binding |
| Value-level spot check | Production columns match causal re-derivation from `*_causal_confirmed` |

**Explicit non-requirement:** do **not** fail FC1-A solely because ledgers are non-identical to the centered-era baseline. Do **not** declare economic irrelevance if ledgers remain identical (PC-2 lesson).

---

## 8. Rollback boundary

- **One construction change** (single change_id / commit stack): ontology/docs + `feature_pipeline` structure binding + tests + provenance annotations.  
- Pre/post: BUILD_IMPACT_MANIFEST + completion validation per Repository Construction Protocol.  
- Config: if any behavioral knobs are externalized, rehash; if hash-neutral section-only, document.  
- Rollback: restore centered production binding + prior tests; provenance tags remain historically true (do not delete).

---

## 9. Finding registration

- **F-051 registered** before implementation (Phase A evidence is durable independent of FC1-A success).  
- Implementation must not quietly reverse F-051’s scope wording.

---

## 10. Stop conditions

**STOP implementation and adjudicate** if any of:

1. A newly discovered production consumer **requires** mixed centered/causal structure semantics.  
2. Live path cannot share delayed-confirmed publication without inventing a third semantic.  
3. Tests show production columns are still prefix-unstable after the binding change.  
4. Implementation would re-enable or promote a `PIT_UNCLEAN_*` artifact without revalidation.  
5. Construction protocol census/lint floors go red and cannot be resolved within the declared change surface.

---

## Acceptance checklist (implementation complete when all true)

- [ ] Production `swing_high`/`swing_low` bind to causal-confirmed publication  
- [ ] Full structure graph (10 + retest secondaries) coherent — no hybrid  
- [ ] `*_centered_batch` preserved and tested  
- [ ] Prefix-invariance tests green for production structure closure  
- [ ] Live contract stated and implemented or STOP documented  
- [ ] Artifact provenance `PIT_UNCLEAN_CENTERED_SWINGS` recorded  
- [ ] Gate-OFF + gate-ON differential reports written (identity not required)  
- [ ] Construction protocol completion validation PASS  
- [ ] SESSION LOG + F-051 citations updated if paths moved  

---

## Explicit non-goals

- Retraining rr_model / zone_registry as part of FC1-A  
- Claiming ΔG001 or economic edge from causal publication  
- Reversing F-029  
- Further Phase-A investigation before code
