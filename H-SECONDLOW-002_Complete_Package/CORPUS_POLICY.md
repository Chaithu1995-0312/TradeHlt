# XAUUSD M15 Corpus Policy (2026-07-06)

## Canonical corpus (production + research)

| Field | Value |
|---|---|
| Path | `data/XAUUSD_M15.csv` |
| SHA-256 prefix | `486cf3616415ff86` (extended 2026-07-07 → 2026-07-06 23:45) |
| Source | MT5 fetch |
| Detector ladder | Trading-day `second_low_20d` (`src/research/secondlow_v1/detector.py`) |

**Rule:** All new hypotheses must be pre-registered and derived on this file. No economic
authority attaches to results computed on any other XAUUSD export unless a new corpus is
promoted via explicit user approval + provenance addendum.

## Regression fixture only (not economic evidence)

| Field | Value |
|---|---|
| Path | `data/XAUUSD_M15_1year.xlsx` |
| SHA-256 prefix | `e0bb97d9a5f3bea9` |
| Purpose | Byte-stable SECONDLOW-v1 detector regression (16 raw / 7 independent) |
| Enforcement | `tests/research/test_secondlow_v1_detector_regression.py` |

**Rule:** Use the xlsx only to verify detector code has not drifted. Do not use it for
hypothesis promotion, confirmatory runs, or threshold selection.

**Canonical MT5 independent counts (trading-day, controlled semantics):** 79 raw purges,
50 independent (21 PRE / 15 DISCOVERY / 14 POST) — enforced by
`test_canonical_corpus_partition_invariants`.

## H-SECONDLOW-002 v1.0 status

The frozen H-SECONDLOW-002 contract was developed on the xlsx discovery slice. Under this
policy it is **archived for provenance** — not a live confirmatory hypothesis on MT5.

Future work: new hypothesis ID, pre-registration doc, MT5 corpus hash stamped on every artifact.

**Forward research plan:** [`SECONDLOW_Forward_Research_Plan_v1.md`](SECONDLOW_Forward_Research_Plan_v1.md)  
**Prereg template:** [`preregistration-template-H-SECONDLOW-v1.md`](preregistration-template-H-SECONDLOW-v1.md)  
**Study closures:** [`study_closures/`](study_closures/)

## Sealed evaluation set + development corpus policy

See [`SECONDLOW_RESEARCH_DATA_POLICY.md`](SECONDLOW_RESEARCH_DATA_POLICY.md) and
[`data/sealed_evaluation_set_v1.json`](data/sealed_evaluation_set_v1.json).

- **21 PRE events** are sealed (timestamps only) — no outcome inspection until prereg.
- **No additional MT5 history** exists in-repo for a development corpus (search 2026-07-06).
- **Next action when data-bound:** prospective MT5 fetch + append-only event ledger.