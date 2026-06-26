# mt5_analytics v0.6.0 — Post-Trade Intelligence Layer ("insight, not authority")

## STATUS: ✅ SHIPPED — AT REST (2026-06-26, commit `2ae1244`, 85 tests)
Built end-to-end: `mt5_analytics/analytics/insight_report.py` (frozen `InsightReport` —
exit-efficiency / adverse-efficiency / cost-drag / risk-adjusted / sufficiency-gated attribution /
Herfindahl `effective_n`), `SufficiencyStatus` Enum, self-describing `AttributionBucket`, wired via
`ui/dashboard_data.insight_summary`. Real-data smoke (ecn/, n=2): correctly INSUFFICIENT yet surfaced
the genuine economic fact — gross expectancy 0.0, commission −0.23 → **net expectancy −0.115/trade**
(a statement the truth engine alone could never make).

**Capability-complete within scope.** The architectural transition is done: v0.1–v0.5 answered *"was
reality reconstructed correctly?"* (truthfulness); v0.6 answers *"what does reality imply?"* (economic
meaning), without adding any execution authority.

**PERMANENT INVARIANT (enforce aggressively):** `MT5 → truth → features → insight → HUMAN`, **never
`insight → decisions`**. The moment an `if session_expectancy > 0: trade()` appears, analytics stops
being *information* and becomes *authority* — a doctrine violation. `analytics/` may NOT grow a
`recommendation_engine` / `optimization` / `auto_tuning` module. The boundary is now structural.

**The bottleneck is no longer software — it is N (real, commission-bearing, NON-demo trade volume).**
On demo-N the sufficiency gates correctly stay shut (expectancy=None). Everything interesting now
depends on accumulating enough executed reality for those gates to open. That is the user's to supply.

**Optional, non-foundational v0.7 menu (build only on a concrete need — none are blocking):**
Streamlit insight cards (with aggressive `⚠ INSUFFICIENT (n/min_n)` rendering) · JSON export ·
Markdown/weekly intelligence report · `realized_r_net` feature (schema bump + migration — ONLY if an
ML/clustering consumer genuinely needs per-episode net R; evidence-driven, not speculative).

## Software-complete ≠ project-complete — Phase C is DATA, not code
~90–95% **software** maturity, ~5–10% **data** maturity. `Capability ≫ Data`. The three phases:

| Phase | Question | Output | State |
|---|---|---|---|
| A (v0.1–0.5) | Was reality reconstructed correctly? | Truth | ✅ |
| B (v0.6) | Can we extract economic meaning? | Insight | ✅ |
| **C (v0.7+)** | **Do live outcomes match research expectations?** | **Belief calibration** | **NOT STARTED — data-gated** |

**The real v0.7 is a campaign, not a release: "Reality Accumulation."** Goal = **50–100
commission-bearing, *qualified-strategy-driven*, human-in-loop MT5 trades.** Demo/random trades only
validate infrastructure (DONE); they can never calibrate belief. Until N accrues, the sufficiency gates
correctly stay shut — and that's the system working, not a gap to code around.

**F-010 bridge (the cross-subsystem reason this matters).** The findings ledger still carries **F-010
(OPEN/Likely): "Headline ROI is BACKTEST-only; live PnL (ExecutionPlanner + UltronRiskGate)
UNVERIFIED."** mt5_analytics is the instrument that can *close* it — but **v0.6 supplies only the
live-actual HALF.** Closing F-010 also needs (a) trades actually driven by the *qualified spine
strategy* (not discretionary/random), and (b) a **Reality-vs-Research Comparator** joining
backtest-expected distribution ↔ live-actual insight. Both are **data-gated and unbuilt** — do NOT
build the comparator before strategy-driven N exists (it would have nothing to compare). Target
architecture: `Backtests → Expected Distribution → Live Trades → Truth Engine → Insight → Reality-vs-
Research Comparator → Human`.

**Explicitly DO NOT build (all require N you don't have):** `realized_r_net`, recommendation/
optimization/auto-tuning engines, ML feedback loops, DuckDB, clustering, Monte Carlo, drift detection,
the Reality-vs-Research Comparator. *The system no longer needs architecture; it needs evidence.* The
likeliest failure mode is building more software because software is easier than generating reality.

**Three (and only three) reopen conditions:**
1. **Data** — `N ≥ 30` real, commission-bearing, strategy-driven trades ⇒ sufficiency gates unlock,
   Phase C begins (build the comparator THEN, against real expected-vs-actual data).
2. **Semantic** — a Case-B (separate commission deal) or mm1 (exchange-margin) account ⇒ truth-engine
   validation resumes (Level 3 remainder / Level 4).
3. **Failure** — a real `verify` FAIL ⇒ everything stops, kernel investigation begins.

**Bookkeeping ≠ Progress ≠ Learning (they compound differently).** Code = new capability (compounds
*sometimes*); docs = lower entropy (*weakly*); **reality accumulation = new evidence (*strongly*);
research-vs-reality calibration = belief updates (*extremely strongly*).** The project now lives in the
last two — `N: 0→30` changes it more than `85→86 tests` ever could. Do not mistake repository
cleanliness for belief calibration.

**Phase C operating loop (no software enters until the evidence demands it):**
`execute qualified strategy → MT5 truth engine → insight → human review → belief update → execute
again`. Not `build → ship → repeat`. The terminal state: **Software COMPLETE (within earned scope) ·
Data INSUFFICIENT (by design) · Next = Reality Accumulation · Success = N ≥ 30 qualified
commission-bearing trades.**

---

## Context
The truth engine (v0.1.0→v0.5.0) is validated across two broker families with zero kernel changes —
but it has only ever been proven *correct*, never *used*. Per §6.1, validated plumbing is noise until
it produces **economic meaning**: the `FeatureRecord` schema itself says "expectancy/PF/win-rate belong
to the later analytics layer" — and that layer does not exist. Today the only rollups are 4 display
stats in [`ui/dashboard_data.py`](../../mt5_analytics/ui/dashboard_data.py) (`summary_stats`,
`session_breakdown`, `regime_breakdown`). This sprint builds the **decision-relevant** intelligence
the engine was built for, as **information-not-authority** (§6.5): it describes the trader's executed
reality and never feeds the spine.

**Reuse finding (do NOT reinvent):** `src/analytics/metrics_oracle.py` already ships the primitives —
`capture_ratio` / `giveback` / `adverse_efficiency` / `time_efficiency` (exit-quality),
`sharpe` / `recovery_factor` / `max_drawdown_rr` (risk-adjusted), `top_n_contribution` /
`largest_winner` / `largest_loser` / `symbol_attribution` (concentration), `median` / `percentile`
(distribution). The analytics layer only has to *compose* them per-episode → portfolio, not implement them.

**Honest-scope guardrail (built in, not bolted on):** the only executed history so far is a handful of
demo episodes. So every insight carries **N + a SUFFICIENT/INSUFFICIENT verdict** (E-001 / F-019
discipline): below `min_n` (default 30) the report states INSUFFICIENT and makes **no claim**. On
current demo data almost everything will correctly read INSUFFICIENT — this builds the *capability* and
proves it on fixtures; it does not fabricate conclusions from demo noise.

## Build — one new pure module + a thin dashboard hook
**New: `mt5_analytics/analytics/insight_report.py`** (new `analytics/` subpackage, sibling of
`engines/`). Pure, read-only, no MT5/Streamlit/writes — same purity contract as `dashboard_data`.
`build_insight(episodes, features, *, min_n=30) -> dict` (or a small `@dataclass InsightReport`),
composing the oracle primitives into:

1. **Exit efficiency** — per-episode `capture_ratio(realized_r, mfe_r)` + `giveback`; portfolio
   median capture ratio + total R given back. ("Are exits leaving R on the table?" — the F-002
   decision-process lens, the highest-value post-trade question.)
2. **Adverse efficiency** — `adverse_efficiency(mae_r, mfe_r)` distribution (heat taken before the move).
3. **Cost drag (v0.5.0 tie-in, schema-free)** — `realized_r` is GROSS (price ÷ risk); the episode's
   `net_pnl` includes commission+swap. Report Σcommission, Σswap, commission as a fraction of gross
   PnL, and gross-vs-net expectancy — computed at the analytics layer from `episode.net_pnl` vs the
   price-derived gross (no `FeatureRecord` schema bump). Newly meaningful now that commission is real.
4. **Risk-adjusted** — `sharpe`, `recovery_factor`, `max_drawdown_rr`, R-percentiles over the
   `realized_r` series.
5. **Conditional attribution WITH sufficiency** — expectancy + capture by `session` × `regime` ×
   duration-bucket, each tagged `n` + `SUFFICIENT/INSUFFICIENT` (reuse/extend `symbol_attribution`);
   a 3-trade "edge" is flagged INSUFFICIENT, never celebrated.
6. **Concentration** — `top_n_contribution`, `largest_winner/loser` (is the edge a few outliers?).

**Wire-in:** add `insight_summary(features, episodes, min_n=30)` to
[`ui/dashboard_data.py`](../../mt5_analytics/ui/dashboard_data.py) delegating to the new module (keep
the "info, not authority" docstring discipline); optionally surface a compact panel in
[`ui/streamlit_dashboard.py`](../../mt5_analytics/ui/streamlit_dashboard.py) (light, last — the module
+ data hook are the substance).

## Critical files
- **New** `mt5_analytics/analytics/__init__.py`, `mt5_analytics/analytics/insight_report.py`
- **Edit** `mt5_analytics/ui/dashboard_data.py` (add `insight_summary` delegating hook)
- **Reuse** `src/analytics/metrics_oracle.py` (all primitives above — import, don't reimplement)
- **New** `tests/mt5_analytics/test_insight_report.py`
- **No change** to the kernel, the `FeatureRecord` schema, or any engine (purity preserved)

## Verification
- **Unit (`tests/mt5_analytics/test_insight_report.py`):** fixtures with hand-computed episodes →
  assert capture_ratio/giveback/cost-drag/sharpe/attribution values; assert **sufficiency gating** (a
  bucket with `n < min_n` ⇒ `INSUFFICIENT`, no expectancy claim; `n ≥ min_n` ⇒ a verdict). Determinism
  (same input → byte-identical report). Existing **74 stay green** (kernel/feature paths untouched).
- **Live smoke (read-only):** run `build_insight` over the real `ecn/` + default artifact roots →
  confirm it produces a well-formed report and that low-N buckets honestly read INSUFFICIENT (the
  guardrail working on real demo data). No trades, no writes.
- **Commit `v0.6.0 "Post-Trade Intelligence Layer"`** once green; MIGRATIONS note (analytics layer is
  information-not-authority, schema-free, sufficiency-gated).

## Open sub-decision (recommend default; not blocking)
Cost-drag is done **at the analytics layer** from `episode.net_pnl` (no schema change) — recommended
for v0.6.0. A dedicated net-of-cost `realized_r_net` *feature* (schema bump + migration) is deferred
unless cost analysis needs per-episode net R downstream.

## NOT doing
No kernel/schema/engine change. No feedback into the trading spine (information-not-authority). No
fabricated conclusions on demo-N data (sufficiency-gated). No new broker validation (that track is
external-evidence-gated — Case-B / mm1 / verify-FAIL). Streamlit rendering is optional/last.
