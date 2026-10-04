# Concatenated session plans — part 7 of 10

Source directory: `docs/plans/`
Files in this part: 7

## Contents

1. `search-all-plans-reports-merry-sunbeam.md` (10598 bytes)
2. `start-with-regime-aware-fusion-rosy-waterfall.md` (14940 bytes)
3. `study-the-code-base-linear-alpaca.md` (16790 bytes)
4. `stusy-readme-of-https-github-com-humming-unified-flamingo.md` (10971 bytes)
5. `system-mandate-architecture-tender-hoare.md` (17628 bytes)
6. `the-root-cause-fancy-marble.md` (5674 bytes)
7. `the-strongest-assumption-that-glistening-clarke.md` (10207 bytes)


================================================================================
SOURCE_FILE: docs/plans/search-all-plans-reports-merry-sunbeam.md
SOURCE_BYTES: 10598
PART: 7/10 FILE 1/7
================================================================================

> Created: 2026-06-03 · Updated: 2026-06-03 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan — Execution-Planner Replay: split the EXECUTION edge into Selection vs SL/TP structure

## Context

The Alpha Ledger (just shipped, `docs/analysis/alpha-ledger-recovery-2026-06-03.md`) established the
operating thesis: **the edge is in the execution-selection process + throughput, not static
features** (F-001/F-002/F-003). But one question underneath it is still open. The gate-contribution
study (`gate-contribution-bnbusdt-2026-06-03.md:13,18`) showed the entire `+0.584R` edge appears at
the **RETEST→EXECUTION** gate (RETEST candidates `−0.039R` → executed `+0.545R`). Its own critical
caveat (`:29`) says that jump **conflates two things it cannot separate**:

1. **Selection** — *which* RETEST candles are chosen (session filter + score threshold), and
2. **SL/TP structure** — the CRT engine's structure-based SL/TP (`sl = swing ± 0.2·ATR`) vs the
   counterfactual scanner's vanilla fixed SL/TP (`1·ATR SL / 2·ATR TP`).

It explicitly names the fix: *"a counterfactual that replays the execution planner's SL/TP on the
rejected retest candidates."* The user chose this as the highest-information-value next step — it
quantifies *why* the edge exists (so all future roadmap decisions are better informed) and is the
RESEARCH item E-18/E-25 / open finding **F-010**.

**Key correction from exploration:** `ExecutionPlannerV1_2` does **not** compute SL/TP — the comment
at `execution_planner.py:9,179` defers it to the CRT engine, and `compute_crt_levels()`
(`src/core/gate_intelligence.py:24-84`) is the pure mirror of `crt_engine_v2.py:1162-1201`. So the
real contrast is **vanilla fixed SL/TP vs CRT structure SL/TP**, on **selected vs rejected** RETEST
candidates — a clean 2×2.

**Decisions locked (via user):**
- **Faithful via additive telemetry** (not offline re-derivation). The CRT engine knows direction +
  structure levels; no log carries them for rejected RETESTs (verified: `crt_transitions.jsonl` has
  `direction:None` for all 6,301 RETEST + 1,519 EXECUTION; `CANDIDATE_LIFECYCLE`/`DECISION_DISTANCE`
  carry score + `death_reason`/`rejection_reason` but no direction or levels). Engine emits the
  fields per RETEST candidate (no behavior change — same pattern as Phases 2b/3b added `shadow_used`,
  `score_at_approval`, `expansion_dwell_stats`).
- **Core 2×2 only** — no live-only ExecutionPlanner+Ultron arm this pass (keeps scope tight; the
  structure SL/TP already mirrors the live SL/TP path).

## The experiment — a 2×2 attribution

All four cells computed with the **same** forward simulator so only the varied dimension moves:

|                          | Vanilla SL/TP (`1·ATR` / `2·ATR`) | CRT structure SL/TP (`swing ± 0.2·ATR`) |
|--------------------------|-----------------------------------|------------------------------------------|
| **Selected** (executed)  | **A**                             | **B**  (anchor: ≈ real `+0.545R`)        |
| **Rejected RETEST**      | **C**  (≈ RETEST stage `−0.039R`) | **D**  (the missing measurement)         |

- **SL/TP-structure effect** = `mean(B−A)` on selected **and** `mean(D−C)` on rejected.
- **Selection effect** = `mean(A−C)` (vanilla) **and** `mean(B−D)` (structure).
- The observed `+0.584R` jump = path `C → B`; the 2×2 decomposes it and reports whether the two
  effects are additive (interaction term).
- **Verdict logic:** if `D` lifts toward `B` (structure SL/TP rescues rejected candidates) → much of
  the edge is **SL/TP structure** (and selection is over-rejecting). If `D` stays ~`C` while
  `B ≫ A,C,D` → the edge is **selection** (the chosen candles are genuinely better, SL/TP is
  secondary). This directly informs whether to invest in selection policy vs exit structure.

## Reuse (do NOT reinvent)

- `compute_crt_levels(entry, direction, low, high, atr, …)` — `src/core/gate_intelligence.py:24` —
  the structure SL/TP (cells B, D).
- `simulate_exit(entry, direction, sl, tp1, tp2, forward_candles, max_candles)` —
  `src/analytics/sl_tp_comparator.py:133` — the single forward simulator for all four cells
  (exit priority TP2>SL>TP1, matches BacktestRunner).
- `_aggregate_variant_results(results)` — `src/analytics/sl_tp_comparator.py:196` — per-cell
  expectancy / WR / PF / drawdown / exit-reason mix.
- `SLTPComparator.load_candles_from_csv(csv)` — `src/analytics/sl_tp_comparator.py:482` — forward
  candle loader.
- Vanilla mults + `max_candles` come from the existing `sl_tp_comparison` config section (consumed
  via `get_prod_section`) — no new config section, no magic numbers. Vanilla = `1.0·ATR` SL /
  `2.0·ATR` TP (the `opportunity_scanner` definition).
- Harness conventions mirror `scripts/research/phase6e_shadow_ab.py` (measure-only, `results/` only,
  control-arm trust gate, point-in-time companion doc).

## Phase A — additive telemetry (engine, no behavior change)

In `src/config_layer/crt_engine_v2.py`, at the RETEST-candidate evaluation point (where the engine
already decides accept→EXECUTION vs reject on session/zone/score — near the existing
`CANDIDATE_LIFECYCLE` / `DECISION_DISTANCE` emission), emit one new append-only JSONL record per
RETEST candidate. Everything below is **already in engine scope** at that moment — this only records
it:

```
kind: "RETEST_REPLAY"            # follows §3.2 JSONL convention (timestamp + kind, append-only)
timestamp, candle_index
direction:    int (1/-1)         # the engine's intended side — the field no log currently carries
entry, low, high, atr            # inputs to compute_crt_levels
sl, tp1, tp2                     # the engine's own structure levels (so D needs no re-derivation)
intent, score
accepted:     bool
reject_reason: str | null        # off_session:* | not_discount_zone | not_premium_zone | score_*
```

- Pure telemetry: no gate, no SL/TP, no transition logic changes. No config change → **no re-hash**.
- Document the new line in `docs/reference/schemas.md §9` (JSONL line schemas).
- This is the only engine edit; it is additive and reversible.

## Phase B — offline replay script (measure-only)

New `scripts/research/execution_planner_replay.py`, thin wrapper mirroring `phase6e_shadow_ab.py`:

1. Run one deterministic backtest on `data/BNBUSDT_M15.csv` (active `v4_multi_2026_06`, seed 1337) to
   produce the new `RETEST_REPLAY` telemetry + `BNBUSDT_trades.csv`. (Reuse `BacktestRunner` /
   `CandleLoader` / `load_prod_config_from_registry` exactly as `phase6e` does.)
2. Partition RETEST candidates: **Selected** = `accepted==True` (cross-check vs `trades.csv candle_idx`);
   **Rejected** = `reject_reason` set.
3. Load forward candles via `SLTPComparator.load_candles_from_csv("data/BNBUSDT_M15.csv")`.
4. Compute the four cells, each via `simulate_exit` on candles strictly **after** the entry index
   (no lookahead):
   - **A/C** = vanilla `1·ATR/2·ATR` levels on selected / rejected.
   - **B/D** = the engine's recorded structure `sl/tp1/tp2` on selected / rejected.
5. Aggregate each cell with `_aggregate_variant_results`; compute the selection / SL/TP / interaction
   deltas; write the verdict.
6. **Trust gate (hard stop, like phase6e control arm):** cell **B** expectancy must reproduce the
   real executed `+0.545R` within tolerance (and `D`'s entry set must match the rejected count from
   the funnel). If not, the harness is untrustworthy → exit non-zero, no doc.
7. Emit `results/execution_planner_replay/replay_bnbusdt.json` + hand-write the companion
   `docs/analysis/execution-planner-replay-bnbusdt-2026-06-03.md` with the point-in-time header
   (`> Point-in-time … NOT a living doc · Driver: scripts/research/execution_planner_replay.py ·
   Raw: results/execution_planner_replay/replay_bnbusdt.json · Config: v4_multi_2026_06`), the 2×2
   table, the attribution decomposition, and the verdict.

## Critical files

- **Edit (additive):** `src/config_layer/crt_engine_v2.py` (emit `RETEST_REPLAY` at the RETEST
  accept/reject point) · `docs/reference/schemas.md` (document the new JSONL line).
- **Create:** `scripts/research/execution_planner_replay.py` · `docs/analysis/execution-planner-replay-bnbusdt-2026-06-03.md`.
- **Reuse (read-only):** `src/core/gate_intelligence.py:24` · `src/analytics/sl_tp_comparator.py:133,196,482` ·
  `scripts/research/phase6e_shadow_ab.py` (template) · `src/runtime/backtest_v2.py` (BacktestRunner/CandleLoader).
- **Tests:** add `tests/` coverage for the new emission + the 2×2 math (see Verification).
- **Findings:** on results, update **F-010** / **F-002** in `docs/current-findings.md` (and the
  Repository Truths Index mirror) per §6.2 — this experiment is exactly what F-010 was waiting on.

## Verification (end-to-end)

- **Determinism / no-lookahead:** seed 1337; `simulate_exit` only sees candles `> entry_index`; two
  runs byte-identical. Confirm the additive telemetry leaves trade count / ROI unchanged vs the prior
  `v4` baseline (telemetry-additive invariant — same check Phases 2b/3b used).
- **Anchor gate:** cell **B** (structure SL/TP on selected) reproduces real executed `+0.545R` /
  PF ~2.54 within tolerance; cell **C** (vanilla on rejected) reproduces the RETEST-stage `≈ −0.039R`
  from gate-contribution. If both anchors hold, cells A and D are trustworthy.
- **Tests:** unit-test the new engine emission (one record per RETEST candidate, required fields
  present, `accepted`/`reject_reason` mutually consistent) and the attribution math (selection +
  SL/TP + interaction deltas reconstruct the `C→B` total). Run `python -m pytest tests/` for the CRT
  + analytics domains; run `tests/test_current_findings.py` after the F-010 update.
- **Artifact review:** the companion doc carries the point-in-time header, the 2×2, the decomposition,
  and a clear selection-vs-SL/TP verdict; `docs/analysis/readme.md` index row added.
- **§6 mandates:** SESSION LOG appended; affected topic doc synced (§6.1); F-010/F-002 updated (§6.2).

## Constraints / non-goals

- Measure-only: writes `results/` + the new docs + the additive telemetry line; **no config edit, no
  promotion, no gate/SL-TP/transition behavior change.** No re-hash (telemetry, not config).
- BNBUSDT-only this pass (per-instrument doctrine F-009); the script takes `--instrument` so SOL/ETH/BTC
  can follow without code change.
- No live-gate (ExecutionPlanner+Ultron) arm this pass — deferred as the natural follow-up that
  closes F-010 fully.


================================================================================
SOURCE_FILE: docs/plans/start-with-regime-aware-fusion-rosy-waterfall.md
SOURCE_BYTES: 14940
PART: 7/10 FILE 2/7
================================================================================

> Created: 2026-05-21 · Updated: 2026-05-21 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan — Regime-Aware Fusion Weights

## Context

`FusionEngine.compute()` ([src/core/fusion_engine.py:256](src/core/fusion_engine.py:256)) currently aggregates four engine scores with **static** weights pulled from `FusionConfig` (`weight_crt`, `weight_gaussian`, `weight_zone_gate`, `weight_rr`, plus optional `weight_strategy_consensus`). Market regime is already detected upstream by `detect_regime()` ([src/core/engine_runner.py:117](src/core/engine_runner.py:117)) but its output is consumed only by `RegimeGovernor` *after* fusion has already run — so fusion never adapts to whether the market is trending vs ranging vs neutral.

This patch wires regime into the fusion-weight selection. Same weighted-sum math, same return contract, same downstream consumers — only **which** weight dict is read changes. The `UNKNOWN` regime profile mirrors the existing static weights exactly so any unrecognised label is byte-identical to today's behaviour.

The implementation prompt the user supplied contained several mismatches with the codebase (wrong file paths, wrong method name, non-existent `bitnet` engine, wrong dataclass). All four have been resolved with the user — see [Resolved deviations](#resolved-deviations-from-original-prompt) below.

---

## Resolved deviations from original prompt

| Prompt said | Reality | Resolution (user-confirmed) |
| --- | --- | --- |
| `src/engines/fusion_engine.py`, `fuse()` method | Actual: `src/core/fusion_engine.py`, `compute()` method | Patch `compute()` in `src/core/fusion_engine.py` |
| Weight keys `{crt, gaussian, rr, bitnet, zone}` | Actual engines: `{crt, gaussian, zone_gate, rr}` + optional `strategy_consensus` | Use `{crt, gaussian, zone_gate, rr, strategy_consensus}` |
| Add field to `CRTConfig` | Fusion weights live in `FusionConfig` ([src/core/fusion_engine.py:107](src/core/fusion_engine.py:107)) | Add field to `FusionConfig` |
| Per-instrument config block | Configs are global; `fusion_engine` is a singleton section | Add inside the global `fusion_engine` section |
| Regime labels `TRENDING/RANGING/VOLATILE/UNKNOWN` | `detect_regime()` returns lowercase `trend/range/neutral` | Normalise inside `compute()` via a 4-entry map (`trend→TRENDING`, `range→RANGING`, `neutral→UNKNOWN`). `VOLATILE` profile is defined but only fires if a future regime detector emits it |

---

## Files to modify

1. **[src/core/fusion_engine.py](src/core/fusion_engine.py)** — add field to `FusionConfig`, add `regime` param to `compute()`, add normalisation + lookup before the weighted sum, replace `self.cfg.weight_*` refs inside the sum with resolved values.
2. **[src/core/engine_runner.py](src/core/engine_runner.py)** — hoist `detect_regime()` call from line ~734 to before the `self.fusion.compute(engine_results)` call at line 663; pass `regime=` through.
3. **[configs/production/v1_multi_2026_03.json](configs/production/v1_multi_2026_03.json)** — add `regime_fusion_weights` under `fusion_engine`; re-hash via `scripts/update_config_hash.py`.
4. **[configs/production/v2_multi_2026_04 - deepdeektry.json](configs/production/v2_multi_2026_04%20-%20deepdeektry.json)** — same JSON edit; re-hash.

**Not modified:** `CRTConfig`, `ConfigBuilder` (uses introspection on `CRTConfig` only, not `FusionConfig` — verify the prod-JSON→`FusionConfig` loader actually picks up the new key during step 4 verification), `FusionEngine.evaluate()` ([engine_runner.py:484](src/core/engine_runner.py:484)) — separate method, out of scope, prompt explicitly scoped to `fuse`/`compute`.

---

## Implementation

### Change 1 — `src/core/fusion_engine.py`

**1a.** At the top of the file, ensure `field` is imported alongside `dataclass`:

```python
from dataclasses import dataclass, field
```

**1b.** Add to `FusionConfig` (after line 135, immediately after `weight_strategy_consensus`):

```python
regime_fusion_weights: dict = field(default_factory=lambda: {
    "TRENDING":  {"crt": 0.38, "gaussian": 0.20, "zone_gate": 0.12, "rr": 0.20, "strategy_consensus": 0.10},
    "RANGING":   {"crt": 0.18, "gaussian": 0.32, "zone_gate": 0.15, "rr": 0.25, "strategy_consensus": 0.10},
    "VOLATILE":  {"crt": 0.28, "gaussian": 0.14, "zone_gate": 0.12, "rr": 0.16, "strategy_consensus": 0.30},
    "UNKNOWN":   {"crt": 0.33, "gaussian": 0.24, "zone_gate": 0.13, "rr": 0.20, "strategy_consensus": 0.10},
})
```

**1c.** Add module-level normalisation map (near the top, beside other constants):

```python
_REGIME_NORM = {
    "trend":           "TRENDING",
    "range":           "RANGING",
    "neutral":         "UNKNOWN",
    "high_volatility": "VOLATILE",
    "volatile":        "VOLATILE",
    "trending":        "TRENDING",
    "ranging":         "RANGING",
}
```

**1d.** Update `compute()` signature (line 256):

```python
def compute(self, engine_results: dict, trade=None, weights=None, regime: str = "UNKNOWN") -> dict:
```

Default `"UNKNOWN"` preserves every existing caller's behaviour.

**1e.** Inside `compute()`, **after** the `missing` check (line 268-274) and **before** the existing `if weights is None:` block (line 277), insert regime-weight resolution:

```python
# ── Regime-aware weight resolution ────────────────────────────────────
# Explicit `weights=` override (used by tests / tuner) takes priority.
# Otherwise look up by normalised regime label; fall back to UNKNOWN.
regime_weights_table = getattr(self.cfg, "regime_fusion_weights", {}) or {}
regime_key = _REGIME_NORM.get(str(regime).lower().strip(), "UNKNOWN")
regime_weights = regime_weights_table.get(regime_key)

if weights is None and regime_weights is not None:
    weights = regime_weights  # use regime-derived weights
    # Telemetry: alert when the raw input was an unrecognised non-empty label
    raw = str(regime).strip()
    if raw and raw.lower() not in _REGIME_NORM and regime_key == "UNKNOWN":
        try:
            from src.utils.integrity_events import emit_integrity_event
            emit_integrity_event(
                "FUSION_UNKNOWN_REGIME", "WARNING", "fusion_engine",
                {"regime_received": raw, "fallback": "UNKNOWN"},
            )
        except Exception:
            pass  # telemetry must never break fusion
```

**1f.** Update the existing weight-resolution block (line 277-291) to recognise the 5-key regime dict (`zone_gate` + `strategy_consensus`) **as well as** the legacy 4-key shape (`zone`):

```python
if weights is None:
    w_crt        = self.cfg.weight_crt
    w_gaussian   = self.cfg.weight_gaussian
    w_zone       = self.cfg.weight_zone_gate
    w_rr         = self.cfg.weight_rr
    w_consensus_override = None  # None → keep cfg.weight_strategy_consensus below
else:
    # Accept either {crt, gaussian, zone, rr} (legacy) or
    # {crt, gaussian, zone_gate, rr, strategy_consensus} (regime profiles).
    zone_key = "zone_gate" if "zone_gate" in weights else "zone"
    required = ("crt", "gaussian", zone_key, "rr")
    if not all(k in weights for k in required):
        raise ValueError(f"Weights dict must contain keys: {required}")
    weight_sum = sum(float(v) for v in weights.values())
    if abs(weight_sum - 1.0) > 0.01:
        raise ValueError(f"Weights sum to {weight_sum:.3f}, must be 1.0 ±0.01")
    w_crt        = weights["crt"]
    w_gaussian   = weights["gaussian"]
    w_zone       = weights[zone_key]
    w_rr         = weights["rr"]
    w_consensus_override = weights.get("strategy_consensus")  # may be None
```

**1g.** Replace the existing weighted-sum block (line 410-424) to use the resolved values:

```python
# Existing dead-engine guard — leave the zone_gate health check intact.
w_zonegate  = 0.0 if zone_gate_dead else w_zone
w_consensus = (
    w_consensus_override if w_consensus_override is not None
    else self.cfg.weight_strategy_consensus
)
total_w = (w_crt + w_gaussian + w_zonegate + w_rr + w_consensus) or 1.0
weighted_fusion_score = _clamp(
    (
        w_crt      * score_crt +
        w_gaussian * score_gaussian +
        w_zonegate * score_zonegate +
        w_rr       * score_rr +
        w_consensus * score_consensus
    ) / total_w
)
```

The only substantive change here: the sum reads from the resolved local variables (`w_crt`, `w_gaussian`, `w_zone`, `w_rr`, `w_consensus`) instead of `self.cfg.weight_*`. When regime lookup misses and `weights is None`, the resolved locals fall through to the config defaults — byte-identical to pre-patch.

### Change 2 — `src/core/engine_runner.py`

The fusion call at line 663 (`fusion_result = self.fusion.compute(engine_results)`) currently runs **before** `detect_regime()` at line ~734. Hoist the regime call:

**2a.** Immediately before line 663 (Step 4 — Fusion), add:

```python
# Compute regime ahead of fusion so weights can adapt to it.
# (Previously this ran only at Step 6 for RegimeGovernor; now shared.)
current_regime = detect_regime(input_data, self.dual_cfg)
```

**2b.** Update line 663:

```python
fusion_result = self.fusion.compute(engine_results, regime=current_regime)
```

**2c.** At the original line ~734 site, replace the redundant `regime = detect_regime(...)` call with `regime = current_regime` so RegimeGovernor sees the same value (and we avoid recomputing).

If `input_data` / `self.dual_cfg` aren't yet available at line 663, fall back to `current_regime = "UNKNOWN"` — the patch still works, the integrity-event path stays clean, and the regime lift can be a follow-up. (Confirm during implementation by reading the variable scope at line 663.)

### Change 3 — Both prod configs

In **[configs/production/v1_multi_2026_03.json](configs/production/v1_multi_2026_03.json)** and **[configs/production/v2_multi_2026_04 - deepdeektry.json](configs/production/v2_multi_2026_04%20-%20deepdeektry.json)**, inside the existing `"fusion_engine"` section, add `regime_fusion_weights` as a peer of `weight_crt` etc.:

```json
"regime_fusion_weights": {
    "TRENDING": {"crt": 0.38, "gaussian": 0.20, "zone_gate": 0.12, "rr": 0.20, "strategy_consensus": 0.10},
    "RANGING":  {"crt": 0.18, "gaussian": 0.32, "zone_gate": 0.15, "rr": 0.25, "strategy_consensus": 0.10},
    "VOLATILE": {"crt": 0.28, "gaussian": 0.14, "zone_gate": 0.12, "rr": 0.16, "strategy_consensus": 0.30},
    "UNKNOWN":  {"crt": 0.33, "gaussian": 0.24, "zone_gate": 0.13, "rr": 0.20, "strategy_consensus": 0.10}
}
```

Note the `UNKNOWN` row matches the existing static weight breakdown — if regime detection ever degrades, behaviour stays identical to pre-patch.

Then re-hash each file:

```bash
python scripts/update_config_hash.py "configs/production/v1_multi_2026_03.json"
python scripts/update_config_hash.py "configs/production/v2_multi_2026_04 - deepdeektry.json"
```

(`v1` currently has **no** `config_hash` field at all — the hash script will populate it. `v2` is at `c2568b6a…` and will rotate.)

---

## Verification

**V1 — Regime adapts weights**

```bash
python -c "
from src.core.fusion_engine import FusionEngine, FusionConfig, GaussianAdapter

class _Stub:
    def compute(self, f, i=0): return 0.5
fe = FusionEngine(GaussianAdapter(_Stub()), config=FusionConfig())
er = {
    'crt':      {'score': 0.7, 'direction': 1},
    'gaussian': {'score': 0.6, 'direction': 1},
    'zone_gate':{'score': 0.5, 'direction': 1},
    'rr':       {'score': 0.4, 'direction': 1},
    'strategy_consensus': {'score': 0.8, 'direction': 1},
}
t = fe.compute(er, regime='TRENDING')['final_score']
r = fe.compute(er, regime='RANGING')['final_score']
u = fe.compute(er, regime='UNKNOWN')['final_score']
d = fe.compute(er)['final_score']                  # default → UNKNOWN
assert abs(t - r) > 1e-4,  f'weights not adapting (t={t}, r={r})'
assert abs(u - d) < 1e-9,  f'UNKNOWN ≠ default (u={u}, d={d})'
print(f'PASS  trending={t:.4f}  ranging={r:.4f}  unknown={u:.4f}')
"
```

**V2 — Unknown regime label emits integrity event**

```bash
python -c "
import json, pathlib, time
from src.core.fusion_engine import FusionEngine, FusionConfig, GaussianAdapter

class _Stub:
    def compute(self, f, i=0): return 0.5
fe = FusionEngine(GaussianAdapter(_Stub()), config=FusionConfig())
er = {k: {'score': 0.5, 'direction': 1} for k in ('crt','gaussian','zone_gate','rr')}
fe.compute(er, regime='SIDEWAYS')                  # unrecognised
last = json.loads(pathlib.Path('logs/integrity_events.jsonl').read_text().strip().splitlines()[-1])
assert last['event'] == 'FUSION_UNKNOWN_REGIME', last
assert last['payload']['regime_received'] == 'SIDEWAYS', last
print('PASS  event:', last['event'])
"
```

**V3 — Lower-case `detect_regime()` output normalises correctly**

```bash
python -c "
from src.core.fusion_engine import FusionEngine, FusionConfig, GaussianAdapter
class _Stub:
    def compute(self, f, i=0): return 0.5
fe = FusionEngine(GaussianAdapter(_Stub()), config=FusionConfig())
er = {k: {'score': 0.6, 'direction': 1} for k in ('crt','gaussian','zone_gate','rr')}
lower = fe.compute(er, regime='trend')['final_score']
upper = fe.compute(er, regime='TRENDING')['final_score']
assert abs(lower - upper) < 1e-9, (lower, upper)
print('PASS  lowercase regime normalised')
"
```

**V4 — Existing pytest suite stays green**

```bash
python -m pytest tests/ -x -q
```

Focus on `tests/test_fusion_engine.py` (if present) and any test that touches `EngineRunner.run()`.

**V5 — Short end-to-end backtest**

```bash
python scripts/backtest/run_backtest.py --instrument EURUSD --bars 500
```

Confirm no `RuntimeError`, no new entries in `logs/integrity_events.jsonl` other than expected ones, and `BacktestMetrics.distribution` is populated.

**V6 — Config hash verification**

```bash
python scripts/update_config_hash.py "configs/production/v1_multi_2026_03.json" --check
python scripts/update_config_hash.py "configs/production/v2_multi_2026_04 - deepdeektry.json" --check
```

Both must report OK after re-hashing.

---

## Out of scope (deliberate non-goals)

- Modifying `FusionEngine.evaluate()` — separate method ([engine_runner.py:484](src/core/engine_runner.py:484)), used by the `fusion_use_evaluate` feature-flag path. Out of scope per the original prompt.
- Fixing the pre-existing `"zone"` vs `"zone_gate"` inconsistency in the legacy `weights=` override (the change above accepts **either** key, so we neither break existing callers nor force a wider cleanup).
- Adding a high-volatility branch to `detect_regime()`. The `VOLATILE` profile is defined for forward-compatibility; with today's detector it never fires. A future change to `detect_regime()` (or a swap to `RegimeClassifier`) activates it for free via the normalisation map.
- Promoting the new config — promotion goes through `PromotionManager` / `ConfigValidator` separately, after this patch lands.


================================================================================
SOURCE_FILE: docs/plans/study-the-code-base-linear-alpaca.md
SOURCE_BYTES: 16790
PART: 7/10 FILE 3/7
================================================================================

> Created: 2026-05-07 · Updated: 2026-05-07 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Groq-Powered Post-Trade Retrospective & ROI Enhancement

## Context

Groq is already wired into `src/config_layer/llama_gate.py` as a fallback LLM, but is criminally underused — it currently receives only 6 aggregate backtest metrics and returns a single float. The codebase has 121,177 historical signal decisions in `results.csv`, rich per-engine score breakdowns, and full fusion audit data. The goal is to use Groq's language reasoning to find high-ROI patterns in past market behavior and eventually filter low-confidence signals before execution.

**User role**: Bridge between Claude and Groq.  
- **Phase 1** (manual relay): Claude prepares rich structured prompts → user sends to Groq → user pastes response back → Claude parses and generates config recommendations.  
- **Phase 2** (automated): winning prompt shapes get hard-wired into `llama_gate.py` so Groq fires automatically post-session.

---

## What We Learned From Codebase Exploration

### Current Groq Capability (Underused)
- File: `src/config_layer/llama_gate.py`
- Function: `llm_score(metrics: dict)` — fallback chain: local llama.cpp → Groq → fail-open 1.0
- Current prompt input: `{win_rate, expectancy_rr, approved_trades, max_drawdown_pct, retests, expansions}`
- Groq output: single float `[0.0, 1.0]`
- Audit trail: `logs/llm_audit.jsonl`
- **Gap**: `llm_insight()` has NO Groq fallback — only static strings on local failure

### Rich Data Available But Not Fed to Groq
| Source | Content | Volume |
|--------|---------|--------|
| `results.csv` | 121,177 APPROVE/REJECT decisions with engine scores, regime, confidence_bucket | 8 MB |
| `configs/promotion_log.jsonl` | 6 config promotions with per-instrument scores | 6 entries |
| `logs/fusion_trades.jsonl` | Trade entries + exits with full feature snapshot + PnL | Configured, not populated yet |
| `logs/signal_audit.jsonl` | Per-bar engine breakdowns with zone/fusion/risk pass/fail | Configured |

### Full Decision Context Available at Runtime
At every signal decision, the system has:
- 4 independent engine scores: `crt, gaussian, zone_gate, rr` each with `score + direction + meta`
- Fusion: `final_score, variance, entropy, normalized_score, threshold_used`
- Features: 35-dim vector including `retest_depth, body_ratio, disp_strength, session_id, regime_id, atr`
- Decision: `reason, confidence, reject_stage`
- Execution plan: `entry, sl, tp, rr_ratio, intent` (BREAKOUT/PULLBACK/REVERSAL/LIQ_SWEEP)

### Key Groq Functions Already Available
```
_groq_request(messages, max_tokens, temperature, stop) → str
_groq_score(prompt) → tuple[float, str]
llm_score(metrics) → float          # uses Groq fallback
llm_chat(messages) → str            # uses Groq fallback
llm_insight(context, report_type)   # NO Groq fallback — gap to fix
```

---

## Phase 1: Manual Bridge — Design & Validate Prompts

### 1.1 New Script: `scripts/groq_bridge/prepare_retrospective.py`

**Purpose**: Parse recent trade history from logs/results.csv, build a rich Groq prompt, print it to console for user to relay.

**Logic**:
1. Accept `--source results.csv` or `--source logs/fusion_trades.jsonl` + `--last-n 50` (default 50 trades)
2. Load trades, split into WINS and LOSSES
3. For each group: extract top-5 by confidence, with `{regime, session, crt_score, gaussian_score, zone_gate_score, rr_score, fusion_score, outcome}`
4. Compute per-engine correlation with wins (which engine's high score predicts wins?)
5. Build the Groq prompt (see template below)
6. Write prompt to `logs/groq_bridge/pending_{YYYYMMDD_HHMMSS}.txt`
7. Print to stdout with instructions: "Copy everything between ===START=== and ===END==="

**Prompt Template**:
```
You are a quantitative trading signal analyst. Analyze these closed trades and find high-ROI patterns.

SESSION SUMMARY:
- Instrument: {instrument}
- Total trades: {n}
- Win rate: {win_rate:.1%}
- Expectancy: {expectancy:.2f}R
- Max drawdown: {max_dd:.1%}
- Best sessions: {top_sessions}

ENGINE PERFORMANCE (correlation with wins):
- CRT engine: avg score in wins={crt_win_avg:.2f}, losses={crt_loss_avg:.2f}
- Gaussian engine: avg score in wins={g_win_avg:.2f}, losses={g_loss_avg:.2f}
- Zone Gate engine: avg score in wins={z_win_avg:.2f}, losses={z_loss_avg:.2f}
- RR engine: avg score in wins={rr_win_avg:.2f}, losses={rr_loss_avg:.2f}

TOP 5 WINNING TRADES:
{formatted_wins}

TOP 5 LOSING TRADES:
{formatted_losses}

QUESTIONS:
1. Which engine score pattern most reliably predicts wins? Give a threshold rule.
2. Which regime+session combinations should be filtered out (high loss rate)?
3. What fusion score minimum would improve expectancy without losing too many winners?
4. Give 3 concrete parameter changes (e.g., "raise crt_weight from 0.25 to 0.35") with ROI rationale.
5. Identify any "trap" signal pattern — setup that looks good but loses consistently.

Respond in structured JSON:
{
  "top_engine_signal": {"engine": str, "threshold": float, "rationale": str},
  "sessions_to_avoid": [{"session": str, "regime": str, "reason": str}],
  "recommended_fusion_min": float,
  "config_changes": [{"param": str, "from": val, "to": val, "rationale": str}],
  "trap_pattern": {"description": str, "filter_rule": str}
}
```

### 1.2 New Script: `scripts/groq_bridge/ingest_response.py`

**Purpose**: Accept Groq's JSON response (user pastes it), parse it, log to audit trail, print human-readable action items.

**Logic**:
1. Read from stdin (user pastes) or `--file` argument
2. Parse JSON response
3. Validate structure (all 5 keys present)
4. Append to `logs/groq_bridge/insights.jsonl` with timestamp + source_prompt_hash
5. Print action items:
   - "APPLY NOW: raise retest_depth_max from 0.25 → 0.30 (in configs/production/v1_multi_2026_03.json)"
   - "MONITOR: avoid ASIA session + RANGE regime — 3 of 5 losses came from there"
   - "NEW FILTER: crt_score < 0.45 → auto-reject even if fusion passes"
6. Optionally: `--apply-config` flag to write config changes directly (with re-hash)

### 1.3 Log File: `logs/groq_bridge/insights.jsonl`

New JSONL file. Each line schema:
```json
{
  "ts": "2026-05-07T...",
  "kind": "GROQ_INSIGHT",
  "source_prompt_hash": "sha256[:12]",
  "model": "llama-3.3-70b-versatile",
  "top_engine_signal": {"engine": "crt", "threshold": 0.55, "rationale": "..."},
  "sessions_to_avoid": [...],
  "recommended_fusion_min": 0.62,
  "config_changes": [...],
  "trap_pattern": {"description": "...", "filter_rule": "..."}
}
```

---

## Phase 2: Automated Integration — Wire Into Pipeline

### 2.1 New Module: `src/agent/groq_retrospective.py`

Follow `docs/EXAMPLE_SERVICE.py` pattern exactly.

**Class**: `GroqRetrospectiveEngine`
- `from_prod_config(cls, cfg: dict) -> "GroqRetrospectiveEngine"`
- `run_session_retrospective(metrics: BacktestMetrics, trades: list[dict]) -> dict`
  - Builds the same prompt as `prepare_retrospective.py` but from in-memory objects
  - Calls `_groq_request()` (imported from `llama_gate`) directly — NOT through `llm_score`
  - Returns parsed insights dict or `{}` on failure (fail-open)
- `_build_prompt(metrics, wins, losses) -> str`
- `_parse_response(raw: str) -> dict`

**Config section** (add to `configs/production/v1_multi_2026_03.json`):
```json
"groq_retrospective": {
  "enabled": true,
  "last_n_trades": 50,
  "min_trades_to_trigger": 10,
  "max_tokens": 800,
  "temperature": 0.1,
  "log_path": "logs/groq_bridge/insights.jsonl"
}
```

### 2.2 Extend `llm_insight()` in `llama_gate.py`

**Gap to fix**: `llm_insight()` currently has NO Groq fallback — falls to static `_fallback_insight()`.

**Change**: After local server fails, call `_groq_request()` with the same prompt before falling to static fallback.

```python
# After local URLError/TimeoutError:
if _groq_available():
    raw = _groq_request(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=_LG_CFG.get("insight_temperature", 0.3),
    )
    if raw:
        return raw
return _fallback_insight(context, report_type)
```

This is a 4-line addition with no API contract change.

### 2.3 Wire Into BacktestRunner Post-Run

**File**: `src/runtime/backtest_v2.py`

After `BacktestMetrics` is finalized (end of `BacktestRunner.run()`), if `groq_retrospective.enabled` and trade count >= `min_trades_to_trigger`:
```python
from agent.groq_retrospective import GroqRetrospectiveEngine
_retro = GroqRetrospectiveEngine.from_prod_config(cfg)
insights = _retro.run_session_retrospective(metrics, self._trade_log)
if insights:
    metrics.distribution["groq_insights"] = insights
```

No hard dependency — `GroqRetrospectiveEngine` is optional-import guarded.

---

## Session Versioning — Full Traceability

Every retrospective run gets a **session ID** so you can trace exactly which Groq consultation produced which config change and what the ROI delta was.

### Session ID Format
```
RETRO_{YYYYMMDD}_{HHMMSS}_{instrument}_{n_trades}
Example: RETRO_20260507_143022_EURUSD_50
```

### Version Registry: `logs/groq_bridge/session_registry.jsonl`

One line per session, append-only:
```json
{
  "session_id": "RETRO_20260507_143022_EURUSD_50",
  "ts": "2026-05-07T14:30:22",
  "instrument": "EURUSD",
  "trades_analyzed": 50,
  "win_rate_before": 0.52,
  "expectancy_before": 0.68,
  "baseline_score": 0.5585,
  "prompt_hash": "sha256[:12]",
  "prompt_file": "logs/groq_bridge/pending_20260507_143022.txt",
  "response_file": "logs/groq_bridge/response_20260507_143022.txt",
  "insights_applied": false,
  "config_version_before": "v1_multi_2026_03",
  "config_version_after": null,
  "score_after": null,
  "roi_delta": null,
  "status": "PENDING_RESPONSE"
}
```

**Status lifecycle**:
```
PENDING_RESPONSE → RESPONSE_RECEIVED → INSIGHTS_APPLIED → VALIDATED → PROMOTED
                                     ↓
                                REJECTED (score_after < baseline)
```

### Session Update Flow

When user runs `ingest_response.py`, the registry entry for that session is updated:
```json
{
  "status": "RESPONSE_RECEIVED",
  "response_file": "logs/groq_bridge/response_20260507_143022.txt",
  "groq_model": "llama-3.3-70b-versatile",
  "insights_summary": "Raise crt threshold to 0.55; avoid ASIA+RANGE"
}
```

When config is applied and backtest re-run:
```json
{
  "status": "VALIDATED",
  "config_version_after": "v1_multi_2026_03_retro_20260507",
  "score_after": 0.612,
  "roi_delta": +0.053,
  "win_rate_after": 0.57,
  "expectancy_after": 0.91
}
```

### Session Trace Index: `logs/groq_bridge/trace_index.md`

Human-readable markdown table auto-updated by `ingest_response.py`:

```markdown
| Session ID | Date | Instrument | Trades | Score Before | Score After | Delta | Status |
|-----------|------|-----------|--------|-------------|------------|-------|--------|
| RETRO_20260507_143022_EURUSD_50 | 2026-05-07 | EURUSD | 50 | 0.5585 | — | — | PENDING |
```

### Session ID Propagation

The `session_id` is embedded in:
1. Prompt file name: `pending_{session_id}.txt`
2. Response file name: `response_{session_id}.txt`
3. `insights.jsonl` line: `"session_id": "RETRO_..."`
4. `llm_audit.jsonl` entry: `"session_id"` field added
5. Config archive name (if applied): `v1_multi_2026_03_retro_{session_id}.json`
6. `promotion_log.jsonl` entry: `"notes": "from groq session RETRO_..."`

### Lookup Commands (built into `ingest_response.py --query`)

```bash
# See all sessions with ROI delta
python scripts/groq_bridge/ingest_response.py --list-sessions

# Replay a specific session's insights
python scripts/groq_bridge/ingest_response.py --session RETRO_20260507_143022_EURUSD_50 --show

# Compare before/after for a session
python scripts/groq_bridge/ingest_response.py --session RETRO_... --compare
```

---

## Implementation Order

| Step | File | Change | Risk |
|------|------|--------|------|
| 1 | `scripts/groq_bridge/prepare_retrospective.py` | New script — generates session_id, writes prompt file, registers to session_registry.jsonl | None |
| 2 | `scripts/groq_bridge/ingest_response.py` | New script — parses response, updates session_registry, writes insights.jsonl, updates trace_index.md | None |
| 3 | `logs/groq_bridge/session_registry.jsonl` | Auto-created by script on first run | None |
| 4 | `logs/groq_bridge/trace_index.md` | Auto-created/updated by ingest_response.py | None |
| 5 | `src/config_layer/llama_gate.py` lines 545–609 | Add 4-line Groq fallback to `llm_insight()`; add `session_id` field to `_append_llm_audit()` | Low |
| 6 | `src/agent/groq_retrospective.py` | New module — embeds session_id in every audit entry | None |
| 7 | `configs/production/v1_multi_2026_03.json` | Add `groq_retrospective` section | Low — rehash required |
| 8 | `src/runtime/backtest_v2.py` | Optional hook at end of `run()` | Low — fail-open |

---

## Manual Bridge Workflow (Phase 1 Day-1 Usage)

```
1. Run backtest:
   python scripts/run_backtest.py --config configs/production/v1_multi_2026_03.json --data-dir data/

2. Prepare Groq prompt (creates session RETRO_YYYYMMDD_HHMMSS_...):
   python scripts/groq_bridge/prepare_retrospective.py --source results.csv --last-n 50
   
   Output:
   ✓ Session ID: RETRO_20260507_143022_EURUSD_50
   ✓ Prompt written to: logs/groq_bridge/pending_RETRO_20260507_143022_EURUSD_50.txt
   ✓ Registered in: logs/groq_bridge/session_registry.jsonl  [status: PENDING_RESPONSE]
   → Copy prompt from the file above and send to Groq

3. [User] Copy prompt → paste into Groq → copy Groq's JSON response

4. [User] Save response and ingest:
   python scripts/groq_bridge/ingest_response.py \
     --session RETRO_20260507_143022_EURUSD_50 \
     --response-file /path/to/groq_response.txt
   
   Output:
   ✓ Session RETRO_20260507_143022_EURUSD_50 updated [status: RESPONSE_RECEIVED]
   ✓ Insights logged to: logs/groq_bridge/insights.jsonl
   ✓ trace_index.md updated
   ACTION: raise retest_depth_max 0.25 → 0.30
   ACTION: avoid ASIA+RANGE (loss rate 71%)
   ACTION: min fusion_score 0.55 → 0.62

5. Apply config changes + rehash:
   python scripts/groq_bridge/ingest_response.py \
     --session RETRO_20260507_143022_EURUSD_50 \
     --apply-config
   
   Output:
   ✓ Session status: INSIGHTS_APPLIED
   ✓ Config archived as: v1_multi_2026_03_retro_RETRO_20260507_...
   ✓ New config hash computed

6. Re-run backtest to validate ROI delta:
   python scripts/run_backtest.py --config configs/production/v1_multi_2026_03.json --data-dir data/
   
7. Record outcome:
   python scripts/groq_bridge/ingest_response.py \
     --session RETRO_20260507_143022_EURUSD_50 \
     --record-score 0.612
   
   Output:
   ✓ ROI delta: +0.053 (0.5585 → 0.612) ✅
   ✓ Session status: VALIDATED
   ✓ trace_index.md updated with final delta
```

---

## Critical Files (Must Read Before Implementation)

| File | Why |
|------|-----|
| `src/config_layer/llama_gate.py` lines 545–707 | `llm_insight` and `llm_chat` — exact insertion points |
| `src/config_layer/llama_gate.py` lines 112–203 | `_groq_request`, `_groq_score` — functions to reuse |
| `src/runtime/backtest_v2.py` | `BacktestMetrics` dataclass, `BacktestRunner.run()` end |
| `docs/EXAMPLE_SERVICE.py` | Canonical pattern for new `GroqRetrospectiveEngine` |
| `configs/production/v1_multi_2026_03.json` | Add `groq_retrospective` section; rehash after |
| `results.csv` | Source data — first 5 columns to validate field names |

---

## Verification

1. **Phase 1 smoke test**:
   ```
   python scripts/groq_bridge/prepare_retrospective.py --source results.csv --last-n 20 --dry-run
   ```
   Expected: prompt printed, `logs/groq_bridge/pending_*.txt` created.

2. **Ingest smoke test**:
   ```
   echo '{"top_engine_signal":{"engine":"crt","threshold":0.55,"rationale":"test"},"sessions_to_avoid":[],"recommended_fusion_min":0.60,"config_changes":[],"trap_pattern":{"description":"","filter_rule":""}}' | python scripts/groq_bridge/ingest_response.py
   ```
   Expected: entry appended to `logs/groq_bridge/insights.jsonl`.

3. **`llm_insight` Groq fallback test**:
   Stop local llama.cpp server, run any insight-generating code path, check `logs/llm_audit.jsonl` — should show `source: groq` or `source: failopen` (not old static string).

4. **BacktestRunner integration test**:
   Run backtest with GROQ_API_KEY set + `groq_retrospective.enabled: true`. Check `BacktestMetrics.distribution["groq_insights"]` is populated.

5. **ROI validation** (true end-to-end):
   Apply one of Groq's config_changes suggestions → re-run backtest → compare new `score` in `configs/promotion_log.jsonl` against baseline score of 0.5585.


================================================================================
SOURCE_FILE: docs/plans/stusy-readme-of-https-github-com-humming-unified-flamingo.md
SOURCE_BYTES: 10971
PART: 7/10 FILE 4/7
================================================================================

> Created: 2026-05-07 · Updated: 2026-05-07 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Hummingbot Historical Data Ingestion for Tradelatest Backtest

## Context

The current `BacktestRunner` (`src/runtime/backtest_v2.py`) is limited to CSV files that must be manually sourced and pre-formatted. This creates a friction point: running backtests on new instruments, date ranges, or exchanges requires manual data procurement. Hummingbot provides production-grade REST + WebSocket connectors for 40+ exchanges (Binance, Bybit, OKX, KuCoin, Gate.io, etc.) and a `CandlesBase` abstraction for fetching historical OHLCV data. The goal is to add a **data-extraction script** that uses hummingbot's candle connectors to pull M15 (and other TF) OHLCV history and write CSV files compatible with Tradelatest's existing `CandleLoader`. Zero changes to `BacktestRunner` internals.

---

## Scope

**In scope:**
- New script `scripts/data/fetch_candles_hummingbot.py` — thin CLI wrapper
- New module `src/inout/hummingbot_candle_fetcher.py` — business logic, follows `EXAMPLE_SERVICE.py` pattern
- New config section `"hummingbot_data"` in `configs/production/v1_multi_2026_03.json`
- Dependency entry in `pyproject.toml` (hummingbot as optional dep)

**Out of scope:**
- Changes to `BacktestRunner`, `CandleLoader`, or any scoring engine
- Real-time streaming or live trading integration
- Order book / slippage model changes (deferred)

---

## How Hummingbot Candles Work

Hummingbot's `CandlesBase` (`hummingbot/data_feed/candles_feed/candles_base.py`):
- Configured via `CandlesConfig(connector, trading_pair, interval, max_records)` and `HistoricalCandlesConfig` (adds `start_time`, `end_time`)
- Fetches from REST endpoint with pagination; fills gaps automatically
- Returns a pandas DataFrame with columns: `timestamp, open, high, low, close, volume, quote_asset_volume, n_trades, taker_buy_base_volume, taker_buy_quote_volume`
- Exchange implementations live at `hummingbot/data_feed/candles_feed/{exchange}_spot_candles.py`

Supported intervals include: `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `1d`.

The Tradelatest `CandleLoader` expects CSV columns: `datetime, open, high, low, close, volume` (standard OHLCV). A simple column rename + timestamp format conversion bridges the two.

---

## Implementation Plan

### Step 1 — Add `"hummingbot_data"` config section

File: `configs/production/v1_multi_2026_03.json`

Add a new top-level key:
```json
"hummingbot_data": {
  "exchange": "binance",
  "trading_pair": "EURUSD",
  "interval": "15m",
  "start_date": "2024-01-01",
  "end_date": "2025-12-31",
  "output_dir": "data/hummingbot",
  "instruments": ["EURUSD", "GBPUSD", "USDJPY"],
  "max_records_per_request": 500
}
```

Re-hash after: `python scripts/maintenance/_compute_hash.py`

### Step 2 — Create `src/inout/hummingbot_candle_fetcher.py`

Follow `docs/EXAMPLE_SERVICE.py` pattern exactly:

```python
# src/inout/hummingbot_candle_fetcher.py

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger("hummingbot_candle_fetcher")

# --- Optional import guard (hummingbot is optional dep) ---
try:
    from hummingbot.data_feed.candles_feed.candles_factory import CandlesFactory
    from hummingbot.data_feed.candles_feed.data_types import HistoricalCandlesConfig
    _HB_AVAILABLE = True
except ImportError:
    _HB_AVAILABLE = False
    logger.warning("hummingbot not installed — HummingbotCandleFetcher disabled")

# --- Config dataclass ---
@dataclass
class HummingbotFetcherConfig:
    exchange: str
    trading_pair: str
    interval: str
    start_date: str
    end_date: str
    output_dir: Path
    max_records_per_request: int = 500

    @classmethod
    def from_prod_config(cls, cfg: dict) -> "HummingbotFetcherConfig":
        s = _require(cfg, "hummingbot_data")
        return cls(
            exchange=_require(s, "exchange"),
            trading_pair=_require(s, "trading_pair"),
            interval=_require(s, "interval"),
            start_date=_require(s, "start_date"),
            end_date=_require(s, "end_date"),
            output_dir=Path(_require(s, "output_dir")),
            max_records_per_request=s.get("max_records_per_request", 500),
        )

def _require(cfg: dict, key: str):
    if key not in cfg:
        raise KeyError(f"HummingbotCandleFetcher: missing required config key '{key}'")
    return cfg[key]

# --- Main class ---
class HummingbotCandleFetcher:
    """Fetches historical OHLCV candles from any hummingbot-supported exchange
    and writes Tradelatest-compatible CSV files (datetime,open,high,low,close,volume).
    """

    def __init__(self, cfg: HummingbotFetcherConfig):
        if not _HB_AVAILABLE:
            raise RuntimeError("hummingbot package is required: pip install hummingbot")
        self._cfg = cfg
        self._cfg.output_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_prod_config(cls, prod_cfg: dict) -> "HummingbotCandleFetcher":
        return cls(HummingbotFetcherConfig.from_prod_config(prod_cfg))

    async def fetch_async(self, instrument: Optional[str] = None) -> Path:
        """Fetch candles and write CSV. Returns output path."""
        pair = instrument or self._cfg.trading_pair
        cfg = HistoricalCandlesConfig(
            connector_name=self._cfg.exchange,
            trading_pair=pair,
            interval=self._cfg.interval,
            start_time=_parse_ts(self._cfg.start_date),
            end_time=_parse_ts(self._cfg.end_date),
        )
        candles = CandlesFactory.get_candle(cfg)
        await candles.start_network()
        await candles.wait_for_ready()
        df = candles.candles_df
        await candles.stop_network()

        # Rename to Tradelatest-compatible columns
        df = df[["timestamp", "open", "high", "low", "close", "volume"]].copy()
        df["datetime"] = df["timestamp"].apply(
            lambda ts: __import__("datetime").datetime.utcfromtimestamp(ts / 1e3).strftime("%Y.%m.%d %H:%M")
        )
        df = df[["datetime", "open", "high", "low", "close", "volume"]]

        out_path = self._cfg.output_dir / f"{pair.replace('/', '')}_{self._cfg.interval}.csv"
        df.to_csv(out_path, index=False)
        logger.info("Wrote %d candles → %s", len(df), out_path)
        return out_path

    def fetch(self, instrument: Optional[str] = None) -> Path:
        """Synchronous wrapper around fetch_async."""
        import asyncio
        return asyncio.run(self.fetch_async(instrument))


def _parse_ts(date_str: str) -> int:
    """Convert 'YYYY-MM-DD' to millisecond UTC timestamp."""
    import datetime
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return int(dt.timestamp() * 1e3)
```

### Step 3 — Create `scripts/data/fetch_candles_hummingbot.py`

Thin CLI wrapper, no business logic:

```python
#!/usr/bin/env python
"""CLI: Fetch historical OHLCV candles via hummingbot and write Tradelatest CSVs.

Usage:
    python scripts/data/fetch_candles_hummingbot.py \\
        --exchange binance \\
        --pair BTCUSDT \\
        --interval 15m \\
        --start 2024-01-01 \\
        --end 2025-01-01 \\
        --out data/hummingbot
"""
import argparse
import json
from pathlib import Path
from src.inout.hummingbot_candle_fetcher import HummingbotCandleFetcher, HummingbotFetcherConfig

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exchange", default=None)
    parser.add_argument("--pair", default=None)
    parser.add_argument("--interval", default="15m")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--out", default="data/hummingbot")
    parser.add_argument("--config", default="configs/production/v1_multi_2026_03.json")
    args = parser.parse_args()

    with open(args.config) as f:
        prod_cfg = json.load(f)

    # CLI args override config values
    hb_cfg = prod_cfg.get("hummingbot_data", {})
    if args.exchange: hb_cfg["exchange"] = args.exchange
    if args.pair:     hb_cfg["trading_pair"] = args.pair
    hb_cfg["interval"] = args.interval
    hb_cfg["start_date"] = args.start
    hb_cfg["end_date"] = args.end
    hb_cfg["output_dir"] = args.out

    fetcher = HummingbotCandleFetcher(HummingbotFetcherConfig(**{
        k: hb_cfg[k] for k in HummingbotFetcherConfig.__dataclass_fields__
    }))

    instruments = prod_cfg.get("hummingbot_data", {}).get("instruments", [hb_cfg["trading_pair"]])
    for instr in instruments:
        path = fetcher.fetch(instrument=instr)
        print(f"  {instr} → {path}")

if __name__ == "__main__":
    main()
```

### Step 4 — Add hummingbot as optional dependency

File: `pyproject.toml`

```toml
[project.optional-dependencies]
hummingbot = ["hummingbot>=2.0.0"]
```

Install with: `pip install -e ".[hummingbot]"`

### Step 5 — Re-hash config

```bash
python scripts/maintenance/_compute_hash.py
```

---

## Critical Files

| File | Action |
|------|--------|
| `src/inout/hummingbot_candle_fetcher.py` | **CREATE** — new fetcher module |
| `scripts/data/fetch_candles_hummingbot.py` | **CREATE** — CLI entry point |
| `configs/production/v1_multi_2026_03.json` | **EDIT** — add `"hummingbot_data"` section |
| `pyproject.toml` | **EDIT** — add optional dep |
| `scripts/maintenance/_compute_hash.py` | **RUN** — re-hash config after edit |

---

## Existing Patterns Reused

- Optional-import guard pattern → `docs/EXAMPLE_SERVICE.py` lines 12–18
- `_require()` strict accessor → `docs/EXAMPLE_SERVICE.py` lines 22–26
- `from_prod_config(cls, cfg)` factory → `docs/EXAMPLE_SERVICE.py` lines 45–52
- Named flow logger → `logging.getLogger("hummingbot_candle_fetcher")`
- CLI thin wrapper → mirrors `scripts/data/` existing scripts pattern

---

## Verification

1. **Unit test** — `tests/inout/test_hummingbot_candle_fetcher.py`:
   - Mock `CandlesFactory.get_candle()` to return a synthetic DataFrame
   - Assert output CSV has columns `datetime, open, high, low, close, volume`
   - Assert optional-import path raises `RuntimeError` when `_HB_AVAILABLE = False`

2. **Integration test** (requires hummingbot installed + network):
   ```bash
   python scripts/data/fetch_candles_hummingbot.py \
     --exchange binance --pair BTCUSDT --interval 15m \
     --start 2025-01-01 --end 2025-01-07 --out /tmp/hb_test
   ```
   Verify `/tmp/hb_test/BTCUSDT_15m.csv` exists, has >500 rows, correct columns.

3. **End-to-end backtest** — feed the generated CSV into `BacktestRunner`:
   ```bash
   python scripts/backtest/run_backtest.py \
     --csv /tmp/hb_test/BTCUSDT_15m.csv \
     --instrument BTCUSDT
   ```
   Confirm run completes, `results/` folder has `_summary.json` and `_trades.csv`.

4. **Config hash** — confirm `python scripts/maintenance/_compute_hash.py` exits 0 after JSON edit.


================================================================================
SOURCE_FILE: docs/plans/system-mandate-architecture-tender-hoare.md
SOURCE_BYTES: 17628
PART: 7/10 FILE 5/7
================================================================================

# Architecture Truth Audit & Synchronization — Tradelatest

> Created: 2026-06-04 · Updated: 2026-06-04 · Milestone: cross-cutting (governance + Trd-track)
> Mode: evidence-only audit. Every claim cites `file:line` or is marked **NOT PROVEN** / **MISSING** / **DRIFT DETECTED**.

## Context

The user issued a 17-phase "Architecture Truth Audit" mandate: assume the architecture is wrong until proven, validate a **proposed pipeline** against the actual implementation, and produce a documentation-synchronization + correction plan. The proposed pipeline:

```
Execution:  MARKET DATA → FEATURE ENGINE → STATE ENGINE → TRANSITION GRAPH →
            PATTERN MEMORY LEDGER → BITNET FILTER → TRADENET MATCHER →
            LLM REASONER → ULTRON RISK GOVERNOR → ALERT ENGINE
Research:   FEATURE SPACE INTELLIGENCE → PATTERN DISCOVERY → PATTERN COURT →
            WALK FORWARD VALIDATION → SHADOW VALIDATION → QUANTUM OPTIMIZATION LAB
```

**Audit verdict (one line):** the *execution spine* is real and hardened; the *proposed "memory/learning" stages* (Transition Graph, Pattern Memory Ledger, Pattern Court, TradeNet wiring) are **MISSING or telemetry-only**, and the system's own living findings (F-001/F-005/F-011) already say intelligence is **not** the binding constraint — so the correct remediation is **truth-synchronization + a reproducibility foundation**, not building the killed stages.

**Approved scope (user):** (1) documentation truth-sync, (2) targeted code reliability fixes, (3) design the feature/state **persistence (reproducibility) layer**.

---

## DELIVERABLE 1 — Repository Truth Report (Phase 1 inventory)

### Execution spine

| Component | Status | Evidence |
|---|---|---|
| Market data ingest (Candle, M15 CSV, optional TimescaleDB) | **EXISTS** | `crt_engine_v2.py:95`; `agent/modes/pipeline_mode.py:80`; `data_ingestion/historical_fetcher.py:197` |
| Feature engine (38-dim `CANONICAL_FEATURES` v3.0, schema hash) | **EXISTS** | `features/feature_schema.py:46-122`; `features/crt_feature_builder.py:23` |
| Feature **persistence** of full vectors | **MISSING** | `feature_pipeline.py:786` (computed, not persisted); only 6-key snapshot in `logs/feature_snapshots.jsonl` (`engine_runner.py:55`) |
| State engine (9-state `CRTState`, `VALID_TRANSITIONS`) | **EXISTS** | `crt_engine_v2.py:63-72` (RANGE,SHADOW_PENDING,SWEEP,DISPLACEMENT,EXPANSION,EXPIRED,RETEST,EXECUTION,RESOLUTION); transitions `crt_engine_v2.py:1069` |
| State **persistence/versioning** across runs | **MISSING** | in-memory `EngineState` (`crt_engine_v2.py:250`); transitions streamed to `logs/crt_transitions.jsonl` but feature context empty |
| Transition **graph** (freq/expectancy/regime matrix) | **MISSING** | static `VALID_TRANSITIONS` only; no frequency/expectancy aggregation |
| Pattern Memory Ledger (state-seq → outcome → decay) | **PARTIAL / telemetry** | `replay/replay_memory_engine.py:113-249` clusters trades + 30-day decay, but cluster-keyed only, no state-sequence expectancy (F-012) |
| BitNet filter (live hard gate, `score<0.55` reject) | **EXISTS** | `crt_engine_v2.py:1793-1802`; persisted `backtest_v2.py:276`; `bitnet/bitnet_inference.py:317` (numpy fwd pass) — **adaptive threshold dormant** (hardcoded `0.55`, `:358`) |
| TradeNet matcher | **PARTIAL (built, unwired)** | `training/trade_net_v2.py` complete; fusion slot stub `fusion_engine.py:8`; `engine_runner.py:392` never passes `neural_fn` → `None` |
| LLM reasoner (tie-breaker, band 0.45–0.65, fail-open 1.0) | **EXISTS** | `config_layer/llm_inference_client.py`; `fusion_engine.py:610-652` (execution-authority isolation Trd-M5) |
| Ultron risk governor (7 checks, kill-switch) | **EXISTS (live-only)** | `core/ultron_risk_gate.py:69-87`; `live_engine_hook.py:864`; **not called in backtest** (`backtest_v2.py` zero hits) |
| Alert engine | **NOT PROVEN as discrete stage** | live outcome telemetry exists (`live_engine_hook.py:899`); no dedicated "alert engine" module found |
| Concept drift action | **PARTIAL (detect, no act)** | `features/feature_monitor.py`; `live_engine_hook.py:669-692` logs only (F-008) |
| Sidecar intelligence (CognitiveBus/ReplayMemory/HMF/Cluster) | **EXISTS (telemetry-only)** | `cognitive/cognitive_bus.py:12-15` ("NEVER returns to execution plane"); `engine_runner.py:429` fire-and-forget (F-012) |

### Research layer

| Component | Status | Evidence |
|---|---|---|
| Feature space intelligence | **PARTIAL (real, marginal, frozen)** | F-011; `analysis/feature-region-oos-persistence-2026-06-01.md:44`; `plans/probability-surface-advisory.md` SCOPED |
| Pattern discovery (scanner + expansion) | **EXISTS** | `scripts/research/opportunity_scanner.py`; `expansion/expansion_engine.py:24` |
| Pattern Court (DISCOVERED/VALIDATING/SHADOW/LIVE/DECAYING/KILLED lifecycle) | **MISSING** | no such state machine; closest = `ShadowPromotionGate` + `model_registry` promotion + Funding Ledger states (different topology) |
| Walk-forward validation | **EXISTS (no lookahead verified)** | `backtest_v2.py:4` "zero lookahead"; `training/trainer.py:489-527` expanding-window, no shuffle |
| Shadow validation | **EXISTS** | `governance/shadow_promotion_gate.py`; `promotion_log.jsonl` (v4 promoted 2026-06-02) |
| Quantum optimization lab | **MISSING** | grep `quantum\|qaoa\|annealing` → zero hits in `src/` |

### Governance

| Component | Status | Evidence |
|---|---|---|
| ConfigValidator (hard+soft gates) | **EXISTS, enforced** | `config_layer/config_validator.py` |
| PromotionManager (APPROVE-only) | **EXISTS, enforced** | `governance/promotion_manager.py:97` |
| `config_integrity` | **ORPHANED** | only caller = cutover script (F-006) |
| ACTIVE_VERSION | **v4_multi_2026_06** (governed) | `configs/production/ACTIVE_VERSION:1` (verified directly) |

---

## DELIVERABLE 2 — Architecture Readiness Report (proposed vs actual)

- **Stages 1–9 of the execution pipeline are largely buildable on top of what exists** — the spine (data→feature→state→BitNet→fusion→LLM→Ultron) is real.
- **"PATTERN MEMORY LEDGER" + "TRANSITION GRAPH" are the architecturally missing middle.** They are *named in the proposal as spine stages* but exist only as **telemetry sidecars** (F-012). They cannot become spine stages without the persistence layer (Deliverable 8C) because the data they need (full feature vectors + state sequences) is discarded.
- **TradeNet socket is empty by construction** (`fusion_engine.py:8`); wiring it is a 1-line init change but is **FROZEN-adjacent** — it has no training loop feeding it and findings say it is not the constraint.
- **Pattern Court + Quantum Lab do not exist.** Pattern Court's *intent* (promotion lifecycle) is partially served by `ShadowPromotionGate` + Funding Ledger. Quantum is **NOT PROVEN / MISSING** — treat as research-only, do not build.
- **Readiness conclusion:** the binding gap is **reproducibility/persistence**, not model intelligence. This aligns with F-001 (intelligence not binding) and is the prerequisite for *any* of the missing learning stages.

---

## DELIVERABLE 3 — Data Loss Report (Phase 2)

Path `raw candle → feature → signal → trade → outcome`; permanently discarded:

1. **Full 38-dim feature vector at decision time** — only a 6-key subset persists (`engine_runner.py:55`, `feature_snapshots.jsonl`). *Reconstruction: impossible without re-running the pipeline on identical OHLCV.*
2. **Per-candle indicator intermediates** (ATR/RSI/MACD/EMA) — not logged. *Reconstruction: recompute-only.*
3. **Feature-frame history** — `FeatureStore` bounded deque max 1000 (`core/feature_store.py:84`), lost on exit.
4. **State-transition feature context** — `crt_transitions.jsonl` records from/to/reason but `metadata.features` is empty.
5. **State-sequence probabilities** — no transition matrix; graph is deterministic, not probabilistic.

**Blocks future intelligence:** (1)+(4)+(5) make exact replay and "why was this trade rejected" forensics impossible, and make Pattern Memory Ledger / TradeNet training infeasible without recompute. **This is the #1 research-integrity finding.**

---

## DELIVERABLE 4 — Pattern Memory Readiness Report (Phases 5/6)

- Can map historical trade → preceding **cluster**? **YES** (`replay_memory_engine.py:194`).
- Can map historical trade → preceding **state sequence**? **NO** (state context discarded).
- Sequence expectancy (e.g. P(EXECUTION | EXPANSION→RETEST))? **MISSING.**
- Pattern decay? **YES** (exp decay, 30-day half-life, `replay_memory_engine.py:145`).
- **Verdict:** memory is **cluster-keyed telemetry**, not a causal state-sequence ledger. Readiness for the proposed Ledger = **blocked on persistence (Deliverable 8C)**.

## DELIVERABLE 5 — Feature Space Intelligence Readiness Report (Phases 3/14)

- Features reproducible **exactly**? **NO** (Deliverable 3). Schema *contract* reproducible (hash) — values not.
- OOS persistence real but marginal (F-011, retention 0.93–1.51, 6/8 zones negative). Advisory path **FROZEN** pending RME schema repair (done 2026-06-02, `project_rme_schema_repair`).
- Quantum lab: **MISSING**, research-only, do not build.

---

## DELIVERABLE 6 — Documentation Drift Report (Phase 15)

| # | Drift | Authoritative | Stale/Conflicting | Severity |
|---|---|---|---|---|
| D1 | Active prod config | `ACTIVE_VERSION` = **v4_multi_2026_06** (F-007) | `MEMORY.md` index ("Active prod = v2_multi_2026_04"); `user-progress-registry.md:10,124` | **HIGH** |
| D2 | Probability Surface state | `current-findings.md` Funding Ledger = **KILLED** | `plans/probability-surface-advisory.md` = "SCOPED, not implemented" | **HIGH** |
| D3 | Zombie plans | Funding Ledger: Liquidity V2 / TradeNet V2 / Prob-Surface = KILLED/FROZEN | `docs/plans/*` (63 files) carry **no** KILLED/FROZEN markers | **MEDIUM** |
| D4 | TradeNet v2 build status | F-005: BUILT-but-unwired | `analysis/audit-2026-06-02/dead-dormant-inventory.md` "designed-not-built" | MEDIUM (archived, dated) |
| D5 | BitNet adaptive threshold | F-004: dormant (hardcoded `0.55`) | code static `crt_engine_v2.py:358,1800` | LOW (frozen, documented) |
| D6 | Concept-drift gating | F-008: detect-not-act | `live_engine_hook.py:676` matches finding | LOW (gap documented) |
| D7 | Internal audit contradiction (this audit) | `CRTState` = 9 states (`:63-72`) | a sub-agent claimed 5 states — **rejected**, verified by direct read | resolved |

---

## DELIVERABLE 7 — Profitability / Impact Matrix

| Item | Profit | Research | Reliability | Maint | Priority |
|---|:--:|:--:|:--:|:--:|---|
| Feature/state persistence layer (8C) | ○ | ●●● | ●● | ● | **P1** (foundation) |
| Doc truth-sync D1/D2/D3 | ○ | ●● | ●● | ●●● | **P1** (cheap, stops rediscovery) |
| Act on concept drift (8B-ii) | ●● | ● | ●●● | ● | **P2** |
| Wire `config_integrity` at runtime (8B-i) | ○ | ○ | ●●● | ●● | **P2** |
| Backtest ↔ live parity (Ultron in backtest) | ●●● | ●● | ●● | ● | **P2** (F-010 OPEN: live PnL unverified) |
| Build Pattern Memory Ledger / Transition Graph | ? | ●● | ● | ●● | **P3** (gated on 8C; not the constraint) |
| Wire TradeNet / Pattern Court / Quantum | ✗ | ○ | ○ | ✗ | **DO NOT BUILD** (KILLED/FROZEN/MISSING) |

---

## DELIVERABLE 8 — Prioritized Remediation Plan (executable after approval)

### 8A — Documentation truth-sync (P1, doc-only, additive)
- **D1:** update `MEMORY.md` index line + `memory/project_trd_m6_downstream.md` ("Active prod = v2_multi_2026_04" → **v4_multi_2026_06**, cite `ACTIVE_VERSION` + promotion_log 2026-06-02). Update `docs/governance/user-progress-registry.md:10,124` (flip the v2 "active/SHIPPED" rows; never delete — supersede per §6.2).
- **D2/D3:** add a `> Status: KILLED — see current-findings Funding Ledger (F-001/F-011)` banner to `plans/probability-surface-advisory.md` and any plan implementing Liquidity V2 / TradeNet V2 / Prob-Surface. Do not delete plans (replay).
- **D4:** add a dated "SUPERSEDED by F-005" note atop `analysis/audit-2026-06-02/dead-dormant-inventory.md`.
- Per §6.1/§6.2: bump affected `docs/topics/*` + re-affirm findings dates.

### 8B — Targeted code reliability fixes (P2, each behind governance/promotion)
- **(i) Wire `config_integrity` at runtime (F-006).** Call `config_integrity` checks at config-load in `runtime/backtest_v2.py` + `inout/live_engine_hook.py` startup (fail-fast if active version ungoverned / validation_summary stale). Mirrors existing `_require` fail-fast pattern. Add config flag `governance.enforce_config_integrity`.
- **(ii) Act on concept drift (F-008).** In `live_engine_hook.py:669-692`, on **HARD** drift (Z>3.0) apply a size-down / block via a new advisory passed to `UltronRiskGateWrapper` (prescale only — never bypass the gate, SR-1). Config: `feature_monitor.hard_drift_action ∈ {log, size_down, block}` (default `log` to preserve current behavior). Backtest: instantiate `FeatureMonitor` for parity telemetry only.
- *(Backtest↔live parity — Ultron in backtest — flagged P2 but deferred to its own plan; F-010 is OPEN and larger.)*

### 8C — Feature/State persistence layer (P1 foundation, the reproducibility fix)
Goal: make every decision **exactly replayable** and unblock any future Ledger/TradeNet.
- **New module** `src/runtime/decision_recorder.py` (copy `docs/reference/example-service.py` template): on each decision, append a self-contained JSONL line to `logs/<instrument>/decision_vectors.jsonl` containing: `timestamp, instrument, schema_hash, candle_ts, full 38-dim feature vector, crt_state, prior_state, transition_reason, fusion_score, bitnet_score, decision, reject_reason`.
- **Wire** as fire-and-forget from `engine_runner.py` alongside the existing `FEATURE_SNAPSHOT_LOG` (extend, don't replace). Reuse `feature_schema.SCHEMA_HASH` for version stamping so vectors are invalidated correctly when schema changes (load-bearing per CLAUDE.md §4).
- **Config section** `inout` / new `decision_recorder` block (enable flag, path, max rotation) — no magic numbers; re-hash via `scripts/maintenance/_compute_hash.py`.
- **Storage:** JSONL only (no DB — convention). Size: comparable to `crt_transitions.jsonl` (~229MB observed) → add rotation.
- **Tests** `tests/`: APPROVE-path record written, schema_hash stamped, disabled-flag no-op, rotation boundary, vector round-trips to `extract_feature_vector` dim=38.
- **Determinism check:** replaying recorded vectors through `FusionEngine.evaluate` reproduces the logged `fusion_score` (no lookahead).

---

## DELIVERABLE 9 — Exact Files To Modify

- `MEMORY.md`, `memory/project_trd_m6_downstream.md` (D1)
- `docs/governance/user-progress-registry.md` (D1)
- `docs/plans/probability-surface-advisory.md` (+ other KILLED-initiative plans) (D2/D3)
- `docs/analysis/audit-2026-06-02/dead-dormant-inventory.md` (D4)
- `src/runtime/backtest_v2.py`, `src/inout/live_engine_hook.py` (8B-i, 8B-ii)
- `src/core/ultron_risk_gate.py` wrapper path (8B-ii prescale)
- `configs/production/v4_multi_2026_06*.json` + re-hash (8B/8C config)
- **NEW** `src/runtime/decision_recorder.py`, `tests/test_decision_recorder.py` (8C)
- `src/core/engine_runner.py` (wire recorder, 8C)

## DELIVERABLE 10 — Exact Documents To Update (per §6.1/§6.2 same-turn)

- `docs/current-findings.md` — re-affirm F-006/F-008 dates; add finding if drift-gating ships; index↔doc consistency (CI `tests/test_current_findings.py`).
- `docs/topics/*` for any touched concept (drift, governance, feature-schema, replay).
- `docs/reference/schemas.md §9` — document the new `decision_vectors.jsonl` line schema.
- `docs/reference/config-reference.md` — new config keys.
- `assistant_project.md` — SESSION LOG entry (§6).

---

## DELIVERABLE — Self-Critique (Phase 17)

- **Assumptions:** classifications rely on grep/explore breadth; an "alert engine" or quantum stub could exist under an unsearched name → marked **NOT PROVEN**, not MISSING-with-certainty for the alert engine.
- **Weak evidence:** transition-graph "MISSING" is from absence-of-search; a probabilistic matrix could be computed offline in an analysis script not yet found. Mitigation: 8C makes it constructible regardless.
- **Alternative interpretation:** the discarded feature vectors may be *intentional* (storage cost), and findings say intelligence isn't the constraint — so 8C's ROI is *research/reliability*, not profit. Stated honestly in the impact matrix (profit ○).
- **What could invalidate:** if a feature-vector dump already exists somewhere in `logs/` or `results/` that I didn't enumerate, 8C is partially redundant — **first step of 8C execution must grep `logs/`/`results/` for any existing full-vector dump before building.**
- **Bias check:** I deliberately did *not* propose building the proposed-but-killed stages (Pattern Court, TradeNet wire, Quantum) — risk is I'm over-trusting the Funding Ledger. Reopen only via documented Reopen Conditions (§6.2).

## Verification (after execution)
1. `python scripts/maintenance/_compute_hash.py` — config re-hash clean.
2. `pytest tests/test_decision_recorder.py tests/test_current_findings.py tests/test_topic_docs.py` green.
3. Run a short backtest with recorder enabled → `decision_vectors.jsonl` non-empty, dim=38, schema_hash stamped; replay reproduces `fusion_score` (determinism).
4. `grep` MEMORY/registry for `v2_multi_2026_04` → only superseded/historical references remain.
5. Toggle `feature_monitor.hard_drift_action=log` → behavior identical to today (safe default).


================================================================================
SOURCE_FILE: docs/plans/the-root-cause-fancy-marble.md
SOURCE_BYTES: 5674
PART: 7/10 FILE 6/7
================================================================================

> Created: 2026-05-10 · Updated: 2026-05-10 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Fix backtest_v2.py ignoring CRT parameters from production config JSON

## Context

`backtest_v2.py main()` constructs `CRTConfig` directly with only three hardcoded CLI defaults, bypassing the production JSON entirely. The `crt_engine` section (containing fields like `body_ratio_min`, `atr_multiplier_min`, `retest_depth_max`, etc.) is never loaded. This means every backtest silently runs with market-router hardcoded defaults instead of the tuned JSON values.

There is also a secondary bug: `BacktestRunner.__init__` falls back to a bare `CRTConfig()` if `bt_config.crt_config` is None, which also bypasses the JSON.

---

## Critical files

- `src/runtime/backtest_v2.py` — primary fix (lines 1990–2010, line 1281)
- `src/config_layer/production_config.py` — provides `load_prod_config_from_registry`, `_coerce_crt_engine`, `PROD_VERSION`
- `src/config_layer/config_builder.py` — provides `ConfigBuilder.from_existing()` for applying CLI overrides on top of loaded config

---

## Changes

### 1. `src/runtime/backtest_v2.py` — top-level imports (line 64)

Add to the existing production_config import line:

```python
# Before:
from config_layer.production_config import PROD_VERSION

# After:
from config_layer.production_config import (
    PROD_VERSION,
    load_prod_config_from_registry,
)
from config_layer.config_builder import ConfigBuilder
```

---

### 2. `src/runtime/backtest_v2.py` — CLI arg defaults (lines 1990–1992)

Change the three CRT CLI arg defaults from hardcoded values to `None`, consistent with every other JSON-backed arg in `main()`:

```python
# Before:
ap.add_argument("--sweep-age",    type=int,   default=20)
ap.add_argument("--decay",        type=float, default=0.10)
ap.add_argument("--threshold",    type=float, default=0.75)

# After:
ap.add_argument("--sweep-age",    type=int,   default=None)
ap.add_argument("--decay",        type=float, default=None)
ap.add_argument("--threshold",    type=float, default=None)
```

---

### 3. `src/runtime/backtest_v2.py` — CRTConfig construction (lines 1999–2010)

Replace the direct `CRTConfig()` instantiation with a proper JSON load + CLI override layer:

```python
# Before:
_cli_overrides: dict = {}

crt_cfg = CRTConfig(
    max_sweep_age_candles=args.sweep_age,
    score_decay_lambda=args.decay,
    score_threshold=args.threshold,
)
# Always record CRT overrides — these always deviate from the JSON default.
_cli_overrides["--sweep-age"]  = str(args.sweep_age)
_cli_overrides["--decay"]      = str(args.decay)
_cli_overrides["--threshold"]  = str(args.threshold)
_cli_overrides["--scorer"]     = args.scorer

# After:
_cli_overrides: dict = {}

# Determine instrument for market routing. Multi-instrument runs use EURUSD as the
# Forex baseline; crt_engine JSON values override the base, so numeric params are
# correct regardless of which instrument is routed later.
_instr_hint = (
    args.instrument if args.instrument not in ("AUTO", "ALL")
    else Path(args.csv).stem.upper() if not Path(args.csv).is_dir()
    else "EURUSD"
)

# Load ALL CRTConfig fields from the production JSON (params + crt_engine merged).
crt_cfg = load_prod_config_from_registry(PROD_VERSION, _instr_hint)

# Apply explicit CLI overrides only for flags that were actually passed.
_crt_cli: dict = {}
if args.sweep_age is not None:
    _crt_cli["max_sweep_age_candles"] = args.sweep_age
    _cli_overrides["--sweep-age"] = str(args.sweep_age)
if args.decay is not None:
    _crt_cli["score_decay_lambda"] = args.decay
    _cli_overrides["--decay"] = str(args.decay)
if args.threshold is not None:
    _crt_cli["score_threshold"] = args.threshold
    _cli_overrides["--threshold"] = str(args.threshold)

if _crt_cli:
    crt_cfg = ConfigBuilder.from_existing(_instr_hint, crt_cfg, extra_overrides=_crt_cli)

_cli_overrides["--scorer"] = args.scorer
```

---

### 4. `src/runtime/backtest_v2.py` — BacktestRunner fallback (line 1281)

Fix the bare `CRTConfig()` fallback to go through `ConfigBuilder` instead of hardcoded defaults:

```python
# Before:
self.crt_cfg  = bt_config.crt_config or CRTConfig()

# After:
self.crt_cfg  = bt_config.crt_config or ConfigBuilder.build(
    bt_config.instrument or "EURUSD"
)
```

This still uses market-router base defaults (not the full JSON), but is only hit when `BacktestConfig` is constructed without a `crt_config` (test/API paths), not the `main()` path.

---

## Verification

1. **Smoke test — single instrument:**
   ```
   python src/runtime/backtest_v2.py --csv data/EURUSD_M15.csv --instrument EURUSD --output results/test_fix
   ```
   Check the `*_config.json` dump in `results/test_fix/` — `body_ratio_min`, `atr_multiplier_min`, `retest_depth_max` should now match the `crt_engine` section in the active production JSON.

2. **CLI override still works:**
   ```
   python src/runtime/backtest_v2.py --csv data/EURUSD_M15.csv --instrument EURUSD --threshold 0.80
   ```
   The config dump should show `score_threshold: 0.80` and only `--threshold` recorded in `cli_overrides`.

3. **No CLI flags — all from JSON:**
   ```
   python src/runtime/backtest_v2.py --csv data/EURUSD_M15.csv --instrument EURUSD
   ```
   `cli_overrides` dict in the config dump should NOT contain `--sweep-age`, `--decay`, or `--threshold` (previously they were always recorded even when not passed).

4. **Existing tests:**
   ```
   python -m pytest tests/ -x -q
   ```
   No regressions expected; tests that construct `BacktestRunner` directly with an explicit `crt_config` are unaffected.


================================================================================
SOURCE_FILE: docs/plans/the-strongest-assumption-that-glistening-clarke.md
SOURCE_BYTES: 10207
PART: 7/10 FILE 7/7
================================================================================

# Execution Plan — Per-Instrument Session Optimization (the pivot's first lever)

> Created: 2026-06-03 · Updated: 2026-06-03 · Milestone: Trd (governance/execution track)

## Context

A Phase-0 funding review (H3) concluded that **state *discovery* is mostly solved; state *exploitation/selection* is the live edge.** Path-enrichment / Liquidity-V2 features FAIL the dual gate (ΔAUC≈0, net RR negative despite AUC 0.65), while **governance + selection dominate measured ROI** (+4.91% → +20.59% vs ~+1.3% intelligence upside). The ruling: **freeze V2 intelligence work; fund governance, execution selection, per-instrument sessions, and drift-based risk scaling** until a challenger beats the incumbent (+0.328R) on the same economic gate.

This plan operationalizes the **#1 measured ROI lever** identified back in Phase 6b: the funnel bottleneck is **RETEST→EXECUTION (11.2%)**, where **64 valid retests are killed by the SESSION filter** (44 OFF_SESSION + 20 ASIA) — *not* by the score threshold (134/135 pass). The lever is the per-instrument `allowed_sessions` set.

### What already exists (verified in code + promotion_log)
- **Resolver is built.** `resolve_allowed_sessions(engine_runner, instrument)` + `_canon_session` (`src/config_layer/production_config.py:266–304`) resolve per-instrument overrides, preserve `OFF_SESSION`. Used by live load, `backtest_v2.py`, **and `ConfigValidator.validate()` (`config_validator.py:435–439`)** — so validation already scores per-instrument sessions exactly like runtime. No new wiring needed for sessions to flow.
- **Filter gate:** `src/config_layer/crt_engine_v2.py:2589–2611` — labels each candle's session from `session_windows` (LONDON 07–10, NEWYORK 13–16, ASIA 00–03 UTC; everything else → `OFF_SESSION`; `overlap` is an inert token — no window), rejects `FILTER_REJECTED` reason `off_session:{SESS}` when not in `allowed_sessions`.
- **Partly shipped.** Active = **`v4_multi_2026_06`** (not v2 — memory was stale). v4 opened **`BNBUSDT` → all sessions** (`london,new_york,overlap,asia,off_session`), ConfigValidator APPROVE (BNB 39 trades / PF 1.63). **`SOLUSDT` was excluded** at PF~0.98 (`promotion_log` line 16, audit-2026-06-02).

### The two gaps this plan closes
1. **Blanket-open ≠ optimal.** BNBUSDT's "all sessions" was a *measurement open*, never compared against subsets. Dropping ASIA or OFF_SESSION may raise PF/expectancy and cut DD. We need a **session-subset sweep** to *select*, not just open.
2. **No OOS evidence.** v4's APPROVE was full-window. OOS today is only tuner-internal date-slicing (`auto_tuner_multi.py` `--train-split`), **never a promotion gate** ("Part 4A OOS" does not exist as a harness). Session selection is the classic overfit trap; it must be confirmed on holdout before promotion.

## Goal

Per instrument, **select the `allowed_sessions` subset that maximizes economic ROI on in-sample and holds up out-of-sample**, then promote those subsets through the governed path. Concretely: confirm/refine BNBUSDT, and rescue or finally retire SOLUSDT with evidence — replacing the blanket-open with an OOS-validated selection.

## Design

The sweep is **additive and measure-only** (mirrors the Phase 6 "ROI Step" doctrine). Sessions resolve independently of the global tuned `params`, so we **hold v4's params fixed** and sweep *only* the per-instrument `allowed_sessions`. Search space per instrument is the 15 non-empty subsets of `{LONDON, NEWYORK, ASIA, OFF_SESSION}` (`overlap` inert; keep for compat).

New tool: **`scripts/analysis/session_sweep.py`** (thin CLI wrapper; no business logic — per `CLAUDE.md §3.3`). For one instrument it:
1. Loads the instrument CSV via `CandleLoader`; computes the in-sample/OOS split index from `--train-split` (reuse the exact index math in `auto_tuner_multi.py:610–622` so OOS semantics match the tuner).
2. For each candidate subset, runs `backtest_v2` on the **in-sample** window with `allowed_sessions` injected via `dataclasses.replace(crt_config, allowed_sessions=subset)` (the same pattern `config_validator.py:435–439` uses) — **no config-file writes**.
3. Records economic metrics per subset: `approved_trades`, `win_rate`, `expectancy_rr`, `profit_factor`, ROI%, `max_drawdown` (reuse `BacktestMetrics`; ROI per the Phase 6 ROI telemetry already in `backtest_v2`).
4. Ranks subsets; re-runs **top-K on the OOS holdout**; flags rank stability (selected subset must keep positive expectancy & PF>1 OOS and not collapse vs in-sample).
5. Emits `results/analysis/session_sweep_{INSTRUMENT}.json` (leaderboard + IS/OOS deltas + recommended subset) and a console summary via `console_safe`.

**Decision rule (the economic gate, reused):** pick the subset with the best in-sample `expectancy_rr`/PF whose **OOS** run keeps `expectancy_rr > 0` and `PF > 1` and ranks in the top-K both windows. If no subset clears OOS → instrument stays at its current/empty selection (document the FAIL, like SOLUSDT).

## Steps

1. **Build the sweep harness** — `scripts/analysis/session_sweep.py`. Reuse `CandleLoader`, `backtest_v2`, `BacktestMetrics`, `resolve_allowed_sessions`/`dataclasses.replace`, `console_safe`. Argparse: `--instrument --data-dir --version (default active) --train-split 0.8 --top-k 5 --output`.
2. **BNBUSDT sweep** — run vs active v4 params. Confirm whether all-sessions is optimal or a subset (e.g. drop ASIA) wins on PF/DD. Reproduce the Phase 6b funnel as a sanity check (OFF_SESSION+ASIA materially change trade count).
3. **SOLUSDT sweep** — find a profitable OOS-stable subset (it may be profitable in a *subset* even though all-sessions was PF~0.98) or confirm retirement with OOS evidence.
4. **Assemble candidate version `v5_multi_2026_06`** — copy v4, set `engine_runner.allowed_sessions_overrides` to the *selected* subsets per instrument (BNBUSDT refined; SOLUSDT added only if it passed). Re-hash: `python scripts/maintenance/_compute_hash.py`.
5. **Validate** — `python src/config_layer/config_validator.py validate-prod --data-dir data --version v5_multi_2026_06`. Must return **APPROVE**.
6. **Promote (governed)** — `python src/governance/promotion_manager.py from-report --report <approved report> --version v5_multi_2026_06 --data-dir data --instruments ...`, with the OOS sweep reports cited in `--notes` as the pre-promotion OOS evidence (compensating for the absent hard OOS gate). Appends `PROMOTED` to `configs/promotion_log.jsonl`; updates `ACTIVE_VERSION`.
7. **(Optional follow-up, separate Brick)** — harden OOS from "required evidence artifact" into a real gate: add an OOS check to `ConfigValidator.validate()` or make `session_sweep`'s OOS-stability a reusable promotion precondition. Out of scope for the first pass to keep governance changes minimal.

## Critical files
- **New:** `scripts/analysis/session_sweep.py` (only new code; thin wrapper).
- **Read/reuse:** `src/config_layer/production_config.py:266–304` (resolver), `src/config_layer/config_validator.py:435–439` (override application pattern), `src/runtime/backtest_v2.py` (runner + ROI/BacktestMetrics), `scripts/training/auto_tuner_multi.py:610–622` (IS/OOS split math), `src/config_layer/crt_engine_v2.py:2589–2611` (filter, for sanity-checking session labels), `src/utils/console_safe.py`.
- **Config edits (Step 4+):** `configs/production/v5_multi_2026_06.json` (new, derived from v4), `configs/production/ACTIVE_VERSION` (via promotion only).
- **Governance:** `src/governance/promotion_manager.py`, `configs/promotion_log.jsonl`.

## Verification (end-to-end)
1. **Harness correctness:** run `session_sweep.py --instrument BNBUSDT --train-split 0.8`. Confirm the all-sessions row reproduces v4's ~39 trades / PF~1.63 on the full window (sanity vs known promotion metrics), and that restricting to `{LONDON,NEWYORK}` collapses trade count (reproduces the Phase 6b 64-retest SESSION kill).
2. **No-lookahead / determinism:** OOS uses a strict forward index split (reuse tuner math); re-running yields identical leaderboards (`CLAUDE.md §4` no-lookahead invariant).
3. **Governance gate:** `config_validator.py validate-prod --version v5_multi_2026_06` returns **APPROVE**; promotion writes a `PROMOTED` line and flips `ACTIVE_VERSION`. Rollback path: restore archived v4 + re-point `ACTIVE_VERSION`.
4. **Regression:** run the pre-promotion pytest pack (`docs/reference/testing.md`); sessions changes touch no engine code, so failures would indicate harness/config breakage.

## Risks & notes
- **Overfit to OOS picks** — mitigated by top-K rank-stability rule + small, interpretable subset space (sessions, not continuous params).
- **`overlap` token is inert** — don't treat it as a real session; selection is over `{LONDON,NEWYORK,ASIA,OFF_SESSION}`.
- **Memory reconciliation (do on implement):** update `project_trd_m6_downstream.md` / Phase 6b notes — active prod is **v4_multi_2026_06**, BNBUSDT all-sessions already promoted, SOLUSDT excluded at PF~0.98; "Part 4A OOS" is a *gap to build*, not an existing harness.
- **Doctrine:** measure-only sweep first (no deviation flag needed); promotion goes through the existing APPROVE gate (no new authority). Per `CLAUDE.md §6`, append a SESSION LOG entry and (if it touches a topic doc) Sync per §6.1 on implement.

---
📝 SESSION LOG ENTRY
Date: 2026-06-03
Topic: Plan — per-instrument session optimization as first lever of the H3 "freeze V2 / fund governance+selection" pivot
Decision/Output: Plan written to plan file. Verified ground truth vs stale memory: active=v4_multi_2026_06; BNBUSDT already opened to all-sessions (APPROVE, PF1.63); SOLUSDT excluded PF~0.98; no OOS gate exists (only tuner --train-split). Plan: build measure-only session-subset sweep (scripts/analysis/session_sweep.py) with IS/OOS rank-stability decision rule → select optimal per-instrument allowed_sessions → promote v5_multi_2026_06 via governed APPROVE path, OOS reports as cited evidence.
Open Questions: Whether to harden OOS into a real ConfigValidator gate now or as a follow-up Brick (plan defers it).
Next Step: On approval — implement session_sweep.py, run BNBUSDT + SOLUSDT sweeps, then assemble/validate/promote v5.
---
