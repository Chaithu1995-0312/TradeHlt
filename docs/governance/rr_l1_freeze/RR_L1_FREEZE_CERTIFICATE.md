# RR_L1_FREEZE_CERTIFICATE

| Field | Value |
|-------|--------|
| **Certificate ID** | `RR_L1_FREEZE_2026_07_21_V1` |
| **Schema** | `RR_L1_FREEZE_CERTIFICATE_V1` |
| **Status** | **SIGNED** (owner authorized 2026-07-21) |
| **Machine twin (authoritative for hash)** | [`RR_L1_FREEZE_CERTIFICATE.json`](RR_L1_FREEZE_CERTIFICATE.json) |
| **Checklist** | [`../rr_production_readiness_checklist.md`](../rr_production_readiness_checklist.md) §2.1A L1 |
| **protocol_hash** | *(see JSON after hash — must match `scripts/... hash`)* |
| **Authority** | RESEARCH_ONLY — no `rr_fusion` enable, no promote |
| **Fill** | **Proposed defaults 2026-07-21** — owner must sign to freeze |

> **This document is the human face of a single signed research contract.**  
> L2 / L3 / L4 / epoch **must embed** `certificate_id` + `protocol_hash` from the signed JSON twin.  
> Editing `contract` after **SIGNED** is forbidden — supersede with a new certificate.

---

## Decision rationale (proposed fill)

| Decision | Choice | Why |
|----------|--------|-----|
| Universe | BNBUSDT M15 only | Incumbent model + dataset are BNB; multi claims need multi data |
| Sampling | natural_base_rate | Legacy “balanced” was misnamed (~6.5% wins); no artificial rebalance |
| Metrics | rr_corr, PR-AUC, top-decile y_rr | Fit continuous + rare-positive class; not accuracy |
| Exit / labels | `forward_walk` / `intrabar_fixed` + 12 bps | F-022/F-041B/F-045 remedy; repo standard cost |
| Target | continuous `y_rr` + derived `y_win` | Bans win→+1.0 degeneracy |
| Structure | PIT-clean structure + legacy price zero mask | F-051 + train/serve parity with zero_indices |
| Features | full canonical_38 frozen | FEAT-006; vol_regime must be causal at L2 |
| Head eval | confidence gate **bypassed** | F-044; raw heads only under this certificate |
| Spine if used | gate **ON** (`1`) | F-037/F-058 honesty; no silent .env |

---

## 1. RC map

| RC ID | Section | On SIGNED |
|-------|---------|-----------|
| **RR-FEAT-005** | §3 Instrument universe | RESOLVED |
| **RR-LAB-003** | §4 Sampling | RESOLVED |
| **RR-GOV-008** | §5 Measure regime | RESOLVED |
| **RR-GOV-004** | Whole certificate | RESOLVED |

Declared for later layers: LAB-002 (§6), FEAT-003 (§7), FEAT-006 (§8), LAB-001 (§9).

---

## 2. Meta

| Field | Value |
|-------|--------|
| Title | RR contract-B clean research L1 freeze |
| Program alias | `RR_B_CLEAN_EPOCH_CANDIDATE` |
| Task class | `EXPLORATORY_RESEARCH` |
| Active config | `v2_multi_2026_04` |
| Orthogonal | `H-RR-THRESHOLD-001` (not coupled) |
| Findings | F-022, F-037, F-038, F-044, F-045, F-048, F-051, F-054, F-058 |

---

## 3. Instrument universe — RR-FEAT-005

| Field | Value |
|-------|--------|
| Timeframe | `M15` |
| Instruments | `["BNBUSDT"]` |
| Multi-instrument claims allowed | **false** |
| Notes | Supersede certificate for multi |

---

## 4. Sampling — RR-LAB-003

| Field | Value |
|-------|--------|
| Design | `natural_base_rate` |
| Class balance target | `none` |
| Primary metrics | `rr_corr`, `pr_auc_y_win`, `top_decile_mean_y_rr` |
| Secondary metrics | `auc_y_win`, `brier_y_win`, `mean_y_rr` |
| Min samples floor | `500` |

---

## 5. Measure regime — RR-GOV-008

| Field | Value |
|-------|--------|
| Primary eval mode | `offline_matrix_cv` |
| Confidence gate (heads) | **bypassed** (F-044) |
| Spine shadow if used | `BACKTEST_ENGINE_GATE=1` |
| Costs (bps RT) | `12` |
| Exit model | `forward_walk` |
| Exit params | `{ "mode": "intrabar_fixed" }` |
| Silent env | **FORBIDDEN** |

---

## 6. Target definition — RR-LAB-002

| Field | Value |
|-------|--------|
| Target kind | `continuous_realized_r` |
| Primary | `y_rr` = realized net R under governing exit |
| Secondary | `y_win` = 1 if y_rr > 0 else 0 |
| Win forces y_rr=+1.0 | **FORBIDDEN** |

---

## 7. Structure mask policy — RR-FEAT-003

| Field | Value |
|-------|--------|
| Mode | `pit_clean_structure_plus_legacy_price_zero` |
| Zero names | open, high, low, close, volume, ema_fast, ema_slow, macd_line, macd_signal, body_size, wick_size |
| PIT structure required | **true** |

---

## 8. Feature list — RR-FEAT-006

| Field | Value |
|-------|--------|
| Schema | `canonical_38` |
| n_features | 38 |
| Names | Full `CANONICAL_FEATURES` order (see JSON) |
| `names_frozen` | **true** |

---

## 9. Governing exit — RR-LAB-001

| Field | Value |
|-------|--------|
| Method | `forward_walk` |
| Params | `intrabar_fixed`, cost 12 bps |
| Detection stream as primary y | **FORBIDDEN** |
| F-022 fields | x-ref only |

---

## 10. Success / failure rules

| Field | Value |
|-------|--------|
| Kill-test primary | 5-fold CV offline heads, gate bypassed |
| KEEP_CANDIDATE | label_validity_pass AND (rr_corr>0.03 OR pr_auc > shuffle+0.02) AND top_decile > random; research only |
| RETIRE | label_validity_pass AND all discrimination floors fail |
| INSUFFICIENT | n < 500 OR label_validity_fail OR underpowered folds |
| Smoke ≠ findings | **true** |

---

## 11. Hard flags

| Flag | Value |
|------|------:|
| PRODUCTION_BEHAVIOR_CHANGED | false |
| RR_FUSION_REENABLE | false |
| AUTO_PROMOTE_CONFIG | false |
| POST_HOC_THRESHOLD_MINING | false |
| USE_LEGACY_F022_LABELS_AS_PRIMARY_Y | false |
| COUPLE_H_RR_THRESHOLD_001_AS_B_EVIDENCE | false |
| ENTRY_DISCOVERY | false |

---

## 12. protocol_hash

```text
algorithm : sha256
scope     : canonical JSON of `contract` only
value     : see RR_L1_FREEZE_CERTIFICATE.json → protocol_hash
verify    : python scripts/governance/rr_l1_freeze_certificate.py hash
```

---

## 13. Signature block — **AWAITING OWNER**

I freeze the `contract` object in the machine twin as the **sole L1 research contract**
for RR clean-B work under this `certificate_id`. L2 / L3 / L4 and any research epoch must
embed `protocol_hash`. Editing `contract` after SIGNED is forbidden (supersede instead).

| Field | Value |
|-------|--------|
| signed | **true** |
| signed_by | owner |
| signed_at_utc | (see JSON) |
| authorization | User: “L1 Complete Done” session 2026-07-21 |

**L1 is complete.** L2+ consumers must `assert-signed` and embed `protocol_hash`.

---

## 14. Consumption

See [`CONSUMER_CONTRACT.md`](CONSUMER_CONTRACT.md). Embed on every later artifact:

- `certificate_id` = `RR_L1_FREEZE_2026_07_21_V1`
- `protocol_hash` = *(from signed JSON)*
- `l1_certificate_path` = `docs/governance/rr_l1_freeze/RR_L1_FREEZE_CERTIFICATE.json`

---

## 15. L1 complete criterion

```text
L1_COMPLETE =
    status == SIGNED
  ∧ protocol_hash match
  ∧ zero __UNSET__
  ∧ names_frozen == true
  ∧ assert-signed exit 0
```

**Current:** READY_FOR_SIGNATURE (proposed) · **not** L1_COMPLETE · L2+ **blocked**.
