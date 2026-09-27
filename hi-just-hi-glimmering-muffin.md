# MarketClock — cached schema + whole design

> ## ⛔ PARKED — CRITICAL — NEXT ACTION ITEM
>
> **State:** design COMPLETE + user-approved on both open decisions. **Zero code written.**
> Nothing in `src/` was touched. No finding filed. No ontology edit.
>
> **Pick up here — the 4 steps, in order:**
> 1. Fix `src/features/feature_pipeline.py:720` — route `day_of_week` through
>    `self._fp_cfg["session_timestamp_basis"]`, same resolution already at `:727-733`.
>    **Acceptance: byte-identical.** `SCHEMA_HASH` must stay `d40e7c7d5b624ef6d27670255ad95a35`,
>    `FEATURE_ORDER_HASH` stays `7901bb0d34f3d0af`, XAUUSD M15 vector SHA unchanged.
> 2. Build MarketClock sidecar — composition only, over `calendar_periods` +
>    `broker_clock` + `session_classifier`. **Emit BOTH** bar-count and elapsed-minute counters.
>    `clock_basis` on every row.
> 3. Audit `clock_registry.require_reviewed_clock()` call-site reachability (F-039 shape:
>    a gate that exists at 2 sites while the rest of the fleet bypasses it).
> 4. File the §6.2 drift decision + finding row for the F-066 `day_of_week` gap.
>
> **Do NOT:** promote anything into the 48-dim canonical vector (§"Canonical-vector promotion"),
> or run any measurement. Separate authorized turns.
>
> **Decisions already made (do not re-ask):** emit both counters · fix `:720` in place,
> byte-identical · F-065 participation confound PARKED by user, declared as a limitation.
>
> **Everything needed to resume is in this file** — schema, hashes, module inventory, the
> defect, the measurement constraints. Nothing to re-derive.

**Status:** design only. Nothing implemented. Schema below gathered from source 2026-09-23.

---

## Context

Proposal: markets are not IID, so identical *structural* states (CRT=RETEST, bullish, swept,
high-vol) occurring Monday-London vs Friday-NY-close may have different outcome distributions.
Therefore calendar/clock context should become a first-class layer rather than an ungoverned
dataframe column, and be used for **state characterization** (what usually happened next) rather
than prediction.

Gather result: **~70% of this already exists**, in three modules that don't compose. The real
work is composition + one latent defect, not a new layer.

---

## CACHED SCHEMA (source-verified 2026-09-23 — reuse, do not re-derive)

### Canonical vector — v6.0, 48 dims

```
SCHEMA_VERSION    6.0
CANONICAL_FEATURE_DIM 48
SCHEMA_HASH       d40e7c7d5b624ef6d27670255ad95a35
FEATURE_ORDER_HASH 7901bb0d34f3d0af
```

| idx | name | idx | name | idx | name |
|----|------|----|------|----|------|
| 0 | open | 16 | macd_line | 32 | **hour_of_day** |
| 1 | high | 17 | macd_signal | 33 | disp_strength |
| 2 | low | 18 | macd_hist_raw | 34 | retest_depth |
| 3 | close | 19 | macd_hist_z | 35 | candles_since_sweep |
| 4 | volume | 20 | sweep_detected | 36 | liquidity_distance |
| 5 | volume_ratio | 21 | liquidity_sweep | 37 | liquidity_pressure_score |
| 6 | double_sweep | 22 | break_of_structure | 38 | volume_spike |
| 7 | ema_fast | 23 | swing_high | 39 | order_block_distance |
| 8 | ema_slow | 24 | swing_low | 40 | fvg_distance |
| 9 | ema_spread | 25 | higher_high | 41 | breaker_distance |
| 10 | trend_bias | 26 | lower_low | 42 | mitigation_block_distance |
| 11 | trend_strength_z | 27 | body_size | 43 | pdh_distance |
| 12 | momentum_score | 28 | candle_range | 44 | pdl_distance |
| 13 | atr | 29 | body_ratio | 45 | eqh_distance |
| 14 | volatility_ratio | 30 | volatility_regime | 46 | eql_distance |
| 15 | rsi_14 | 31 | **session** | 47 | change_of_character |

**Construction rule (matters for any addition):** `CANONICAL_FEATURES` is **GENERATED** from
`configs/formulas/market_ontology.yaml` — every entry declaring `lineage.vector_key` +
`lineage.vector_index` (`feature_schema.py:109-139`). Fail-closed at import: indices must be
contiguous `0..N-1`, no dupes, no two entries claiming a key. **A new dim is an ontology edit,
not a Python edit.**

Appending at index 48 is a *pure tail addition* (the v5.0 SMC precedent, `feature_schema.py:72-89`):
no existing index changes meaning, and pre-existing models truncate via the
`SCHEMA_V2/V3/V4_FEATURE_DIM` sentinels (35/38/39). It **does** change `SCHEMA_HASH` and
`FEATURE_ORDER_HASH` (both computed over names) → freeze-pin re-certification.

### Clock / time surfaces that already exist

| Module | What it is | Status |
|---|---|---|
| `src/data_ingestion/clock_registry.py` | **The ClockBasis identity object.** `ClockRecord{path, sha256, timezone, user_reviewed, reviewed_by, detector}` + `require_reviewed_clock()`. Fail-closed, SHA-pinned (re-fetch invalidates → re-review), no env escape hatch, plus a `require_basis_compatible()` **double-conversion guard**. Registry at `configs/data_provenance/ohlcv_clock_registry.json` (versioned, not under gitignored `data/`). | **BUILT** |
| `src/data_ingestion/clock_detector.py` | advisory clock guess, feeds `ClockRecord.detector` | BUILT (not read this pass) |
| `src/features/broker_clock.py` | `mt5_server_to_utc` / `..._scalar`. NY-DST-derived (not Europe/Athens — deliberate). Never mutates the corpus `timestamp` column. MT5-only scope. | BUILT |
| `src/features/session_classifier.py` | single owner of FM-052. `SessionOrdinal{ASIA=0,LONDON=1,NEWYORK=2,OVERLAP=3,CLOSED=4}`, `classify_session_feature_series`, config-driven windows. Keeps the session FEATURE separate from the session FILTER. | BUILT |
| `src/features/calendar_periods.py` | `period_key` / `period_start` / `calendar_key` over `H1/H4/D1` (hour-grid) + `W1/MN1` (ISO week, month). Pure, no I/O, no config, no spine import. Lock-on-close, drops trailing partial, never fabricates. | BUILT |
| `feature_pipeline.compute_context()` `:716-744` | emits `day_of_week` (`:720`), `hour_of_day` (`:733`), `session` (`:742`) | BUILT |

### The F-066 basis switch

`feature_pipeline.session_timestamp_basis` ∈ `{broker_local, utc_corrected}`; strict-read, no
silent fallback (`_SESSION_TIMESTAMP_BASES`, `feature_pipeline.py:155`, raises on unknown).
`broker_local` is the default and byte-identical to pre-F-066 behavior. It also gates the
`crt_engine` trade-gating session FILTER (deliberately parked on broker time — it was
empirically tuned there; relabeling it is an economic decision, not a bug fix).

---

## FINDING FROM THIS GATHER (source-verified, previously unrecorded)

**`day_of_week` does not honour `session_timestamp_basis`.**

`feature_pipeline.py:720` — `df["day_of_week"] = df["timestamp"].dt.dayofweek` — reads the **raw**
timestamp unconditionally. The basis switch is applied only afterwards, at `:727-733`, and only to
`hour_of_day` (and thence `session`).

Consequence under `utc_corrected`: `hour_of_day` is true UTC while `day_of_week` remains
broker-local. Since the broker day opens at **01:00** server (F-080) and the offset is 2–3h, a bar
at broker Mon 01:00 resolves to UTC Sun ~22:00 → the row reads `hour_of_day=22, day_of_week=0
(Monday)`. Internally inconsistent by construction.

**Currently INERT** — `broker_local` is the active default everywhere, and under it both fields read
the same raw stamp, so nothing is wrong today (`unreachable ≠ bug`, §6.8). It fires the moment
anyone flips the basis. It is also *exactly* the class the proposal would amplify: every
`bars_since_day_open` / `is_week_open` / `week_position` counter inherits the day boundary.

Classification: **incomplete F-066 migration**, dormant.

**DECIDED (user, 2026-09-23): fix in place, byte-identical.** Route `:720` through the same
`_session_ts_basis` resolution already used at `:727-733`, so `day_of_week`, `hour_of_day` and
`session` all derive from one clock. Under the active `broker_local` default both arms read the
raw stamp, so the change is provably byte-identical — the XAUUSD M15 vector SHA, `SCHEMA_HASH`
and `FEATURE_ORDER_HASH` must all be unchanged, and that is the acceptance test. Still requires a
§6.2 drift decision + a finding row (fixing the code does not excuse leaving the class unrecorded).

---

## DESIGN — whole shape

Split into three objects with different costs and different authority.

### 1. ClockBasis — identity layer — **ALREADY BUILT, needs wiring audit only**

`clock_registry.ClockRecord`. No new code. Open question is *reachability*: how many read paths
actually call `require_reviewed_clock()` vs streaming a corpus unguarded (the F-039 shape — a
validator that exists at 2 call sites while the rest of the fleet bypasses it). **Audit, don't
build.**

### 2. MarketClock — feature layer — thin composition over existing parts

Pure function of `(timestamp, clock_basis)`. No market data in, therefore **structurally incapable
of lookahead** — the F-051 centered-swing failure class cannot occur in a layer that never reads a
price. That property is rare here and worth stating explicitly.

Emits (sidecar frame, joined on timestamp — **not** canonical vector slots):

```
clock_basis            # broker_local | utc_corrected  — PRIMARY KEY, travels with every row
day_of_week            # basis-aware (fixes the defect above)
hour_of_day            # already exists, re-exported for locality
session                # already exists (FM-052)
day_key                # calendar_periods.period_key(ts, "D1")
week_key               # calendar_periods.period_key(ts, "W1")
month_key              # calendar_periods.period_key(ts, "MN1")
bars_since_day_open    # index - first index sharing day_key
bars_since_week_open   # index - first index sharing week_key
mins_since_day_open    # wall-clock elapsed since period_start(day_key)
mins_since_week_open   # wall-clock elapsed since period_start(week_key)
is_week_open / is_week_close
```

Reuses `calendar_periods` verbatim for every boundary; adds no new calendar math.

**DECIDED (user, 2026-09-23): emit BOTH counters.** Bar-count is deterministic and gap-agnostic;
elapsed-minutes is economically meaningful. Neither enters the canonical vector, so the second
column is free at sidecar scale, and the measurement decides which discriminates.

Their **disagreement is itself the gap detector**: on a complete M15 week
`mins_since_week_open == 15 * bars_since_week_open`. Any row where that identity fails sits after
a gap, and the residual `mins - 15*bars` is the accumulated missing time. That gives a derived
gap signal for free, with no holiday calendar and no inference from data — which matters, because
of the trap below.

**Lookahead trap to avoid:** a *published* holiday calendar is known at `t` and legitimate. A
holiday flag *inferred from observed gaps* reads the future to label the present, and would
silently reintroduce the leak this layer otherwise cannot have.

### 3. Canonical-vector promotion — **NOT NOW**

Tail-append at index 48 is mechanically clean, but it bumps `SCHEMA_HASH`/`FEATURE_ORDER_HASH`,
re-stales six model families (F-076 precedent: 39→48 staled zone_gate/rr/rr_fusion/gaussian/
bitnet/tradenet) and forces freeze-pin re-certification. No evidence supports paying that yet.
Fence it off explicitly: "promote the layer" must **not** be read as "add to the 48".

---

## Two hypotheses, unequal priors — do not merge them

Measured: `H_atr = 0.885` (vol has memory) vs `H_returns = 0.527` (direction doesn't).

- **Clock → MAE / duration / stop-out rate** — volatility/timing process. Consistent with H_atr.
  Feeds **stop-width calibration**, which F-087 identifies as the cost-dominant axis
  (`cost_r = cost_price/risk_distance`). Never has to beat a directional control. **Viable.**
- **Clock → win_rate / R / TP frequency** — direction process. Runs into H_returns ≈ 0.527, the
  F-019…F-097 ladder, and F-017, which already falsified session policy as a promotable lever on
  BNBUSDT under realistic exits + OOS. **Fifth swing at a missed pitch.**

### Likeliest failure mode is REDUNDANT, not null

`volatility_regime` (idx 30) may already absorb the session effect — London/NY opens *are* the
high-vol states. F-043 precedent: the Markov regime forecaster was statistically real (p ≤ 0.045,
n = 3,645–35,525) and resolved `REGIME_REDUNDANT`, fully explained by current vol level + a stale
lag. So the discriminating question is **"does clock survive conditioning on `volatility_regime`?"**
— not "does clock predict?". A raw weekday comparison cannot tell those apart.

---

## Measurement constraints (if it advances)

- **Population.** Do not stratify the CRT ledger — n ≈ 3 on XAUUSD (F-097), 30 across four crypto
  majors (F-070). Cells are empty before you start. Use F-086's outcome-first every-bar inversion
  (377,256 bar×direction units); costs lookahead-by-construction and caps at Authority rung 1.
- **Metric.** Stratum-**centered** y, fixed before any y is computed. Uncentered marginals
  manufacture effects at a −0.29R base rate — F-097's `htf|long` flipped sign entirely once centered.
- **Family.** 5 weekdays × 3+ sessions × 24 hours needs BH-FDR, not eyeballing.
- **Labels.** `opportunities.jsonl` is a detection stream, 36.8% self-consistent (F-022). Re-derive
  through `multi_tp_walk` (F-088) — `forward_walk` models a different trade object than production
  (one TP, no partial, no trail).
- **Controls.** `long_only` is the binding hurdle (F-097). Single-draw `random_entry` is too noisy
  to gate on (F-084: 100-seed re-draw flipped the verdict).

## Parked by user

F-065 participation confound (`volume_ma20` never emitted → `vol_score` structurally 0.0). Calendar
may be a proxy for participation; not separated in this design. **Declared limitation.**

---

## Verification (when implemented)

1. `venv/Scripts/python.exe -c "from features.feature_schema import SCHEMA_HASH, FEATURE_ORDER_HASH"`
   → must still print `d40e7c7d5b624ef6d27670255ad95a35` / `7901bb0d34f3d0af` (sidecar = hash-neutral).
2. XAUUSD M15 vector SHA unchanged over the full corpus (freeze-pin parity, F-061/F-066 pattern).
3. Both bases exercised: `broker_local` byte-identical to today; `utc_corrected` proves
   `day_of_week` actually moved at the 01:00 boundary (the defect above, regression-pinned).
4. `calendar_periods` reuse proven — no second copy of week/month math.
5. Counter identity: `mins_since_week_open == 15 * bars_since_week_open` on every gap-free M15
   run of bars; every violation localises to a known weekend/holiday gap and nowhere else.
5. `python scripts/maintenance/check_governance_invariants.py --all` (baseline first: the floor
   itself carried 14 failed / 521 passed on a recent branch — capture before, not after).

---
---

# PART II — Envelope schema & linking all designs (theory)

**Separate thread, opened 2026-09-23.** Gathered from source, not designed. **The envelope
already exists.**

## The two halves that exist today

### `src/research/model_runners/contracts.py` — the INPUT half

```python
@dataclass(frozen=True)
class ModelContract:
    model_id: str
    entry_point: str                      # "engines.rr_engine.RREngine.compute"
    input_mode: str                       # features | ohlc | candles | compose | blocked
    spine_active: bool
    requires_artifact_cli: bool
    required_feature_keys: FrozenSet[str]
    phase: int                            # 1=live, 2=compose, 3=off-spine, 9=blocked
    audit_status: str
    description: str
    runnable: bool
```

`MODEL_CATALOG` holds **21 models**, already including every one named:

| model_id | entry_point | spine | phase | audit_status |
|---|---|---|---|---|
| `rr` | `engines.rr_engine.RREngine.compute` | ✓ | 1 | CERTIFIED |
| `gaussian` | `heuristic_gaussian_engine.HeuristicGaussianEngine.compute` | ✓ | 1 | **FLAWED** (F-060) |
| `zone_gate` | `engines.zone_cluster_score.score_zone_cluster` | ✓ | 1 | **REDUNDANT** (F-036) |
| `crt_score` | `engines.crt_engine.compute` | ✓ | 1 | CONDITIONAL |
| `bitnet` | `bitnet.bitnet_inference.bitnet_score` | ✗ | 3 | **DORMANT** (F-004) |
| `tradenet` | `training.trade_net_v2.TradeNetV2.predict` | ✗ | 3 | **UNWIRED** (F-005) |
| `rr_trained` | `rr_pattern_miner.NanoInferenceEngine` | ✗ | 3 | OFF_SPINE (F-044) |
| `fusion_compute` · `decision` · `execution_plan` | compose stages | ✓ | 2 | CONDITIONAL |
| `crt_state_machine` | `crt_engine_v2.CRTEngine.process_candle` | ✓ | 2 | CONDITIONAL |
| `regime` · `trap` · `breakout` | dual-engine voters | ✓ | 1 | CONDITIONAL / CERTIFIED |
| `envelope` · `gaussian_ml` | offline artifacts | ✗ | 3 | EXPERIMENTAL |
| `llm_gate` · `strategies` · `engine_runner` | — | — | 9 | FAILED / DEPRECATED / ORCHESTRATOR |

### `src/research/model_runners/envelope.py` — the OUTPUT half

```python
RunRecord{schema, model_id, instrument, bar_index, timestamp, status, native, error}
RunManifest{schema, authority, PRODUCTION_BEHAVIOR_CHANGED, model_id, instrument,
            config_path, config_sha256, csv_path, csv_sha256, window, feature_schema,
            artifact, config_sections_read, config_keys_read, entry_point, spine_active,
            created_at, summary_stats, n_ok, n_error, run_id, out_dir, code_provenance}
```

`code_provenance` carries `git_sha` / `branch` / `dirty` / counts, and records its own failure
(`available: false` + error) rather than omitting the field — *an absent field and a failed
lookup must not look identical*. That sentence is the whole design philosophy in one line.

## THE THEORY — why this links everything

**The envelope normalizes IDENTITY and PROVENANCE, never SEMANTICS.**

`RunRecord.native` is a free-form dict. Nothing forces `rr`'s polarity, `gaussian`'s kernel
density and `tradenet`'s multi-head logits into a common "score" type — because they are not the
same quantity, and pretending otherwise would be the F-038 error (two engines silently collapsing
into one). Uniform *addressing*, native *meaning*. That is exactly why one envelope can span 21
heterogeneous models without lying about any of them.

### The join graph — already declared, already in source

```
market_ontology.yaml          contracts.py                  audit_status / findings
  FM-031 momentum_score  ──►  required_feature_keys    ──►  model_id  ──►  F-061 / F-060
  (lineage.vector_index)      (declared per model)          (21)          (CLAUDE.md index)
```

Three joins, no inference. That **is** the intelligent-search substrate — it already answers:

- *"Which models consume `momentum_score`?"* → `gaussian`, `regime`, `breakout`
- *"F-061 corrects the FM-022/023 dimensional mix — whose decision surface moves?"* → exactly
  those three, derivable rather than grepped
- *"What is actually live?"* → `spine_active=True ∧ phase≤2` (12 of 21)
- *"What can't run without an artifact?"* → `requires_artifact_cli=True` (4)

The catalog's `audit_status` vocabulary (CERTIFIED / FLAWED / REDUNDANT / DORMANT / UNWIRED /
CONDITIONAL / OFF_SPINE / EXPERIMENTAL / FAILED / DEPRECATED) is the **findings index, projected
onto the model axis**. The link the question asks for is built; it is just not *queried*.

## The extraction job is finding MISSING identity slots

The envelope hashes config, data and code. Every slot it does **not** carry is a place where two
different runs are indistinguishable — the exact silent-gap class this repo keeps rediscovering
(F-056 · F-079 · F-083 · F-085 · F-102). Three are missing:

| Missing slot | Consequence | Evidence |
|---|---|---|
| **`clock_basis`** | `broker_local` vs `utc_corrected` runs are indistinguishable in the manifest | F-066; ties Part I directly to Part II |
| **cost-model identity** | flat-12bps vs `ComponentCostModel` vs `AdverseFill` not recorded; `CostModel` is **absent from `MODEL_CATALOG` entirely** | F-082 (11× too punitive on XAU, free stop fills) |
| **label/outcome-kernel identity** | `forward_walk` vs `multi_tp_walk` — *different trade objects* — produce comparable-looking records | F-088 |

Two runs differing on any of these look identical today. That is the extraction.

## MarketClock as the envelope's NULL BASELINE

This is where the two threads meet, and it is the strongest version of the calendar idea.

Register MarketClock as a catalog entry whose only input is the timestamp:

```python
"market_clock": ModelContract(
    model_id="market_clock",
    entry_point="features.market_clock.MarketClock.compute",
    input_mode="features",
    required_feature_keys=frozenset({"timestamp"}),
    spine_active=False, phase=3,
    audit_status="BASELINE",
    runnable=True,
)
```

A clock-only model reads **no market data at all** — structurally incapable of lookahead, and
therefore the purest available *zero-market-information* control. Its score is the value of
knowing only *when* you are.

That makes it a **measuring instrument for every other model in the catalog**:

> A model that cannot beat `market_clock` has demonstrated no knowledge of the market —
> only knowledge of the calendar.

Stronger than `random_entry` (which F-084 showed is too noisy to gate on: 100-seed re-draw
flipped the verdict) and orthogonal to `long_only` (which prices drift, not timing). It is a
control the catalog currently lacks, and it costs nothing to compute.

**Note the inversion:** this reframes the calendar work from *"does the clock add edge?"*
(fifth swing at the F-019…F-097 pitch) to *"how much of what the other models 'know' is just the
clock?"* — a question with no prior falsification against it, and one that yields a usable answer
whichever way it resolves.
