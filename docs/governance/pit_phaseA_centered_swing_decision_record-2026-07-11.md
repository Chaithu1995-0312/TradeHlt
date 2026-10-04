# PIT Phase A — Centered-Swing Remediation Decision Record

_Date: 2026-07-11 · ACTIVE_VERSION=`v2_multi_2026_04` · investigation complete (zero production changes this phase)._  
_Corrected 2026-07-11 (same day): PC-2 / ledger-null wording tightened; RR artifact operational rule strengthened; finding registered as F-051; FC1-A contract frozen._

**Artifacts**
- Blast radius: [`pit_phaseA_swing_blast_radius-2026-07-11.json`](pit_phaseA_swing_blast_radius-2026-07-11.json) / [`.md`](pit_phaseA_swing_blast_radius-2026-07-11.md)
- Gate-ON A/B: [`pit_phaseA_gateon_ab-2026-07-11.json`](pit_phaseA_gateon_ab-2026-07-11.json) / [`.md`](pit_phaseA_gateon_ab-2026-07-11.md)
- FC1-A contract: [`feature_pipeline_change_contracts/FC1-A-SWING-CAUSAL.json`](feature_pipeline_change_contracts/FC1-A-SWING-CAUSAL.json) · [`FC1-A-SWING-CAUSAL-implementation-contract-2026-07-11.md`](FC1-A-SWING-CAUSAL-implementation-contract-2026-07-11.md)
- Probes: `scripts/analysis/pit_swing_blast_radius.py`, `scripts/analysis/pit_swing_gateon_ab.py`

**Scope guard.** Exposure and decision consequence are never conflated. F-029’s gate-OFF trade-generation claim is **refined in scope**, not reversed (gate-OFF replay confirms byte-identical ledgers).

### Corrected defensible claims (do not over-read)

**Proved [Certain]:**
> Centered swing semantics are non-PIT, materially alter canonical feature values, propagate into CRT/ZoneGate/model inputs, and differ from the default-absent live path.

**Not proved — CORRECTED wording for ledger-null:**
> ~~“The current spine trade ledger is structure-vector-insensitive.”~~  
> **Under the tested BNB/SOL corpora, active config `v2_multi_2026_04`, and observed decision population, neither the causal 10-feature intervention nor the stronger zero-all-10 intervention changed the final ledger; however, end-to-end sensitivity to this feature family was not demonstrated (PC-2 failed), so the null ledger result is *inconclusive* about structural importance.**

---

## 1. Per-channel verdict table

| Channel | Verdict | Evidence |
|---|---|---|
| **Value (centered vs causal chain)** | **EXPOSED** — 63.5% of BNB bars differ on ≥1 of 10 contaminated features; EURUSD also high | Blast A: BNB any-of-10 differ_rate=0.635; swing_high/low differ ~29%; BOS 11.6%; liq_dist 16.3%; sweep 6.3% |
| **Leakage (prefix-invariance)** | **PROVED** | B1: centered flag at raw_index=873 flips 0→1 when future bars arrive (prefix_n=874); `*_causal_confirmed` interior prefix-invariant |
| **Gate-OFF ledger** | **No change observed; F-029 stands** | Gate-OFF A/B BNB: 13→13 trades, identical=True, overlap=100% |
| **Gate-ON ledger** | **No change observed; structural importance INCONCLUSIVE** | Gate-ON A/B BNB 11→11 identical; SOL 6→6 identical. PC-2 failed → null is **sensitivity-bounded**, not a proof of irrelevance |
| **CRT score channel** | **EXPOSED (local)** | B2a: final CRT score differ_rate=7.07% when only sweep_detected/double_sweep swapped |
| **ZoneGate VALUE** | **EXPOSED** | B2b ZONE_VALUE: mean contaminated weight fraction=40% across 8 zones |
| **ZoneGate SCORE** | **EXPOSED** | B2b: centered vs causal score differ_rate≈63.3%; \|Δ\| mean≈0.032 |
| **ZoneGate HARD gate** | **NEAR-NULL on sample** | B2b: HARD flip rate centered→causal ≈0.01% (1 flip / ~10k scored) |
| **FINAL_LEDGER** | **NO CHANGE OBSERVED (not “structure irrelevant”)** | Deliverable 2 only: identical ledgers under full causal graph swap *and* under PC-2 zero-all-10 |
| **Live contract** | **LIVE-ZERO on default-absent path** (CONDITIONAL_PROVEN) | B3: `live_engine_hook.py:394-402` defaults structure dims to 0.0; FeatureStore only rewrites `double_sweep` from `liquidity_sweep` history; no production inout feeder runs FeaturePipeline |
| **Artifacts (rr_model)** | **PIT_UNCLEAN_CENTERED_SWINGS** (weights active; path inactive) | C: `zero_indices` zeroes 0/10 contaminated dims — ALL_10_ACTIVE; `rr_fusion.enabled=false` (F-038) |
| **Artifacts (zone_registry)** | **PIT_UNCLEAN_CENTERED_SWINGS** (weights); decision consequence unproven | 40% weight mass; HARD flips ~0; ledger no-change observed |
| **Datasets** | **EMBEDDED / PIT-unclean era** | CRT `cached_features.double_sweep` → opportunities.jsonl → stage1; rr_dataset via FeaturePipeline 38-vector |

### PC harness status (gate-ON A/B)

| Check | Result |
|---|---|
| Corpus parity | PASS (same CSV sha256 both arms; candle counts equal) |
| INTERVENTION_ISOLATION | PASS (only the declared 10-feature causal closure changes; other 28 invariant) |
| PC-1 (local CRT channel) | PASS (s_sweep/final move on forced sweep perturbation) |
| PC-2 (end-to-end sensitivity) | **FAILED** — zeroing all 10 structure dims left ledger identical (11→11). **Interpretation (binding):** end-to-end sensitivity to this feature family was **not demonstrated** on the tested population/config; therefore the causal A/B null ledger is **inconclusive about structural importance**, not evidence that structure is economically irrelevant. |

---

## 2. Remediation options + recommendation

### 2.1 Production vector binding (swing_high/low + structure chain)

| Option | Description | Recommend? |
|---|---|---|
| **A. Causal publication (FC1-A)** | Bind production `swing_high`/`swing_low` + **coherent** structure graph to causal-confirmed semantics; keep `*_centered_batch` as explicit research/legacy columns | **YES — next phase after contract freeze** |
| B. Leave production centered | Accept batch lookahead as intentional research convenience | NO — PIT leakage is proved; live-train skew risk remains |
| C. Dual-emit without rebinding | Keep production centered; only add causal columns | Partial — Phase-1 already dual-emits causal columns; production still centered-bound |

**Recommendation:** Option A under the frozen FC1-A implementation contract. Rationale: leakage is proved and value/channel exposure is large. Ledger no-change does **not** make lookahead free — it is **PC-2–bounded and inconclusive** about structural importance. Live defaults already diverge from training vectors. Further Phase-A investigation is not warranted.

### 2.2 Centered identity preservation

- Keep `swing_high_centered_batch` / `swing_low_centered_batch` (and any research_view env) as **explicit non-production** identities.
- Do not silently rename; dual-emit under feature_id discipline (Phase-1 pattern).

### 2.3 Artifact consequences (zone_registry / rr_model)

**Operational rule (binding — stronger than “no retrain now”):**

> Existing RR (and structure-weighted Zone) artifacts are **PIT-unclean** (`PIT_UNCLEAN_CENTERED_SWINGS`) and **must not be promoted, re-enabled, or used as economic evidence** without causal re-dataset / retrain / revalidation.  
> **No immediate retrain is justified** because the trained RR path is inactive (`rr_fusion.enabled=false`, F-038/F-044/F-045 lineage) and its marginal value is already unproven.  
> “No retrain now” **must not** be read as “artifact remains valid.”

| Artifact | Exposure | Decision path | Recommendation |
|---|---|---|---|
| `models/rr_model.json` | 10/10 dims active; trained on non-PIT structure values | Inactive (`rr_fusion.enabled=false`) | Tag `PIT_UNCLEAN_CENTERED_SWINGS`; **block promote/re-enable** until causal re-dataset+retrain+revalidation; no immediate retrain |
| `models/zone_registry.json` | 40% weight mass; scores move | HARD flips near-null; ledger no-change observed | Same provenance tag; no automatic retrain |
| stage1 / rr datasets / opportunities | Embed centered chain | Downstream research/train | Annotate corpus era `centered_swing_batch`; rebuild only when a consumer is re-authorized under Authority Ladder |

### 2.4 Live-skew remediation ordering

1. **FC1-A:** production batch vector → causal publication (coherent graph; see contract).
2. **Live contract (in same change or immediate follow-on):** delayed confirmed swings with explicit `SWING_WINDOW=2` confirmation latency — not silent live-zero vs batch-centered skew.
3. **Artifact rebuild:** only if a decision-path consumer is re-enabled with measured sensitivity (Authority Ladder).

---

## 3. Finding — F-051 (REGISTERED)

Registered in [`docs/current-findings.md`](../current-findings.md) as **F-051** (ARCH, VALIDATED, Likely). Full block there.

**One-line:** Centered-swing production binding is non-PIT and contaminates 10 canonical dims + model inputs; final-ledger consequence under tested BNB/SOL gate-ON/OFF remains **inconclusive** (PC-2 failed); F-029 gate-OFF claim stands as a scope-refined trade-generation result.

**Relation to F-029:** REFINEMENT of scope, not a reversal. Gate-OFF trade generation remains byte-identical under causal structure intervention (13≡13). Value-level and train/serve integrity claims are **new**, not a contradiction of F-029’s trade-generation scope.

---

## 4. Backlog status

| ID | Status note |
|---|---|
| **FU-FC1-A-PIT** | OPEN → **READY for implementation** under frozen contract; investigation closed. |
| **FU-STRUCTURE-CAUSAL-GRAPH** | OPEN → **coupled to FC1-A** (no hybrid graph). |

---

## 5. What Phase A does / does not authorize

**Authorizes:** documentation of F-051; FC1-A contract freeze; provenance classification of existing artifacts as PIT-unclean.

**Does not authorize:** silent “structure is economically irrelevant”; automatic retrain; promote/re-enable of PIT-unclean RR/Zone artifacts; hybrid centered→causal graphs.

**Implementation** proceeds only under [`FC1-A-SWING-CAUSAL-implementation-contract-2026-07-11.md`](FC1-A-SWING-CAUSAL-implementation-contract-2026-07-11.md).

---

## 6. Next step (highest leverage)

1. ~~Tighten overstatements~~ (this correction).  
2. ~~Register F-051~~.  
3. ~~Freeze FC1-A contract~~.  
4. **Implement FC1-A** per contract — no further Phase-A investigation.
