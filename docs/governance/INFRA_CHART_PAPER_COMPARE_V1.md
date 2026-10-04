# INFRA — Chart · Paper · Broker Compare · V1 (Design Freeze)

| Field | Value |
|---|---|
| **ID** | `INFRA-CPC-V1` |
| **Frozen** | 2026-08-06 |
| **Amended** | 2026-08-06 — §3 Layer V3 FM labels + dual-EMA trap + formation columns (user: amend INFRA FM labels) |
| **Status** | **DESIGN_FROZEN** — no implementation this decision |
| **User lock** | (1) **D** design only for A+B+C · (2) chart payload = bars + CRTState + 8-layer tags + selected FM · (3) ZONE-X = **reference only** |
| **Instrument default** | XAUUSD M15 (aligned VA + MT5 freeze) |
| **ACTIVE_VERSION pin** | `configs/production/ACTIVE_VERSION` (today `v2_multi_2026_04`) |
| **Authority** | Infra design only — **no** promotion, **no** ZONE-X geometry reopen, **no** G001 claim |

Companion: `docs/architecture/goal.md` · `docs/architecture/signal-flow.md` · `ZONE-X-DECISION-2026-08-06.md` · `docs/governance/VALIDATION_ACCESS_VA_XAUUSD_M15.md` · `configs/research/market_story_ontology.yaml` · `active_models.yaml` (CRT intent + state_contracts).

---

## 0. Goal this infra serves

Move toward G001 **using existing INFRA**, with:

1. **Own charts** built from the same OHLC the system consumes (MT5-sourced).
2. **Semantic overlays** so structure is visible (CRT states + story layers + selected features).
3. **Compare** those charts to the **same broker** MT5 charts (parity protocol).
4. **Paper trades** on MT5 demo when the spine reaches a tradable state — noted, designed, not coded here.

Profit is **not** claimed by this freeze. Priorities stay: replay correctness > explainability > telemetry > advisory AI (`goal.md`).

---

## 1. Scope freeze (A · B · C under design D)

| Workstream | Name | In V1 design | Out of V1 |
|---|---|---|---|
| **A** | Own chart renderer | OHLC bars + overlays (below) | Live tick-by-tick UI polish, multi-symbol mosaic |
| **B** | Paper trade on demo | CRT → **EXECUTION** (and optional RESOLUTION close) → MT5 **demo** order | Live money, sizing optimization, multi-broker |
| **C** | Broker compare | Side-by-side / export protocol vs MT5 chart | Pixel-perfect automated screenshot OCR as gate |
| **D** | This document | Freeze only | Code, CI, control-plane commands |

**Implementation order (when authorized later):** A0 (data frame + CRT color) → A1 (8-layer tags) → A2 (FM panel) → C0 (export pack for compare) → B0 (paper adapter) → B1 (link EXECUTION events).  
Do **not** implement B before A0 has a stable bar series hash (compare needs a pin).

---

## 2. ZONE-X (user: treat as reference)

| Rule | Detail |
|---|---|
| **Status** | `ZONE-X-DECISION-2026-08-06.md` path **(a) Stop** remains in force |
| **Role in this infra** | **Reference only** — cost dual-`c`, stop protocol, knowledge transfer |
| **Forbidden** | Geometry/feature search under ZONE-X branding; using ZONE-X g(W) to form CRT states; unsealing test year for chart work |
| **Allowed residual** | Read cost notes; accumulate live stop samples **outside** this chart programme if operator chooses |
| **Parquet link (2026-08-23)** | Window occupancy ledger joined to XAUUSD parquet by timestamp — `results/research/zone_x_parquet_link/`. Calendar overlap is full on opportunities/clean_labels/events; §6 feature-null is NOT_REACHABLE_VIA_PARQUET. Path (a) Stop unchanged. |
| **Docs (root)** | `ZONE-X-SPEC-v0.8.md` · `ZONE-X-DECISION-2026-08-06.md` · `ZONE-X-COST-NOTE.md` · `ZONE-X-KNOWLEDGE-TRANSFER.md` · `ZONE-X-DESIGN-CONTINUATION-v0.9.md` |

CRT states come from **CRT SM + CRTConfig + features**, never from ZONE-X.

---

## 3. Workstream A — Own charts (semantic visual)

### 3.1 Data authority (must match broker feed)

| Layer | Source | Pin |
|---|---|---|
| OHLC | MT5 terminal (same account/symbol as compare) via `src/inout/mt5_candle_fetcher.py` or frozen `data/mt5/XAUUSD_M15.csv` | File sha256 + symbol + TF + broker server |
| Clock | Broker server time as stored; **do not silently relabel** session for chart default | F-066: document `session_timestamp_basis`; chart legend must show basis |
| Features | Production `FeaturePipeline` under ACTIVE_VERSION | Schema hash / FEATURE_ORDER |
| CRT states | `crt_engine_v2.process_candle` stream, config from **production JSON path** (avoid F-057 programmatic split-brain) | Config version + hash |
| Semantic story tags | `market_story_ontology.yaml` + binder (structure maps CRT; other layers descriptive) | Ontology version field |

**Invariant:** Chart series for bar `t` uses only data ≤ `t` (no lookahead). Same generator discipline as spine.

### 3.2 Visual layers (user-selected payload — all three)

#### Layer V0 — Bars
- Candlestick (or OHLC bar) from authority series.
- Volume optional (secondary pane); default on if MT5 tick_volume present.

#### Layer V1 — CRTState color
- Per-bar **background or wick outline** color by `CRTState` after that bar is processed.
- Fixed palette (implement later; freeze names only):

| CRTState | Color token |
|---|---|
| RANGE | `crt.range` |
| SHADOW_PENDING | `crt.shadow` |
| SWEEP | `crt.sweep` |
| DISPLACEMENT | `crt.disp` |
| EXPANSION | `crt.exp` |
| RETEST | `crt.retest` |
| EXECUTION | `crt.exec` |
| RESOLUTION | `crt.res` |
| EXPIRED | `crt.expired` |

- Transition markers: thin vertical tick on bar where state **changes**.
- Legend mandatory on every export.

#### Layer V2 — Full 8-layer story tags
From `configs/research/market_story_ontology.yaml` layers:

| Layer id | Chart affordance (V1 design) |
|---|---|
| **structure** | Primary badge = mapped `crt_state_map` (redundant with V1 color but named for LLM/export) |
| **trend** | Tag chip under bar / hover (uptrend, ranging_trend, …) |
| **liquidity** | Tag chip (sweep_low, stop_hunt, …) |
| **volatility** | Tag chip (compression, expansion_vol, …) |
| **pattern** | Tag chip (bull_flag, failed_breakout, …) |
| **momentum** | Tag chip (momentum_increasing / decreasing) |
| **session** | Tag chip (london / newyork / asian / overlap) — **clock basis labeled** |
| **outcome** | Only when an episode has a closed outcome (paper or forward_walk); not on open live bar |

**Binding rules:**
- **structure** is the only layer with runtime CRT coupling (`crt_state_map`).
- Other layers are **descriptive**; missing tag = `UNKNOWN` / empty, never invent.
- Phase A stories cover 4 families; live chart tags may be **sparse** until a live tagger exists. Design allows:
  - **Mode STORY_FIXTURE:** tags from synthetic library (VA S).
  - **Mode LIVE_PARTIAL:** structure from CRT SM always; other layers only if a registered producer exists (else blank).
- No promotion of descriptive tags to fusion/execution (story ontology authority model).

#### Layer V3 — Selected FM (features) — **frozen default set**

User asked for bars + FM selected and which. Defaults below are **CRT-decision-relevant** FMs (from `state_contracts` + story `feature_signature` + ontology), not the full 39-dim dump.

**Authority for identities:** `configs/formulas/market_ontology.yaml` · vector order `src/features/feature_schema.py` `CANONICAL_FEATURES` · producers `src/features/feature_pipeline.py` (unless noted).  
**Amended 2026-08-06:** every core row carries FM id, vector index (if any), config keys, and formation one-liner (formation-trace discussion).

##### Default FM chart set (`FM_CHART_CORE_V1`)

| FM id | Vector name | Idx | Config knobs | How formed (one line) | Why on chart | Pane |
|---|---|---|---|---|---|---|
| **FM-010** | `body_ratio` | 29 | (structural candle math; gate uses `crt_engine` `body_ratio_min`) | `body_size / candle_range` via `candle_math` | SWEEP/DISP/EXP/RETEST gates | Subplot / tooltip |
| **FM-002** | `candle_range` | 28 | — | `high - low` (v4 rename of `wick_size`) | Sweep / range geometry | Tooltip |
| **FM-041** | `atr` | 13 | `feature_pipeline.atr_period` (default 14) | SMA(true_range)/close — **close-relative** | Scale for ATR thresholds | Subplot / scale |
| **FM-020** | `disp_strength` | 33 | `feature_pipeline.disp_strength_clip_*` | `clip(body_size / (atr * close))` | Displacement narrative / story signatures | Tooltip / subplot |
| **FM-028** | `displacement_atr_ratio` | — / engine meta | CRT path (not always same column as FM-020) | range/ATR multiple (CH-002; **≠ FM-020**) | EXPANSION / CRT strength path | Subplot (label **FM-028**) |
| **FM-027** | `displacement_retrace` | — / engine meta | CRT / derived_math | retrace toward disp.open (**≠** pipeline retest_depth) | RETEST path | Subplot |
| **FM-021** | `retest_depth` | 34 | `feature_pipeline.retest_depth_clip_*` | distance close→**pipeline** ema_fast / (atr·close), gated by retest_flag | Pipeline retest metric; **label distinctly from FM-027** | Subplot |
| **FM-058** | `liquidity_sweep` | 21 | `feature_pipeline.swing_window` (refs) | +1/−1/0 stop-run vs prev swing, close back inside | Event side markers | Marker |
| **FM-059** | `sweep_detected` | 20 | — (derived) | `liquidity_sweep != 0` → {0,1} | Event presence markers | Marker |
| **FM-043** | `ema_fast` | 7 | `feature_pipeline.ema_fast_span` (default **9**) | `close.ewm(span=9).mean()` | Pipeline trend reference (vector truth) | Price overlay (thin) |
| **FM-044** | `ema_slow` | 8 | `feature_pipeline.ema_slow_span` (default **21**) | `close.ewm(span=21).mean()` | Pipeline trend reference | Price overlay (thin) |
| **FM-051** | `hour_of_day` | 32 | `feature_pipeline.session_timestamp_basis` | hour 0–23 from chosen clock | Time root | Chip / tooltip |
| **FM-052** | `session` | 31 | `session_windows_utc` + `session_timestamp_basis` | window model → {0..4} ASIA…CLOSED | Session chips; **legend must show clock basis** (F-066) | Chip |
| **FM-024** | `volatility_ratio` | 14 | (inherits atr period) | `(high-low)/(atr*close)` else 1.0 | Range expansion vs ATR | Tooltip / subplot |
| **FM-050** | `volatility_regime` | 30 | `volatility_percentile_window`, `volatility_tercile_*` | tercile of **absolute** atr_14 rolling rank {0,1,2} — **not** FM-041 | Vol regime story | Chip / tooltip |

##### Dual-name trap — CRT soft-conf EMAs (**not** FM-043/044)

| Chart series id | FM? | Vector slot? | Config | How formed | Pane |
|---|---|---|---|---|---|
| **`crt_live_ema_fast`** | **No FM** | **No** | `crt_engine` / CRTConfig **`ema_fast`** (typical span **2**) | `EngineState.update_emas` in `crt_engine_v2` | Optional **separate** thin overlay — **must not** reuse FM-043 label |
| **`crt_live_ema_slow`** | **No FM** | **No** | `crt_engine` / CRTConfig **`ema_slow`** (typical span **5**) | same | Optional separate overlay — **must not** reuse FM-044 label |

Ontology caveat (FM-043/044): *same bare names, different modules — do not conflate.*  
**Default chart rule:** always plot **FM-043/044** when EMA lines are shown from the feature frame. Plot **`crt_live_ema_*`** only when soft-confirmation context is requested, with distinct color tokens `crt.ema_fast` / `crt.ema_slow`.

##### Related non-vector notes

| Name | Note |
|---|---|
| CRT **SWEEP** state | State-machine outcome — **not** identical to FM-058/059 on every bar; V1 color layer owns CRTState |
| `atr` IND-001 | Descriptive supersession pointer only; production identity is **FM-041** |
| FM-050 vs FM-041 | Regime ranks **absolute** ATR path; vector `atr` is **close-relative** |

##### Explicitly **not** default on chart (until user expands)

| Avoid by default | FM / reason |
|---|---|
| `momentum_score` / `ema_spread` | **FM-023 / FM-022** — saturate on XAU under `atr_relative` (F-060/F-064); use FM-031/030 only if corrected basis activated |
| Full 39-dim heatmap | Cognitive overload; export optional advanced mode later |
| RR / ZoneGate scores | Separate engines; optional later as **score ribbon**, not FM core |
| ZONE-X g-features | Reference only — not chart authority |

##### Expand modes (later, config flags)
- `FM_CHART_CORE_V1` (default table above)
- `FM_CHART_EXTENDED` — add **FM-057** `break_of_structure`, **FM-060** `double_sweep`, **FM-049** `macd_hist_raw`, **FM-053** `macd_hist_z`, **FM-042** `rsi_14`
- `FM_CHART_FULL_VECTOR` — research dump only, not default UI
- `FM_CHART_CRT_EMA` — enables `crt_live_ema_fast/slow` dual overlay (still not FM-labeled)

### 3.3 Chart export artifact (for C and LLM)

```
results/charts/xauusd_m15/<run_id>/
  series.parquet|csv     # time, o,h,l,c,v, crt_state, tags..., fm...
  chart.png|svg          # rendered view
  legend.json            # color tokens + FM list + clock basis
  config_pin.json        # ACTIVE_VERSION, config hash, schema hash, mt5 symbol
  INDEX.md
```

Same dual-surface spirit as VA: human image + machine series separated.

---

## 4. Workstream B — Paper trades (MT5 demo)

| Item | Design |
|---|---|
| **Trigger** | Spine emits CRT **EXECUTION** (not mere SWEEP/RETEST) |
| **Venue** | MT5 **demo** (paper) — ICMarkets-class demo already used for ZONE-X O-1; **note: paper capable** |
| **Sizing** | UltronRiskGate / planner outputs only; no ad-hoc lots in chart code |
| **SL/TP** | From `ExecutionPlanner` / active config — not ZONE-X k,m |
| **Log** | Append-only `results/paper_trades/xauusd_m15.jsonl` + MT5 ticket id |
| **Fail mode** | If terminal down / not demo → **FAIL_CLOSED** (no silent skip to live) |
| **Not in V1** | Auto-management beyond broker SL/TP; multi-position netting |

**Dependency:** B0 requires a single callable “on EXECUTION event” from live/hook path (`live_engine_hook` / engine runner), not a new SM.

---

## 5. Workstream C — Compare with same broker charts

| Step | Protocol |
|---|---|
| C1 | Same symbol, TF, broker account as chart data source |
| C2 | Export `chart.png` + time window [t0, t1] from own renderer |
| C3 | Open MT5 chart same symbol/TF; align visible window to [t0, t1] |
| C4 | Human (or later tool) checklist: bar OHLC match sample of N bars; session open lines if shown |
| C5 | Record `compare_note.md`: PASS / FAIL / UNKNOWN + screenshots paths |
| C6 | **Do not** claim economic edge from visual match |

Known trap: F-066 session labels vs wall-clock UTC — compare **price geometry** first; session chips second with basis labeled.

---

## 6. Flow problems this design acknowledges (not solved by freeze)

| ID | Issue | Design response |
|---|---|---|
| F-057 | CRTConfig split-brain | Chart/paper **must** load via production ACTIVE_VERSION path |
| F-066 | Broker clock | Legend `session_timestamp_basis`; default chart = broker series as stored |
| F-037 | Research fusion off | Chart CRT state = SM path; optional second ribbon for fusion scores later |
| F-060/064 | Saturated momentum/spread | Excluded from FM_CHART_CORE_V1 |
| ZONE-X halt | No geometry hunt | Reference docs only |
| E OPEN | No MC seal | Charts/paper ≠ validated edge |

---

## 7. Semantic / intent links (codebase)

| Concern | Link |
|---|---|
| Happy flow | `docs/architecture/signal-flow.md` |
| Goal | `docs/architecture/goal.md` · G001 in prod config |
| CRT intent + transitions | `active_models.yaml` crt · `state_identity.VALID_TRANSITIONS` · `crt_engine_v2` |
| Feature math | `configs/formulas/market_ontology.yaml` · `src/features/` |
| 8-layer tags | `configs/research/market_story_ontology.yaml` · `src/research/synthetic/` |
| Validation access | `VA-XAUUSD-M15` · `src/validation_access/` |
| MT5 OHLC | `src/inout/mt5_candle_fetcher.py` |
| ZONE-X ref | root `ZONE-X-*.md` |

---

## 8. Non-goals (hard)

- No ZONE-X feature search reactivation.
- No treating chart beauty as G001 proof.
- No mixing Surface “pretty PNG” as sole audit trail (series file is authority).
- No paper trading on live account under this design.
- No full 39-dim default UI.

---

## 9. Acceptance criteria (when implementation is authorized)

| ID | Criterion |
|---|---|
| A-AC1 | Exported series bar OHLC matches source CSV/MT5 for window (sample N≥50 exact) |
| A-AC2 | CRTState per bar reproduces SM on same config pin (hash parity on state sequence) |
| A-AC3 | Legend lists FM_CHART_CORE_V1 **by FM id + vector name** + 8 layer ids + color tokens; CRT EMAs (if shown) use non-FM series ids |
| A-AC3b | Legend never labels pipeline EMA as CRT soft-conf EMA or vice versa |
| A-AC4 | LIVE_PARTIAL never fabricates non-structure tags |
| B-AC1 | Paper order only on demo; ticket logged; refuse if not demo |
| B-AC2 | Trigger only on EXECUTION (configurable allowlist) |
| C-AC1 | Compare pack includes config_pin + window + checklist template |
| Z-AC1 | No ZONE-X geometry module imported by chart/paper code |

---

## 10. Reopen / amend

Amend this freeze only by a new dated decision section or superseding doc.  
Implementation starts only on explicit user authorize (e.g. `build A0` / `build A0-C0` / `build full CPC`).

### Amendment 2026-08-22 — **A0 AUTHORIZED AND BUILT**

User authorized the renderer (build the chart tool, then use it). **Workstream A0 only.**
A1 (8-layer story tags), A2 (FM panel), B (paper trades) and C (broker compare) remain
DESIGN_FROZEN and unbuilt; `legend.json` declares `V2_story_tags:false` / `V3_fm_panel:false`
so an export cannot advertise a layer it does not draw.

**Shipped:** `src/charts/{chart_series,crt_overlay,render}.py` · CLI
`scripts/analysis/render_chart.py` (SITS-registered) · floor `tests/test_chart_series.py`
(38 tests) · optional extra `charts = ["mplfinance"]` in `pyproject.toml`.

**Header pin CORRECTED.** This document's header records `ACTIVE_VERSION` as
`v2_multi_2026_04` (true on 2026-08-06). On `feature/truth-registry-v2` at 2026-08-22,
`configs/production/ACTIVE_VERSION` reads **`v2_htfcrt_2026_08`** (§4.0 Tier 0). Both
statements are correct for their date/branch; the §3.1 rule — load via the production
ACTIVE_VERSION path, never a programmatic config — is what binds, and A0 honours it.

**§9 acceptance status:**

| ID | Status | Evidence |
|---|---|---|
| A-AC1 | **PASS** | 66 sampled bars equal `data/mt5/XAUUSD_M15.csv` exactly; corpus sha256 pinned in `config_pin.json` |
| A-AC2 | **PARTIAL** | states come from a real `BacktestRunner` run under ACTIVE_VERSION via `load_prod_config_from_registry`; engine→base index shift is SOLVED from event timestamps (measured **+62**, unanimous over 2,382 transitions) and fails closed on disagreement. A state-sequence *hash* pin is not yet written |
| A-AC3 | **PASS** | legend lists colour tokens by frozen name + clock basis + state source |
| A-AC3b | **PASS** | legend carries an explicit FM-043/044 vs `crt_live_ema_*` guard (A0 draws neither) |
| A-AC4 | **N/A** | LIVE_PARTIAL/story tags are A1, not built |
| Z-AC1 | **PASS** | enforced by test — no ZONE-X token reachable from `src/charts/` |

**Finding recorded against §3.2 Layer V1 (measured, descriptive):** the per-bar CRTState
colour is **legible only at M15/H1**. CRT is an M15 state machine; on XAUUSD under
`v2_htfcrt_2026_08` it transitions 2,382 times across 47,275 bars (~1 per 20 bars, ~5 h),
so a D1 bucket contains ~5 flips and its close-state is near-random — the rendered chart
is a barcode that *looks* like structure. A0 does not suppress the layer; it measures the
change-rate, sets `legend.crt_aliasing.aliased`, and stamps a WARNING into the image title
(the PNG travels without its legend). Design impact: §3.2's "per-bar background colour by
CRTState" is sound but implicitly assumes the chart timeframe is the state machine's
timeframe. A future A1/A2 pass wanting HTF semantics needs a *bucket-summary* vocabulary
(e.g. "did EXECUTION occur in this bucket"), which is NOT in this freeze.

Authority unchanged: infra only. No promotion, no G001 claim, no economic claim.

---

## 11. Topic track cross-ref

| Topic ID | Update |
|---|---|
| T03 ZONE-X | REFERENCE_ONLY (confirmed) |
| T04 MT5 paper | DESIGNED in §4; not built |
| T05 Semantic charts | DESIGNED in §3; not built |
| T06 Goal infra | This freeze is the infra plan |
| T07 CRT states | §3 V1 + SM links; ZONE-X not a source |

---

## 12. One-line summary

**Design D freezes:** own MT5-pinned charts with **CRTState colors + 8-layer tags + FM_CHART_CORE_V1** (every row FM-id labeled; CRT live EMAs non-FM optional), demo **paper on EXECUTION**, broker **compare protocol**, ZONE-X **reference only** — **no code until authorize.**
