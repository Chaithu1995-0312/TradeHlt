# Determinism Report (2026-06-12)

> **Purpose (Phase 5):** prove that *same config + same CSV + same window* yields identical trades,
> metrics **and artifacts**; locate any nondeterminism. Extends the
> [`replay-governance.md`](../architecture/replay-governance.md) acceptance gate.

## What was proven (empirical, executed)
Ran each instrument **twice** (40k candles) and SHA-256-diffed every artifact in the run's output dir:

| Instrument | trades.csv | crt_telemetry.jsonl | events.jsonl | summary.json | report.txt |
|---|---|---|---|---|---|
| **BNBUSDT** | ✅ identical | ✅ identical (3.86 MB) | ✅ identical (3.67 MB) | ✅ identical | ✅ identical |
| **SOLUSDT** | ✅ identical | ✅ identical (4.09 MB) | ✅ identical (3.89 MB) | ✅ identical | ✅ identical |

**Every byte of every content artifact is replay-identical, for two independent instruments.** This
is stronger than the pre-existing gate (which checked only the ledger + 7 summary scalars for one
instrument): the full *decision-explainability trail* (telemetry + events) is deterministic, and the
property is shown to be a property of the **engine**, not of one CSV.

## Sources of (benign) variance — located
| Source | Determinism-safe? | Why |
|---|---|---|
| Run **directory name** `run_<wallclock>_<INSTR>` | safe | wall-clock in the *name* only; **file contents** carry no wall-clock |
| `summary.json` / `report.txt` body | safe | no `generated_at`/`run_id` embedded in content (verified byte-identical) |
| Slippage RNG | safe | F3 hygiene fix landed (seeded; `backtest_v2.py` discarded-call removed) |
| dict/set iteration | safe | no observed ordering leak (artifacts identical) |
| LLM tie-breaker | safe | off the replay path; fail-open neutral 1.0 (non-negotiable, replay-governance §LLM) |
| Float accumulation order | safe | identical ledger ⇒ identical accumulation |

No nondeterminism found in the data→decision→backtest→metrics→artifacts path.

## Gate extension (this session, additive)
`tests/runtime/test_replay_determinism.py` extended with
`test_all_artifacts_byte_identical_across_runs`, parametrized over **BNBUSDT + SOLUSDT**, asserting
the full artifact set (telemetry/events/summary/report/trades) is byte-identical across two runs
(skips if a CSV is absent). The original ledger+metrics tests are retained.

## Residual risk (honest)
- **Coverage is 2 instruments × 40k candles.** Determinism is proven, not exhaustively (other
  instruments/full spans untested). The engine has no instrument-specific RNG, so generalization is
  *likely*, not *certain*.
- **Cross-process / cross-machine** determinism not tested (same-process here). Float determinism
  across BLAS/NumPy builds is a known general risk; the spine is largely pure-Python arithmetic,
  lowering exposure.
- **Sidecars** (ReplayMemory/Cluster) are non-deterministic-looking in tests (cluster collapse) but
  are off the spine (F-012) — out of scope for spine replay.

## Verdict
Spine determinism — including telemetry artifacts — is **proven and now gated**. Grade A. A
researcher can trust that re-running a backtest reproduces the exact ledger *and* the exact audit
trail used to explain it.
