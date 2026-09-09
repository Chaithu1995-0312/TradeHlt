# Feature-Math Ownership Lint

_Generated 2026-08-20T18:52:30.741170+00:00 by `scripts/analysis/feature_math_lint.py` (read-only)._

**Modules scanned** 108 · **registered features** 75 · **derivations found** 1 (NEW 0 · pins 1 · retired 9 · stale-pins 0)

## NEW violations (must be empty — fix by routing through the registry)

_none — floor is green_

## Grandfather ledger (GD-0NN → Matrix v1 adjudication)

| GD | site | semantic | formula_equiv | exec_reach | decision_reach |
|---|---|---|---|---|---|
| GD-010 | `engines/rr_engine.py` RREngine.compute::candle_range | same_quantity | byte_identical | conditional | conditional |

_Ledger: baseline 10 · current 1 · retired 9. Full evidence + call-chains: `docs/analysis/feature-math-divergence-adjudication.md`._

## Structural shape copies (RC-6 — SP-001 sweep / SP-002 F-074 core, shape not name)

**NEW** 0 — the pair (pierce AND close-back) is required, never a lone compare.

_none — floor is green_

## Dimensional-unit mismatches (F-072, naming-convention heuristic — see module docstring)

**Watch-list** compute_crt_levels(atr) · **NEW** 0 · **pinned** 0 · **stale-pins** 0

_none — floor is green_