# XAUUSD M15 Corpus Timestamp / Gap / Overlap Report

Generated (UTC): `2026-07-10T19:54:12Z`

Computed from **raw CSV bytes** (`data/XAUUSD_M15.csv` + `data/mt5/XAUUSD_M15.csv`).
Machine twin: `reports/xauusd_m15_corpus_timestamp_gap_report.json`.

## Identity

| Corpus | Path | SHA-256 prefix | Rows | Unique ts | First | Last |
|---|---|---|---:|---:|---|---|
| `C-ROOT-EXTENDED` | `data/XAUUSD_M15.csv` | `486cf3616415ff86…` | 50169 | 50169 | 2024-05-22 01:00:00 | 2026-07-06 23:45:00 |
| `C-PINNED-LEGACY` | `data/mt5/XAUUSD_M15.csv` | `4d73f5cebe33ec91…` | 47275 | 47275 | 2024-05-22 01:00:00 | 2026-05-21 23:45:00 |

Quarantine twin: `data/mt5/_rejected/XAUUSD_M15.csv` sha `486cf3616415ff86…` byte_identical_to_root=True.

## Per-corpus integrity

| Metric | Root extended | Legacy pinned |
|---|---:|---:|
| duplicate timestamps | 0 | 0 |
| out-of-order adjacent pairs | 0 | 0 |
| wall-clock missing 15m slots | 24323 | 22801 |
| residual UNEXPLAINED missing slots | 0 | 0 |
| config+broker-pattern explained slots | 24323 | 22801 |
| config-only explained slots | 21335 | 19985 |
| broker-pattern explained slots | 2988 | 2816 |
| residual unexplained gap events | 0 | 0 |
| long residual unexplained (≥4 bars) | 0 | 0 |
| weekend bars present | 0 | 0 |
| partial weekday days | 0 | 0 |

### Missing-slot class counts (root)

```json
{
  "OBSERVED_MIDNIGHT_ROLLOVER": 2108,
  "WEEKEND_SESSION_CLOSE": 20240,
  "CONFIG_OPEN_NO_BAR": 880,
  "HOLIDAY": 838,
  "KNOWN_GAP": 257
}
```

### Missing-slot class counts (legacy)

```json
{
  "OBSERVED_MIDNIGHT_ROLLOVER": 1984,
  "WEEKEND_SESSION_CLOSE": 19136,
  "CONFIG_OPEN_NO_BAR": 832,
  "HOLIDAY": 838,
  "KNOWN_GAP": 11
}
```

### Delta histogram (root, labeled top)

```json
{
  "15m": 49618,
  "75m": 418,
  "2955m": 104,
  "225m": 14,
  "3195m": 3,
  "2h": 2,
  "1515m": 2,
  "1710m": 2,
  "3090m": 2,
  "4395m": 2,
  "30m": 1
}
```

### Delta histogram (legacy, labeled top)

```json
{
  "15m": 46758,
  "75m": 394,
  "2955m": 99,
  "225m": 13,
  "1515m": 2,
  "1710m": 2,
  "3090m": 2,
  "4395m": 2,
  "2h": 1,
  "3195m": 1
}
```

## Overlap / extension

- Shared timestamps: **47275**
- Only in root: **2894** (after legacy last: **2894**; inside legacy window: **0**)
- Only in legacy: **0** (inside root window: **0**)
- OHLCV mismatches on shared ts (sample size): **0**
- Extension range: `2026-05-22 01:00:00` → `2026-07-06 23:45:00`

## Verdicts (revised — prior `EXPECTED_MARKET_CLOSURES_ONLY` OVERCLAIMED)

Classifier circularity: missing slots are “expected” if they match production
`session_calendar`, **observed** broker pattern, or pre-registered `known_gaps`.
That does **not** independently prove market closures.

| Axis | Value |
|---|---|
| SEQUENCE_INTEGRITY | **PASS** (0 dups, 0 OOO, modal 15m) |
| OVERLAP_INTEGRITY | **PASS** (47,275 shared; 0 OHLCV mismatch) |
| HISTORICAL_REWRITE | **NOT_DETECTED** |
| MID_SESSION_UNCLASSIFIED_GAPS | **0** |
| SESSION_CALENDAR_CONSISTENCY | **FAIL** (config vs corpus open/break) |
| KNOWN_GAP_INDEPENDENT_VALIDATION | **UNPROVEN** |
| MARKET_CLOSURE_ONLY_CLAIM | **UNPROVEN** |
| PAIR_DIVERGENCE_TYPE | **APPEND_ONLY_EXTENSION** |
| AUTHORITY_STATUS | **UNRESOLVED** |

Strict-REJECT forensic (same 50,169-row bytes):
[`docs/governance/xauusd_m15_strict_reject_forensic-2026-07-10.md`](../docs/governance/xauusd_m15_strict_reject_forensic-2026-07-10.md)
— REJECT class = **CALENDAR_CONTRACT** (16 Fri evening slots before Jul-4 `known_gap`).

### Legacy labels (superseded for market-truth)

- ~~`EXPECTED_MARKET_CLOSURES_ONLY`~~ — circular; do not treat as market proof
- Residual classifier UNEXPLAINED = 0 (not equal to “market was closed”)
- Prefer `APPEND_ONLY_EXTENSION` over bare `CORPUS_DIVERGENCE` for this pair

## Top residual unexplained gap events (root)

- *(none under implemented classifier)*

## Top residual unexplained gap events (legacy)

- *(none under implemented classifier)*

---

Authority: analysis/evidence only. Grants no corpus promotion.
