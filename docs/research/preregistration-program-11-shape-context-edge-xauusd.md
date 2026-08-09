# Pre-Registration — Program 11 (Semantic Shape/Context Directional Edge, Clean-Substrate Re-test, XAUUSD)

> **Status:** FROZEN — owner-signed 2026-07-24 (AskUserQuestion "Sign off — freeze & run B1").
> protocol_hash + `.json` twin generated at freeze. Written before any run. Authority: research/docs
> only (§6.5 Authority Ladder). This
> FREEZES the hypothesis, target, direction rule, thresholds, execution construction, controls, and
> closure rule **before** results exist, so a null cannot be re-spun and a hit cannot be
> threshold-shopped. Enforced by the Epistemic Integrity ritual (Program E-001).

## Context & scope

Track B of the semantic-layer program. The user distrusts the legacy entry-info nulls
(F-019…F-041) because they sit on contaminated substrate — F-022 (opportunities.jsonl labels 36.8%
self-consistent), F-051 (centered-swing PIT leak, 10/38 dims), F-037 (research spine was CRT-only,
fusion gate OFF), F-044/F-038 (RR gate mis-spec). This program **re-derives** the verdict on a
clean substrate rather than inheriting it: does the semantic Market-Shape layer
(`MarketShapeClassifier`, Layer 5) carry a directional edge on XAUUSD, net of cost, through the
**unchanged** M4 gate — using clean forward-walk labels and PIT-clean features?

It **updates** F-023 (KMeans morphology separates shape not expectancy, BNBUSDT) and F-041B (zone
labels contaminated) as priors — it never cites them as settled premises. Different instrument
(XAUUSD), different method (content-addressed shapes, not KMeans), fresh clean labels ⇒ the verdict
cannot inherit their substrate.

**FM-030 role (A2a outcome, 2026-07-24).** The FM-030 trend bands are persistent, adjacency-ordered
structural regimes but their forward-return semantics do **not** replicate across years (2024
inverted-U / 2025 increasing / 2026 flat; see `results/research/fm030_band_validation.json`,
session log, held finding F-062). Therefore FM-030 enters this program ONLY as a **neutral
structural trend-strength level** (L0…L4, no directional-payoff implication) and is **reserved for a
secondary conditioning extension (11b)** — the primary test (11a) is the shapes' own declared
direction. No ontology freeze is assumed (A2b declined).

## Universe (frozen)

| Instrument | Data | Coverage |
|---|---|---|
| XAUUSD (M15) | `data/mt5/XAUUSD_M15.csv` | 2024-05-22 → 2026 (47,197 pipeline bars) |

XAUUSD-only by owner standing instruction. **Cost caveat registered up-front (F-035):** 12 bps is
large relative to the median XAUUSD M15 bar, so a negative Stage-2 magnitude may be cost-dominated;
a **0 bps sensitivity twin** is run so the *direction* of any null is robust to cost.

## Hypothesis 11a (frozen, PRIMARY)

The directionally-named Market Shapes, entered in their **declared** direction, carry positive net
expectancy through the M4 gate.

- **Signal source (pure `detect()`):** classify `window[-1]` via `MarketShapeClassifier`
  (`classify_vector`). Emit a `Signal` iff the coarse shape name is one of the frozen directional
  set below; the direction is the shape's **pre-declared, non-fitted** bias (from the shape name /
  `market_shapes.yaml`), never chosen after seeing returns.

| Shape (coarse) | Declared direction |
|---|---|
| BullishBreakoutExpansion | long |
| BearishBreakoutExpansion | short |
| BullishStructuralBreak | long |
| BearishStructuralBreak | short |
| BuySideLiquidityGrab | short (grab-and-reverse, ICT-declared) |
| SellSideLiquidityGrab | long (grab-and-reverse) |

Non-directional shapes (Compression, DoubleSweepTrap) are **excluded** from 11a (no declared
direction — including them would require inventing one).

- **H0 (null):** each directional shape's declared-direction expectancy ≤ its winning control's,
  net of cost. A clean 0-PROMOTE is a successful experiment (no edge under the unified standard).
- **Cohort:** all directional shapes submitted as **one cohort** so Benjamini-Hochberg (gate 7)
  corrects across them — the primary defense against a shape sweep becoming a false-discovery engine.

## Hypothesis 11b (frozen, RESERVED — runs only if pre-declared, not in the first run)

11a conditioned additionally on the neutral FM-030 trend-strength level (L0…L4) — tests whether the
declared-direction edge concentrates in a trend-strength regime. Reserved to keep 11a minimal;
same gate, same cohort discipline (levels × shapes as one cohort). Not run without a separate freeze.

## Anti-contamination guarantees (frozen)

1. **F-022 (labels):** outcomes ONLY from `forward_walk(exit_model="intrabar_fixed")` on raw CSV
   bars. `detect()` reads only OHLCV-derived features and **fail-fasts if fed any**
   `outcome`/`rr_achieved`/`mfe` key. `opportunities.jsonl` is never opened.
2. **F-051 (PIT leak):** BLOCKING projection audit — the shape projection ∩ centered-swing-
   contaminated dims **must be ∅** (`tests/test_shape_hypothesis_pit.py`); any intersection drops or
   re-derives that dimension. Plus the kernel's structural `bar.index > entry_index` guarantee,
   inherited free by adding no exit logic.
3. **Feature substrate:** the trend axis (11b) bands **FM-030** (dimensionless, scale-invariant),
   never legacy FM-022 (F-061 price-scaled defect); as a neutral level only (A2a/F-062).
4. **F-037 / F-044 gate config:** `exit_model=intrabar_fixed`; `round_trip_bps` explicit **+ a 0 bps
   twin**; a pure shape hypothesis never invokes the fusion spine, so `BACKTEST_ENGINE_GATE` is
   **N/A (stated, not silent)**; `rr_fusion` stays `enabled:false` and is never constructed.
5. **Controls (gate-4 "beats winning control"):** `always_long`, `random_baseline` at matched signal
   density, and a pre-registered **unconditional-entry twin** (same geometry, fire every bar in the
   declared direction) — isolates "the shape SELECTS" from "the geometry/direction pays."

## FROZEN thresholds (no post-hoc changes)

M4 `QualificationGate` via `configs/research/research_config_shape_xauusd.json`:

| Knob | Value |
|---|---|
| exit_model | intrabar_fixed |
| round_trip_bps | 12 (+ 0 bps sensitivity twin) |
| q_min_samples | 30 |
| q_expectancy_min | 0.0 (net R) |
| q_pf_min | 1.0 |
| q_oos_split | 0.30 (chronological) |
| q_oos_retention_min | 0.50 |
| n_permutations | 2000 |
| significance_alpha | 0.05 |

## Closure rule (frozen)

- **0 PROMOTE** (expected prior): register the null as a finding that **updates** F-023/F-041B on a
  clean XAUUSD substrate (does not overturn — different instrument/method). Research authority only.
- **≥1 PROMOTE:** a *candidate* only. Requires (a) the 0 bps twin to agree on direction, (b)
  replication before any authority, (c) **no** production/fusion weight (that stays behind demonstrated
  ΔG001, §6.5). A single PROMOTE never grants the shape layer authority.
- Overturning a VALIDATED finding (F-023/F-041B) or any production/config change → owner sign-off (gate).

## Determinism & verification

- Two runs produce a byte-identical `edge_report` (runner-guaranteed; asserted).
- Blocking `tests/test_shape_hypothesis_pit.py` (projection ∩ contaminated-dims == ∅; `detect`
  raises on stream fields).
- Full 7-gate `reject_reasons` captured; n/PF/E cross-checked against `analytics/metrics_oracle`.
- 0 bps twin proves the null's direction is cost-robust.

## Freeze metadata (completed at sign-off)

- `protocol_hash`: _TBD at freeze_ · `.json` twin: `preregistration-program-11-shape-context-edge-xauusd.json`
- task_class: `EXPLORATORY_RESEARCH_DESIGN_ONLY` · authority: `RESEARCH_ONLY` ·
  grants_production_authority: false · branch_scope: `feature/truth-registry-v2` ·
  active_version_at_design: `v2_multi_2026_04`.
