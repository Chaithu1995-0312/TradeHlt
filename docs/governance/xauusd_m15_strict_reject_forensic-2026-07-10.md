# XAUUSD M15 Strict-REJECT Forensic (R2 evidence)

| Field | Value |
|---|---|
| Artifact under investigation | 50,169-row XAUUSD M15 (`sha256:486cf3616415ff86…a8a42af`) |
| Physical twins | `data/XAUUSD_M15.csv` (root) ≡ `data/mt5/_rejected/XAUUSD_M15.csv` (quarantine) |
| Legacy comparison | `data/mt5/XAUUSD_M15.csv` (`4d73f5ce…`, 47,275 rows) — append-only predecessor |
| Generated (local session) | 2026-07-10 |
| Method | Deterministic gate replay + filesystem mtimes + config/docs evidence |
| Authority | Analysis only — **no promote / replace / delete** |

---

## Executive result

```text
REJECT CLASS           = CALENDAR/CONTRACT DEFECT (tradable-gap vs known_gaps), NOT OHLCV CORRUPTION
FAILED RULE            = strict_fetch max_single_gap_candles=0 / max_gap_span_minutes=0
FAILED TIMESTAMPS      = 16 slots 2026-07-03T20:00 → 2026-07-03T23:45 (early-close before Jul-4 weekend)
CURRENT STRICT (w/ Jul-4 known_gap) = APPROVE
STRICT WITHOUT Jul-4 known_gap      = REJECT (same 16 bars, span 240 min)
DEFAULT L3 (thresholds)            = WARN/APPROVE (no hard fail)
HISTORICAL REWRITE                 = NOT_DETECTED (prior dual-corpus analysis)
AUTHORITY_STATUS                   = UNRESOLVED (Option C pending — preserve both corpora)
```

There is **no durable REJECT fingerprint report** still on disk for the quarantine event.
The only stored `reports/dataset_integrity/XAUUSD_M15.json` is a later **APPROVE** of the
**root** path under default (or post–known_gap) conditions. Rejection is **reconstructed**
by replaying `validate_dataset` with `strict_fetch` and ablating the Jul-4 `known_gaps` entry.

---

## 1. REJECT EVENT (reconstructed)

| Field | Evidence |
|---|---|
| Event type | Strict fetch gate REJECT → `shutil.move` to quarantine |
| Mechanism (code) | `scripts/data/fetch_and_verify_mt5.py:180-194` — `validate_dataset(..., cfg_override=strict_fetch)`; on `decision=="REJECT"`, move to `--quarantine` default `data/mt5/_rejected` |
| Source artifact hash | `486cf3616415ff86f7647e23bec1043b50ff24a08f85898b9d79d1103a8a42af` |
| Quarantine path | `data/mt5/_rejected/XAUUSD_M15.csv` (byte-identical to root) |
| Quarantine mtime | **2026-07-07 16:24:08** local |
| Root mtime | **2026-07-07 16:25:07** local (~59s later) |
| Root APPROVE report | `reports/dataset_integrity/XAUUSD_M15.json` — `evaluated_at: 2026-07-07T10:55:07Z`, path = root, decision **APPROVE**, `hard_failures: []`, hash matches |
| Durable REJECT report | **ABSENT** (fingerprint path is single-file per symbol_tf; later APPROVE overwrote) |
| Operator narrative | `H-SECONDLOW-002_Complete_Package/PROSPECTIVE_COLLECTION_CADENCE.md` §notes: `--end 2026-07-08` can quarantine (future bar / Jul-3 gaps); Jul-4 window registered 2026-07-07; use `--end 2026-07-07` after fix |

**Fetch run identity:** No dedicated fetch log line with run-id was found in
`logs/integrity_events.jsonl` for this quarantine (that stream does not record dataset REJECT).
Attribution is therefore **mtime + code path + gate replay**, not a ledger row.

---

## 2. STRICT GATE CONFIG (active production)

From `configs/production/v2_multi_2026_04.json` → `dataset_integrity.strict_fetch`:

```json
{
  "max_missing_pct": 0.0,
  "max_single_gap_candles": 0,
  "max_gap_span_minutes": 0,
  "tradability_mode": "autoderive",
  "autoderive_presence_min": 0.5
}
```

- **Zero tolerance** on any **tradable** missing bar (after autoderived weekly mask + holidays + `known_gaps`).
- Default (non-strict) thresholds remain loose (`max_missing_pct=0.02`, `max_single_gap_candles=100`, `max_gap_span_minutes=1440`) — so the **same bytes** can APPROVE under default L3 and REJECT under strict.

This is CX-OHLCV-005 (same bytes, different config) made concrete for XAUUSD.

---

## 3. FAILED RULE + EXACT FAILED TIMESTAMPS (replay)

### 3.1 Current config (includes Jul-4 known_gap reviewed 2026-07-07)

| Path | Gate | Decision | hard_failures |
|---|---|---|---|
| root / quarantine twin / legacy | `strict_fetch` | **APPROVE** | `[]` |
| quarantine twin | default L3 | **WARN** (intra-session gaps reported; not hard) | `[]` hard |

### 3.2 Strict with Jul-4 XAUUSD known_gap **removed** (pre-registration state)

| Decision | **REJECT** |
|---|---|
| hard_failures | `single gap of 16 tradable candles exceeds 0` |
|  | `largest tradable gap span 240 min exceeds 0 min` |

**Exactly 16 missing tradable timestamps** (autoderive mask + holidays, **without** Jul-4 known_gap):

```text
2026-07-03T20:00:00
2026-07-03T20:15:00
2026-07-03T20:30:00
2026-07-03T20:45:00
2026-07-03T21:00:00
2026-07-03T21:15:00
2026-07-03T21:30:00
2026-07-03T21:45:00
2026-07-03T22:00:00
2026-07-03T22:15:00
2026-07-03T22:30:00
2026-07-03T22:45:00
2026-07-03T23:00:00
2026-07-03T23:15:00
2026-07-03T23:30:00
2026-07-03T23:45:00
```

Gap envelope in the file: last present bar `2026-07-03 19:45:00` → next present `2026-07-06 01:00:00`.
Only the **Fri 20:00–23:45** interior slots are tradable under the autoderived mask;
Sat/Sun interiors are non-tradable and do not count toward the strict fail.

### 3.3 Ablation: all XAUUSD known_gaps removed

42 missing tradable bars across **three** early-close windows:

| Window | Missing tradable count | Range of missing tradable |
|---|---:|---|
| Memorial Day early-close 2026-05-25 | 10 | 21:30 → 23:45 |
| Juneteenth early-close 2026-06-19 | 16 | 20:00 → 23:45 |
| Jul-4 early-close 2026-07-03 | 16 | 20:00 → 23:45 |

These three are exactly the three **XAUUSD-scoped** `known_gaps` entries in the active config
(reviewed 2026-07-02 / 2026-07-07). Full known_gaps list → **0** missing tradable.

### 3.4 Interpretation

```text
REJECTION IS DATA DEFECT OR CALENDAR/CONTRACT DEFECT?
→ CALENDAR/CONTRACT: early-close holes that the zero-tolerance strict gate
  treats as tradable until registered in known_gaps (or holidays covering those slots).
→ NOT: duplicate ts, OOO, NaN, OHLC geometry, or mid-session random holes.
```

Whether those early closes are “genuine market closures” is still an **external** claim
(`KNOWN_GAP_INDEPENDENT_VALIDATION = UNPROVEN`). Governance registered them; the gate
then stops flagging them. That is **not** independent market proof.

---

## 4. HOW IDENTICAL BYTES REACHED ROOT

| Step | Evidence |
|---|---|
| 1. Strict fetch wrote `data/mt5/XAUUSD_M15.csv` then REJECT → move to `_rejected/` | Code path + quarantine file exists with extended hash |
| 2. Legacy tree still holds pre-extension `4d73f5ce…` at `data/mt5/XAUUSD_M15.csv` | On-disk; mtime 2026-07-02 |
| 3. Same extended bytes appear at `data/XAUUSD_M15.csv` | Byte-identical to quarantine; mtime **~1 min after** quarantine |
| 4. Default (or post–known_gap) integrity run APPROVEs root | Fingerprint report 2026-07-07T10:55:07Z |
| 5. Research pins move to `486cf361…` | `corpus.py`, CORPUS_POLICY, sealed set |
| 6. HANDOFF pin stays `4d73f5ce…` | Stale pin (BC-5) |
| 7. **No promotion decision record** | Authority table UNRESOLVED |

Likely operator sequence (best fit to mtimes + docs, not a logged transaction):

```text
strict fetch (end past Jul-3) → REJECT → quarantine
→ register Jul-4 known_gap + holiday
→ copy/re-place extended corpus at root (or re-fetch to root)
→ default/strict validate APPROVE
→ update research pin; leave HANDOFF stale; leave quarantine twin in place
```

**Undeclared promotion channel:** quarantine bytes re-enter the canonical root without a
corpus authority decision (BC-5 / FC-OHLCV-23).

---

## 5. VERDICT REVISION (gap analysis + this forensic)

The prior gap-report label `EXPECTED_MARKET_CLOSURES_ONLY` is **too strong**. Revised axes:

```text
C-ROOT-EXTENDED / C-PINNED-LEGACY / PAIR
────────────────────────────────────────
SEQUENCE_INTEGRITY                 = PASS
  (0 dups, 0 OOO, modal 15m)

OVERLAP_INTEGRITY                  = PASS
  (47,275 shared ts; 0 OHLCV mismatches)

HISTORICAL_REWRITE                 = NOT_DETECTED
  (root = legacy + 2,894 append-only bars)

MID_SESSION_UNCLASSIFIED_GAPS      = 0
  (under implemented classifier; residual UNEXPLAINED=0)

SESSION_CALENDAR_CONSISTENCY       = FAIL
  (config open Sun 22:00 vs corpus open Mon 01:00;
   config daily_break_hours=[21] vs observed 00:xx rollover)

KNOWN_GAP_INDEPENDENT_VALIDATION   = UNPROVEN
  (Memorial / Juneteenth / Jul-4 registered; not independently proven here)

MARKET_CLOSURE_ONLY_CLAIM          = UNPROVEN
  (classifier uses config + observed pattern + known_gaps — circular if used as proof)

PAIR_DIVERGENCE_TYPE               = APPEND_ONLY_EXTENSION

STRICT_REJECT_CLASS                = CALENDAR_CONTRACT
  (16 Fri evening early-close slots before Jul-4 known_gap registration)

AUTHORITY_STATUS                   = UNRESOLVED
  (Option C: quarantine decision pending; both corpora preserved unchanged)
```

---

## 6. What this changes for Options A/B/C/D

| Option | Impact of this forensic |
|---|---|
| **A** Restore legacy | Still possible, but discards clean append-only extension; no integrity rewrite found |
| **B** Ratify root | **Stronger than before** on SEQUENCE/OVERLAP/REWRITE; **not sufficient alone** — still needs independent extension validation + explicit promotion record; known_gaps remain UNPROVEN as market truth |
| **C** Dual-track / pending | **Recommended now:** keep both files; authority UNRESOLVED; do not promote |
| **D** Leave UNRESOLVED | Equivalent operational posture to C for authority |

**Highest-value remaining checks (not done this turn):**

1. ~~Strict-REJECT forensic~~ **DONE (this document)**  
2. Independent extension re-fetch for `2026-05-22 → 2026-07-06` from same broker (external)  
3. Independent broker session/holiday calendar (external), then reclassify all wall-clock misses  

---

## 7. Reproduction commands

```text
# Strict vs default on quarantine twin (write_report=False — do not overwrite fingerprint)
python -c "..."  # see scripts/analysis/xauusd_strict_reject_forensic.py if present

# Dual-corpus gap analysis
python scripts/analysis/xauusd_corpus_timestamp_gap_analysis.py
```

Gate replay used: `dataset_integrity.validate_dataset` + `cfg_override=strict_fetch` with
optional ablation of `session_calendar.known_gaps` Jul-4 / all-XAU entries.

---

## 8. Explicit non-actions

- No corpus promote / replace / delete  
- No HANDOFF hash rewrite  
- No freeze pin change  
- No authority APPROVED status  

---

## Evidence index

| Item | Path / fact |
|---|---|
| Quarantine twin | `data/mt5/_rejected/XAUUSD_M15.csv` |
| Root | `data/XAUUSD_M15.csv` |
| Legacy | `data/mt5/XAUUSD_M15.csv` |
| APPROVE fingerprint | `reports/dataset_integrity/XAUUSD_M15.json` |
| Strict gate script | `scripts/data/fetch_and_verify_mt5.py` |
| Gate implementation | `src/data_ingestion/dataset_integrity.py` |
| Config | `configs/production/v2_multi_2026_04.json` `dataset_integrity` |
| Operator notes | `H-SECONDLOW-002_Complete_Package/PROSPECTIVE_COLLECTION_CADENCE.md` |
| Prior gap analysis | `reports/xauusd_m15_corpus_timestamp_gap_report.json` |
| Authority decision | `docs/governance/corpus_authority_decisions.jsonl` `CAD-XAUUSD_M15-R2` |
