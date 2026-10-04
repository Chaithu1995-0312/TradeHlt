# CRT 13-Candidate Causal Provenance — Phase 6

**Program:** CRT Closure (audit-first)  
**Phase:** 6 of 8  
**Status:** **PASS**  
**Twin:** [`crt_13_candidate_provenance.json`](crt_13_candidate_provenance.json)  
**Scope:** CRT-side only — stop at `TRADE_OPENED`  
**Corpus:** frozen gate-ON baseline `results/baseline/run1` · BNBUSDT M15 · `v2_multi_2026_04`

---

## Verdict

| Field | Value |
|---|---|
| **CRT_13_CANDIDATE_PROVENANCE_STATUS** | **COMPLETE** |
| Candidates | **13 / 13** reconstructed |
| Unexplained CRT `TRADE_OPENED` | **0** |
| Evidence completeness | **13 COMPLETE** |
| Shadow path | 6 |
| Golden path | 7 |
| In gate-ON `trades.csv` | 11 (2 CRT-opened, ER-vetoed downstream — out of scope) |

Every CRT `TRADE_OPENED` has a reconstructable chain:

```text
input candle/context
  → state sequence (from events.jsonl)
  → transition guards (implied by successful transitions)
  → soft-conf S_score + session
  → CRT-internal diversions passed
  → candidate payload
  → TRADE_OPENED
```

---

## Summary table

| # | trade_id | timestamp | dir | path | S_score | session | risk_pct | journaled |
|---:|---|---|---|---|---:|---|---:|---|
| 1 | CRT-0001 | 2024-05-24 07:45 | LONG | SHADOW | 0.510 | LONDON | 0.005 | **no** |
| 2 | CRT-0002 | 2024-10-28 13:45 | SHORT | SHADOW | 0.571 | NEWYORK | 0.005 | yes |
| 3 | CRT-0003 | 2024-11-07 14:00 | SHORT | SHADOW | 0.537 | NEWYORK | 0.005 | yes |
| 4 | CRT-0004 | 2025-01-13 15:15 | LONG | GOLDEN | 0.480 | NEWYORK | 0.005 | yes |
| 5 | CRT-0005 | 2025-01-19 09:15 | LONG | GOLDEN | 0.371 | LONDON | 0.005 | yes |
| 6 | CRT-0006 | 2025-02-17 13:45 | SHORT | GOLDEN | 0.418 | NEWYORK | 0.005 | yes |
| 7 | CRT-0007 | 2025-03-15 08:15 | LONG | GOLDEN | 0.485 | LONDON | 0.005 | yes |
| 8 | CRT-0008 | 2025-06-15 09:15 | LONG | SHADOW | 0.461 | LONDON | 0.005 | yes |
| 9 | CRT-0009 | 2025-08-02 09:00 | LONG | GOLDEN | 0.471 | LONDON | 0.005 | yes |
| 10 | CRT-0010 | 2025-10-04 09:45 | LONG | SHADOW | 0.445 | LONDON | 0.005 | yes |
| 11 | CRT-0011 | 2025-12-09 07:30 | LONG | GOLDEN | 0.456 | LONDON | 0.005 | **no** |
| 12 | CRT-0012 | 2026-02-12 14:00 | SHORT | GOLDEN | 0.556 | NEWYORK | 0.005 | yes |
| 13 | CRT-0013 | 2026-03-18 13:45 | LONG | SHADOW | 0.442 | NEWYORK | 0.005 | yes |

### Path templates

**GOLDEN (7):**
```text
RANGE → SWEEP → DISPLACEMENT → EXPANSION → RETEST → EXECUTION
```

**SHADOW (6):**
```text
RANGE → SHADOW_PENDING → SWEEP → EXPANSION → RETEST → EXECUTION
```
(strength re-check skipped on shadow hop; Phase 3 graph)

---

## CRT-internal gates passed (all 13)

Inferred from successful emission (see Phase 4 diversion IDs):

| Diversion | Status |
|---|---|
| Soft-conf S ≥ tier_2 (0.30) | PASSED (S ∈ [0.371, 0.571], all tier_2) |
| Zone discount/premium | PASSED |
| Session filter | PASSED (LONDON/NEWYORK only) |
| Inverted-SL | PASSED (build_trade succeeded) |
| BitNet | INACTIVE (`use_bitnet=false`) |

`risk_pct=0.005` on all 13 → sizing band tier_2 (score below 0.75 full band).

---

## Downstream note (not Phase 6)

| trade_id | CRT opened | In gate-ON trades.csv |
|---|---|---|
| CRT-0001 | yes | **no** |
| CRT-0011 | yes | **no** |

Matches baseline: 13 CRT candidates → 2 EngineRunner rejects → 11 journal admits. **OI-ER-001** owns why those two were rejected.

---

## Evidence sources

- `results/baseline/run1/BNBUSDT_events.jsonl` — state transitions, TRADE_OPENED, soft conf  
- `results/baseline/run1/BNBUSDT_crt_telemetry.jsonl` — expansion episode sidecar (when matched)  
- `results/baseline/run1/BNBUSDT_trades.csv` — cached feature snapshot for journaled 11  
- `reports/PRE_REMEDIATION_BASELINE.md` — corpus pin  

No new backtest. No production code changes.

---

## Phase 6 return

```text
CRT_13_CANDIDATE_PROVENANCE_STATUS = COMPLETE
CANDIDATE_COUNT = 13
COMPLETE = 13
PARTIAL = 0
UNKNOWN = 0
SHADOW = 6
GOLDEN = 7
PHASE6_STATUS = PASS
NEXT = await Phase 7 authorization
```
