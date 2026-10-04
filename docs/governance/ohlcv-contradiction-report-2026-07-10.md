# OHLCV Contradiction Report — PHASE 1 (OHLCV Truth Closure) PASS A

| Field | Value |
|---|---|
| Program | Layer-by-layer repository audit (bottom-up) |
| Phase | 1 of 16 — OHLCV Truth |
| Pass | A (Evidence Freeze) |
| Generated (UTC) | 2026-07-10T13:09:06Z |
| Pinned commit | `b48d4d9a7abfb429f2a17c790d4b32083da5dd92` (worktree DIRTY) |
| Branch | `feature/truth-registry-v2` |
| Verdict | (none — `closure_blocker_candidate` flags only; final BLOCKER / PROVEN_NON_BLOCKER classification is PASS B) |

**NO REMEDIATION was performed on any item below.** Per §6.2 rule 3, no
contradiction was silently resolved. Severity encoding follows the geometry
precedent: reachability + affected-surface, not a numeric scale.

---

### CX-OHLCV-001 — Same logical corpus resolves to different bytes across families
- **Claim A:** a logical corpus id (`{SYMBOL}_{TF}`) denotes one dataset.
- **Claim B (measured):** 12 of 48 logical corpora have MULTIPLE active
  claimants; **9 resolve to DIFFERENT byte content** under the same logical name
  (census `logical_rollup`: AUDUSD/BTCUSDT/DOGEUSDT/ETHUSDT/EURCAD/GBPUSD/
  USDJPY/XAUUSD/XRPUSDT `_M15`).
- **Evidence:** `ohlcv-corpus-fingerprint-manifest-2026-07-10.json`
  (`same_logical_different_bytes: true` rows) — EXECUTABLE.
- **Runtime reachability:** REAL — consumers select a corpus by PATH STRING at
  each call site (no repository-wide logical→physical resolver exists), so which
  bytes "BTCUSDT_M15" means depends on which path a script hard-codes.
- **Affected:** every cross-family comparison; any claim of the form "measured
  on BTCUSDT M15" is under-specified without the path/hash.
- **Closure-blocker candidate:** **YES** (corpus identity — C1 UNKNOWN rule).
- **Required resolution (PASS B):** an authoritative logical→physical binding
  (per family) in the output contract; no data changes needed.

### CX-OHLCV-002 — Root crypto majors descend from the UNGATED family, not the strict-gated one
- **Claim A (implied by architecture):** the canonical corpus is produced by the
  strict fetch-and-verify gates.
- **Claim B (measured):** root `BTCUSDT/ETHUSDT/XRPUSDT/DOGEUSDT_M15.csv` are
  byte-identical to `data/yfinance/` twins (DUP-024/026/029/010) and DIFFER from
  the strict-gated `data/binance/` fetches; the yfinance family has NO verify
  gate and performs acquisition-time repairs (T-006: `fillna(0)` volume,
  `drop_duplicates keep="last"`).
- **Evidence:** census duplicate groups + `fetch_forex_yfinance.py:130-171` —
  EXECUTABLE + STATIC.
- **Runtime reachability:** REAL — the root corpus is what
  `canonical_data_roots=["data"]` gates and what historical backtests consumed.
- **Closure-blocker candidate:** **YES** (transformation provenance of the
  canonical corpus).
- **Required resolution:** PASS-B decides whether root-crypto provenance is a
  BLOCKER or provably non-blocking (e.g. if all downstream findings re-derive
  from provider corpora); alternatively re-derivation of root crypto from the
  gated `binance/` family is a REMEDIATION decision, out of PASS-A scope.

### CX-OHLCV-003 — Volume semantics vary silently under one column name
- **Claim A (schema):** `volume` is one quantity
  (`ohlcv_schema.py` treats it as a single mandatory field).
- **Claim B (measured):** `volume` is tick count (mt5 family), exchange base
  volume (binance/ccxt), a leg's volume or 0 for SYNTHESIZED crosses
  (yfinance T-006), Decimal-sum of children (resampled), and — latently — a
  PRICE RANGE (feature-layer T-003 proxy).
- **Evidence:** `mt5_candle_fetcher.py:105` (tick_volume), ccxt convention,
  `fetch_forex_yfinance.py:135,157`, `resample.py:93`,
  `feature_pipeline.py:214-216` — STATIC (+ NARRATIVE for ccxt).
- **Runtime reachability:** REAL for cross-family consumers (any script mixing
  mt5 and binance corpora compares tick counts to base volume); LATENT for the
  T-003 proxy (census: 0 all-zero-volume files today).
- **Closure-blocker candidate:** **YES** for the output contract (the contract
  must declare per-family volume semantics; a single undeclared `volume`
  guarantee would be CONTRADICTED).
- **Required resolution:** per-family `volume_semantic` declaration in the
  PASS-B contract; feature-layer proxy must be a DECLARED substitution.

### CX-OHLCV-004 — The HANDOFF-canonical XAUUSD corpus is byte-identical to a QUARANTINED artifact
- **Claim A:** `HANDOFF.md standing_rules.canonical_corpus =
  data/XAUUSD_M15.csv` (the H-SECONDLOW canonical corpus).
- **Claim B (measured):** `data/XAUUSD_M15.csv` ≡
  `data/mt5/_rejected/XAUUSD_M15.csv` (census DUP-008) — the strict gate
  REJECTED exactly these bytes, yet they serve as the canonical corpus at root.
  (Known prior context: XAUUSD was excluded from F-035 for a 26h holiday gap
  that REJECTs the FX gap gate.)
- **Evidence:** census hash groups — EXECUTABLE.
- **Runtime reachability:** REAL (root path is consumable; HANDOFF names it).
- **Closure-blocker candidate:** **YES** (corpus identity + gate-semantics
  coherence: "quarantined" bytes are simultaneously "canonical").
- **Required resolution:** PASS-B classification; possibly a declared known-gap
  acceptance (the `known_gaps` accept-list mechanism exists,
  `dataset_integrity.py:125-130`) — a governance decision, not a PASS-A action.

### CX-OHLCV-005 — Same bytes both APPROVED and REJECTED across locations
- **Claim A:** quarantine separates bad data from good.
- **Claim B (measured):** 12 H1/H4 FX files in `data/_rejected/` are
  byte-identical to ACTIVE `data/mt5/` files (DUP-003/004/005/007/011/012/013/
  017/018/020/022/023).
- **Evidence:** census duplicate groups — EXECUTABLE.
- **Runtime reachability:** LOW direct risk (no code reads `_rejected/` —
  transformation-graph negative result #4), but the gate's verdict for these
  bytes is location/config-dependent, which weakens "REJECTED" as a property of
  DATA (it is a property of data × path × config-at-time).
- **Closure-blocker candidate:** NO (candidate PROVEN_NON_BLOCKER — no active
  read path; PASS B must still confirm with positive evidence).
- **Required resolution:** document that a REJECT verdict is contextual;
  optionally record gate-config provenance in quarantine (remediation-class,
  out of scope).

### CX-OHLCV-006 — A dormant DB-backed OHLCV chain contradicts the no-database doctrine
- **Claim A:** "Everything is file-backed — no database" (CLAUDE.md §1) and
  `ohlcv_schema`/`CandleLoader` as THE ingestion funnel.
- **Claim B:** `HistoricalFetcher` (TimescaleDB, `historical_fetcher.py:198`,
  `_DBConnection :170`) is importable, lazily imported by
  `portfolio/correlation_engine.py:77-78`, and registered in
  `control_plane/registry.py:800-805` — a second ingestion chain bypassing
  T-001/T-002.
- **Evidence:** STATIC (cited lines).
- **Runtime reachability:** LATENT (no evidence of a configured DB; topics
  index marks data ingestion DORMANT).
- **Closure-blocker candidate:** NO (candidate PROVEN_NON_BLOCKER if PASS B
  confirms no DB config exists on this machine/branch).
- **Required resolution:** PASS-B positive evidence of non-activation, or
  doctrine-side acknowledgment (doc drift, §6.2 rule 2).

### CX-OHLCV-007 — Two coexisting, semantically different HTF definitions
- **Claim A:** "the H4 context" is a well-defined object.
- **Claim B:** the research path builds CALENDAR-aligned HTF buckets
  (T-004 `resample.py:105`), while the backtest/live spine builds COUNT-based
  windows (T-005 `HTFBuilder`, `backtest_v2.py:797-805`) whose boundaries drift
  off calendar after any gap. Same words, different objects.
- **Evidence:** STATIC (both paths cited); temporal report worked example 4.
- **Runtime reachability:** REAL (both ACTIVE in their pipelines).
- **Closure-blocker candidate:** NO for OHLCV-layer closure (both are
  DOWNSTREAM aggregations of the same certified rows; the output contract can
  declare both) — but it MUST be declared, else the Phase-2+ handoff inherits an
  ambiguous term.
- **Required resolution:** name them distinctly in the output contract
  (calendar-HTF vs rolling-count-HTF).

### CX-OHLCV-008 — The L1 gate admits the all-zero-volume precondition that activates a silent unit change
- **Claim A:** `ohlcv_schema.py` module docstring: "no column substitution, and
  no zero/one-fill for the six mandatory fields".
- **Claim B:** `validate_ohlcv_frame` deliberately PERMITS an all-zero volume
  column (`feature_pipeline.py:171-174`), which is precisely the trigger for
  T-003's silent `volume := high-low` substitution (`:207,214-216`) — the
  substitution the docstring forbids, one layer up.
- **Evidence:** STATIC. Census: 0 current corpora trigger it (LATENT).
- **Runtime reachability:** LATENT (needs an all-zero-volume corpus; none on
  disk today; yfinance FX path can produce `volume=0` rows via `fillna(0)`).
- **Closure-blocker candidate:** NO as data-truth today (candidate
  PROVEN_NON_BLOCKER with the census as evidence) — **YES as a contract term**:
  the output contract must either forbid all-zero-volume corpora (fail-closed)
  or declare the substitution.
- **Required resolution:** contract clause in PASS B; test-coverage seed
  SEED-OHLCV-19 (the branch has no test).

### CX-OHLCV-009 — Prereg says 26 failure classes; the frozen matrix says 27
- **Claim A:** `preregistered_experiments.md` §E-MT-00: "26 FC-*".
- **Claim B:** `e_mt_01_adversarial_mutation_matrix.json`
  `coverage_summary.n_failure_classes: 27` (authoritative; frozen).
- **Evidence:** both files, backup-manifest-pinned hashes.
- **Runtime reachability:** none (doc-count drift).
- **Closure-blocker candidate:** NO (DOC_DRIFT class; the JSON is the machine
  authority).
- **Required resolution:** one-line prereg correction under the Documentation
  Drift Protocol — deferred (PASS A does not edit existing docs).

### CX-OHLCV-010 — "Every backtest entry point" vs actual L3 coverage (known, F-039)
- Recorded for completeness: L3 pre-flight runs at exactly two runtime call
  sites (`backtest_v2.py:2542/:2586`) + the fetch gates; all other ~45
  `CandleLoader` consumers stream with the inline L1/L2 backstop only.
- **Evidence:** `dataset_integrity.py:24-31` (docstring now states this
  correctly) + call-site sweep — STATIC/REPRODUCIBLE.
- **Closure-blocker candidate:** NO as a NEW item (already a registered finding
  F-039, conf. Certain); the output contract must carry
  `dataset_integrity_level` per consumer path (the E-MT schema already has the
  enum `L1_L2_only|L1_L2_L3`).

---

## Roll-up

| id | one-line | blocker candidate |
|---|---|---|
| CX-OHLCV-001 | same logical name → different bytes (9 corpora) | **YES** |
| CX-OHLCV-002 | canonical root crypto descends from the ungated yfinance family | **YES** |
| CX-OHLCV-003 | `volume` = 5 different quantities under one name | **YES** (contract term) |
| CX-OHLCV-004 | canonical XAUUSD ≡ quarantined bytes | **YES** |
| CX-OHLCV-005 | same bytes APPROVED and REJECTED | no (pending positive proof) |
| CX-OHLCV-006 | dormant TimescaleDB ingestion chain | no (pending positive proof) |
| CX-OHLCV-007 | calendar-HTF vs count-HTF homonym | no (must be declared) |
| CX-OHLCV-008 | L1 admits the trigger of a forbidden substitution (latent) | no as data / **YES** as contract term |
| CX-OHLCV-009 | 26 vs 27 FC count (doc drift) | no |
| CX-OHLCV-010 | L3 single-callsite (= F-039) | no (already registered) |

## What this report did NOT do

No remediation, no doc edits, no finding flips, no closure verdicts, no
economic claims.

```text
OHLCV_CONTRADICTIONS_REGISTERED = 10
OHLCV_CONTRADICTIONS_BLOCKER_CANDIDATES = 4 (+2 contract-term)
OHLCV_CONTRADICTIONS_STATUS = EVIDENCE_FROZEN
```
