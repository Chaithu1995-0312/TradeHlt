# RR L1 Freeze — Consumer Contract (L2 / L3 / L4 / Epoch)

**Authority:** Every artifact produced after L1 must prove it was built under a **SIGNED**
`RR_L1_FREEZE_CERTIFICATE`. The machine twin JSON is authoritative.

**Certificate path (canonical):**  
`docs/governance/rr_l1_freeze/RR_L1_FREEZE_CERTIFICATE.json`

**Gate command (must exit 0 before L2+ work that claims this freeze):**

```bash
python scripts/governance/rr_l1_freeze_certificate.py assert-signed
```

---

## Required embeddings

Every **versioned** L2 / L3 / L4 / epoch artifact MUST include at least:

| Field | Source |
|-------|--------|
| `certificate_id` | certificate root |
| `protocol_hash` | certificate root (must match recompute of `contract`) |
| `l1_certificate_path` | relative repo path to the signed JSON |

Optional but recommended: `certificate_status` (must be `SIGNED` at write time).

---

## Layer-specific checks

### L2 — Feature truth

Before writing a feature matrix:

1. `assert-signed`  
2. Emit features only for `contract.instrument_universe`  
3. Apply `contract.structure_mask_policy`  
4. Feature names/order must equal `contract.feature_list.names` (or declared subset rule)  
5. Provenance must record PIT policy consistent with certificate hard flags / notes  
6. Artifact header must embed `certificate_id` + `protocol_hash`

### L3 — Label generation

Before writing labels / clean dataset:

1. Re-verify `protocol_hash` still matches signed certificate (no contract drift)  
2. Use only `contract.governing_exit` for primary y  
3. Target columns must match `contract.target_definition`  
4. Sampling must match `contract.sampling`  
5. Dataset provenance must embed L1 ids + L2 `schema_hash`

### L4 — Research execution

1. Load certificate; recompute hash; fail if mismatch  
2. Harness config must equal `contract.measure_regime` (gate, costs, exit)  
3. Refuse primary y from any path not governed by this `protocol_hash`  
4. Smoke and epoch charter must cite `certificate_id` + `protocol_hash`

### Research epoch

1. All findings / kill-test reports under this epoch cite the same `protocol_hash`  
2. New scientific decisions → new certificate (new epoch candidate), not an edit

---

## Failure modes (mandatory refuse)

| Condition | Action |
|-----------|--------|
| Certificate `status` ≠ `SIGNED` | Refuse L2+ |
| Any `__UNSET__` remains in `contract` | Refuse READY/SIGNED |
| Recomputed hash ≠ stored `protocol_hash` | Refuse (tamper / drift) |
| Artifact missing `protocol_hash` | Refuse as non-traceable |
| Artifact `protocol_hash` ≠ certificate | Refuse (orphan artifact) |

---

## Non-goals

- This contract does **not** re-enable `rr_fusion` (hard flag).  
- This contract does **not** grant GATE-P or production authority.  
- H-RR-THRESHOLD-001 is a **separate** program; do not embed its outcomes as B-model evidence under this certificate unless the certificate explicitly lists that coupling (default: **forbidden**).
