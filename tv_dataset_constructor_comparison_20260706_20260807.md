# TV-Forensic ↔ Dataset-Identity ↔ Constructor-Trace Comparison

**Window:** XAUUSD M15, 2026-07-06 → 2026-08-07 (broker time) · **Corpus:** `data/mt5/XAUUSD_W2026-07-06-to-2026-08-07.csv` (2,300 bars)
**Dataset:** `XAUUSD_MT5_TVWINDOW_20260706_20260807` (R3, `decision_status: UNRESOLVED`)
**Scope:** `economic_claims_allowed: false` · no G001 · no promotion · `OHLCV_CLOSURE_STATUS` unchanged `BLOCKED:BC-1..BC-6`

---

## 1. Provenance

| Field | Value |
|---|---|
| Requested path | `data/mt5/XAUUSD_W2026-07-06-to-2026-08-07.csv` |
| **Resolved path** | same — admission Step 1 (exact canonical match), **not rewritten** |
| sha256 | `dcaf88a76b927d530924be4dc1f8dda4fcba431725099a8db4f1dfd806e8a78b` |
| Rows / range | 2,300 rows · 2026-07-06 01:00:00 → 2026-08-07 23:45:00 (broker) |
| Fetch source | live MT5 (ICMarketsSC-Demo, terminal build 6140), same session/terminal as the F-098/F-099 BC-2/BC-4 probes |
| `clock_basis` | `broker_local` (F-066 — **not** laundered to UTC) |
| `volume_semantic` | `TICK_VOLUME_APPROXIMATE` (F-099's measured verdict for this producer family; **not independently re-verified for this specific window** — carried as the honest expected value, not a transferred proof) |
| `decision_status` | `UNRESOLVED` — never Phase-1-validated |
| Registered under | R3 Dataset Identity, `docs/governance/datasets/XAUUSD_MT5_TVWINDOW_20260706_20260807.json` |

**Silent-redirect check (the 2026-08-30 class):** this report prints the *resolved* path, not only the requested one. `admit_csv_path` was exercised for real for the first time with two bound XAUUSD records; the new file is addressed by its explicit canonical path and correctly bypasses the legacy `XAUUSD_M15*` rewrite heuristic (Step 1 beats Step 2). Verified by direct call before use, not assumed.

**A destructive near-miss during this run, corrected:** `fetch_and_verify_mt5.py`'s default output path (`{out_dir}/{symbol}_{tf}.csv`) collided with the frozen Phase-1 candidate's own path when both used `data/mt5/` as the output root, **overwriting the frozen file's bytes**. Caught immediately (sha changed from `4d73f5ce…` to `dcaf88a7…`), recovered from a byte-identical copy retained in a prior test run's pytest tmp directory, and re-verified against `verify_phase1_frozen_candidate()` before continuing. The fresh fetch was preserved separately, clock-declared, and renamed to the `XAUUSD_W<first>-to-<last>` convention (`export_xauusd_window.py::_out_name`'s own established pattern) specifically so it never collides with `is_xauusd_m15_request`'s rewrite heuristic or the L2 filename parser again.

**Independent-refetch check:** the 2,116 bars overlapping the older one-month export (`data/XAUUSD_M15.csv`, now declared FORENSIC on this record) show **0 field mismatches** across open/high/low/close/volume. The fresh fetch adds 184 bars of padding (Jul 6 + Aug 7) beyond that file's range.

---

## 2. Integrity

Strict `dataset_integrity.validate_dataset` (the `strict_fetch` override — zero tolerance for tradable-bar gaps):

```
decision: APPROVE
rows: 2300
hard_failures: []
```

No tradable-bar gaps. Clock declared via `review_ohlcv_clocks.py --review` (`MT5_SERVER_NY_DST`, advisory-only per the tool's own authority model — a single series cannot self-confirm DST/offset).

---

## 3. Consumption trace — who / how / why

Two independent consumers read the same CSV; verified against current source, not from a prior session's cached narrative.

### 3a. Engine path (production decision surface)

```
CSV → CandleLoader.__init__ → admit_csv_path (R3) → dataset_integrity L1/L2/L3
    → stream() → Candle → CRTEngine.process_candle → StateMachine (8 try_* methods)
    → ExecutionEngine → events.jsonl / crt_telemetry.jsonl / trades.csv
```

- `process_candle(self, candle: Candle, htf_candle_id, ...)` (`crt_engine_v2.py:2841`) takes a raw `Candle` — **no feature vector parameter**. ATR is computed from the engine's own candle buffer; EMAs update from `candle.close` directly.
- The 48-dim canonical vector (schema v5.0, F-076) is pulled **only** inside `if "TRADE_OPENED" in action` (`backtest_v2.py:2610` → `:2654 .tolist()`), i.e. after a trade already exists — for scoring/RR/telemetry, never as an input to the state machine's transitions.
- `StateMachine` (`crt_engine_v2.py:1056-1849`) has exactly 8 `try_*` transition methods: `try_range_to_sweep`, `try_range_to_shadow_pending`, `try_shadow_pending_to_expansion`, `try_sweep_to_displacement`, `try_displacement_to_expansion`, `try_expansion_to_retest`, `try_retest_to_execution`, `try_execution_to_resolution`. This geometry — not the enum or the branch sites — is where the actual decision logic lives (confirmed in the 2026-08-31 CRT-rewrite-cost measurement: 887 of 981 StateMachine lines are inside these 8 methods).

### 3b. Resolver path (declarative meaning layer, F-069's subject)

```
CSV → FeaturePipeline.run() → 48-dim vector + enriched columns → FeatureStateEncoder
    → CRTStateResolver.resolve() → per-bar ontology occupancy
```

- `FeaturePipeline.run()` (`feature_pipeline.py:1437`) returns the enriched DataFrame and the canonical vector matrix — schema v5.0, 48 dims.
- `CRTStateResolver` (`crt_state_resolver.py:413`) owns its own `FeatureStateEncoder` instance and resolves state purely from declared `when:` predicates over feature states — a **different construction** from the engine's geometry-driven state machine, not a mistuned copy of it (F-069's own finding, re-confirmed on this window in §5 below).

### 3c. L1/L2/L3 dataset-integrity gate (`dataset_integrity.py`)

Numbered stages inside `validate_dataset`: **1** path consistency (`:310`) → row/OHLC/NaN checks (L1) → **5** timeframe consistency (`:379`) → **6** missing-candle session-aware threshold gate (L2, `:398`). L3 (cross-file) is a separate, independently-evolving layer per the module's own header comment (`:84-87`).

---

## 4. Live drill — both constructors, decision-neutrality proven

Driver: [`scripts/research/emit_dual_construction_trace.py`](scripts/research/emit_dual_construction_trace.py) (new, this session), three isolated-config-root arms via `src/utils/isolated_config_root.py`, comparison logic imported from `scripts/analysis/v3_config_parity.py::compare` (not reimplemented). `ACTIVE_VERSION` confirmed `v2_htfcrt_2026_08` on disk before and after.

| Arm | Config | Emitters |
|---|---|---|
| A | `v2_htfcrt_2026_08` (active) | — |
| B | `v4_dual_construction_2026_09` | both OFF |
| C | `v4_dual_construction_2026_09` | both ON |

**Decision-neutrality proof:**

```
A vs B: events.jsonl OK (byte-identical, 72,740 bytes) · crt_telemetry.jsonl OK (65,185 bytes) · trades.csv both absent · summary.json OK
B vs C: events.jsonl OK (byte-identical, 72,740 bytes) · crt_telemetry.jsonl OK (65,185 bytes) · trades.csv both absent · summary.json OK
```

Both `bar_structure_snapshot` (122 structural fields/bar) and `crt_construction_trace` (engine + resolver + gate trace/bar, `injection` hard-pinned to `"none"`) are decision-neutral on this corpus, holding the same guarantee `v3_config_parity.py` established on the frozen 2-year candidate.

**Non-vacuity:** both streams wrote exactly 2,300 rows — one per corpus bar (78 WARMUP + 2,222 LIVE), matching corpus size exactly.

**Zero trades on this window** — expected, not anomalous: F-086/F-087 measured ~0.18 expected executions per 2,116 bars on the frozen corpus; this 2,300-bar window is an unremarkable slice by that base rate.

Streams: `logs/dual_construction/XAUUSD_bar_structure.jsonl`, `logs/dual_construction/XAUUSD_crt_construction.jsonl`.

---

## 5. Arm 2 — Engine vs Resolver (whole window)

```
LIVE-only agreement: 1,551 / 2,222 = 69.80%
```

Below F-069's 88.16% (measured on the full 2-year corpus) — **not** far above it, so the `crt_construction_trace` injection guard (RISK 1: agreement far above 88.16% would signal a leaked engine-state injection) is satisfied; no defect signal from that angle. The gap vs F-069 is not itself surprising — this is a different, much smaller (2,300 vs 47,275 bars), out-of-sample window; no claim is made that the two numbers are directly comparable without controlling for population.

Full confusion matrix (engine → resolver), LIVE bars only:

| Engine | Resolver | Count | |
|---|---|---:|---|
| RANGE | RANGE | 807 | AGREE |
| SWEEP | SWEEP | 647 | AGREE |
| EXPANSION | RANGE | 345 | DIVERGE |
| EXPANSION | SWEEP | 187 | DIVERGE |
| EXPANSION | EXPANSION | 75 | AGREE |
| EXPANSION | DISPLACEMENT | 65 | DIVERGE |
| RANGE | DISPLACEMENT | 46 | DIVERGE |
| DISPLACEMENT | DISPLACEMENT | 22 | AGREE |
| SWEEP | DISPLACEMENT | 18 | DIVERGE |
| SWEEP | RANGE | 5 | DIVERGE |
| RANGE | SWEEP | 2 | DIVERGE |
| RETEST | SWEEP | 1 | DIVERGE |
| RETEST | RANGE | 1 | DIVERGE |
| EXPANSION | SHADOW_PENDING | 1 | DIVERGE |

**On this window the EXPANSION-disagreement is one-directional**, not the bidirectional signature F-097 reported on the full corpus: `EXPANSION(engine)→RANGE(resolver)` under-fire = 345, but `RANGE(engine)→EXPANSION(resolver)` over-fire = **0**. This is stated as an observation specific to this window, not a revision of F-097 — the two corpora differ enormously in size and are not a matched comparison.

---

## 6. Arm 1 — Bars vs TradingView (7 shots, existing sidecars reused, none re-captured)

| Shot | TF | Window (broker) | Status | Mean abs err | Notes |
|---|---|---|---|---:|---|
| `03_h4_jul27_31` | H4 | Jul27 00:00 → Jul31 23:45 | DIVERGENT | 0.998 | 2 divergent bars, both at **broker 00:00** (H4 daily-open slot) |
| `04_m15_jul28_forensic` | M15 | Jul28 03:45 → Jul30 08:00 | DIVERGENT | 0.395 | 1 divergent bar at **broker 01:00** (M15 daily-open slot) |
| `05_m15_jul28_displacement` | M15 | Jul28 04:00 → Jul28 07:00 | OK | 0.339 | |
| `06_m15_jul30_trade` | M15 | Jul30 06:45 → Jul30 08:00 | OK | 0.295 | |
| `07_m15_jul15_episode` | M15 | Jul15 02:45 → Jul15 23:00 | OK | 0.378 | |
| `08_m15_jul20_episode` | M15 | Jul20 09:00 → Jul20 18:00 | OK | 0.283 | |
| `09_h4_jul15_20` | H4 | Jul14 20:00 → Jul21 08:00 | DIVERGENT | 0.894 | 2 divergent bars at **broker 00:00**; 12 `NO_ENGINE_BAR` bars Jul18–19 |

**All three DIVERGENT verdicts trace to the pre-existing F-080 daily-open artifact** (engine's first print of the trading day lands after OANDA already traded the session-open gap) — not a new defect: every divergent bar sits exactly on the documented H4-00:00 / M15-01:00 slot, and the open field dominates the delta in every case (e.g. shot 04: open Δ=5.82 vs H/L/C Δ≤1.7). Re-checked, not re-derived: this window reproduces F-080's signature rather than contradicting it.

The 12 `NO_ENGINE_BAR` rows in shot 09 (Jul18 00:00 → Jul19 20:00, every 4h slot) are the expected weekend closure for gold — not a defect, and not counted toward the divergence figure above (F-080's own methodology excludes non-tradable slots).

---

## 7. Arm 3 — LLM narration (descriptive, no gate)

Per the user decision this session: **not scored, no kappa, no pass/fail, no fidelity claim.** Recorded as a third column beside engine/resolver, from a genuine visual read of each shot's raw (non-annotated) PNG.

**Honesty caveat, stated plainly rather than concealed:** this narration is **not blind** in the strict sense the plan specified. Arm 2 (engine-vs-resolver, §5) was computed and viewed in this same session *before* these images were read. The narration is still a genuine visual read of the picture alone — no sidecar JSON, no engine/resolver value was consulted while looking at any image — but it cannot be presented as an independent blind label the way a separately-run human or model session would provide. This limitation is inherent to doing narration and mechanical analysis in one continuous session, not a shortcut taken quietly.

Full segment-by-segment narration: `results/tv_structure_comparison/narration.json`. Summary (last structure seen, broker time, read off chart tick marks ± 15–30 min):

| Shot | Last structure narrated (broker) |
|---|---|
| `03_h4_jul27_31` | ~Aug01 02:45 — "declining off the Jul30 high, no new base formed" |
| `04_m15_jul28_forensic` | Jul30 08:00 — "declining / distribution, no new base formed" |
| `05_m15_jul28_displacement` | Jul28 07:00 — "post-displacement pullback, unresolved" |
| `06_m15_jul30_trade` | Jul30 08:00 — "stop-hunt wick at the bottom, closing off the low" |
| `07_m15_jul15_episode` | Jul15 23:00 — "declining off a double-top, no new base yet" |
| `08_m15_jul20_episode` | Jul20 18:00 — "small recovery bounce off a fresh low, unresolved" |
| `09_h4_jul15_20` | Jul21 08:00 — "recovering rally off the multi-day low, still climbing" |

---

## 8. Arm 4 — "till this time": your worked example, mechanized

For each shot: the engine's last state transition at/before the window end, the resolver's last transition, and the last narrated structure — the exact question "the screenshot shows structure through *this* time; what did the engine say?"

| Shot | Last engine transition | Last resolver transition | Last narrated | Mechanical classification* |
|---|---|---|---|---|
| `03_h4_jul27_31` | Jul31 23:45 → **RANGE** | Jul31 23:45 → **RANGE** | Aug01 02:45 — declining | TIMING_DIVERGENT |
| `04_m15_jul28_forensic` | Jul30 02:45 → **RANGE** | Jul30 02:45 → **RANGE** | Jul30 08:00 — declining | TIMING_DIVERGENT |
| `05_m15_jul28_displacement` | Jul28 05:00 → **SWEEP** | Jul28 05:00 → **SWEEP** | Jul28 07:00 — pullback | TIMING_DIVERGENT |
| `06_m15_jul30_trade` | Jul30 06:45 → **RANGE** | Jul30 06:45 → **RANGE** | Jul30 08:00 — stop-hunt | TIMING_DIVERGENT |
| `07_m15_jul15_episode` | Jul15 21:45 → **SWEEP** | Jul15 21:45 → **SWEEP** | Jul15 23:00 — declining off double-top | TIMING_DIVERGENT |
| `08_m15_jul20_episode` | Jul20 14:45 → **RANGE** | Jul20 14:45 → **RANGE** | Jul20 18:00 — recovery bounce | TIMING_DIVERGENT |
| `09_h4_jul15_20` | Jul21 08:00 → **SWEEP** | Jul21 08:00 → **SWEEP** | Jul21 08:00 — recovering rally | TIMING_DIVERGENT |

\* Produced by `tv_structure_comparison.py`'s literal-substring classifier (does the CRT state name appear inside the narration text). **All 7 read TIMING_DIVERGENT — this is a vocabulary-gap artifact of the classifier, not 7 real disagreements.** Trader-language narration ("declining", "stop-hunt", "recovery bounce") never naturally reaches for the engine's exact state tokens (RANGE/SWEEP/DISPLACEMENT/…), so a substring match fails even when the underlying read is compatible. A qualitative re-read of each pair:

- **Genuinely worth flagging (3/7):** `03`, `04`, `06` — engine and resolver both call the window's final state **RANGE** while the visual read is a *sustained one-directional move* (a continuing decline in 03/04, an uninterrupted drop to a stop-hunt wick in 06). RANGE ordinarily implies consolidation, not persistent direction. This is a real candidate for the same F-069/F-097 "different construction" signature — engine/resolver may be tracking a specific narrow sub-range invisible in a compressed screenshot, or this may be a genuine construction gap. Not adjudicated here; flagged as the concrete next question.
- **Plausibly compatible (4/7):** `05`, `07`, `08`, `09` — a SWEEP label sitting at or just before a described reversal/pullback/rally-off-a-low is not inherently contradictory; without a frozen CRT-state↔trader-language dictionary (which does not exist in this repo), "compatible" is the honest ceiling of this comparison, not "confirmed agreement".

**No such dictionary should be built retroactively to make this table look cleaner** — that would be exactly the kind of post-hoc rigging the repo's epistemic discipline exists to prevent. If a real Arm-4 verdict is wanted, it needs its own pre-registration (a frozen state↔language mapping, agreed before any narration is scored against it), the same discipline the blind-label programs already follow.

---

## 9. Scope ceiling

- One instrument (XAUUSD), one window (2,300 M15 bars), one config epoch (`v2_htfcrt_2026_08` / `v4_dual_construction_2026_09`, identical `params` hash).
- `economic_claims_allowed: false`. No G001. No promotion. No `ACTIVE_VERSION` change (confirmed `v2_htfcrt_2026_08` throughout).
- `OHLCV_CLOSURE_STATUS` unchanged: `BLOCKED:BC-1..BC-6`. BC-2/BC-4 evidence (F-098/F-099) attaches to the Phase-1 hash `4d73f5ce…` only and **does not transfer** to this window's hash `dcaf88a7…` as a proof — only as the honest expected value, stated as such in §1.
- `decision_status: UNRESOLVED` on the new dataset record — never Phase-1-validated, not APPROVED, not AUTHORITATIVE.
- Narration (§7) is descriptive only, not blind in the strict sense (stated plainly, not concealed), and not run under either frozen blind-label pre-registration.
- Not fixed, recorded as a finding for separate authorization: `run_crt_state_on_mt5_xauusd.py` reads its CSV via bare `pd.read_csv`, bypassing R3 admission entirely (same silent-gap class as F-056/F-079/F-083/F-085).

---

## Artifacts

| Artifact | Path |
|---|---|
| Fresh corpus | `data/mt5/XAUUSD_W2026-07-06-to-2026-08-07.csv` |
| Dataset record | `docs/governance/datasets/XAUUSD_MT5_TVWINDOW_20260706_20260807.json` |
| Clock declaration | `configs/data_provenance/ohlcv_clock_registry.json` |
| Dual-construction driver | `scripts/research/emit_dual_construction_trace.py` |
| Bar-structure snapshot (122 fields/bar) | `logs/dual_construction/XAUUSD_bar_structure.jsonl` |
| Construction trace (engine+resolver+gates/bar) | `logs/dual_construction/XAUUSD_crt_construction.jsonl` |
| Run summary | `logs/dual_construction/XAUUSD_dual_construction_run_summary.json` |
| Comparison driver | `scripts/research/tv_structure_comparison.py` |
| Narration (Arm 3) | `results/tv_structure_comparison/narration.json` |
| Full per-shot comparison (Arms 1/2/3/4) | `results/tv_structure_comparison/comparison.json` |
| Kept scratch roots (3 backtest arms) | `logs/dual_construction/scratch_roots/` |

## Registry/code changes this session (Phase 1 — R3 generalized to multi-dataset)

| File | Change |
|---|---|
| `docs/governance/dataset_identity.schema.json` | + `TICK_VOLUME_APPROXIMATE` enum value, + optional `legacy_rewrite_target` |
| `src/data_ingestion/dataset_registry.py` | Phase-1 pin scoped from symbol to `dataset_id`; generic hash-verify for other records; `admit_csv_path` 4-step resolution (exact match → legacy rewrite → forensic → passthrough); `load_bound_datasets` fails closed on >1 legacy target |
| `docs/governance/datasets/XAUUSD_MT5_PHASE1_20260521.json` | + `legacy_rewrite_target: true` (behaviour-preserving — verified against all 16 pre-existing tests, unmodified) |
| `tests/test_dataset_registry.py` | 16 pre-existing tests pass unmodified + 8 new (two-record load, explicit-path routing, ambiguous-legacy fail-closed, bad-hash fail-closed, generic `resolve_canonical`, new enum value) + 1 necessarily-updated assertion (registry now legitimately holds 2 records, not 1) |
