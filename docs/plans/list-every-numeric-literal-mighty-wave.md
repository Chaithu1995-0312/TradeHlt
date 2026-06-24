> Created: 2026-06-06 · Updated: 2026-06-06 · Milestone: Trd-M5 / Gov-M2

# Plan: Externalize High-Leverage Hard-Coded Literals

## Context

Audit confirmed ~75% of runtime parameters are already config-driven. Only ~20 literals remain hard-coded with material outcome impact. This plan converts the top 5 highest-leverage items only. Blanket externalization has poor ROI; backtest sensitivity must be measured before touching others.

Aligns with F-003 (throughput is the bottleneck) — fusion consensus rules directly control trade frequency and selection quality.

---

## Scope: 5 Items Only

| Priority | Literal | File:Line | Current Value | Config Key to Add | Config Section |
|----------|---------|-----------|---------------|-------------------|----------------|
| 1 | `min_signals` (consensus) | `src/core/fusion_engine.py:731` | `2` | `min_consensus_signals` | `fusion_engine` |
| 2 | `min_agreement` (consensus) | `src/core/fusion_engine.py:741` | `0.60` | `min_consensus_agreement` | `fusion_engine` |
| 3 | Score component weights | `src/engines/scoring_engine.py:44` | `0.35/0.25/0.20/0.20` | `score_component_weights` | `crt_engine` |
| 4 | `_FALLBACK_TOP_N` | `src/core/decision_engine.py:38` | `3` | `fallback_top_n` | `decision_engine` |
| 5 | `PROMOTION_MARGIN` | `src/core/model_registry.py:40` | `0.02` | `model_promotion_margin` | `governance` |

**Do NOT touch:** normalizer window (1000), threshold window (1000), dataset sample gates — these require deeper impact analysis first.

---

## Implementation Steps

### Step 1 — Add config keys to active production config (`configs/production/v4_multi_2026_06.json`)

For each of the 5 literals, add a key to the appropriate section. Also add to `v1_multi_2026_03.json` (baseline) with same values to keep configs in sync.

New keys:
```json
// fusion_engine section
"min_consensus_signals": 2,
"min_consensus_agreement": 0.60,

// crt_engine section
"score_component_weights": [0.35, 0.25, 0.20, 0.20],

// decision_engine section
"fallback_top_n": 3,

// governance section
"model_promotion_margin": 0.02
```

### Step 2 — Wire each literal to read from config

**fusion_engine.py:731** — replace `min_signals=2` with `min_signals=self._cfg.get("min_consensus_signals", 2)`  
**fusion_engine.py:741** — replace `min_agreement=0.60` with `min_agreement=self._cfg.get("min_consensus_agreement", 0.60)`  
**scoring_engine.py:44** — replace tuple literal with `self._weights = cfg.get("score_component_weights", [0.35, 0.25, 0.20, 0.20])`  
**decision_engine.py:38** — replace `_FALLBACK_TOP_N = 3` with value loaded from config at init  
**model_registry.py:40** — replace `PROMOTION_MARGIN = 0.02` with value loaded from governance config section  

Follow `_require()` / `get_prod_section()` pattern per `docs/reference/example-service.py`. No magic numbers remain in Python.

### Step 3 — Re-hash the config

```
python scripts/maintenance/_compute_hash.py
```

### Step 4 — Run regression suite

```
pytest tests/ -x -q
```

Confirm: no test failures, no drift in existing backtest metrics.

### Step 5 — Backtest sensitivity (before any value changes)

Run a baseline backtest with values held at current defaults, then vary each new config key ±1 step to measure impact on trade count and PF. Record in SESSION LOG. Only then tune values.

---

## What NOT to Convert (Frozen by Doctrine)

`0.0/1.0` clamp bounds · EMA `2.0/(period+1)` formula · weight-sum tolerance `0.01` · direction midpoint `0.5` · Fibonacci `1.618` reset · `1e-9` epsilon · confidence mapping `abs(s-0.5)*2.0`

---

## Verification

1. `pytest tests/ -x -q` — all green
2. Spot-check: run a single backtest and confirm `score_component_weights` from config is used (add a debug log or assert in test)
3. Confirm `promotion_manager.py` reads `model_promotion_margin` from config instead of the constant
4. Config hash updated — `python scripts/maintenance/_compute_hash.py` exits 0

---

## Citation Sync (§6.3)

After editing `model_registry.py` and `scoring_engine.py`, check `docs/architecture/citation-map.generated.md` for any `path:line · Symbol` citations that reference these files and update line numbers.

After changes, append SESSION LOG to `assistant_project.md`.
