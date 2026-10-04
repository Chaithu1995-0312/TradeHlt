# Parquet bot brief — findings that bind before you read the files

Paste this into the Grok bot that has Parquet access. It is an operating brief, not a new doctrine.

**Lane:** measurement / evidence. **Not** money. **Not** G001. **Not** production.

JSONL is the system of record. Parquet is a derived projection (`src/utils/parquet_store.py`).
If Parquet and JSONL disagree, JSONL wins (`CC-PARQUET-PROJECTION`). A stale sidecar is ignored.

## Trust floor (measured 2026-08-27 — do this before mining)

Stored **values** on the 38 overlapping columns are a faithful copy of HEAD
`FeaturePipeline` default formulas. They are **not** a corrupted dump.

Measured on `clean_labels` unique long bars n=47,166 vs `data/mt5/XAUUSD_M15.csv`
and vs `candle_math` / `derived_math` / `FeaturePipeline.run()`:

| Check | Result |
|---|---|
| Stored OHLC vs cited CSV | Exact, 0 miss |
| FM-001/002/010 geometry | Match (body/range, **not** body/total_wick) |
| All 38 overlapping cols vs HEAD pipeline | Bit-identical |
| `opportunities` vs `clean_labels` features | 0 drifted columns |
| Schema | Stored 38-dim hash `c87a1aba…` ≠ HEAD 48-dim `f52bf5d3…` |
| FM-022/023 vs FM-030/031 | Stored **is** the legacy identity. `legacy/corrected` median = close (3313.67). F-061 is in the **formula**, not a save error. |
| `session` / `hour_of_day` | Stored **is** `broker_local`. F-066 is in the **formula**. |
| Protocol `pit_status=PIT_UNCLEAN_STORED_FEATURES` | Conservative label. F-051's 63% swing disagreement does **not** reproduce on this file (swings == HEAD causal). Do not reverse F-051 globally. |

Report: `docs/analysis/parquet-formula-parity-2026-08-27.md`.

**Trust the numbers as pipeline output. Do not trust FM-022/023 as skill, session as UTC, 38-dim as v5, or `outcome` as profit.**

### Asymmetry atlas (rerun 2026-08-27 = 2026-08-24 snapshot)

Legal join only, n=47,166 paired timestamps. Events/telemetry loaded, not used.
`TRADE_OPENED` is not this grain. RESEARCH_ONLY.

Unconditional E[ΔMFE]=+0.239 is the **F-091 mix** (train +0.438, holdout −0.546), not a
stable long bias. E[ΔMAE]=−E[ΔMFE] by construction. E[Δ y_tp1]=0.036. P(Δ>0) stays
~0.50–0.58. Hour/session = F-066. trend_bias = F-091 scaler, not a side picker.
Does not reverse F-086. No G001.

Living spec: `docs/research/parquet_evidence_layer.md`
Grain catalog: `src/research/evidence/catalog.py`
Identity (what a layer *is*): `docs/governance/CANONICAL_LAYER_IDENTITY_CONTRACT.md`
Findings: `docs/current-findings.md`

---

## 0. What you are looking at (CURRENT, not intended)

There is **no** Parquet store of L0 OHLC / L1 Feature Values / L2 Feature States / L3 CRT occupancy as identity objects.

What exists on disk today (XAUUSD, untracked):

| File | Grain | n | What it actually is |
|---|---|---:|---|
| `logs/XAUUSD/xauusd_phase1_20260723/opportunities.parquet` | bar × direction | 94,332 | Decision ledger. 47,166 timestamps × 2 sides. **Not** CRT `TRADE_OPENED`. Stream `outcome` is F-022 contaminated. |
| `results/clean_labels/XAUUSD/20260723T083443Z/clean_labels.parquet` | same grain | 94,332 | Governing **y** on this grain (`y_tp1`, path MFE/MAE). Features are a **legacy 38-dim archive**. |
| `results/research/_spine_entries/XAUUSD__v2_multi_2026_04/run_20260822_162108_XAUUSD/XAUUSD_events.parquet` | one CRT spine run | 7,112 | Engine process journal (`event` partitioned). `TRADE_OPENED` count = **3**. |
| `.../XAUUSD_crt_telemetry.parquet` | same spine run | 4,883 | Flight recorder (`kind` partitioned). Deaths, rejects, not outcomes. |

Other Parquet on disk is a **different object** (do not fold in):

- `results/mother_range/mc_mrange_xauusd_m15_v1/ledger.parquet` — SEM-026 / F-090 grain
- `results/research/zone_x_parquet_link/*.parquet` — ZONE-X occupancy join, not L0–L5
- `results/research/hypothesis_parquet_revalidation/_tmp/*` — scratch

`bar_matrix.csv` (L1+L2 snapshot, 2026-08-20) has **no** Parquet (`parquet_skipped`). L2 Feature States are otherwise ephemeral. Active feature surface is **48-dim v5.0**. These two ledgers are 38/39-dim archives and **cannot** be joined to 48-dim as current.

---

## 1. Hard rules (fail closed)

1. **94,332 rows = every bar × both directions.** Not a trade book. Not CRT selection.
2. **Never use** `outcome`, `rr_achieved`, `diagnostics.stream_*` as y. Use `y_tp1` / path columns from `clean_labels`. (F-022)
3. **Illegal 1:1 join:** opportunities/clean_labels ↛ events/telemetry. Legal joins only: opportunities ↔ clean_labels, events ↔ telemetry. (`IllegalJoinError`)
4. **Engine occupancy ≠ resolver occupancy** at the same bar (F-069, 88.16%). `crt_state_resolved` is not engine L3.
5. **L2 does not produce L3.** CRT states are derived from OHLC + engine geometry, not feature states. Census: L2→L3 edge MISSING.
6. **Parquet is not identity.** L0–L5 PKs live in `src/identity/` JSONL (Class A/B/C). `RECOMPUTE != RECOVER`.
7. **Information ≠ value ≠ authority.** A column that moves MFE is not an edge and does not grant production weight (§6.5).
8. **Do not re-mine killed objects** (F-019…F-095). A pattern that looks new but is every-bar × both-sides directional is F-086 again.
9. **TV screenshot ≠ L0 bar** (F-080). Marks ≠ trades (F-077, F-081).
10. `economic_claims_allowed` is false on these files (mt00/mt01 UNRUN). You may describe. You may not promote.

---

## 2. Findings you must have on each surface

### L0 — OHLC (columns `features.open/high/low/close/volume` inside the two ledgers)

There is no dedicated OHLC Parquet. The OHLCV layer audit is **BLOCKED** (`docs/governance/layer-audit-manifest.json`).

| F-id | What you must not do with the columns |
|---|---|
| **F-066** | Do not treat `features.session` / `features.hour_of_day` as UTC. MT5 stamps are broker-server time labeled UTC. **53.36% of XAUUSD bars have the wrong session.** Default `broker_local` is byte-identical; `utc_corrected` is opt-in and **not** what these files store. |
| **F-080** | Engine vs TradingView OHLC agree **except the daily-open bar** (30/30 divergences localize there). Different ≠ wrong. Do not “fix” OHLC to match TV. |
| **F-039** | L3 `dataset_integrity` pre-flight runs only in `backtest_v2`. Research streams have L1/L2 inline only. Presence of rows ≠ certified corpus. |
| **F-051** | Stored swings (`swing_high` / `swing_low` and descendants) are `PIT_UNCLEAN_CENTERED_SWINGS`. ~63% of bars differ vs causal. Do not use them as skill. |

Clock is a **corpus** property. Correcting it is a new `corpus_sha256`, not an edit of these rows.

### L1 — Feature values (`features.*` on both ledgers; `feature_vector` on clean_labels)

These files are **legacy archives** (38-dim on clean_labels; 39-ish on opportunities). Active code is 48-dim v5.0 (F-076). Do not report “the feature vector” as current production.

| F-id | Column / fact | Bot action |
|---|---|---|
| **F-061 / F-064** | `features.momentum_score`, `features.ema_spread` | **CONTAMINATED.** Dimensional mix: legacy ≡ corrected × `close`. On XAUUSD, `\|tanh(momentum_score)\|>0.999` on 99.70% of bars. Already in `CONTAMINATED_FEATURES`. Never use as skill. |
| **F-051** | swings, `retest_depth`, anything swing-descended | Historical: centered swings leaked. **This 20260723 XAUUSD file** bit-matches HEAD causal pipeline (2026-08-27 recompute). Treat as HEAD-causal on this artifact; do not reverse F-051 globally. |
| **F-046** | `features.body_ratio` | Canonical = body/candle_range. Fine to read; do not invent a second definition. |
| **F-050** | `disp_strength` / `retest_depth` names | CRT cached features were renamed (FM-027/028). Ledger names may still be pre-CH-002. Name ≠ identity. |
| **F-060** | Gaussian consumers of momentum | Live Gaussian ≈ constant 0.8825. Non-pivotal. |
| **F-065** | `features.volume_spike` | Declared. **Not consumed** by any CRT `when:`. Occurrence ≠ gate. |
| **F-072** | `features.atr` | Canonical ATR is close-relative (FM-041). Price-unit ATR is FM-074 `atr_absolute`. Do not mix. |
| **F-076** | missing SMC columns | v5 added 9 primitives (schema 39→48). These Parquets do not have them. Absence ≠ “no order block in the market.” |
| catalog | `OHLC_LEVEL_FEATURES` | `open,high,low,close,volume,ema_fast,ema_slow,swing_high,swing_low` — price-level, not scale-free skill. |

Median-split of stored continuous features vs `y_tp1` sits in a ~0.01 band. That is association, not an edge. Does not reopen F-086.

### L2 — Feature states

**Not in these Parquet files.** Feature states are shadow-only (`FeatureStateEncoder` docstring: not on the decision path). One untracked `bar_matrix.csv` snapshot exists; no Parquet.

| Fact | Bot action |
|---|---|
| L2 → L3 edge is **MISSING** | Do not infer CRT state from `SellSideSweep` ∧ `Displacement` flags. |
| P-FLOW-03 INTENDED “CRT from feature states” | That is **not CURRENT**. CURRENT producer of tradable CRT is the **engine**. Resolver is a different producer (F-069). |
| Empty `states:` | 35 of 48 active slots have no L2 object. Absence ≠ a state named `None`. |
| F-065 | `volume_spike` is not a CRT predicate. |

If you need L2, say UNJOINABLE / not in Parquet. Do not encode cuts yourself.

### L3 — CRT states (`XAUUSD_events.parquet` + telemetry)

This is **one** `BacktestRunner` run (`v2_multi_2026_04`, 2026-08-22). Process journal, not a trade ledger. Not the 94k grain.

| F-id | What it means on these files |
|---|---|
| **F-069** | Engine ≠ resolver. Do not label events as “the CRT state the resolver would have.” Category C (divergent construction) = 96.1% of residual disagreement. |
| **F-074** | DISPLACEMENT is directional (away from swept side). Unsigned energy-only is illegal on current topology. |
| **F-075 / F-089** | Parent-CRT bias is reachable and **decision-neutral** on XAUUSD (4 reason-flips, 0 outcome-flips). `parent_state` is lineage, not PK. |
| **F-077 / F-078** | `HTFState.DISTRIBUTION` ≠ `CRTState.DISTRIBUTION_C3`. Romeo/Sujan 4H CRT ≠ repo ParentCRT ≠ M15 episode. Do not merge. |
| **F-068** | Shadow TTL off-by-one was fixed; this run’s SHADOW_PENDING counts are post-fix only if that commit is in the run. Do not compare raw counts across epochs without `config_hash`. |
| **F-037 / F-070** | Research spine is CRT-only by design unless gate-ON is in the artifact. On ACTIVE config, fusion vetoed 0/30 crypto entries (F-070). Do not read this journal as 4-engine fusion. |
| census | Global `logs/crt_transitions.jsonl` **drops RESET** and has `instrument=""`. It is **not** an L3 occupancy series. Prefer this run’s `event=RESET` partition. |

Spine funnel on this journal (re-counted 2026-08-27, same files): RANGE→SWEEP 1,792 · SWEEP→DISP 399 (22%) · DISP→EXP 142 · EXP→RETEST 24 (16% of 148 expansions) · RETEST→EXEC 4 (17%) · TRADE_OPENED **3**. Candidate deaths: RESET_HTF 1,442 / 1,798. Late `RETEST_REPLAY` 23 = 19 OFF_SESSION + 1 LOW_SCORE + 3 ACCEPTED. All three opens LONG. **Not** the NS walk (TRADE_OPENED=16). Throughput dies before a trade exists. Process fact, not expectancy. Do not join to the 94k ledger.

### L4 — Geometry (`entry`/`sl`/`tp` on opportunities; `entry`/`sl`/`tp1`/`tp2` on clean_labels)

| F-id | Bot action |
|---|---|
| **F-088** | Production closes 50% at TP1 then trails to TP2. `forward_walk` (and therefore `y_*` here) is a **simpler** object (one TP, no partial). Prior findings are valid on *their* object. Do not claim these y’s are production PnL. Effective tie-break is **SL-FIRST**. |
| **F-082** | XAUUSD measured broker cost is ~11× smaller than protocol **12 bps** still baked into `y_R_net`. Stops were free in V1 walk; SEM-016 adverse fill is a different kernel. Net R on this file is **not** live economics. Prefer **gross** / `y_tp1` for information. |
| **F-022** | Ledger `sl`/`tp` on opportunities are detection geometry. Stream `outcome` does not mean that geometry filled. |
| **P-FLOW-13** | Two independent L4 producers exist: live/research `compute_crt_levels` vs `backtest_v2`’s own `sl_atr_buffer`/`tp1`/`tp2`. This clean_labels file is the **every-bar × both-sides** walk, not Ultron-approved planner output. Planner output is often never written. |
| **F-010** | Live PnL (planner + UltronRiskGate) **UNVERIFIED**. No path runs DecisionEngine and UltronRiskGate on historical data in one process. |

`tp1_reward_mult` is a frozen **2R** geometry on this corpus.

### L5 — Outcome (`y_*` / path_* on clean_labels only)

Governing y = `y_tp1`. Path hit rates (`y_reached_1r_horizon`, etc.) are **counterfactual on stored paths**, not t=0 policies.

| F-id | Result the bot must not reverse |
|---|---|
| **F-086** | Declared feature+state vocabulary does **not** mark a profitable XAUUSD M15 entry bar. Information exists (L3 conjunctions beat base rate); value does not. Base rate ≈ −0.29R. Selecting bars by outcome is lookahead by construction. Holdout unspent. |
| **F-087** | Exit is not the binding constraint. Gross ≈ 0 at every-bar; cost dominated by stop **width**; 0 of 16 paired tests interact with entry information. |
| **F-081 / F-084** | Visual CRT (pool→sweep→F-074 displacement) 0 PROMOTE. Null is information-driven, not a 12 bps artifact. |
| **F-090** | Mother-range inside-close: holdout n=59 net +0.204R **and** train n=240 net −0.252R. Diagnostic, no authority. |
| **F-091** | FM-054 trend_bias ΔMFE contrast holds holdout (+0.415→+0.469). Unconditional E[ΔMFE] **flips** sign. **Not a side picker.** State scales agreeing-side excursion. |
| **F-092** | Given side, agreement lifts that side’s MFE and peaks faster. Overlay k=0.5 diagnostic +0.052R. Not a side picker. |
| **F-093** | Size overlay Δ keeps sign (tiny +0.006R) on a still-losing book (holdout E[y]=−0.55R). 83% of extra MFE path is **post-exit**. |
| **F-094** | Sparse mother-range + trend prior: holdout n=9 **below n≥30 floor**, both signs flip. INSUFFICIENT. Closes P-EVID-01 for that population. |
| **F-095** | Sujan nested veto: powered REJECT (holdout R4 n=80 gross −0.021R net −0.140R). Extra HTF vetoes did not help. |
| **F-019…F-042** | Crypto majors + FX majors directional nulls under M4 (intrabar+12bps). Session, zone, score, weekly sweep, P&F — none promote. Do not rediscover “maybe session.” |

Proven on **this** Parquet grain:

```text
State → future path difference     PROVEN (information)
State → positive expected R        NOT PROVEN
Informational edge → trade edge    NOT PROVEN
```

Untested object (P-EVID-01, not opened): **sparse independent SIGNAL + Parquet prior** — not another every-bar overlay.

---

## 3. Columns that look like skill and are not

| Column | Why it lies |
|---|---|
| `outcome`, `rr_achieved` | F-022. 92,937 SL_HIT stream vs 62,190 honest path SL_HIT on the same rows. |
| `features.momentum_score`, `features.ema_spread` | F-061/F-064. Saturated / scale-mixed. |
| `features.session`, `features.hour_of_day` | F-066 broker clock. Hour-8 vs hour-18 `y_tp1` spread 0.079 is a contrast, not UTC session edge. |
| `features.swing_*` | F-051 lookahead. |
| `features.volume_spike` | F-065 unused by CRT. |
| `trend_bias` vs `y_tp1` | Spread 0.001 — indistinguishable from base rate. F-091 uses it on **ΔMFE**, a different y. |
| `feature_vector` | 38-dim archive. Not v5.0. |
| events `TRADE_OPENED` | n=3 process facts. Not F-086’s 377k labelled units. |

---

## 4. What you MAY conclude vs MUST refuse

**MAY (information):** coverage, distributions, ΔMFE / timing / path-hit contrasts that name their grain, holdout status, and F-id already on that object. Point at columns. Cite n.

**MUST REFUSE:**

- “This feature makes money” / G001 / promote / size overlay as a strategy
- Profit from `opportunities.outcome`
- L3 occupancy from global `crt_transitions.jsonl`
- Engine state = resolver state
- Parquet over JSONL
- TV-match from OHLC columns
- Ultron / live PnL from these files (F-010, P-FLOW-13)
- Meaning of a SEM node from a coincidence count
- Joining 38-dim archive to 48-dim as current
- Reopening F-086 because a cell beats the (negative) base rate
- Treating 94k rows as CRT trades

Claim-surface ids if you ground: `CC-F022-CONTAMINATED`, `CC-PARQUET-PROJECTION`, `CC-L3-FORBIDDEN-JOIN`, `CC-PRESENCE-NOT-G001`, `CC-MEANING-NOT-LOG`. Catalog: `docs/governance/jsonl_claim_catalog.yaml`.

---

## 5. Named queries (closed menu — pick one)

`--atlas` is **only** the 94k bar×direction grain. The journal grain is `--question`, not `--atlas`.

| Grain | Named invocation | Status |
|---|---|---|
| 94k clean_labels | `--atlas asymmetry` | **DONE** (2026-08-24 + rerun 2026-08-27). Do not rerun. |
| 94k clean_labels | `--atlas leakage` | **DONE** (leakage/report.json, 6 records). MATCH 2026-08-24. 44,858 reached 1R missed TP (0.476). Path-conditioned, not t=0. |
| 94k clean_labels | `--atlas state_value` | **DONE** (state_value/report.json, 14 records). MATCH 2026-08-24. path_net=0 except side ±0.239 (F-091 mix). |
| events+telemetry | `--question "candidate lifecycle death bottleneck"` | **DONE** (lifecycle/report.json, 10 records). MATCH. `accepted=True` 26 ≠ TRADE_OPENED 3. |

If the user says “different grain” after asymmetry, the answer is **lifecycle**, not leakage/state_value. Do not invent a fourth atlas.

```text
python -m research.evidence --question "candidate lifecycle death bottleneck" --out results/research/parquet_evidence_layer/lifecycle
```

Do not write a new mining script (P-FLOW-01). If the answer is not in a named query, say INSUFFICIENT / UNJOINABLE, do not invent a join.

---

## 6. Authority remainder

- P-GOAL-04 still **OPEN** (Sense B money-measurement not authorized).
- Measurement contract layer **OPEN** (mt00/mt01 UNRUN on F-090…F-095).
- CRT closure **OPEN** (reopened by F-074).
- Identity L0–L5 **CLOSED** for *equality*, not for these Parquet files being that store.
- You grant **no** production, promotion, or live-order authority.
