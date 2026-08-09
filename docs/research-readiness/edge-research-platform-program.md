# Edge Research Platform Program

> **Living program control surface** (human). Machine twin:
> [`edge-research-platform-program.json`](edge-research-platform-program.json).
> Update **both** in the same turn when status, decisions, or conversation log change.
>
> **Authority:** tracking + research planning only. Grants **no** production, promotion,
> or capital authority (CLAUDE.md §6.5 Authority Ladder).

| Field | Value |
|---|---|
| **Program ID** | `EDGE_RESEARCH_PLATFORM` |
| **Status** | `ACTIVE` |
| **Opened** | 2026-07-14 |
| **Updated** | 2026-07-16 |
| **Branch scope** | `feature/truth-registry-v2` (statements are branch-scoped) |
| **ACTIVE_VERSION at open** | `v2_multi_2026_04` |
| **Testing plan (DESIGN)** | [`edge-research-platform-testing-plan.md`](edge-research-platform-testing-plan.md) |
| **I/O map (DESIGN)** | [`edge-research-platform-io-map.md`](edge-research-platform-io-map.md) |
| **Synthetic 4h OHLCV trace** | [`erp-synthetic-4h-trace.md`](erp-synthetic-4h-trace.md) + `data/synthetic/erp_4h_m15/` |
| **Integrated research + multi-LLM design** | [`edge-research-platform-multi-llm-design.md`](edge-research-platform-multi-llm-design.md) |
| **Decision board + story authority (READ FIRST)** | [`erp-decision-board-and-story-authority.md`](erp-decision-board-and-story-authority.md) |
| **Phased design plan (ACTIVE)** | [`edge-research-platform-phased-plan.md`](edge-research-platform-phased-plan.md) |
| **Before / after full implement** | [`edge-research-platform-before-after.md`](edge-research-platform-before-after.md) |
| **Promise ladder (path to wealth language)** | [`edge-research-platform-promise-ladder.md`](edge-research-platform-promise-ladder.md) |
| **Multi-LLM HOW (initiated)** | [`edge-research-platform-mllm-how.md`](edge-research-platform-mllm-how.md) + [`multi_llm/research_lane/`](../../multi_llm/research_lane/README.md) |
| **Unknowns discussion** | **PARKED** until full implementation plan is written — *phased plan now exists; unknowns stay parked until P0 freeze if desired* |

**Read order for planning turns:** §2 Trust → **I/O map** → **multi-LLM integrated design** → **testing plan** → §4 Priority stack.  
(§12 Unknowns / §13 Assumptions: reference only — **discuss after full implementation plan**.)

---

## 1. Goal

**Primary goal**

Maximize the probability of either:

1. finding a **small number** of edges that survive costs, OOS, regime splits, and realistic execution, **or**
2. proving cleanly that the **current information set cannot produce** such edges —

**per unit of calendar time and capital risk.**

**Not goals**

- Maximize architecture elegance or model count
- Treat CRT / Gaussian / Zone / RR / BitNet / TradeNet existence as edge
- Optimize a backtest until it looks profitable
- **Trust raw backtest numbers before validation-flow review** (see §2)

**The bet**

A rigorous research system (honest costs, no lookahead, controls, OOS, demotion of weak ideas)
beats hand-tuning indicators until a ledger looks good — *without claiming a profitable strategy
already exists.*

---

## 2. Trust policy (HARD) — do not skip

### TP-BACKTEST-VALIDATION-GATE

> **Do NOT trust backtest data, ledgers, PF / expectancy / win-rate numbers, or qualification
> verdicts until the validation flow that consumed them has been reviewed and confirmed to
> match the intended implementation.**

| Default trust on any new result | `UNTRUSTED_RAW` |
|---|---|
| Severity | **HARD** — no decision, finding upgrade, or “it works” claim on unreviewed flow |

**Applies to**

- `backtest_v2` outputs and golden ledgers used as economic evidence
- Spine / research qualification results
- Opportunity-stream derived labels (F-022 contamination class)
- M4 / `forward_walk` results when used for edge claims
- Any PF, E[R], WR, or trade-count used for ranking ideas

**Required before trust**

1. Name the **exact validation path consumed** (e.g. CRT-only gate-OFF research spine vs fusion gate-ON; which exit model; cost model; label source).
2. Review that path against **intended implementation** (code + config + `ACTIVE_VERSION`).
3. Confirm no lookahead, wrong exit model, wrong cost model, or contaminated labels for the claim being made.
4. Set the work item’s `validation_flow_review` status (see tokens below) **before** treating numbers as research evidence.

**Status tokens**

| Token | Meaning |
|---|---|
| `UNTRUSTED_RAW` | Artifacts exist; validation flow not reviewed |
| `FLOW_REVIEWED` | Consumed path inspected and documented |
| `FLOW_MATCHES_INTENT` | Path matches intended implementation; numbers may be used as **research evidence only** |
| `AUTHORITY_ELIGIBLE` | Survived qualification + Authority Ladder; still not automatic production authority |

**Related repo evidence (why this rule exists)**

- F-022 — opportunity stream ≠ trade ledger; labels can lie
- F-037 — research spine often CRT-only (`BACKTEST_ENGINE_GATE=0`); fusion path differs
- F-010 — live PnL unverified
- F-041B / F-045 — contaminated or indeterminate economic labels
- F-048 — live decision path structural issues

---

## 3. Lifecycle (how we work this program)

Every work item moves through:

```text
DESIGN → IMPLEMENTATION → REVIEW → TESTING → VALIDATION
```

| Phase | Purpose | Typical exit |
|---|---|---|
| **DESIGN** | Pre-register hypothesis, population, targets, controls, kill criteria | Design freeze or owner grant |
| **IMPLEMENTATION** | Surgical code / config / data plumbing | Diff + construction protocol if code |
| **REVIEW** | Design and/or implementation vs intent; **includes validation-flow review** | Review PASS / FAIL |
| **TESTING** | Unit / integration / determinism / parity floors | Tests green (not economic truth) |
| **VALIDATION** | Frozen scientific/economic protocol | Verdict + trust token (never skip §2) |

**Rule:** `TESTING` green ≠ edge. `VALIDATION` numbers ≠ trusted evidence until §2 is satisfied.

---

## 4. Priority stack (default until owner revises)

| Rank | Workstream | Status | Phase | Why first |
|---|---|---|---|---|
| 0 | **WS-TEST-HARNESS** — H1–H3 + real-market test pyramid (Binance/MT5/Playwright) | PLANNED | DESIGN | Without harness, every later validation is chat-vulnerable; see [testing plan](edge-research-platform-testing-plan.md) |
| 0b | **WS-MLLM-RCP** — thin Multi-LLM Research Control Plane (4 artifact kinds + cycle scorecard) | PLANNED | DESIGN | Anti echo-chamber; **parallel thin protocol only** — does not jump factory (AMB-04); see [integrated design](edge-research-platform-multi-llm-design.md) |
| 1 | **WS-OUTCOME-FACTORY** — honest opportunity population + outcome factory | PLANNED | DESIGN | Contaminated labels poison everything (F-022 class) |
| 2 | **WS-OI-PATH-ABSTAIN** — OI / positioning / liquidation as incremental path + abstain evidence | PLANNED | DESIGN | OHLCV direction exhausted; OI open/deferred (Program 7 class) |
| 3 | **WS-ENGINE-DEMOTION** — incremental-value audit; demote zero-Δ engines | PLANNED | DESIGN | Existence ≠ authority |
| 4 | **WS-NEW-INFO-SEARCH** — automated search over non-dead families | BLOCKED | DESIGN | Needs clean factory |
| 5 | **WS-SHADOW-LIVE** — shadow / small capital for survivors only | BLOCKED | VALIDATION | F-010 / F-048 |

### Do not fund first

- CRT geometry / threshold archaeology  
- Session as “new alpha” (F-017)  
- Zone knobs as edge (F-036 / F-041B)  
- Same M15 OHLCV directional toys (F-019 family)  
- Carry spot-dispersion / simple harvest reopen without a new structural thesis (F-033 / F-034)  
- Wire TradeNet / BitNet because they exist (F-005 / F-004)

---

## 5. Target architecture (intent — not current proven edge)

```text
Market data
  → verified features / events
  → neutral opportunity population
  → models add evidence (not free BUY/SELL votes)
  → structured opportunity record
  → decision policy from survivors only
  → risk → execution
  → honest outcome measurement
  → research feedback / demotion
```

Models contribute **different evidence** (structure, region, statistical, payoff, sequence).  
Authority is earned only by **measured incremental value** after costs and honest outcomes.

---

## 6. Work items

> Append rows; do not delete. Close with `CLOSED` / `KILLED` + reason.

| ID | Workstream | Title | Phase | Status | validation_flow_review | Notes |
|---|---|---|---|---|---|---|
| WI-001 | WS-OUTCOME-FACTORY | Findings-Revalidation Gate (Epoch E4) — P2.0 | DESIGN | **FROZEN** 2026-07-16 | UNTRUSTED_RAW | Prereg [findings-revalidation-gate-e4-preregistration.md](findings-revalidation-gate-e4-preregistration.md) frozen (protocol_hash `sha256:454b2351…`). RVG-U1 (E3 baselines on disk) + RVG-U2 (Class B feature-independent) resolved. Next: grant Implement RVG-1. Grants no run/production authority. |
| WI-002 | WS-TEST-HARNESS | Market-story ontology + multi-story golden library (P1.1/P1.2 slice) | TESTING | **IMPLEMENTED** 2026-07-16 | FLOW_MATCHES_INTENT | Ontology `configs/research/market_story_ontology.yaml` (descriptive-only) + engine `src/research/synthetic/` + driver `scripts/research/story_library_build.py`. 12 stories / 4 active families / 6-layer binding; 12/12 pass; anchor reproduces erp_4h_m15; 38 golden tests + full research suite (318) green. Substrate (9 CRT states, 38-dim vector, market_ontology.yaml) UNCHANGED. Pending owner Decision-Board note (D-2N). No edge claim. |
| WI-003 | WS-TEST-HARNESS | T0 anti-hallucination scaffold (markers + run_manifest + AH/VP + green CI) | TESTING | **IMPLEMENTED** 2026-07-16 | FLOW_MATCHES_INTENT | 10 pytest markers (additive) + `src/utils/run_manifest.py` (fail-closed) + `src/utils/validation_contract.py` (H1/H2/H3 guards) + `tests/harness/` AH-01..05 / VP-01..05 (18 tests). Story driver wired as first real `run_manifest` producer (AH-05 golden). `.github/workflows/erp-test-harness.yml` = path-scoped green subset (56 tests); `governance.yml` untouched. Next: T1 Binance public. No network/broker/UI; no runtime/promotion/capital authority. |
| WI-007 | WS-OUTCOME-FACTORY | Trace k-NN similarity graph (descriptive) + determinism-test fix | TESTING | **IMPLEMENTED** 2026-07-16 | FLOW_MATCHES_INTENT | `trace_knn.py`: sklearn NearestNeighbors (cosine) over `geometry.npz` (same morphology space), reusing `ReplaySimilarityIndex.aggregate_top_k_stats`. k=10/23,428: neighbourhood same-outcome concordance **0.5498 vs random baseline 0.5459**; TP-rate **0.3149 vs global 0.3176** → **static entry-state OHLCV morphology** gives no LOCAL outcome structure on this corpus (finest-resolution **F-023**; scoped null — other information classes UNMEASURED, see [`erp-information-class-boundary.md`](erp-information-class-boundary.md)). Neighbourhoods are NOT edges (§6.5). Also replaced the flaky ~10-min determinism subprocess test with a fast in-process kernel-equivalence check. `test_trace_knn.py` green; CI subset unchanged (58); corpus `FROZEN_CANDIDATE`; `ACTIVE_VERSION` unchanged. |
| WI-006 | WS-OUTCOME-FACTORY | Trace Geometry (descriptive clustering) + determinism-gated parallel build | TESTING | **IMPLEMENTED** 2026-07-16 | FLOW_MATCHES_INTENT | `trace_geometry.py`: StandardScaler + KMeans (k by silhouette sweep) on a **dimensionless morphology** feature set (15 price-level features excluded). k=4; clusters = bearish / mild-bullish / strong-momentum / **liquidity-sweep** (z=+3.75) — but outcomes **~uniform** (SL 66–68% / TP 31–33%) across all → descriptive re-confirmation of **F-023** (morphology = shape, not expectancy; no cluster is a signal). `build_trace_corpus.py --jobs` parallel forward_walk **proven byte-identical** to sequential (`--jobs 1` == `--jobs 4`, 23,446 traces). Clusters are NOT edges (§6.5); no GPU; corpus `FROZEN_CANDIDATE`; `ACTIVE_VERSION` unchanged. LLM interpretation deferred. |
| WI-005 | WS-OUTCOME-FACTORY | Mathematical Trace Corpus (descriptive) from toy+spine executions | TESTING | **IMPLEMENTED** 2026-07-16 | FLOW_MATCHES_INTENT | Reframe: "why do these fail mathematically?" not discovery. `build_trace_corpus.py` joins the 38 canonical **PIT** features at entry (causal FeaturePipeline, keyed by stream `_pos`) to the forward outcome; `analyze_trace_corpus.py` = per-feature distributions by outcome/timing/MFE + family comparison. **23,447 traces** (expansion 8063 / mean_reversion 15383 / spine 1); SL_HIT 15640 / TP_HIT 7444 / TIMEOUT 363. Test 3 green (slow). DESCRIPTIVE / non-promotable — information not authority (§6.5); no edge claim. Corpus `FROZEN_CANDIDATE`; `ACTIVE_VERSION` unchanged. LLM layer deferred. |
| WI-004 | WS-TEST-HARNESS | T1 (offline) — XAUUSD local-corpus certification + thin non-promotable research pass | TESTING | **IMPLEMENTED** 2026-07-16 | FLOW_MATCHES_INTENT | Owner redirect: local OHLCV, XAUUSD, certify+research. Canonical = `data/mt5/XAUUSD_M15.csv` (frozen candidate, sha256 `4d73f5ce…`) via `guard_xauusd_csv_path` (NOT the root file). `certify_xauusd_corpus.py` (guard→verify→`validate_dataset`=**WARN**→schema→manifest `network=none`); `qualify_xauusd.py` (M4 pass, families **toy** {expansion_breakout REJECT n=8063, mean_reversion REJECT n=15383} + **spine** {v2_multi_2026_04 INSUFFICIENT n=1, E=−1.69R} — F-035/F-029-consistent; lens recorded truthfully `fusion_gate_on`; non-promotable). Tests: certify (fast, in CI=58) + toy/spine research smokes (slow, opt-in). Corpus stays `FROZEN_CANDIDATE`; `ACTIVE_VERSION` unchanged; no promotion/edge claim; offline. Also fixed CI dep install (pandas/pyyaml/numpy). |

**Work item template (copy when opening)**

```text
ID: WI-00N
Workstream: WS-...
Title:
Phase: DESIGN | IMPLEMENTATION | REVIEW | TESTING | VALIDATION
Status: PLANNED | IN_PROGRESS | BLOCKED | REVIEW | DONE | KILLED
validation_flow_review: UNTRUSTED_RAW | FLOW_REVIEWED | FLOW_MATCHES_INTENT | AUTHORITY_ELIGIBLE | N/A
Validation path consumed: (name entrypoint, gate flags, exit model, costs, labels)
Intent match evidence: (file:line / config keys / ACTIVE_VERSION)
Owner grant: yes/no
```

---

## 7. Conversation log

### CL-001 — 2026-07-14 — Trader-friend project narrative

- Project = **research/verification platform**, not a proven money printer.
- Bet = process quality vs manual indicator optimization.
- Risk = years of governance/features without economically valuable information.
- Action proposed: show trader the honest pitch; collect 5–10 objections; classify  
  `already-falsified | unresolved assumption | testable hypothesis`.

### CL-002 — 2026-07-14 — What to test first + goal

- Goal locked as §1.
- First scientific priority: outcome factory, then OI/path/abstain, parallel demotion.
- Explicit non-reopen of killed OHLCV directional families.

### CL-003 — 2026-07-14 — Program tracker created

- Owner asked to track this conversation in MD + JSON for  
  **design → implementation → review → testing → validation**.
- **Trust rule formalized:** do not trust backtest data until validation flow consumed is
  reviewed and matches intended implementation (§2 / `TP-BACKTEST-VALIDATION-GATE`).
- These two files are the continue-from surface for this program.

### CL-004 — 2026-07-14 — Unknowns, assumptions, tool-hallucination policy

- Owner asked to define unknowns in the plan, explain assumptions, and handle
  **hallucinated tool output**.
- Added §12 Unknowns, §13 Assumptions, §14 Tool-output hallucination policy
  (and matching JSON blocks). No new market claim; no code.

### CL-005 — 2026-07-14 — Strong testing plan (H1–H3 + real market outlets)

- Owner asked for a strong testing plan using real market outputs and frameworks
  (Playwright, Binance API, MT5, etc.) aligned to H1/H2/H3.
- Added DESIGN doc [`edge-research-platform-testing-plan.md`](edge-research-platform-testing-plan.md):
  layers L0–L8, pytest markers, run_manifest anti-hallucination, BN/MT5/Playwright packs,
  validation-path identity (VP-*), phases T0–T5. **Implementation not started.**
- Workstream: **WS-TEST-HARNESS** registered (PLANNED / DESIGN).

### CL-006 — 2026-07-14 — I/O map; unknowns parked

- Owner: save unknowns; discuss after full implementation plan; deliver **each topic input and output**
  per plan + codebase.
- Added [`edge-research-platform-io-map.md`](edge-research-platform-io-map.md).
- §12 unknowns marked PARKED (inventory only).

### CL-007 — 2026-07-14 — Synthetic 4h OHLCV intentional pack + trace

- Owner: 4h synthetic OHLCV (not random); trace through topics; intended vs produced.
- Generator: `scripts/research/erp_synth_4h_trace.py`
- Artifacts: `data/synthetic/erp_4h_m15/` (CSV, intended_spec, produced_compare, TRACE)
- Doc: [`erp-synthetic-4h-trace.md`](erp-synthetic-4h-trace.md)
- CRITICAL_COMPARE=PASS (TP_HIT, rr=2.0, tp_offset=4, sweep low, schema)

### CL-008 — 2026-07-14 — Engines topic designed (intended feature contract + real engines)

- Owner: design engines scores as per intended (not NOT_RUN / not invented).
- Added `engines_feature_contract` + `engines_intended` from story geometry.
- Produced via `crt_engine.compute`, `HeuristicGaussianEngine`, soft zone, `RREngine`.
- Scores: CRT 0.8227 · Gaussian 0.9432 · Zone 0.882419 · RR 0.6429 — **all match**.
- Fusion still NOT_RUN (isolation).

### CL-018 — 2026-07-16 — P1 slice: story ontology + multi-story golden library + six-layer harness

- Owner-approved plan slice of P1 (P1.1 golden + P1.2 story externalization).
- Built a **descriptive-only** semantic story ontology (`configs/research/market_story_ontology.yaml`):
  8 layers, 12 families (4 active), 38 market states — mapping **onto** the UNCHANGED 9 CRT states + 38
  canonical features.
- Generalized the single `erp_synth` pack into a reusable engine (`src/research/synthetic/`) + **12
  deterministic stories** across 4 families; driver `scripts/research/story_library_build.py`.
- Harness validates **six layers per story** (family / market-states / CRT-path / feature-signature /
  engine-signature / outcome). 12/12 pass; anchor reproduces `erp_4h_m15`; outcomes cover
  TP_HIT / SL_HIT / TIMEOUT.
- Corrected 3 owner drift feature names → canonical (`disp_strength`, `ema_fast/slow/spread`,
  `volatility_ratio/regime`); a test mechanically forbids `ema_long`/`displacement_strength`/`volatility`.
- **D-23 preserved** (geometry in CODE). Semantic ontology is a **new descriptive authority** —
  **PENDING owner Decision-Board note (proposed D-2N)** before it is a locked decision. No runtime,
  fusion, or promotion authority (§6.5). Full P1 (markers/run_manifest/AH-VP) still PLANNED.

### CL-019 — 2026-07-16 — P1 / T0: anti-hallucination test harness

- Implemented testing-plan **T0** (WI-003): the H1/H2/H3 guards as pure-CI tests.
- **Markers** (10, additive — no `--strict-markers`) in `pyproject.toml`.
- **`src/utils/run_manifest.py`** — fail-closed provenance manifest (build/write/read/hash); a claim
  without provenance cannot be constructed (H1). **`src/utils/validation_contract.py`** —
  `require_manifest` (H1), `assert_summary_matches_manifest` + `summary_from_assertions` (H2),
  `validate_manifest_against_intent` (H3).
- **`tests/harness/`** — AH-01..05 + VP-01..05 + manifest round-trip (18 tests). **AH-05 is a real
  golden**: it subprocess-invokes `scripts/research/story_library_build.py`, now the **first real
  `run_manifest` producer** (`data/synthetic/stories/run_manifest.json` + `RUN_SHA256.txt`).
- **CI** `.github/workflows/erp-test-harness.yml` runs a **path-scoped green subset** (harness + story
  goldens, 56 tests) — NOT the full suite (intentionally red, F-018). `governance.yml` untouched.
- Helper home = `src/utils/` (reusable), not `tests/support/` per the doc sketch. Next real market-out
  = **T1 Binance public**; retro-marking the existing suite deferred to Phase B. No runtime/promotion/
  capital authority.

### CL-020 — 2026-07-16 — T1 (offline): XAUUSD local-corpus certify + thin research pass

- Owner redirected T1 from live Binance to **local OHLCV, XAUUSD, both certify + research**, and
  **corrected the canonical path**: XAUUSD M15 is the governance-frozen candidate
  **`data/mt5/XAUUSD_M15.csv`** (`guard_xauusd_csv_path` + [`CORPUS_AUTHORITY.md`](CORPUS_AUTHORITY.md)),
  NOT the root `data/XAUUSD_M15.csv`.
- **Certify** `scripts/research/certify_xauusd_corpus.py`: guard → `verify_phase1_frozen_candidate`
  (sha256 `4d73f5ce…`, 47,275 rows) → `validate_dataset` = **WARN** (honest — gold's residual gaps) →
  schema → `run_manifest` (`network=none`, `data_source=local_csv_mt5`). Corpus stays `FROZEN_CANDIDATE`.
- **Research** `scripts/research/qualify_xauusd.py`: thin **non-promotable** M4 toy pass
  (`HypothesisRunner` + `forward_walk(intrabar_fixed)`) → expansion_breakout / mean_reversion both
  **REJECT** (PF≈0.18–0.20, E≈−1.1R) — consistent with **F-035**'s XAUUSD/FX entry-info null.
  `UNTRUSTED_RAW`; no edge claim.
- Tests: certify (fast, in the CI subset → **58 total**) + research smoke (`slow`, opt-in); both
  SKIP-if-corpus-absent. Fixed the T0 CI dep gap (install pandas/pyyaml/numpy — the project declares no
  base deps). Offline; `governance.yml` untouched.

### CL-021 — 2026-07-16 — T1 (cont.): SPINE-family XAUUSD pass

- Extended `qualify_xauusd.py` with the **production decision spine** (`v2_multi_2026_04`) as the
  `spine` hypothesis through the same M4 gate on the certified frozen candidate (new
  `configs/research/research_config_spine_xauusd.json`; `RESEARCH_SPINE_CONFIG` pin). Report is now
  `families: {toy, spine}`.
- **Governance held automatically**: the spine source globs the root path, but `CandleLoader`/
  `BacktestRunner` guard-rewrite it to `data/mt5/XAUUSD_M15.csv`; `PROD_VERSION` is set locally and
  **restored** (`ACTIVE_VERSION` untouched).
- **Result**: spine **n=1, PF=0.0, E=−1.69R → INSUFFICIENT** (throughput-starved on gold, F-029/F-035).
  Lens recorded **truthfully as `fusion_gate_on`** (the runtime `.env` has the gate on) — NOT misstated
  as F-037 CRT-only. Non-promotable; no edge claim.
- Tests: updated toy smoke (families shape) + new spine smoke (`slow`, `collect('spine',…)`-level to
  avoid the 47k control sweep). CI green subset unchanged (58).

### CL-022 — 2026-07-16 — Mathematical Trace Corpus (descriptive laboratory)

- Owner reframe: **park throughput**; since all verdicts are null there's **no positive target**, so
  instead of "find profitable mathematics" ask *"what mathematical structures repeatedly FAIL?"*.
- `build_trace_corpus.py` joins the 38 canonical **PIT** features at the entry bar (causal
  `FeaturePipeline`) to the forward outcome per execution; `analyze_trace_corpus.py` describes the
  distributions (overall + by outcome / timing / MFE segments + family comparison).
- **23,447 traces** on the certified XAUUSD frozen candidate (expansion 8063 / mean_reversion 15383 /
  spine 1); outcomes **SL_HIT 15640 / TP_HIT 7444 / TIMEOUT 363**.
- **GOTCHA caught**: `FeaturePipeline` drops a 78-row warmup head + resets the index, so features are
  keyed by a carried **stream position (`_pos`)**, not `iloc` — a PIT-alignment test proves the join is
  index-correct.
- **DESCRIPTIVE / non-promotable**: information not authority (§6.5); no edge/profit claim; describes
  failure structure only. Corpus stays `FROZEN_CANDIDATE`; `ACTIVE_VERSION` unchanged; CI subset
  unchanged (58). LLM hypothesis generation deferred.

### CL-023 — 2026-07-16 — Trace Geometry (organize by shape) + parallel build

- Owner milestone: organize the 23k-trace population into mathematically-similar **regions** before any
  LLM interpretation. `trace_geometry.py` = `StandardScaler + KMeans` (k by subsampled silhouette over
  {4,6,8,10,12}) → cluster library (size / family / centroid / outcome-distribution / feature-signature /
  representatives), extending F-023's `cluster_morphology`.
- Clustered on a **dimensionless morphology** feature set (excluded 15 absolute price-level features) —
  otherwise gold's 2400→4500 trajectory splits clusters on price regime, not shape.
- **Result**: k=4 → bearish-structure / mild-bullish / strong-momentum / a distinct **liquidity-sweep**
  region (z=+3.75), but outcome distributions are **~uniform** (SL 66–68% / TP 31–33%) across all → a
  clean descriptive **re-confirmation of F-023** (morphology = shape, not expectancy; no cluster is a signal).
- Parallelized `build_trace_corpus.py` (`--jobs`: parallel `forward_walk`; `--jobs 1` = the proven
  `run_instrument` reference), **proven byte-identical** (`--jobs 1` == `--jobs 4`, 23,446 traces) — the
  F-series determinism is preserved. No GPU (research ETL). Clusters are NOT edges (§6.5); LLM
  interpretation deferred.

### CL-024 — 2026-07-16 — Trace k-NN similarity graph (no LOCAL outcome structure)

- Built `trace_knn.py` — per-trace k-NN graph in the **same standardized morphology space** as the
  clusters (reuses `geometry.npz` `Xs` + `cluster_assignments` + `ReplaySimilarityIndex.aggregate_top_k_stats`).
  Batch graph via `sklearn.NearestNeighbors` (the replay index's per-query scan / a 2 GB cosine matrix
  don't scale to 23k²).
- **k=10, cosine**: neighbourhood same-outcome concordance **0.5498 vs random baseline 0.5459**;
  neighbourhood TP-rate **0.3149 vs global 0.3176**. A trace's 10 nearest morphological neighbours share
  its outcome at the **random rate** → the sharpest, finest-resolution re-confirmation of **F-023**.
  **SCOPE (E-001 correction, CL-025):** the measured null is *"static entry-state OHLCV morphology did
  not discriminate outcomes on this corpus"* — NOT a claim about UNMEASURED information classes
  (temporal / HTF / execution / order-flow / macro / alt-data). See
  [`erp-information-class-boundary.md`](erp-information-class-boundary.md) (RC-005..010 OPEN).
  Descriptive; neighbourhoods are NOT edges (§6.5).
- Fixed the flaky determinism test (a ~10-min full-corpus subprocess that timed out) → a fast in-process
  **kernel-equivalence** check (`_fw_worker` == `forward_walk` on sampled real signals); full byte-identity
  kept as a documented manual command. LLM interpretation deferred.

### CL-025 — 2026-07-16 — E-001 scope-correction + Information-Class Boundary registry

- **Caught me overclaiming; I owe you a correction.** "shape carries no outcome information at any
  resolution" over-generalized the null → `CORRECTED` to: *static entry-state morphology derived from
  OHLCV did not discriminate outcomes on the XAUUSD corpus.* "Not measured" ≠ "uninformative."
- Registered the boundary + the six distinct **open information classes** (temporal / HTF / execution /
  order flow / macro / alt-data) as a durable twin
  [`erp-information-class-boundary.md`](erp-information-class-boundary.md) (refines **U-008**, phased-plan
  **P4**), each an OPEN question opened one at a time on grant (PL-0).
- Fixed the source (this twin CL-024/WI-007, memory, `trace_knn.py` + KNN.md, SESSION LOG). **The registry
  has since evolved to v1.1** (IC-001 COMPLETE; IC-002/RC-005 MEASURED; IC-003 ARCHIVED; IC-003B NEXT) —
  the registry twin is authoritative. **Did NOT** seed `research_cycle_ledger.jsonl` with `PROPOSED`
  RC-005..010 stubs (would be stale/contradictory vs the v1.1 MEASURED/ARCHIVED states; §6.2).

### CL-026 — 2026-07-17 — IC-003B sequence geometry: resume + validation + robustness → `IC003B_PARTIAL`

- Resumed the parallel-session (Grok) **frozen** IC-003B run from its checkpoint (executor, not designer).
  **Validated** the four completed units (`S_N4·T_N4·C_N4·S_N16`) against prereg+code and **independently
  re-derived** the gates from raw data — G2 silhouette reproduced **exactly** (0.0561), G1 to ~0.003,
  n_is/n_oos exact, floors 7/7. Trust = `FLOW_MATCHES_INTENT` (completed units).
- **Verdict locked to `IC003B_PARTIAL`**: Arm S OK at N=4 (marginal: G1 0.8216, G2 0.0561) but FAIL at
  N=16 (G1 0.8863>0.85) → one-N only; Arm T FAIL at N=4 (DTW sil 0.019<0.05) → not both-N. G1 stays 0.85
  (no gate move); `LIBRARY_OK`/`PARTIAL` grant **no** authority (§6.5).
- **Robustness (8-seed, read-only):** verdicts are **seed-robust** (S_N4 OK 8/8, S_N16 FAIL 8/8 → PARTIAL
  is stable, not a seed artifact) but the library **structure is under-determined** (k\* seed-unstable) and
  **near-noise** (G1 0.80–0.90 → 10–20% variance captured; silhouette just above a permissive 0.05 floor).
  Arm C `DISCRETE_HINT` is a **dimensionality artifact** (PC-space silhouette 0.54 on 4 PCs explaining only
  32% variance; full-space 0.056) → weak continuum, not clean prototypes.
- Run reached **RUN_COMPLETE** (checkpoint 2026-07-17T06:49Z, all 9 units; `report.json` label
  `IC003B_PARTIAL`) — confirming the verdict I'd independently locked from the completed primary units,
  and adding Arm T N=16 FAIL + N=8 diagnostics FAIL.
- Doc-sync only (registry v1.2 IC-003B `MEASURED_PARTIAL`); no code/config/gate/`ACTIVE_VERSION` change;
  corpus stays FROZEN_CANDIDATE. Consistent with archived IC-003 + F-019…F-041 → stop chasing a shape
  library from path summaries; `discipline.next` → **owner grant** picks the next class (P4).

---

## 8. Open questions

1. Trader friend’s strongest 5–10 objections (pending).
2. Is OI history acquisition feasible for Program-7-class tests?
3. Is a non-spot instrument available if vol-info needs long-vol expression (F-040)?
4. Owner authorize **WS-OUTCOME-FACTORY** design package next?
5. Which concrete code paths + scripts constitute the “intended” outcome factory for WS-OUTCOME-FACTORY? (U-002)
6. Who performs independent review of validation-flow matches (owner / second model / checklist only)?
7. Nightly runner: Windows+MT5 vs Linux CI public-only? (testing plan §12)
8. Owner authorize **T0 scaffold** (markers + run_manifest + AH/VP fixtures) implement?

---

## 9. Next actions

| ID | Action | Status |
|---|---|---|
| NA-001 | Treat this MD+JSON pair as the program control surface | DONE |
| NA-002 | Draft WS-OUTCOME-FACTORY design (population, re-derive, trust checklist) — design only unless owner grants implement | PENDING |
| NA-003 | Ingest trader objections when available; classify each | PENDING |
| NA-004 | Keep §12–§14 current whenever a workstream design freezes | PENDING |
| NA-005 | Testing plan DESIGN published; await owner grant for Phase T0 implement | PENDING |
| NA-006 | I/O map published; unknowns parked until full implementation plan | DONE |
| NA-007 | Write **full implementation plan** (work packages citing I/O map rows) | DONE → see phased plan |
| NA-008 | Owner freeze P0 + grant Implement P1 (default next) | PENDING |
| NA-009 | Grant **Implement RVG-1** (epoch-pinning harness), then Run RVG Class A/B/C (WI-001) | PENDING |

---

## 10. How to continue (for any session / model)

1. Read this file + the JSON twin (especially §12–§14).
2. Run ORIENT_RUNTIME (`ACTIVE_VERSION`) before any config/runtime claim.
3. Do not promote backtest numbers past `UNTRUSTED_RAW` without §2.
4. Treat LLM prose and un-audited tool summaries as **non-evidence** until §14 checks pass.
5. Append conversation log + update JSON `conversation_log` / `next_actions` same turn.
6. Open work items under §6; never skip DESIGN for economic claims.
7. Code changes still go through construction protocol + SESSION LOG (`assistant_project.md`).

---

## 11. Evidence anchors (thin)

Full text in [`docs/current-findings.md`](../current-findings.md):  
F-001, F-005, F-010, F-019, F-022, F-025, F-036, F-037, F-038, F-040, F-048.

> **`PROVISIONAL (pending E4)` — 2026-07-16.** The economic anchors (F-019 family, F-025, F-036) were
> computed before the F-051 (centered-swing PIT-leak) + F-054 (feature-DAG re-cert) feature-layer
> fixes; last revalidation E3 (2026-06-27) predates both. Trust status pending the **Findings-
> Revalidation Gate (E4)** — [`findings-revalidation-gate-e4-preregistration.md`](findings-revalidation-gate-e4-preregistration.md)
> (frozen, WI-001). RVG-U2 narrowed the risk to Class C (morphology/zone/RR/gaussian); the toy arms
> are feature-pipeline-independent (expected byte-identical).

---

## 12. Unknowns (plan-level)

> **PARKED FOR DISCUSSION:** Owner directive 2026-07-14 — **do not workshop unknowns now**;
> revisit **after the full implementation plan** is complete. List retained as inventory only.
>
> **Unknown** = something the plan needs but we do **not** currently know with evidence.
> Unknowns are not bugs; leaving them unlisted is. Status: `OPEN` | `NARROWED` | `RESOLVED` | `ACCEPTED_RISK`.

### 12.1 Economic / scientific unknowns

| ID | Unknown | Why it blocks or shapes the plan | Status | How it gets resolved |
|---|---|---|---|---|
| **U-001** | Does **any** durable edge exist in reachable data after costs and realistic execution? | Core outcome of the whole program; not assumed true | OPEN | Survive Stage-3 validation under §2, or multi-axis clean null |
| **U-002** | What is the **canonical honest opportunity + outcome** definition for this program? | WS-OUTCOME-FACTORY has no frozen population/label contract yet | OPEN | DESIGN freeze: seed events, join keys, `forward_walk` params, cost model |
| **U-003** | Are opportunity-stream labels (F-022 class) still contaminating any path we might reuse? | Determines how much of existing JSONL is unusable | OPEN | Census of label sources + re-derive sample vs stream |
| **U-004** | Can **OI / positioning / liquidations** be acquired at history depth and PIT quality sufficient for incremental tests? | WS-OI-PATH-ABSTAIN may be data-blocked (Program 7 prior) | OPEN | Data acquisition spike + coverage/PIT audit |
| **U-005** | If vol/path info is real but not spot-expressible (F-040 class), do we have **any instrument/payoff** that can express it? | Else vol-info may stay research-only forever | OPEN | Owner: options/perp/vol product scope or accept abstain-only consumer |
| **U-006** | Will **incremental** model value (Δ over OHLCV baseline) ever clear costs, or only Level-1 information? | Demotion vs promotion of engines | OPEN | WS-ENGINE-DEMOTION protocol after factory exists |
| **U-007** | Can the **live path** ever admit and measure trades as research intends (F-010 / F-048 class)? | Shadow/live step may be structurally blocked | OPEN | Structural review of DecisionEngine / planner / risk gate before capital |
| **U-008** | Is the binding constraint **missing information**, **wrong execution model**, or **efficient markets at our horizon**? | Changes whether to buy data vs redesign payoff vs stop | OPEN | Sequence of nulls + one new-info family; do not decide early |

### 12.2 Engineering / measurement unknowns

| ID | Unknown | Why it matters | Status | How it gets resolved |
|---|---|---|---|---|
| **U-009** | Exact **validation path map**: which scripts, flags (`BACKTEST_ENGINE_GATE`, fusion on/off), exit models, and cost models each workstream will consume | §2 trust requires naming the path; not yet frozen per workstream | OPEN | Per-WI “validation path consumed” field at DESIGN freeze |
| **U-010** | Parity between **research spine** and **live-equivalent** measurement for any claim we care about | F-037: CRT-only research ≠ full fusion live | OPEN | Explicit dual-lens policy or single declared lens per claim |
| **U-011** | Completeness of **feature/formula identity** for any feature used in new tests (PIT, registry, GD residual) | Wrong inputs → false edges or false nulls | OPEN | Only consume certified/promoted or explicitly scoped experimental features |
| **U-012** | Multiplicity / repeated-experiment debt when many hypotheses share the same opportunity set | False discovery risk | OPEN | Pre-registration + family-wise controls in DESIGN |
| **U-013** | Owner review bandwidth and **who signs** `FLOW_MATCHES_INTENT` | Trust tokens without an owner are theater | OPEN | Owner names reviewer role |

### 12.3 Process / external unknowns

| ID | Unknown | Why it matters | Status | How it gets resolved |
|---|---|---|---|---|
| **U-014** | Trader-friend objections (content unknown) | May reorder priority stack or kill assumptions | OPEN | Collect verbatim; classify |
| **U-015** | Time/capital budget for infrastructure vs discovery | Failure mode = perfect lab, no alpha | OPEN | Owner budget rule (e.g. max design weeks before new-info RUN) |
| **U-016** | Whether LLM agents will **accelerate falsification** more than they inject false claims | §14 risk | OPEN | Hallucination policy + mechanical floors; measure correction rate |

### 12.4 Explicitly *not* unknown (do not re-open as mystery)

These are **known nulls / constraints under their stated scopes** (see findings). Reopening requires new ontology/data/domain, not hope:

> **`PROVISIONAL (pending E4)` — 2026-07-16:** these nulls were established pre-F-051/F-054; they hold
> as *current* truth only after the Findings-Revalidation Gate (E4, WI-001) confirms them. RVG-U2:
> the toy arms are feature-pipeline-independent (expected to survive); Class C is the real check.

- Global M15 OHLCV directional toys failing M4-style gates (F-019 family, scoped)
- Session-as-improvable lever under tested conditions (F-017)
- Zone knob ΔG001 ≡ 0 under tested conditions (F-036)
- Carry signal / simple harvest as tested (F-033 / F-034)
- TradeNet unwired / BitNet inert on active patch (F-005 / F-004)

---

## 13. Assumptions (plan-level)

> **Assumption** = a belief the plan relies on that is **not fully proven**.
> Each must be: stated, classed, and either tested, replaced, or accepted as risk.
> Class: `STRUCTURAL` (how the lab works) · `ECONOMIC` (markets) · `OPERATIONAL` (how we work) · `DATA`.

| ID | Assumption | Class | Confidence | If false, what breaks | Disposition |
|---|---|---|---|---|---|
| **A-001** | A rigorous research process **raises** P(find or cleanly reject edge) vs unaudited backtest-fitting | ECONOMIC / OPERATIONAL | Likely | Program ROI thesis fails; still may retain hygiene value | **Working thesis** — not proven; measure by time-to-kill bad ideas |
| **A-002** | Honest opportunity + outcome factory is **buildable** from existing stack (`forward_walk`, qualification, loaders) without a full rewrite | STRUCTURAL | Likely | WS-1 balloons; plan must shrink scope | Test in DESIGN spike; stop if scope explodes |
| **A-003** | Contaminated / stream labels are a **first-order** risk for any learning or engine retrain | STRUCTURAL | Certain *(mechanism documented; extent of live reuse still U-003)* | Wasted if we only ever use clean re-derive and never touch stream labels | Keep factory first |
| **A-004** | **New information families** (OI/positioning/etc.) are higher EV than more OHLCV directional geometry | ECONOMIC | Likely *(prior from F-019…F-040 arc)* | Priority stack wrong; still need factory | Reorder only with evidence or strong trader objection |
| **A-005** | Path / abstain / P(hit TP before SL) targets are more decision-relevant than raw up/down after prior nulls | ECONOMIC | Possible–Likely | Wrong targets; change prediction objects | Freeze targets in WS design |
| **A-006** | Models should earn **incremental** authority only; presence in code grants none | STRUCTURAL | Certain *(repo doctrine §6.5)* | Reverts to “sophisticated system = edge” fallacy | Enforce demotion workstream |
| **A-007** | Research default CRT-only spine (F-037 class) is an **intended isolation lens**, not automatically the live decision lens | STRUCTURAL | Certain for mechanism; intent user-classified historically | Claims mislabeled as “full system” | Every claim names lens |
| **A-008** | 12 bps (or declared cost) is an acceptable **research cost prior** for crypto majors qualification | DATA / ECONOMIC | Possible | Cost-dominated nulls or false promotes | Sensitivity only after Stage-1 info; not first knob |
| **A-009** | Feature/formula governance reduces false results enough to justify sequencing integrity before discovery | OPERATIONAL | Likely | Over-invest in lab; under-invest in info | Cap integrity work; don’t block all discovery forever |
| **A-010** | Owner will not risk meaningful capital until shadow + flow review | OPERATIONAL | Likely *(stated intent)* | Live loss / unmeasured path | Hard gate on WS-SHADOW-LIVE |
| **A-011** | LLM/tool outputs are **advisory** and can be wrong even when fluent | OPERATIONAL | Certain | False findings re-propagate (E-001 class) | §14 policy |
| **A-012** | “Kill failed hypotheses and keep infrastructure” is preferable to forcing models into production | ECONOMIC | Likely | Capital and reputation risk | Explicit non-goal: force CRT profitable |

**Assumption hygiene rules**

1. New workstream DESIGN must list which A-ids it depends on.
2. Do not silently upgrade `Possible` → `Certain` without artifact evidence.
3. If an assumption is load-bearing and untested, the work item stays DESIGN or ACCEPTED_RISK with owner sign-off.

---

## 14. Tool-output hallucination policy

### 14.1 What “hallucinated tool output” means here

Three failure modes (all in scope):

| Mode | Definition | Example |
|---|---|---|
| **H1 — LLM invents a tool result** | Model states numbers, paths, or “pytest green” **without** a real tool return in-session | “BNBUSDT PF=1.4” with no run |
| **H2 — LLM misreads a real tool result** | Tool returned truth; model **wrongly summarizes** or swaps instruments/flags | Gate-OFF ledger described as fusion gate-ON |
| **H3 — Tool/script output is real but mis-specified** | Command ran; **wrong flow / labels / config** so the artifact is not the intended experiment | Valid JSON from contaminated opportunity labels (F-022 class) |

§2 primarily catches **H3**. §14 catches **H1–H2** and forces H3 into explicit review.

### 14.2 Default trust for agent/tool claims

| Source | Default | May become evidence only if |
|---|---|---|
| LLM chat prose | **NON_EVIDENCE** | N/A (never sole basis for findings) |
| LLM “remembered” past run | **NON_EVIDENCE** | Re-run or open on-disk artifact + hash |
| Shell / pytest / script stdout in-session | **UNTRUSTED_RAW** | Path reviewed (§2) + summary checked against artifact |
| On-disk JSON/JSONL under `results/` | **UNTRUSTED_RAW** | Same + provenance (command, config, version) recorded |
| Finding already in `docs/current-findings.md` | **RESEARCH_RECORD** | Still scope-bound; not production authority |
| `ACTIVE_VERSION` + loaded config | **RUNTIME_TIER0** | Fail-fast if mismatch |

### 14.3 Mandatory anti-hallucination checks (before using a number)

1. **Provenance:** command (or script entrypoint), cwd, key flags, `ACTIVE_VERSION`, instrument, date.
2. **Artifact:** path to file on disk when claim matters beyond chat; prefer hash or byte size.
3. **Flow name:** which validation lens (CRT-only vs fusion; exit model; cost; label source).
4. **Intent match:** does that flow match the **intended** implementation for this work item? (§2)
5. **No silent fill:** if tool failed, timed out, or returned empty — say so; **do not invent** success.
6. **UNKNOWN tag:** if unsure, write `UNKNOWN:` / leave status OPEN — never invent a PF/E/path.
7. **Correction rule:** if a false claim was written into MD/JSON/findings, fix the **source** same turn (E-001 / §6.2).

### 14.4 Phrases that are automatic red flags

Treat as **H1-suspect** until proven:

- “Tests all passed” / “backtest shows edge” without command output citation
- “Live would do X” without live-path evidence (F-010 / F-048)
- “All engines agree” without per-engine scores on a named opportunity id
- Rounded “nice” metrics with no artifact path
- Cross-session memory of ledgers without re-read of files

### 14.5 Allowed use of tools under this program

| Allowed | Not allowed |
|---|---|
| Run scripts to **create** artifacts | Cite chat-only metrics as validation |
| Quote tool output **with path** | Upgrade `UNTRUSTED_RAW` without review |
| Mark `UNKNOWN` / fail-closed | Invent missing JSON fields or trade counts |
| Compare two on-disk artifacts | Treat LLM rewrite of JSON as the artifact |

### 14.6 Relation to program phases

```text
Tool run
  → artifact (UNTRUSTED_RAW)
  → REVIEW: did we run the intended flow? (H3 + §2)
  → REVIEW: did the agent report the artifact correctly? (H1/H2)
  → only then: research evidence (FLOW_MATCHES_INTENT)
  → never automatic: production authority
```

---

## 15. Quick reference — unknowns vs assumptions vs hallucinations

| Kind | Question it answers | Failure if ignored |
|---|---|---|
| **Unknown** | What do we not know yet? | Plan pretends certainty |
| **Assumption** | What are we relying on without full proof? | Silent dependency; wrong priority |
| **Hallucinated / mis-specified tool output** | Is this number even real and on the right path? | False edge or false kill enters the ledger |

**Operator slogan:** *Unknowns listed · Assumptions labeled · Tool numbers untrusted until flow + quote check.*

---

## 16. Utilizing models for tool-output hypotheses

> **Purpose:** Models help *propose and stress-test* claims about tool outputs.
> They do **not** create market edge and do **not** upgrade `UNTRUSTED_RAW` by fluency.
> Full authority still: artifact → validation-flow review → Authority Ladder.

### 16.1 Two different “models” (do not mix)

| Kind | Examples in this repo | Job re: tool output |
|---|---|---|
| **A. Market engines / research models** | CRT scorer, Gaussian, Zone, RR, BitNet, TradeNet, interpreters | Emit **evidence scores** on an opportunity; subject to incremental-value tests |
| **B. LLM / agent models** | Multi-LLM pipeline, agent tools, chat assistants | Propose **hypotheses about what a tool run means**, draft tests, spot H1–H3 failures |

Both feed **tool-output hypotheses** — statements of the form:

```text
H_tool: "If we run <entrypoint> with <args/lens>, we expect <observable artifact fields>
         because <mechanism>. Falsify if <counter-evidence>."
```

That is **not** the same as:

```text
H_market: "This structure predicts positive expectancy after costs."
```

### 16.2 What a tool-output hypothesis is allowed to claim

| Allowed claim class | Example | Becomes evidence only after |
|---|---|---|
| **Path identity** | “Gate-OFF backtest uses CRT-only entries” | Manifest + code/env check (H3) |
| **Artifact shape** | “forward_walk returns TP_HIT on synth pack” | Re-run + intended_spec compare |
| **Engine contract** | “With feature contract X, CRT score ≈ 0.8227” | Real `crt_compute` vs closed form |
| **Delta / ablation** | “Turning zone weight to 0 does not change entries” | Byte-identical ledgers or scored Δ |
| **Failure mode** | “Empty stdout must not be summarized as SUCCESS” | AH-* tests |

| Forbidden upgrade | Why |
|---|---|
| Chat: “PF=1.4 so edge exists” | H1 + economic claim without flow review |
| Engine score alone → production authority | Existence ≠ Authority Ladder |
| LLM rewrite of JSON as the artifact | Replaces tool truth |

### 16.3 How to use **LLM/agent models** (B)

**Role:** hypothesis *generator*, *adversary*, and *checklist writer* — never sole validator.

| Step | LLM does | System / human does |
|---|---|---|
| 1 Propose | Draft `H_tool` from code/docs/logs | Store as claim with status `PROPOSED` |
| 2 Bind | Name entrypoint, flags, ACTIVE_VERSION, instrument | Reject unbound claims |
| 3 Predict | Expected artifact fields (outcome, scores, keys) | Write `intended_*` before run when possible |
| 4 Attack | List H1/H2/H3 ways the claim could be fake | Prefer worst-case first |
| 5 Design test | Suggest pytest / synth pack / dual-lens | Owner grants implement |
| 6 Interpret | Explain *after* artifact exists | Quote-check vs `run_manifest` (H2) |
| 7 Demote | Suggest kill/reopen conditions | Record in findings only if gates pass |

**Prompt contract for agents (copy into handoffs):**

```text
You may only emit H_tool claims.
Each claim must include: entrypoint, args/env, expected artifact path fields,
falsifier, H1/H2/H3 risk.
You must not state PF/E/WR as fact without an on-disk artifact path.
If no tool ran this turn, every numeric market result is NON_EVIDENCE.
```

### 16.4 How to use **market engines / models** (A)

**Role:** produce **structured evidence** on a fixed opportunity population — inputs to *market* hypotheses, and also to *tool* hypotheses (“did the engine path fire?”).

| Pattern | How |
|---|---|
| **Same opportunity, four evidence channels** | Synth pack pattern: design feature contract → CRT/Gaussian/Zone/RR scores → compare intended vs produced |
| **Incremental value H_tool** | “Removing engine E does not change outcome distribution under lens L” → ablation artifact |
| **Abstain evidence** | Model score as *filter*, not as direction vote; test Δ after costs |
| **Shadow only** | BitNet/TradeNet: log scores; no fusion authority until ΔG001 measured |
| **Never** | Treat engine score as fill/PnL proof |

### 16.5 Combined loop (recommended)

```text
          ┌─────────────────────────────┐
          │ LLM proposes H_tool / H_mkt │
          │ (PROPOSED, NON_EVIDENCE)    │
          └─────────────┬───────────────┘
                        ▼
          ┌─────────────────────────────┐
          │ Bind path + intended fields │
          │ (intended_spec / contract)  │
          └─────────────┬───────────────┘
                        ▼
          ┌─────────────────────────────┐
          │ Real tool run               │
          │ engines / backtest / MT5…   │
          │ → artifact + run_manifest   │
          └─────────────┬───────────────┘
                        ▼
          ┌─────────────────────────────┐
          │ Compare intended vs produced│
          │ (AH/VP/synth pack style)    │
          └─────────────┬───────────────┘
                        ▼
              match? ──no──► H_tool FAIL / fix path
                │
               yes
                ▼
          FLOW_REVIEWED → (optional) market H_mkt under M4
                ▼
          only survivors: decision authority
```

**Worked example already in-repo:**  
`scripts/research/erp_synth_4h_trace.py` — OHLCV design → engines feature contract → intended scores → real engines → `produced_compare.json`. That is the template for “models help tool-output hypotheses” without H1 invention.

### 16.6 Which model for which tool-output job

| Job | Prefer | Avoid |
|---|---|---|
| “Did validation path match intent?” | Deterministic VP/manifest + code | LLM alone |
| “What might be wrong with this log?” | LLM adversary (propose) + re-run | Accepting LLM diagnosis as truth |
| “What score should CRT emit on this contract?” | Closed-form + `crt_compute` | Hand-waved “high CRT” |
| “Does gaussian add Δ?” | Ablation on factory population | Single pretty chart |
| “New market idea?” | LLM/interpreter for *search*; M4 for *verdict* | Promoting chat ideas live |
| “UI showed SUCCESS” | Playwright + artifact exists | Trusting UI copy |

### 16.7 Authority boundary (hard)

```text
Model output (A or B)
  → may create H_tool / H_mkt (PROPOSED)
  → may never set FLOW_MATCHES_INTENT alone
  → may never set production / capital authority
  → may only assist after artifact+review into RESEARCH_RECORD or AUTHORITY_ELIGIBLE
```

### 16.8 Practical utilization checklist (operator)

1. Decide claim type: **tool-path** vs **market-edge** (never one label for both).  
2. If tool-path: write intended fields **before** or immediately with the run.  
3. Run real tool; store path + hash.  
4. Use LLM only to *diff* narrative vs artifact (H2 check).  
5. Use engines only as *named evidence channels* on a frozen population.  
6. Promote nothing that skipped §2 / §14.  

### CL-009 — 2026-07-14 — Model use for tool-output hypotheses

- Owner asked how to utilize models that help tool-output hypotheses.
- Added §16: split market engines (A) vs LLM agents (B); H_tool contract;
  combined loop; authority boundary; synth pack as worked example.

### CL-010 — 2026-07-14 — Incorporate research loop + multi-LLM RCP design; ambiguities

- Owner provided trader-facing research steps 1–13 + multi-LLM control plane design;
  asked to incorporate into current design and discuss ambiguity.
- Added [`edge-research-platform-multi-llm-design.md`](edge-research-platform-multi-llm-design.md):
  spine mapping, four artifact kinds, 8-step loop, WS-MLLM-RCP (thin), AMB-01…AMB-12.
- **Key ambiguity:** proposed roles ≠ existing `multi_llm/` role cards → dual-lane recommended until owner freezes AMB-01.
- Pitch accuracy footnotes: F-037 lens, F-048 RR, F-004/F-005 inert models.

### CL-011 — 2026-07-14 — Decision board MD + story authority reverse-engineer

- Owner: keep decisions tracked/shout-out; single easy MD; reverse-engineer scripted story vs WHAT/WHO/HOW.
- Added [`erp-decision-board-and-story-authority.md`](erp-decision-board-and-story-authority.md)
  (D-01…D-23 + Part B reverse-engineer).
- **Finding D-23:** changing story prices/phases **requires CODE** in `erp_synth_4h_trace.py` today;
  NOT manageable by WHAT/WHO/HOW alone. HOW still owns live knobs; WHAT owns formulas;
  re-run pack after any story edit.

### CL-012 — 2026-07-14 — Phased design plan P0–P7

- Owner: with data and design, produce design plan in phases.
- Added [`edge-research-platform-phased-plan.md`](edge-research-platform-phased-plan.md):
  P0 freeze → P1 harness/golden → P2 factory → P3 demotion → P4 OI/path → P5 shadow →
  P6 MLLM cycles → P7 capital micro. Parallel rules, exits, grant sequence.
- NA-007 closed; next = owner P0 freeze + Implement P1.

### CL-013 — 2026-07-14 — Before/after full design description

- Owner: describe before and after entire design implemented.
- Added [`edge-research-platform-before-after.md`](edge-research-platform-before-after.md):
  identity, trust, spine, synth, multi-LLM, phases, artifacts, non-goals, checklist.

### CL-014 — 2026-07-14 — Parallel path toward earned wealth promise

- Owner: parallel design still not a false promise of wealth; design must **move toward** promise.
- Added [`edge-research-platform-promise-ladder.md`](edge-research-platform-promise-ladder.md):
  Track I integrity ∥ Track II path-to-promise; PL-0…PL-5; KPIs; PR-01…PR-05.
- D-25/D-26: no false promise + forced search after factory; lab-forever without P4 pressure ≠ success.
- Phased plan north star + parallel rules updated.

### CL-015 — 2026-07-14 — Multi-LLM HOW design + Research Lane initiated

- Owner: design HOW for plan; initiate multi-LLM architecture if required.
- **Required thin:** dual-lane Research Lane initiated under `multi_llm/research_lane/`.
- HOW doc: [`edge-research-platform-mllm-how.md`](edge-research-platform-mllm-how.md).
- Artifacts: package_schema.json, research_cycle_ledger.jsonl (RC-000), roles, templates, scorecard.
- Lane I (`MULTI_LLM_PROTOCOL`) **not** rewritten. Promise rung still PL-0.
- Next: owner phase grant Implement P1; optional RC-001 H_tool after P1.

### CL-016 — 2026-07-14 — initiate_plan commands (model-separated PROPOSAL)

- `scripts/multi_llm/initiate_plan.py` + ps1 shortcuts + CP `research.initiate_plan`.
- Per-model `proposals/<model>/<cycle>/` with curated CONTEXT_BUNDLE (manifest, not full repo).
- Master prompt: `prompts/PLAN_DESIGN_PROMPT.md`. Docs: `INITIATE_PLAN_COMMANDS.md`.

### CL-017 — 2026-07-16 — Findings-Revalidation Gate (E4) designed, frozen, registered; RVG-U1/U2 resolved

- Whole-folder analysis found the program's findings anchors (§11 / §12.4 / decision-board D-16,
  findings F-019…F-035) rest on a State+Feature layer **since bug-fixed** — F-051 (centered-swing
  PIT-leak removed, 10/38 dims) + F-054 (feature-DAG re-cert, legacy FM-022/023 SUPERSEDED). Last
  revalidation was **E3** (2026-06-27), which **predates both** → epoch **E4** untested.
- Designed + **FROZEN** a targeted revalidation prereg (WS-OUTCOME-FACTORY **P2.0**, WI-001):
  [`findings-revalidation-gate-e4-preregistration.md`](findings-revalidation-gate-e4-preregistration.md)
  (+ json twin), protocol_hash `sha256:454b2351…`.
- **RVG-U1** resolved: E3 baselines are on disk (`results/research/qualification_2026_06_27/`,
  `phase_s_2026_06_27/`, `phase_b/`, `phase_d/`, `qualification_htf/`, `qualification_fx_metals/`,
  `*_run2/` twins) — no E3 re-run needed.
- **RVG-U2** resolved: the Class-B toy arms run on the isolated `src/research/` stack
  (`research.indicators` / `research.measurement.bar_features`), which never imports `src/features/`
  (where F-051/F-054 live) → **feature-pipeline-independent**; suspect set narrows to **Class C**
  (morphology / zone / RR / gaussian). Reclassified: drift-check + determinism, not feature re-derive.
- Anchors tagged **`PROVISIONAL (pending E4)`** — annotation only, **no finding flipped**. Freeze
  grants **no** run authority; RVG-1…5 still require explicit grants.
