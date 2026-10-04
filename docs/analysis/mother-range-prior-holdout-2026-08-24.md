# MC-MRPRIOR-XAUUSD-M15-V1 holdout (2026-08-24)

> Point-in-time. Object: `docs/research/mother_range_prior_object.md` (SEM-030).
> Sealed contract: `configs/research/measurement_contracts/instances/MC-MRPRIOR-XAUUSD-M15-V1.json`

Sparse signal = SEM-026 mother-range inside-close entries, resolved to clean-label `(entry_ts, direction)` rows. Prior = SEM-028/FM-054 agreement. This is not the every-bar F-093 grain, not the SEM-026 trade ledger, not a side picker, not P-GOAL-04, and not G001.

## Split

- Population: 320 sparse entries
- Train: 255
- Holdout: 64
- Holdout start: `2025-12-24 19:15:00`
- Embargo: 96 M15 bars
- Purge horizon: 40 M15 bars
- F-086 stride holdout spent: false

## Result

| Arm | y | Train contrast | Holdout agree n | Holdout disagree n | Holdout contrast | Verdict |
|---|---:|---:|---:|---:|---:|---|
| S | `y_mfe_r` | +0.2915 | 9 | 55 | -0.8093 | INSUFFICIENT |
| T | `y_time_to_mfe` | +0.2198 | 9 | 52 | -2.6346 | INSUFFICIENT |

The pre-registered gate required both holdout cells to have `n>=30` per arm and the holdout contrast sign to match train. Both arms fail the power floor because the holdout agreeing cell has `n=9`; both signs also flip.

## E-001

`INSUFFICIENT` is the finding. The sparse signal + prior object was tested under the frozen population, and the result does not authorize threshold changes, a different sparse signal, a different y, a side-picking interpretation, or a pooled/full-sample replacement. `economic_claims_allowed` remains false; mt00/mt01 are UNRUN.
