# RR L1 Freeze Package

**Layer:** L1 — Experiment freeze  
**Checklist:** [`../rr_production_readiness_checklist.md`](../rr_production_readiness_checklist.md) §2.1A  
**Centerpiece:** **`RR_L1_FREEZE_CERTIFICATE`** — the single signed research contract that **every**
later layer (L2 feature truth, L3 labels, L4 harness, research epoch) must embed and verify.

---

## Purpose

Make every subsequent dataset, label set, and experiment **traceable to one immutable contract**:

```text
protocol_hash  ←  SHA-256(canonical JSON of certificate.contract)
certificate_id ←  stable id of this freeze package instance
```

If features, labels, or metrics change the scientific decisions inside `contract`, a **new**
certificate (new `protocol_hash`) is required. Silent patching of a signed certificate is forbidden.

---

## Package contents

| File | Role |
|------|------|
| [`RR_L1_FREEZE_CERTIFICATE.md`](RR_L1_FREEZE_CERTIFICATE.md) | Human-readable certificate (sign here) |
| [`RR_L1_FREEZE_CERTIFICATE.json`](RR_L1_FREEZE_CERTIFICATE.json) | Machine twin — **authoritative for hashing** |
| [`RR_L1_FREEZE_CERTIFICATE.schema.json`](RR_L1_FREEZE_CERTIFICATE.schema.json) | JSON Schema for structure |
| [`CONSUMER_CONTRACT.md`](CONSUMER_CONTRACT.md) | What L2 / L3 / L4 / epoch must embed and check |
| This README | Package index |

**Validator (repo root):**

```text
python scripts/governance/rr_l1_freeze_certificate.py status
python scripts/governance/rr_l1_freeze_certificate.py validate
python scripts/governance/rr_l1_freeze_certificate.py hash
python scripts/governance/rr_l1_freeze_certificate.py assert-signed   # exit 0 only if SIGNED
```

---

## RC IDs closed by a **signed** certificate

| RC ID | Contract section |
|-------|------------------|
| **RR-FEAT-005** | `contract.instrument_universe` |
| **RR-LAB-003** | `contract.sampling` |
| **RR-GOV-008** | `contract.measure_regime` |
| **RR-GOV-004** | whole certificate = frozen prereg artifact |

**Also declared in the certificate (resolved in later layers):**

| Field | Later layer | RC ID |
|-------|-------------|-------|
| `contract.target_definition` | L3 | RR-LAB-002 |
| `contract.structure_mask_policy` | L2 | RR-FEAT-003 |
| `contract.feature_list` | L2 | RR-FEAT-006 |
| `contract.governing_exit` | L3 | RR-LAB-001 |
| `contract.success_failure_rules` | Epoch | (prereg rules) |

---

## Lifecycle

| Status | Meaning | L2+ allowed? |
|--------|---------|:------------:|
| `UNSIGNED_DRAFT` | Fields may be `__UNSET__`; hash not binding | **NO** |
| `READY_FOR_SIGNATURE` | All required fields set; hash computed; awaiting human sign | **NO** |
| `SIGNED` | Signature block filled; `protocol_hash` immutable | **YES** |
| `SUPERSEDED` | Replaced by a newer certificate_id | **NO** (use successor) |

**Sentinel:** any required scalar/list still equal to `"__UNSET__"` (or containing it) blocks READY/SIGNED.

---

## How to freeze (owner)

1. Edit **`RR_L1_FREEZE_CERTIFICATE.json`** — replace every `__UNSET__` in `contract` with frozen values.  
2. Keep the **md** twin in sync (same decisions).  
3. Run `python scripts/governance/rr_l1_freeze_certificate.py validate` → must PASS with 0 unset.  
4. Run `... hash` → writes `protocol_hash` into the JSON (and prints it).  
5. Set `status` to `READY_FOR_SIGNATURE` if not auto-set.  
6. **Human signs:** fill `signature.signed_by`, `signature.signed_at_utc`, set `signature.signed=true`, set `status=SIGNED`.  
7. Re-run `validate` + `assert-signed`.  
8. Record L1 complete in the checklist §9.2 layer table with `protocol_hash` and `certificate_id`.

**Do not** generate L2 features or L3 labels before step 7.

---

## Immutability rule

After `status=SIGNED`:

- Do **not** edit `contract.*` or `protocol_hash`.  
- Corrections require a **new** certificate file/id (or version suffix) and a new hash.  
- Mark the old certificate `SUPERSEDED` with `superseded_by`.

---

## Current package status

```text
PACKAGE_STATUS     = SIGNED
certificate_id     = RR_L1_FREEZE_2026_07_21_V1
protocol_hash      = 521fc88f97b13e91ab0a768b1b852fb09f46f12327ca920d707eb722d2ae993e
L1_COMPLETE        = YES
L2+_allowed        = YES (assert-signed PASS)
L2_FEATURE_TRUTH   = COMPLETE  results/rr_research/l2/RR_L1_FREEZE_2026_07_21_V1/
L3_LABEL_GENERATION = COMPLETE results/rr_research/l3/RR_L1_FREEZE_2026_07_21_V1/ (n=139942)
L4_RESEARCH_EXEC   = COMPLETE results/rr_research/l4/RR_L1_FREEZE_2026_07_21_V1/
GATE-R             = READY
RR research epoch  = AUTHORIZED (not RUNNING)
```

See the JSON `status` field as machine truth.
