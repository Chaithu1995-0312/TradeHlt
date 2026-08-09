# OHLCV Closure Report — PHASE 1 (OHLCV Truth Closure) PASS B

| Field | Value |
|---|---|
| Program | Layer-by-layer repository audit (bottom-up) |
| Phase | 1 of 16 — OHLCV Truth |
| Pass | B (Blocked-State Adjudication) |
| Generated (UTC) | 2026-07-10T13:09:06Z (session) |
| Pinned commit | `b48d4d9a7abfb429f2a17c790d4b32083da5dd92` (worktree DIRTY — pre-existing, pinned in backup manifest) |
| Branch | `feature/truth-registry-v2` |
| Machine twin | `docs/governance/ohlcv-output-contract-2026-07-10.json` |
| PASS-A evidence | census + fingerprint manifest + lineage map + transformation graph + temporal report + contradiction report + adversarial matrix (all `-2026-07-10`, hash-pinned in `layer-audit-manifest.json`) |
| **Verdict** | **`OHLCV_CLOSURE_STATUS = BLOCKED:BC-1,BC-2[mt5|binance|yfinance],BC-3,BC-4,BC-5,BC-6[yfinance]`** |

---

## 1. Blocker-candidate adjudication (independent verification vs user adjudication)

Every BC was re-verified against the frozen PASS-A artifacts plus targeted
read-only probes run in this pass. Concur/dissent recorded per §13.8 (advice is
non-binding; evidence decides).

| BC | User classification | Independent verification (this pass) | Final | Concur? |
|---|---|---|---|---|
| BC-1 identity unbound | BLOCKER 10/10 | Spot-recomputed hashes independently (`data/BTCUSDT_M15.csv` `e175fa7c…` ≠ `data/binance/BTCUSDT_M15.csv` `ceb96026…`) — manifest faithful; no logical→physical resolver exists (grep: consumers hard-code paths) | **BLOCKER** | CONCUR |
| BC-2 timestamp semantics | BLOCKER, family-scoped 9/10 | Evidence ceiling re-verified: zero tests reference `open_time`/label conventions (grep over `tests/`, 2026-07-10) → NARRATIVE-ONLY stands for all three acquisition families; PROVEN for resampled/converter outputs (`resample.py:95`) | **BLOCKER, scoped to mt5/binance/yfinance acquisition families** (and their root descendants); resampled family exempt | CONCUR |
| BC-3 ungated canonical crypto | BLOCKER 9/10 | Hash descent re-confirmed (DUP-010/024/026/029); per instruction, NOT resolved by declaring Binance authoritative — contract marks `data_root_crypto` NOT_ADMISSIBLE_AS_AUTHORITATIVE with an explicit no-remediation note | **BLOCKER** | CONCUR |
| BC-4 volume semantics | BLOCKER 10/10 | Five semantics re-cited at source lines; no `volume_semantic` metadata anywhere; contract guarantee G-08 CONTRADICTED | **BLOCKER** | CONCUR |
| BC-5 canonical ≡ quarantined | BLOCKER pending lineage proof 8/10 | **Lineage probe RESOLVED the unknown — and it is worse than PASS A recorded.** `HANDOFF.md:11` pins `canonical_corpus: data/XAUUSD_M15.csv` at sha `4d73f5ce…`; the CURRENT root file is `486cf361…` (50,169 rows, ends 2026-07-06) — the pinned bytes now live at `data/mt5/XAUUSD_M15.csv` (47,275 rows, ends 2026-05-21). The current root bytes are byte-identical to `data/mt5/_rejected/XAUUSD_M15.csv` (strict-gate QUARANTINED) yet `reports/dataset_integrity/XAUUSD_M15.json` records **APPROVE** for hash `486cf361…` at the root path (default thresholds). So: a newer fetch was quarantined by the strict gate, its bytes nonetheless REPLACED the hash-pinned canonical corpus, no promotion decision is recorded anywhere, and the stale pin went unnoticed until this probe. This is failure-class FC-OHLCV-23 (stale identity pin) live in production data | **BLOCKER** (lineage proven: silent replacement post-pin; promotion decision unrecorded) | CONCUR + STRENGTHEN |
| BC-6 yfinance tz / forming bar | BLOCKER, yfinance-scoped 10/10 | Re-verified: no tz normalization in `fetch_forex_yfinance.py`; no completed-bar check in any fetcher; no verify gate for the family | **BLOCKER, scoped to yfinance + its root-crypto descendants** | CONCUR |

## 2. Contradiction adjudication (CX-001…010)

| CX | Final classification | Positive evidence (for PROVEN_NON_BLOCKER) |
|---|---|---|
| CX-OHLCV-001 | **BLOCKER** (= BC-1) | — |
| CX-OHLCV-002 | **BLOCKER** (= BC-3) | — |
| CX-OHLCV-003 | **BLOCKER** (= BC-4) | — |
| CX-OHLCV-004 | **BLOCKER** (= BC-5, mechanism now proven) | — |
| CX-OHLCV-005 same bytes approved+rejected | PROVEN_NON_BLOCKER | Mechanism POSITIVELY explained this pass: strict gate (zero-tolerance override) REJECTs what default thresholds APPROVE — same bytes, different config (`XAUUSD_M15.json` APPROVE vs `_rejected/` twin; `dataset_integrity.py:275-284` cfg_override). No reader of `_rejected/` exists (PASS-A grep). Residual risk (bytes re-entering at root) is BC-5's channel, adjudicated there |
| CX-OHLCV-006 dormant DB chain | PROVEN_NON_BLOCKER (for OHLCV closure) | **Correction to PASS A:** DB config DOES exist — `v2_multi_2026_04.json:493` `"db_url": "postgresql://localhost/tradelatest"`. However: its only consumers are the F-013-ORPHANED portfolio layer (`allocator.py:6`, `signal_pool.py`) — not the active spine; and census attributes NO corpus to DB provenance. Non-blocking for OHLCV truth; flagged as DOC_DRIFT vs the "no database" doctrine (follow-up, user-gated) |
| CX-OHLCV-007 two HTF definitions | PROVEN_NON_BLOCKER | Both are downstream aggregations of certified rows; the contract now NAMES them (`calendar_htf` vs `rolling_count_htf`) — ambiguity closed at the contract level |
| CX-OHLCV-008 L1 admits proxy trigger | PROVEN_NON_BLOCKER as data-truth | Census: 0/224 all-zero-volume corpora (executable). As a CONTRACT term it is absorbed into G-08/G-10 (CONTRADICTED → part of BC-4's blocker surface) |
| CX-OHLCV-009 26 vs 27 FC count | PROVEN_NON_BLOCKER | Doc drift only; matrix JSON is machine-authoritative. One-line prereg fix deferred to a Drift-Protocol turn (PASS B edits no existing docs) |
| CX-OHLCV-010 L3 single-callsite | PROVEN_NON_BLOCKER | Already registered (F-039, Certain); contract G-11 carries per-path `dataset_integrity_level` |

## 3. Guarantee rollup (the contract's spine)

| Status | Guarantees |
|---|---|
| PROVEN (6) | G-01 schema presence · G-02 unique/monotonic ts · G-03 value integrity · G-04 canonical ts formats · G-13 resample determinism · (G-11 scoped-PROVEN at L3-gated entries only) |
| UNPROVEN (5) | G-06 open-time labeling (acquisition families) · G-07 UTC (yfinance + descendants) · G-09 forming-bar protection · G-11 layer-wide gap policy · G-14 provenance records |
| CONTRADICTED (3) | G-05 identity binding (live counterexample: BC-5) · G-08 volume semantics · G-10 no undeclared substitution |

Handoff-required set: G-01…G-10. **Three CONTRADICTED + three UNPROVEN ⇒ the
handoff gate cannot pass.** Row-level cleanliness (G-01…G-04) is real and
preserved — the layer fails on identity, semantics, and provenance, exactly as
the PASS-A headline stated.

## 4. Closure-gate walk (Prompt-2 STEP 10 criteria)

| # | Criterion | Result |
|---|---|---|
| 1 | Every corpus inventoried or excluded with reason | **PASS** (224 artifacts; perp EXCLUDED; parquet stats-UNKNOWN declared) |
| 2 | Every active loader path identified | **PASS** (single funnel + dormant DB chain registered) |
| 3 | Every active transformation traced | **PASS** (13 T-records) |
| 4 | Timestamp/observability semantics proven per active path | **FAIL** (G-06/G-07/G-09 non-PROVEN for acquisition families) |
| 5 | Resampling semantics proven | **PASS** (T-004 static + parity harness; count-HTF divergence declared) |
| 6 | Silent substitutions absent or surfaced | **FAIL as "absent"** — surfaced instead (T-003 latent, T-006 reached canonical root undeclared → G-10 CONTRADICTED) |
| 7 | Corpus fingerprints deterministic | **PASS** (census `--check` byte-identity) |
| 8 | Contradictions resolved or classified non-blocking with evidence | **PASS as process** (all 10 classified; 4 remain BLOCKERs — which is why the verdict is BLOCKED, not a criterion violation) |
| 9 | Adversarial probes cover all applicable failure classes | **FAIL** (29/29 registered, 21/29 detectable today; 8 detector gaps — §5) |
| 10 | Output contract machine-readable and fail-closed | **PASS** (contract emitted; fail-closed consumption rule + handoff gate rule) |
| 11 | OHLCV→CandleMath handoff tested | **FAIL** (handoff gate cannot pass with non-PROVEN required guarantees) |
| 12 | No economic claim made | **PASS** |

7 PASS / 4 FAIL / 1 process-PASS ⇒ closure is not forceable. Per C1 grammar:

## 5. Measurement-trust metrics (mutation registration ≠ detection coverage)

```text
failure_classes_registered = 29
canonical_seeds_defined    = 29
detectors_implemented      = 21
clean_path_probes_green    = NOT_MEASURED
mutants_killed             = NOT_MEASURED
mutation_score             = NOT_MEASURED
```

The 8 detector-less classes (FC-OHLCV-04/05/06/08/19/20/21/24) all require the
identity/semantics binding specified by the contract — they are the SAME gap as
BC-1/BC-2/BC-4/BC-6 seen from the adversarial side. **"29/29 seeds defined" must
never be reported as E-MT-01 COMPLETE.**

## 6. Remediation prerequisites (design-level only — NOTHING remediated in this pass)

Minimal set to flip each blocker; smallest-first ordering. These are
*prerequisites*, not designs — the remediation program is a separate,
user-authorized effort.

| Blocker | Minimal flip condition |
|---|---|
| BC-1 (+G-05) | A corpus-binding manifest (logical_corpus_id → physical_path + sha256 + authority_class + source_family + transformation_chain) + a load-time admission check that verifies the hash before streaming. The census fingerprint manifest is 90% of the data; the missing piece is the binding DECISION per logical id + the enforcer |
| BC-2 (+G-06) | One executable proof per acquisition family: fetch a small window where the label convention is decidable (e.g. compare a bar fetched mid-interval vs after close; or cross-verify one instrument's bars against a second independent source with known labeling). Repository-side proof, not API documentation |
| BC-3 (+G-12) | A recorded PROVENANCE DECISION for root crypto: either re-derive root from a gated family (user choice — not prejudged here) or document acceptance of yfinance descent with declared caveats. Decision + record, then re-hash + re-bind |
| BC-4 (+G-08) | Per-corpus `volume_semantic` (+ `is_synthetic`) metadata in the binding manifest; the T-003 proxy branch must set a declared flag (and gain its first test — matrix SEED-OHLCV-19) |
| BC-5 (+G-05/G-10) | Adjudicate the XAUUSD replacement: either restore the pinned `4d73f5ce…` corpus as canonical or record a promotion decision for `486cf361…` (incl. the strict-gate REJECT rationale — the 26h holiday-gap class known from F-035); then fix the HANDOFF pin. Add the "no silent replacement of hash-pinned corpora" check to the admission layer |
| BC-6 (+G-07/G-09) | yfinance family: either independently reconstruct + fingerprint-match its artifacts with tz/forming-bar proof, or retire the family from authoritative use (it is already NOT_ADMISSIBLE_AS_AUTHORITATIVE in the contract). Add a completed-bar guard to fetchers (label + width ≤ fetch time) |

## 7. What PASS B did NOT do

No remediation; no re-pointing of canonical paths; no declaration of Binance as
authoritative; no edits to PASS-A artifacts or any pre-existing doc; no new
F-finding registration (deferred to a user-gated turn — proposed: a GOV finding
for the identity-unbound conclusion + the BC-5 event); no Phase 2; no economic
claims.

## 8. Return block

```text
PHASE1_PASS_A = EVIDENCE_FROZEN (9 artifacts, hash-pinned)
PHASE1_PASS_B = ADJUDICATED
GUARANTEES_PROVEN = 6
GUARANTEES_UNPROVEN = 5
GUARANTEES_CONTRADICTED = 3
BLOCKERS_FINAL = BC-1, BC-2[mt5|binance|yfinance], BC-3, BC-4, BC-5, BC-6[yfinance]
PROVEN_NON_BLOCKERS = CX-005, CX-006, CX-007, CX-008(data-truth), CX-009, CX-010
MUTATION_REGISTRATION = 29/29 ; DETECTION_COVERAGE = 21/29 ; MUTATION_SCORE = NOT_MEASURED
OHLCV_CLOSURE_STATUS = BLOCKED:BC-1,BC-2[mt5|binance|yfinance],BC-3,BC-4,BC-5,BC-6[yfinance]
NEXT = user-authorized remediation program design (smallest set per section 6); Phase 2 does NOT begin
```
