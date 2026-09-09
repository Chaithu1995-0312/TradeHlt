# Parquet evidence layer

> Research-only. JSONL is the system of record. Parquet is a derived projection
> (`src/utils/parquet_store.py`). This layer does **not** train a model and does
> **not** grant G001.

**Change:** `CH-parquet-evidence-layer` (2026-08-23)

## Mental model

```
State → Decision → Lifecycle → Outcome
```

captured on **two grains**, not one:

| Surface | Role | Grain | Governing field |
|---|---|---|---|
| `opportunities.parquet` | decision ledger | bar × direction | geometry + state; **not** stream `outcome` (F-022) |
| `clean_labels.parquet` | outcome surface | bar × direction | `y_tp1` / path MFE-MAE (`TN_ENV_CLEAN_L2`) |
| `events.parquet` | state-machine journal | later CRT spine run | event / `state_from`→`state_to` |
| `crt_telemetry.parquet` | decision-flight-recorder | later CRT spine run | `kind` / `death_reason` / reject |

Illegal: 1:1 join of the 94k ledger onto the spine journal. Legal: opportunities ↔ clean_labels; events ↔ telemetry.

On the current XAUUSD files, 94,332 rows = unique timestamps × 2 sides. That is every bar × both directions, **not** CRT `TRADE_OPENED`.

## Capabilities

Implemented as named queries in `src/research/evidence/queries.py`:

1. Feature effectiveness census — coverage, distribution, median-split Δ`y_tp1`
2. Regime discovery — existing `session` / `volatility_regime` / `hour_of_day` / `trend_bias` / side cells
3. Opportunity quality — losses with large MFE, high-MFE low-TP, wins with deep MAE
4. Exit research — stored 0.5R / 1R / 2R hit rates; no re-detection; path-conditioned rates are **not** t=0 policies
5. Candidate lifecycle — telemetry death / reject / event funnel
6. Ontology coincidence — flag occurrence vs `y_tp1` (does not graduate a SEM node)
7. Evidence graph — grain-scoped edges
8. Question → candidate finding — route + n / effect / confidence / caveats
9. Opportunity leakage atlas — reached 0.5/1/2R missed TP; high-MFE+high-MAE; low-MAE failed TP; exclusive ladder
10. State value surface — E[MFE], E[MAE], E[time], E[TP1], E[TP2] per emitted state (not win rate). CRT engine states are a different grain.
11. Asymmetry atlas — Long MFE − Short MFE at the same timestamp, then E[Δ \| state]

```text
python -m research.evidence --atlas leakage
python -m research.evidence --atlas state_value
python -m research.evidence --atlas asymmetry
```

Atlases snapshot: [`docs/analysis/evidence-atlases-2026-08-24.md`](../analysis/evidence-atlases-2026-08-24.md).

Highest-value output: a defensible explanation supported by measurements.

## What this is not

- A training dataset
- A Feature Store
- A second measurement authority over JSONL
- A reopen of F-086
- Production authority
- A finder of economic edges (G001). It finds informational edges.

## Demonstrated vs unproven (2026-08-24)

Lock from F-091 / F-092 / F-093, the leakage atlas, and the MFE→R-net collapse.
Not a new F-id. `economic_claims_allowed` stays false (mt00/mt01 UNRUN).

```text
State → Future Path Difference     PROVEN on holdout (information)
State → Positive Expected R        NOT PROVEN (harvest)
Informational Edge → Trade Edge    NOT PROVEN
```

| Capability | Status | Binding evidence |
|---|---|---|
| Find interesting patterns | Proven | leakage atlas; ΔMFE; magnitude prior |
| Survive holdout | Proven for *information* objects | F-091 contrast +0.415→+0.469; F-092 +0.265→+0.209; F-093 overlay +0.0058→+0.0064 |
| Separate drift from signal | Proven | F-091 unconditional E[ΔMFE] flips +0.438→−0.546 while FM-054 contrast holds |
| Explain why effects collapse | Proven | +0.209 horizon MFE → +0.035 walk MFE → +0.026 R-net (83% post-exit) |
| Discover path-level information | Proven (count) | 47.6% reach ≥1R and miss unit TP; exclusive 2R-missed-TP n=28,007. **Mechanism “SL-first” is F-088 (walk kernel), not an atlas proof** (Path A 2026-08-28). |
| Produce E[R]>0 after costs | Not proven | F-093 book still −0.55R; F-090 holdout +0.204R / train −0.252R sign-flip |
| Produce a deployable strategy | Not proven | P-GOAL-04 unopened; no G001 |

F-091 does **not** pick the winning side. P(Δ>0) barely moves; the state scales agreeing-side excursion.

F-093 **was** `independent entry + state prior`. The independent entry was every-bar × both sides. That grain is structurally losing (F-086). The overlay survived as a tiny information lift and did not harvest. The untested object is:

```text
Sparse independent SIGNAL  +  Parquet-derived prior  →  different trade object
```

not a re-run of every-bar. That is a new `MC-*` if authorized. It is not opened by this lock.

Probability ranking on this grain: high = path/state/timing objects; medium = sparse signal + prior; low = one feature → money.

## Run

```text
python -m research.evidence --out results/research/parquet_evidence_layer
python scripts/research/run_evidence_layer.py --question "losses with large MFE"
```

First snapshot: [`docs/analysis/parquet-evidence-layer-2026-08-23.md`](../analysis/parquet-evidence-layer-2026-08-23.md) (point-in-time).

## Value fidelity vs formulas (2026-08-27)

Measured once on `clean_labels` n=47,166 unique long bars. Point-in-time:
[`docs/analysis/parquet-formula-parity-2026-08-27.md`](../analysis/parquet-formula-parity-2026-08-27.md).

- Stored OHLC == cited CSV (exact).
- Geometry columns == `candle_math` FM-001/002/010 (canonical body/range).
- All 38 overlapping columns == HEAD `FeaturePipeline.run()` (bit-identical).
- Remaining “drift” is the **active formula identity** (FM-022/023 `atr_relative` = F-061;
  `broker_local` session = F-066), plus schema 38 vs live 48, plus gated `retest_depth`.
- This does **not** make parquet an identity store or a G001 surface.

## Asymmetry atlas rerun (2026-08-27)

Named query `python -m research.evidence --atlas asymmetry` on the **legal**
opportunities↔clean_labels join only. Events/telemetry were loaded and **not**
1:1 joined. `TRADE_OPENED` is a different grain. Artifact:
`results/research/parquet_evidence_layer/report.json` (`generated_at` 2026-08-27,
`route=asymmetry`, `authority=RESEARCH_ONLY`).

This is a **replication** of
[`docs/analysis/evidence-atlases-2026-08-24.md`](../analysis/evidence-atlases-2026-08-24.md)
§3, not a new F-id. Unconditional E[ΔMFE]=**+0.2388** (P(Δ>0)=0.531, median 0.408)
matches the 2026-08-24 write-up’s +0.239 / 0.531 / 0.408. Spreads match:
hour 0.923 · session 0.774 · vol 0.615 · trend_bias 0.457.

Do **not** treat +0.239 as a stable long-path bias. F-091 already split that mix:
train +0.438 / holdout **−0.546**. The PRIMARY (FM-054 contrast) kept sign;
the unconditional mean flipped.

**Same-file recompute 2026-08-27 (this session, clean_labels parquet):**
train n=37,621 E[ΔMFE]=**+0.4376** contrast **+0.4152**; holdout n=9,454
E[ΔMFE]=**−0.5463** contrast **+0.4686**; embargo dropped 91. MATCH to F-091
(+0.415 / +0.438 ; +0.469 / −0.546). E[Δ y_tp1] train +0.049 / holdout −0.016
(still not a TP edge). A Grok Task `parquet-f091-split-check`
(`08266784-f85f-45a6-b1df-995936338a14`) was queued with the same brief so the
file-access bot does not rerun the full-sample atlas.

`E[ΔMAE]=−0.239` is **the same number with opposite sign**, not a second discovery:
on this grain long MFE ≈ short MAE at the same timestamp (atlas §2).
`E[Δ y_tp1]=0.036` is the information≠value gap (atlas long TP1 0.341 − short 0.306).
P(Δ>0) stays ~0.50–0.58 while E[ΔMFE] moves — excursion size, not a coin-flip.
Hour/session are F-066 broker clock. `higher_high`/`lower_low` are F-051 structure
cols (this file bit-matches HEAD causal; still not skill). `volume_spike` F-065 unused.
`liquidity_sweep` spread 0.008 is POSSIBLE / no contrast. Does not reverse F-086.
No G001.

## Leakage atlas rerun (2026-08-27)

Named query `--atlas leakage` on the **94k** clean_labels grain. Artifact:
`results/research/parquet_evidence_layer/leakage/report.json` (6 records).

MATCH to [`docs/analysis/evidence-atlases-2026-08-24.md`](../analysis/evidence-atlases-2026-08-24.md) §1
(byte-level counts):

Nested: 0.5R-missed-TP 54,157 (0.574) · 1R-missed-TP **44,858** (0.476) ·
2R-missed-TP 28,007 (0.297) · high-MFE+high-MAE 56,664 (0.601) ·
low-MAE failed TP 498 (0.005).

Exclusive ladder (sums to 94,332): TP captured 30,525 (0.324) · 2R-missed-TP 28,007
(0.297) · 1R-not-2R 16,851 (0.179) · 0.5R-not-1R 9,299 (0.099) · never 0.5R 9,650
(0.102).

Path-conditioned, not a t=0 policy. 2R-missed-TP **count** is atlas-proven.
“SL-first” is F-088 (walk kernel), not this atlas (Path A). Frozen 2R unit TP
is the label geometry. Not `opportunities.outcome` (F-022). Not G001.

All three 94k atlases are now rerun MATCH: leakage · state_value · asymmetry.

## State value atlas rerun (2026-08-27)

Named query `--atlas state_value` on the **94k** clean_labels grain (not the journal).
Artifact: `results/research/parquet_evidence_layer/state_value/report.json`
(does not overwrite asymmetry or lifecycle).

MATCH to [`docs/analysis/evidence-atlases-2026-08-24.md`](../analysis/evidence-atlases-2026-08-24.md) §2:

| State | n | E[MFE] | E[time] | E[TP1] | path_net |
|---|---:|---:|---:|---:|---:|
| hour=8 | 4,120 | 5.295 | 3.07 | 0.347 | 0 |
| hour=18 | 4,120 | 2.167 | 9.40 | 0.268 | 0 |
| session=1 | 20,600 | 4.765 | 3.86 | 0.337 | 0 |
| session=2 | 20,580 | 2.569 | 7.56 | 0.298 | 0 |
| vol=0 | 31,828 | 4.991 | 3.55 | 0.334 | 0 |
| vol=2 | 33,200 | 2.803 | 6.79 | 0.307 | 0 |
| side=long | 47,166 | 4.035 | 5.36 | 0.341 | **+0.239** |
| side=short | 47,166 | 3.796 | 4.58 | 0.306 | **−0.239** |

E[MFE] spreads: hour 3.128 · session 2.195 · vol 2.188. Ontology flags 0.06–0.37.
`path_net=0` on every state shared by both sides (long MFE ≈ short MAE). Only `side`
has a non-zero path_net, and that number **is** the F-091 mix, not a new edge.
CRT engine states are **not** on this grain. Hour/session = F-066. Not win rate. No G001.

## CRT spine journal grain (2026-08-27)

Separate from the 94k ledger. Snapshot:
[`docs/analysis/crt-spine-journal-2026-08-27.md`](../analysis/crt-spine-journal-2026-08-27.md).

Replication of the 2026-08-23 process counts on
`run_20260822_162108_XAUUSD` (events 7,112 / telemetry 4,883):
SWEEP→DISP **22%**, EXP→RETEST **16%**, TRADE_OPENED **3**, RESET_HTF **1,442**/1,798.
Added this turn: RETEST_REPLAY 23 = 19 OFF_SESSION + 1 LOW_SCORE + 3 ACCEPTED;
all three opens LONG; **not** the NS walk (that one had TRADE_OPENED=16 and
RETEST→EXEC 23/24). n=3 is INSUFFICIENT. No join to clean_labels. No G001.

Named query (2026-08-27): `--question "candidate lifecycle death bottleneck"`
→ route=`lifecycle`. Artifact:
`results/research/parquet_evidence_layer/lifecycle/report.json` (does **not**
overwrite the asymmetry `report.json`). MATCH to the hand census: deaths
RESET_HTF=1442/1798; events TRADE_OPENED=3; reject_reason OFF_SESSION=19.
Caveat: the query’s “state transition bottlenecks” n=5269 **folds RESET edges**
(`SWEEP→RANGE` 1393) in with golden-path `STATE_TRANSITION`. Funnel keep-rates
still use STATE_TRANSITION-only counts.

Bot ingest (2026-08-27/28): same named line, route=`lifecycle`, 10 records.
MATCH to this file. It did not join ΔMFE. `accepted=True` 26/4883 is sparse
kind flags (DECISION_DISTANCE 23 APPROVED + other kinds), **not** 26 trades;
`TRADE_OPENED` remains 3. Driver `grain` block still prints the 94k join
envelope even on this route — that is load metadata, not a used join.

## LLM / Parquet-bot consumer

A Grok bot with file access is an intended reader of these projections (P-FLOW-04 / P-FLOW-07), not a second authority. Before querying columns, it must consume the findings that bind to each surface. Operating brief (paste-pack, not this spec): [`.grok/PARQUET_BOT_BRIEF.md`](../../.grok/PARQUET_BOT_BRIEF.md). That brief does not grant G001 and does not turn Parquet into L0–L5 identity storage.
