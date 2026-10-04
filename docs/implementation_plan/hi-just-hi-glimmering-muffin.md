# MarketClock — cached schema + whole design

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

Classification: **incomplete F-066 migration**, dormant. Needs a §6.2 drift decision + a finding
row before any clock counters are built on top of it.

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
is_week_open / is_week_close
```

Reuses `calendar_periods` verbatim for every boundary; adds no new calendar math.

**Unresolved spec decision (blocking):** `bars_since_*` counts *bars* or *elapsed time*. They
diverge exactly at weekend/holiday gaps — i.e. precisely at the boundaries of interest. Bars is
deterministic and gap-agnostic; elapsed time is economically meaningful but needs a gap policy.
Pick one and declare it; do not leave it implicit.

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
5. `python scripts/maintenance/check_governance_invariants.py --all` (baseline first: the floor
   itself carried 14 failed / 521 passed on a recent branch — capture before, not after).
