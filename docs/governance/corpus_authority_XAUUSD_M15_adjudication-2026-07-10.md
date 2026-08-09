# XAUUSD_M15 Corpus Authority Adjudication (R2)

| Field | Value |
|---|---|
| Logical id | `XAUUSD_M15` |
| Decision id | `CAD-XAUUSD_M15-PHASE1-FROZEN` |
| Decision status | **`FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION`** (scope freeze — not AUTHORITATIVE) |
| Phase-1 binding | [`xauusd_m15_phase1_frozen_candidate.json`](xauusd_m15_phase1_frozen_candidate.json) → `data/mt5/XAUUSD_M15.csv` @ `4d73f5ce…b26aba56` |
| Freeze | `OHLCV-CORPUS-FREEZE-2026-07-10` |
| PASS-B blocker | **BC-5** (canonical ≡ quarantined; stale pin; no promotion record) |
| Closure | [`ohlcv-closure-report-2026-07-10.md`](ohlcv-closure-report-2026-07-10.md) |

**Scope freeze recorded.** Not full validation. No promote. Phase-1 work binds only to the frozen candidate.

---

## 1. TruthConflict surface

Multiple surfaces claim authority over the **same path name** with **different bytes**:

| Surface | Path | SHA-256 prefix | Role claimed |
|---|---|---|---|
| `HANDOFF.md:11` | `data/XAUUSD_M15.csv` | `4d73f5cebe33ec91` | Standing-rule canonical pin (**stale vs on-disk**) |
| On-disk root | `data/XAUUSD_M15.csv` | `486cf3616415ff86` | Current bytes (50,169 rows → 2026-07-06) |
| `data/mt5/XAUUSD_M15.csv` | same logical id | `4d73f5cebe33ec91` | Older MT5 tree (47,275 rows → 2026-05-21) |
| `src/research/secondlow_v1/corpus.py` | root | `486cf3616415ff86` | Research + regression hash pin |
| `CORPUS_POLICY.md` | root | `486cf3616415ff86` | Policy “canonical” (extended 2026-07-07) |
| Sealed evaluation set | root | `486cf361…` | SECONDLOW sealed PRE events |
| `data/mt5/_rejected/XAUUSD_M15.csv` | quarantine | `486cf3616415ff86` | **Strict-gate QUARANTINED** (DUP-008 twin of root) |
| `reports/dataset_integrity/XAUUSD_M15.json` | root | `486cf361…` | Default L3 **APPROVE** (2026-07-07) |
| Output contract `data_root_fx` | — | — | **NOT_ADMISSIBLE_AS_AUTHORITATIVE** until adjudicated |

Averaging these into a silent “current root wins” ruling would **launder BC-5**.

---

## 2. Failure chain (proven, PASS B)

```text
PINNED CANONICAL HASH (HANDOFF 4d73f5ce…)
        ↓
NEW FETCH (ends 2026-07-06, 50,169 rows)
        ↓
STRICT-GATE REJECT → data/mt5/_rejected/XAUUSD_M15.csv
        ↓
BYTES APPEAR AT CANONICAL ROOT data/XAUUSD_M15.csv (486cf361…)
        ↓
DEFAULT L3 GATE APPROVES (reports/dataset_integrity/XAUUSD_M15.json)
        ↓
RESEARCH/POLICY PINS MOVE TO 486cf361… (CORPUS_POLICY, corpus.py)
        ↓
HANDOFF PIN STAYS 4d73f5ce… (stale)
        ↓
NO LOAD-TIME IDENTITY DETECTOR
```

Class: **FC-OHLCV-23** (stale identity pin) live in production data.

---

## 3. Candidate matrix

| Candidate ID | Physical path | Full SHA-256 | Rows | End ts | Family | Gate outcome |
|---|---|---|---|---|---|---|
| **C-PINNED-LEGACY** | `data/mt5/XAUUSD_M15.csv` | `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56` | 47,275 | 2026-05-21 23:45 | mt5 | unknown (legacy tree) |
| **C-ROOT-EXTENDED** | `data/XAUUSD_M15.csv` | `486cf3616415ff86f7647e23bec1043b50ff24a08f85898b9d79d1103a8a42af` | 50,169 | 2026-07-06 23:45 | data_root | default L3 **APPROVE** |
| **C-QUARANTINE-TWIN** | `data/mt5/_rejected/XAUUSD_M15.csv` | *(identical to C-ROOT-EXTENDED)* | 50,169 | 2026-07-06 23:45 | quarantine | strict_fetch **QUARANTINED** |
| **C-YFINANCE** | `data/yfinance/XAUUSD_M15.csv` | `7dd8282bfaa1575312e730e6c3aeb81db785b9962c6918d860f5399d024b5642` | 2,294 | 2026-05-22 08:45 | yfinance | no verify gate |

### Consumers (non-exhaustive)

- SECONDLOW-v1: partition invariants **79 raw / 50 independent** on the **current root** (`486cf361…`).
- Regression fixture `data/XAUUSD_M15_1year.xlsx` is **separate** (detector-only; hash `e0bb97d9…`).
- HANDOFF still documents the **legacy** pin.

### Strict-gate REJECT rationale (reconstructed, not guessed)

1. **Mechanism (CX-OHLCV-005, PROVEN_NON_BLOCKER as process):** the same bytes can be
   REJECTed under `strict_fetch` zero-tolerance and APPROVEd under default L3 thresholds
   (`dataset_integrity.py` cfg_override path). That explains twin co-existence; it does
   **not** authorize root promotion.
2. **Holiday / gap class:** active config
   `configs/production/v2_multi_2026_04.json` → `dataset_integrity.known_gaps` includes
   XAUUSD `2026-07-03T20:00 → 2026-07-06T01:00` (“Jul-4-holiday early-close through
   weekend reopen, reviewed 2026-07-07”). Default APPROVE report is timestamped
   `2026-07-07T10:55:07Z` with `hard_failures: []` and `file_hash` = `486cf361…`.
3. **Missing artifact:** no recorded **promotion decision** that says “accept strict-reject
   twin as new canonical after adding known_gaps.” CORPUS_POLICY/code moved first;
   HANDOFF did not.
4. **If deeper strict-reject logs are absent:** Option B ratification still requires an
   explicit user decision that the Jul-4 / known_gaps accept-list is the intended
   authority basis — not silent byte presence at root.

---

## 4. Options (user selects one)

### Option A — Restore legacy pin (`4d73f5ce…`)

- **APPROVED** binding target: `data/mt5/XAUUSD_M15.csv` bytes (or restore those bytes to root).
- Treat current root `486cf361…` as **REJECTED** or **QUARANTINED** (undeclared promotion).
- Later apply step: rewrite root + HANDOFF + corpus.py + CORPUS_POLICY + freeze pin;
  SECONDLOW partition expectations will change (79/50 was measured on extended).
- **Cost:** invalidates research artifacts stamped on `486cf361…` unless re-run.

### Option B — Ratify extended corpus (`486cf361…`)

- **APPROVED** binding target: current root bytes.
- Record promotion decision: undeclared replacement + strict twin + default APPROVE +
  known_gaps Jul-4 window as the explicit acceptance basis.
- Fix HANDOFF pin to `486cf361…` (and keep research pins).
- Document CX-005: strict vs default divergence remains a **gate-config** fact, not proof
  of two different markets.
- **Risk if done without this record:** launders BC-5.

### Option C — Dual-track (split logical roles)

- Never one logical name for two hashes.
- Example roles: `XAUUSD_M15` research-extended (`486cf361…`) vs frozen pre-extension
  archive / HANDOFF-era slice (`4d73f5ce…`) under an explicit second role id or path
  contract.
- Requires clear consumer mapping (which studies use which).

### Option D — Leave `UNRESOLVED`

- No binding; freeze remains; XAUUSD stays
  `NOT_ADMISSIBLE_AS_AUTHORITATIVE` for OHLCV handoff.
- SECONDLOW work may continue as research-local with documented non-authority,
  but cannot close Phase 1 on this corpus.

---

## 5. Recommendation for review (non-binding) — UPDATED after strict-REJECT forensic

| Preference | Rationale |
|---|---|
| **C (pending / dual-track authority) or D** | **Recommended now.** Preserve both corpora unchanged; do not APPROVE root or restore legacy yet. |
| Prefer **C/D over B** | Root is a clean append-only extension (strong), but `MARKET_CLOSURE_ONLY_CLAIM` and `KNOWN_GAP_INDEPENDENT_VALIDATION` are **UNPROVEN**; strict REJECT of the 50,169-row file is a **calendar/contract** fail (16 Jul-3 20:00–23:45 tradable slots) until `known_gaps` was registered — not OHLCV corruption. Promoting on internal cleanliness alone is the circular-classifier failure mode. |
| Option B later | Only after: (1) this forensic on record, (2) independent extension re-fetch OR explicit user acceptance of known_gaps as authority basis, (3) written promotion decision + HANDOFF pin fix. |
| Option A | Still a hard reset that discards clean additive bars with no rewrite benefit; not indicated by sequence integrity. |

**Strict-REJECT forensic:** [`xauusd_m15_strict_reject_forensic-2026-07-10.md`](xauusd_m15_strict_reject_forensic-2026-07-10.md)

### Adopted scope freeze (user 2026-07-10)

```text
XAUUSD_CANDIDATE_CORPUS
  physical_path:  data/mt5/XAUUSD_M15.csv
  allowed_time_range: 2024-05-22T01:00:00 → 2026-05-21T23:45:00
  rows: 47275
  content_hash: 4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56
  policy: exclude all timestamps after 2026-05-21T23:45:00
  status: FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION
```

**Not** AUTHORITATIVE / VALIDATED / ECONOMICALLY_ADMISSIBLE / APPROVED.

Remaining Phase-1 validation (against this object only): provenance, open-time semantics,
broker session/holiday, volume semantics, adversarial probes — then promote **this exact hash**.

---

## 6. Apply checklist (after Phase-1 validation pass — not yet)

1. Keep `CAD-XAUUSD_M15-PHASE1-FROZEN` until remaining probes pass on **this exact hash**.
2. On pass: new decision row `APPROVED` for same path+sha256+range; set `approved_*` only then.
3. Never promote a different file/hash under `XAUUSD_M15` without a new decision.
4. Align HANDOFF + consumers only after APPROVED (SECONDLOW research pin is separate and currently extended-root).
5. Only then authorize **R3** general admission for this logical id.

---

## 7. G-10 note (scope)

Synthetic corpora are out of scope for XAUUSD MT5 candidates. Global rule remains:
do not ban synthesis; require declared lineage + semantics on identity.

---

## 8. Evidence index

- Closure BC-5: `docs/governance/ohlcv-closure-report-2026-07-10.md`
- CX-004 / CX-005: `docs/governance/ohlcv-contradiction-report-2026-07-10.md`
- Fingerprint DUP-008: `docs/governance/ohlcv-corpus-fingerprint-manifest-2026-07-10.json`
- Integrity APPROVE: `reports/dataset_integrity/XAUUSD_M15.json`
- known_gaps: `configs/production/v2_multi_2026_04.json` (`dataset_integrity`)
- Decision row: `docs/governance/corpus_authority_decisions.jsonl` (`CAD-XAUUSD_M15-PHASE1-FROZEN`)
- Phase-1 binding: `docs/governance/xauusd_m15_phase1_frozen_candidate.json`
- Enforcer: `src/data_ingestion/xauusd_phase1_candidate.py`
