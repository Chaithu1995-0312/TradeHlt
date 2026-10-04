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
