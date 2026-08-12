# SECONDLOW Research Data Policy

**Version:** 1.0  
**Date:** 2026-07-06  
**Status:** ACTIVE  
**Companion:** [`CORPUS_POLICY.md`](CORPUS_POLICY.md) · [`data/sealed_evaluation_set_v1.json`](data/sealed_evaluation_set_v1.json)

---

## 1. Purpose

Deterministic governance for SECONDLOW-family research on the canonical MT5 corpus. This
policy separates **development** from **evaluation**, seals the current evaluation pool
before any further inspection, and defines what to do when additional history does not
exist.

LLMs may assist hypothesis drafting on development data. They do **not** create
independence, sample size, or promotional authority.

---

## 2. Corpus tiers

| Tier | Path | Role | Economic authority |
|---|---|---|---|
| **Canonical OHLCV** | `data/XAUUSD_M15.csv` | Single production/research price series | Yes (when pre-registered) |
| **Regression fixture** | `data/XAUUSD_M15_1year.xlsx` | Detector bytecode pin only | **No** |
| **Sealed evaluation manifest** | `data/sealed_evaluation_set_v1.json` | Frozen event IDs (21 PRE timestamps) | Holdout only — one shot per prereg |

**SHA-256 prefixes:** MT5 `4d73f5cebe33ec91` · xlsx `e0bb97d9a5f3bea9`

---

## 3. Sealed evaluation set (frozen 2026-07-06)

**Population:** 21 independent PRE_DISCOVERY purge times on MT5 CSV, detected with
`src/research/secondlow_v1/detector.py` (trading-day ladder, 120min independence).

**Seal rule:** Until a new hypothesis is **pre-registered and user-approved**, no agent or
script may compute on these events:

- `close_disp_atr` or any post-purge outcome
- `pre_2h_return_atr`, `purge_depth_atr`, or exposure labels
- Threshold sweeps, path typing, or conjunction mining

Permitted before prereg: detector regression tests, count-only audits, timestamp manifest
verification.

**Enforcement:** `tests/research/test_secondlow_sealed_evaluation_set.py`

---

## 4. Development corpus search (2026-07-06)

**Question:** Does additional same-broker/feed MT5 M15 history exist for development?

**Result:** **NO** — within this repository.

| Candidate | Rows | Span | Hash prefix | Verdict |
|---|---|---|---|---|
| `data/XAUUSD_M15.csv` | 47,275 | 2024-05-22 → 2026-05-21 | `4d73f5ce` | Canonical (duplicate of `data/mt5/`) |
| `data/mt5/XAUUSD_M15.csv` | 47,275 | same | `4d73f5ce` | Byte-identical duplicate |
| `data/yfinance/XAUUSD_M15.csv` | 2,294 | 2026-04-17 → 2026-05-22 | `7dd8282b` | Different feed/prices — **not development** |
| `data/_archive_5wk/XAUUSD_M15.csv` | 2,294 | same as yfinance | `7dd8282b` | Not MT5 canonical |
| `data/XAUUSD_M15_1year.xlsx` | 2,294 | discovery window | `e0bb97d9` | Regression fixture only |

No file extends MT5 history before **2024-05-22** or after **2026-05-21**. POST_DISCOVERY
independent events = **0**.

**Conclusion:** A separate in-repo development event pool **does not exist**. Mining the
21 sealed evaluation events is the only available PRE pool — which is why they are sealed.

---

## 5. When development corpus is unavailable

The correct action is **not** another hypothesis on the sealed set.

### 5.1 Prospective event collection protocol

1. **Extend OHLCV** — fetch MT5 XAUUSD M15 forward from `2026-05-21` via
   `scripts/data/fetch_and_verify_mt5.py` (same broker path as canonical corpus).
2. **Re-run detector** — `count_only_audit_secondlow_v1.py` on updated CSV; record new
   `corpus_hash` in an addendum.
3. **POST_DISCOVERY gate** — new independent events with `purge_time > 2026-05-22` enter
   the **prospective pool** (not mixed with sealed PRE until prereg defines consumption).
4. **Append-only ledger** — `data/secondlow_prospective_events.jsonl` (one line per new
   event: `purge_time`, `corpus_hash`, `detector_git_sha` or package version, `collected_at`).
5. **Promotion rule** — prospective events earn evaluation authority only through a new
   pre-registration that names them explicitly.

### 5.2 What is forbidden while waiting

- Re-opening H-SECONDLOW-002 thresholds (-2.0 / 1.5) on MT5
- Soft carry-forward of xlsx forensic conclusions
- Multiple exposure variants on the 21 sealed events without prereg
- Declaring "promising" from descriptive passes on the sealed set

---

## 6. Pre-registration

**Draft:** [`preregistration-H-SECONDLOW-003-v0.1.md`](preregistration-H-SECONDLOW-003-v0.1.md)  
**Status:** DRAFT — pending user approval. Sealed set remains locked until approved.

Any approved hypothesis must declare **before** sealed-set inspection:

1. MT5 CSV as sole data source + stamped `corpus_hash`
2. Low-dimensional exposure (justify any conjunction)
3. Primary endpoint + decision rules realistic for available N
4. Holdout strategy: prospective POST events **or** explicit descriptive-only framing
5. Implementation = regression-pinned detector module

---

## 7. Archived hypotheses

| ID | Status | Notes |
|---|---|---|
| H-SECONDLOW-002 v1.0 | **ARCHIVED** | xlsx discovery; non-promotable on MT5 |

---

## 8. Related artifacts

- Detector: `src/research/secondlow_v1/`
- Regression: `tests/research/test_secondlow_v1_detector_regression.py`
- Count audit: `scripts/research/count_only_audit_secondlow_v1.py`
- HANDOFF: `standing_rules.canonical_corpus`