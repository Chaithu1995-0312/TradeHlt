# Draw the 122-field structural record on our own charts + capture it into forensic sidecars

## Context

We emit a complete per-bar structural record — `logs/bar_structure/XAUUSD_bar_structure.jsonl`,
**47,275 rows / 181 MB**, 78 WARMUP rows (23 fields) then full rows (122 fields), produced by
`src/runtime/bar_structure_snapshot.py` via `scripts/research/emit_bar_structure_snapshots.py`
under the v3 config's `bar_structure_snapshot` section (CH-v3-unified-market-structure-v1).

Right now **nothing draws it**. `src/charts/` renders bars + a single CRTState colour layer;
`tools/tv_forensic/` records OHLC and pixel geometry with 7 hand-curated, self-declared
`SUPERSEDED` annotation markers. The structural record is written and never seen.

**Goal, per user:** draw the structural layers on **our own charts** (`src/charts/`), and
separately **capture** the same rows into the **TradingView forensic sidecars** so a shot
carries the structural state of every bar it shows.

Prior turns established: the file the user is reading is a slice of the full corpus file (78
WARMUP matches exactly), and the join is mechanically straightforward because
`capture_tv.py:299` already performs timestamp → epoch → containing-bar → pixel-x resolution.

## GOVERNANCE GAP — read before implementing

`src/charts/` is governed by a **design freeze**:
`docs/governance/INFRA_CHART_PAPER_COMPARE_V1.md` (INFRA-CPC-V1, frozen 2026-08-06, amended
2026-08-22 "A0 AUTHORIZED AND BUILT").

That freeze declares exactly two future layers, and **neither is what the user asked for**:

| Frozen layer | Source it declares | Is it the 122 fields? |
|---|---|---|
| Layer V2 — 8-layer story tags | `configs/research/market_story_ontology.yaml` (structure/trend/liquidity/volatility/pattern/momentum/session/outcome) | **No** |
| Layer V3 — FM panel | `FM_CHART_CORE_V1` feature identities | **No** |

The snapshot vocabulary — parent-CRT 12-state sub-graph (F-075), `htf_state` (F-078),
objective status (F-078), 4× SMC zone families (F-076) — **postdates the freeze**. Drawing it
is a **new layer**, not the completion of A1/A2.

**Therefore step 0 is an amendment to INFRA-CPC-V1 §10 declaring "Layer V4 — structural
snapshot", not silent invention inside `src/charts/`.** The doc has an explicit Reopen/amend
path and the user is the authority; this is a declare-then-build sequencing requirement
(§6.6 ontology-first, §6.8 no-silent-remediation), not a blocker.

## Part 1 — Draw on our own charts

### 1a. Amend the design authority
`docs/governance/INFRA_CHART_PAPER_COMPARE_V1.md` — add a §10 amendment declaring Layer V4:
its source (`bar_structure_snapshot` stream), its field groups, its per-shot selectability,
and that it is **additive to** and **does not implement** V2/V3. Keep A1/A2 marked unbuilt.

### 1b. Extend the legend-honesty mechanism (non-negotiable)
`src/charts/chart_series.py:278` `build_legend()` already declares
`"V2_story_tags": False` / `"V3_fm_panel": False` so *an export cannot advertise a layer it
does not draw*. Add `V4_structural` with the **per-group** truth (which of CRT / parent /
HTF / objective / SMC / liquidity / structure were actually drawn on this render), not a
single bool. Extend `write_export_pack()` (`:317`) so `INDEX.md` names the snapshot file +
its `run_id` / `corpus_sha256` / `config_version`.

### 1c. Load + join
New module `src/charts/structural_layer.py` (keeps `render.py` a drawing layer):
- **Stream-scan** the JSONL filtered to the chart's timestamp window. Do **not** load 181 MB
  to draw 300 bars.
- Join on `timestamp`; carry `bar_index` / `engine_candle_index` for cross-checks.
- **Assert `timestamp_basis` agreement** between snapshot rows and `config_pin`
  (`session_timestamp_basis`). Fail closed on mismatch — F-066 makes this a real hazard.
- Reuse the existing fail-closed precedent: `crt_overlay.py`'s engine→base index shift is
  measured and unanimous-or-fail. Mirror that posture, do not invent a new one.

### 1d. Draw — two visually different kinds, do not conflate
1. **Price-geometry layers** (SMC zones ×4, liquidity EQH/EQL + PDH/PDL). These are
   *rectangles and levels in price space* — `high`/`low`/`mid`, `width_atr`, `age_bars`.
   They render correctly **at any timeframe** because they are price objects, not per-bar
   categories.
2. **Per-bar categorical layers** (parent_crt_state, htf_state, objective_status, CRT
   action/direction). These carry **the exact aliasing hazard already measured for V1** —
   the amendment records that per-bar CRT colour is legible only at M15/H1 (2,382
   transitions over 47,275 bars; a D1 bucket holds ~5 flips and renders a barcode that
   *looks* like structure).

   → **Every new per-bar categorical layer must route through the existing
   `crt_aliasing()` treatment**: measure change-rate, set an `aliased` flag in the legend,
   and stamp the warning into the image title (`render.py:64` — the PNG travels without its
   `legend.json`). Do not add a categorical layer that skips this.

### 1e. CLI
`scripts/analysis/render_chart.py` — add `--structural <group,group,...>` (default `none`),
groups being `crt,parent,htf,objective,smc,liquidity,structure`. Thin-wrapper rule (§3.3)
holds: argv parsing only, all decisions in `src/charts/`.

## Part 2 — Capture into the forensic sidecar

**Sidecar only. No new drawing on TradingView shots** (per user).

`tools/tv_forensic/capture_tv.py` — the machinery exists; this is a **source swap**, not new
plumbing. At `:299` it loops `plan["engine_events"]` and per entry resolves epoch → containing
TV bar → `x` / `in_frame` / `exact_bar` / `engine_ohlc` / `tv_ohlc`.

- Add a `structural_rows` sidecar key populated from the snapshot stream filtered to the
  shot's achieved window, reusing that same resolution path.
- Size is fine: ~3.8 KB/row × ~300 on-screen bars ≈ 1.1 MB per shot.
- **Do not hand-convert times.** `capture_tv.py` resolves the broker↔UTC offset by
  measurement (−12..+12h, refuses unless the winner beats runner-up 5×; Jul 2026 → UTC+3,
  MAE 0.371 vs 38.679) because per F-066 the MT5 server tracks *US* DST. Assert the
  snapshot's `timestamp_basis` against the resolved clock; fail closed.
- **Retire the SUPERSEDED markers.** `engine_events_provenance` self-reports
  `"status": "SUPERSEDED"` (pre-F-074 run). Once real rows are attached, mark the 7
  hand-curated events superseded-in-place (§6.2 rule 4 — never delete) and point them at
  `structural_rows`.

## Files

| File | Change |
|---|---|
| `docs/governance/INFRA_CHART_PAPER_COMPARE_V1.md` | §10 amendment declaring Layer V4 (**do first**) |
| `src/charts/structural_layer.py` | NEW — windowed load, join, `timestamp_basis` assertion |
| `src/charts/render.py` | draw V4; route categorical layers through `crt_aliasing()` |
| `src/charts/chart_series.py` | `build_legend()` per-group V4 truth; export pack provenance |
| `scripts/analysis/render_chart.py` | `--structural` flag |
| `tools/tv_forensic/capture_tv.py` | `structural_rows` sidecar key; supersede old events |
| `tests/test_chart_series.py` | extend the 38-test floor |

## Verification

1. `pytest tests/test_chart_series.py tests/test_tv_forensic_smoke.py`
2. **Legend honesty:** render with `--structural none` → every V4 group `false`; render with
   `--structural smc` → only `smc` true. An export must never advertise an undrawn layer.
3. **Aliasing:** render `--timeframe D1 --structural parent,htf` → confirm the `aliased` flag
   sets and the title warning is stamped (this is the V1-measured failure mode recurring).
4. **Join integrity:** pick a known EXPANSION bar (user's example: SHORT, parent H4 `RANGE_C1`,
   `htf_state` REVERSAL, bearish FVG 63 bars old / 0.58 ATR wide / 0.68 ATR away, not inside)
   and confirm the drawn zone's price box matches the row's `fvg_high`/`fvg_low`.
5. **Clock fail-closed:** feed a snapshot with a mismatched `timestamp_basis` → must raise,
   not silently draw.
6. **tv_forensic:** `capture_tv.py --preset jul28-long`, confirm `structural_rows` count
   equals on-screen bar count and timestamps align to `bars[].t`.

## Authority (hard)

Infra only. `bar_structure_snapshot` is **OBSERVATION_ONLY** (§6.5) and
`context_attribution.promoted_families` is enforced-empty. Drawing structural state grants
**no economic claim, no G001, no promotion** — a convincing picture is not evidence. F-097
already returned a powered null (0/22) on this vocabulary's incremental value.
Z-AC1 still holds: no ZONE-X import reachable from `src/charts/`.
