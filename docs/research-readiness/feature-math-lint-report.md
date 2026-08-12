# Feature-Math Ownership Lint

_Generated 2026-08-12T05:08:59.389022+00:00 by `scripts/analysis/feature_math_lint.py` (read-only)._

**Modules scanned** 84 · **registered features** 57 · **derivations found** 1 (NEW 0 · pins 1 · retired 9 · stale-pins 0)

## NEW violations (must be empty — fix by routing through the registry)

_none — floor is green_

## Grandfather ledger (GD-0NN → Matrix v1 adjudication)

| GD | site | semantic | formula_equiv | exec_reach | decision_reach |
|---|---|---|---|---|---|
| GD-010 | `engines/rr_engine.py` RREngine.compute::candle_range | same_quantity | byte_identical | conditional | conditional |

_Ledger: baseline 10 · current 1 · retired 9. Full evidence + call-chains: `docs/analysis/feature-math-divergence-adjudication.md`._

## Dimensional-unit mismatches (F-072, naming-convention heuristic — see module docstring)

**Watch-list** compute_crt_levels(atr) · **NEW** 0 · **pinned** 1 · **stale-pins** 0

_none — floor is green_

| pin | site | reason |
|---|---|---|
| DM-001 | `runtime/live_engine_hook.py:916` | dead code per F-073 (HookedLiveEngine never instantiated); fix is scoped with the live-rail repair/retire decision, not here |