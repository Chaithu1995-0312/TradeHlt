# H-SECONDLOW-006 v0.1 — Pre-Registration

**Status:** APPROVED (2026-07-07) — count-only phase; **no outcome analysis** until promotion gate passed + separate outcome prereg  
**Date:** 2026-07-07  
**Hypothesis ID:** H-SECONDLOW-006  
**Version:** 0.1  
**Program type:** Higher-frequency **count-only exploration** (parallel to H-SECONDLOW-004 v0.2)  
**Predecessor:** H-SECONDLOW-004 v0.2 (primary prospective stream — unchanged)

---

## Purpose

Systematically screen detector/exposure variants for **material POST_DISCOVERY EXPOSED
frequency gain** without mining outcomes on the v0.2 prospective ledger.

H-SECONDLOW-004 v0.2 remains the **primary** outcome stream. This ID owns **count
diagnostics only** until a variant clears the promotion gate below and earns a
separate outcome prereg (likely H-SECONDLOW-007+).

---

## Data Use Declaration

- [x] Descriptive / count-only on full canonical corpus: **ALLOWED**
- [ ] Outcome analysis on sealed 21 PRE: **FORBIDDEN**
- [ ] Outcome analysis on v0.2 prospective ledger (`secondlow_prospective_events.jsonl`): **FORBIDDEN** under this ID
- [ ] Outcome analysis on any variant stream: **FORBIDDEN** until promotion + new outcome prereg

**Corpus:** `data/XAUUSD_M15.csv` · hash `486cf3616415ff86` (2026-07-07)  
**Baseline detector pin:** `src/research/secondlow_v1/detector.py` — 20d trading-day ladder, 120min spacing

---

## Promotion Gate (count-only → outcome-eligible)

A variant may advance to a **new outcome hypothesis** only if **all** hold:

| # | Criterion | Rationale |
|---|---|---|
| 1 | `Δ n_post_v02_exposed ≥ +2` vs 20d/120min baseline | Depth 0.8, R4, R3 failed at +0 POST |
| 2 | Variant is **pre-declared** in this doc (not mined post-hoc) | Governance |
| 3 | Separate ledger tag / hypothesis ID for forward events | No v0.2 stream contamination |
| 4 | User **APPROVED** outcome prereg (new ID) | Authority gate |
| 5 | Exposure rule justified pre-data (quality-first note required) | OR variants flagged explicitly |

**v0.2 EXPOSED rule for counting:** `purge_depth_atr ≥ 1.0` (unchanged across variants unless exposure axis is the variant).

---

## Variant Screen (2026-07-07 — count-only results)

| ID | Variant | Script | n_ind | n_POST | n_POST_EXPOSED | Δ POST EXPOSED | Verdict |
|---|---|---|---:|---:|---:|---:|---|
| — | **Baseline** (20d, 120min, depth≥1.0) | detector pin | 50 | 14 | **3** | 0 | v0.2 primary |
| R1 | depth ≥ 0.75 (conjunction) | relaxation | 50 | 14 | 3 | 0 | **KILL** |
| v0.3 | depth ≥ 0.8 | `secondlow_v03_depth08_count_diagnostic.py` | 50 | 14 | 3 | 0 | **KILL** |
| R2 | depth ≥ 1.0 only (exposure) | — | — | — | 3 | 0 | → H-SECONDLOW-004 |
| R4 | 90min spacing | `secondlow_r4_spacing_count_diagnostic.py` | 55 | 14 | 3 | 0 | **KILL** |
| R3-15 | 15d lookback | `secondlow_r3_lookback_count_diagnostic.py` | 85 | 14 | 3 | 0 | **KILL** |
| R3-10 | 10d lookback | same | 128 | 14 | 3 | 0 | **KILL** |
| **R5** | `depth≥0.75 OR pre_2h≤−1.5` | relaxation (exposure) | 50 | 14 | **7** | **+4** | **CANDIDATE** |

**R3 note:** +35/+78 historical independent events and +8/+16 historical EXPOSED — all incremental mass is **PRE_DISCOVERY**; POST window unchanged (14 events, 3 EXPOSED). Same failure mode as R4 (adds historical noise, not prospective candidates).

**R5 note:** Only variant clearing promotion gate #1 on current corpus. Tradeoff: EXPOSED rate 7/14 (50%) vs 3/14 (21%) — **quality vs frequency**; OR logic dilutes depth-only interpretation.

---

## Leading Candidate (if exploration advances)

### H-SECONDLOW-007 (reserved) — R5 OR exposure variant

**Not active.** Draft outcome prereg only if user accepts quality tradeoff.

| Field | Proposed value |
|---|---|
| Detector pin | Unchanged (20d, 120min) |
| EXPOSED if | `purge_depth_atr ≥ 0.75` **OR** `pre_2h_return_atr ≤ −1.5` |
| Reference | Events meeting neither condition |
| Forward ledger | `data/secondlow_r5_prospective_events.jsonl` (separate file) |
| Outcome endpoint | Same as v0.2 (`close_disp_atr` +120m) — only after APPROVED outcome prereg |

---

## Forbidden (this ID)

- Outcome analysis on any variant before promotion
- Retuning thresholds on v0.2 using prospective results
- Declaring PROMOTE from count diagnostics alone
- Merging R5 events into `secondlow_prospective_events.jsonl`

---

## Artifacts (generated)

| Path | Content |
|---|---|
| `results/relaxation_count_diagnostic/relaxation_counts.json` | R1/R2/R5 + detector grid |
| `results/v03_depth08_count_diagnostic/depth08_count_diagnostic.json` | depth 0.8 |
| `results/r4_spacing_count_diagnostic/r4_spacing_count_diagnostic.json` | 90min spacing |
| `results/r3_lookback_count_diagnostic/r3_lookback_count_diagnostic.json` | 10d/15d lookback |

---

## Standing Orders (parallel program)

```
H-SECONDLOW-004 v0.2  →  quiet prospective collection + dual-track updates (primary)
H-SECONDLOW-006 v0.1  →  count-only screen (this doc); monthly re-run diagnostics on corpus growth
H-SECONDLOW-007       →  reserved for R5 outcome prereg IF user approves quality tradeoff
```

**Monthly cadence (006):** After MT5 fetch, re-run count diagnostics; log if any variant newly clears `Δ POST EXPOSED ≥ +2`.

---

## Approval Gate

| Phase | Status |
|---|---|
| Count-only exploration (006) | **APPROVED** (2026-07-07) — user sign-off |
| R5 outcome prereg (007) | **Not drafted** — deferred; user must explicitly request |

**Approval note:** Formalizes completed variant screen (R3/R4/depth KILL; R5 CANDIDATE +4 POST EXPOSED). H-SECONDLOW-004 v0.2 primary stream unchanged. Summary: `results/higher_frequency_screen_summary.json`.