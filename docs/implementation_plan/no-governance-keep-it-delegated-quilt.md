# Reusable CRT trace workflow — playbook + instrument parameterization + driver

## Context

This session built three observe-only scripts that, chained, took a question from "what data do
we have" to a replayable numerical proof of why a specific trade was rejected:

| Stage | Script | Answers |
|---|---|---|
| **SURVEY** | `xauusd_excel_feature_state_trace.py` | What happened, bar by bar? OHLC → 39 features → CRT state |
| **LOCATE** | `session_filter_funnel_probe.py` | Where does it die, and what would change that? Gate funnel × counterfactual arms |
| **PROVE** | `crt_episode_number_trace.py` | Exactly which numbers produced that outcome? Provenance-classed operands + engine-parity |

Run once on XAUUSD it found: `OVERLAP` is a dead token in `allowed_sessions`, the session windows
cover 6 of 23 hours, the windows are commented UTC but compared against broker time, and behind
all of that a **second binding gate** (inverted SL) that the session filter was masking.

It also found two defects in its own instrumentation — both from asserts that could not fail.
That is the pattern worth institutionalizing: the method is only as good as its falsifiability
discipline.

The goal now is to be able to re-run this repeatedly — different instruments, different windows —
as a **bug-hunting loop over the trading flow**, not a one-off.

**A finding that shapes the design:** all six MT5 instruments (XAUUSD, EURUSD, GBPUSD, AUDUSD,
USDJPY, EURCAD) resolve to *identical* CRT config today — same `allowed_sessions`, same
`sl_atr_buffer`, same `body_ratio_min`. So the instrument axis varies **data only**, and the
`OVERLAP` dead-token defect is repo-wide rather than XAUUSD-specific. The driver should say this
out loud in its preflight so a cross-instrument run is never mistaken for a config comparison.

## 1. Playbook — `scripts/analysis/CRT_TRACE_WORKFLOW.md`

The methodology, written to be followed by someone (or some session) with no memory of this work.

- **The three stages**, what question each answers, what it consumes and emits, and when to stop.
- **Corpus sizing rule:** debug on the *small* corpus. 47k bars hid both instrumentation defects;
  1,195 bars exposed them in one run. Use the large corpus only to put rates on a mechanism the
  small corpus has already explained.
- **Assert discipline (the core of it):**
  - An assert that cannot fail is worse than none — it manufactures false confidence.
  - Both real instances from this session, as worked examples: defining
    `reached_session = passed + rejected` then asserting that identity; and
    `if "sl_engine" in names: assert ...` when the missing row *was* the bug.
  - Every parity-style assert ships with a **three-state demo**: normal → PASS, perturbed → FAIL,
    restored → PASS.
- **Provenance vocabulary** (`OHLC` / `FEATURE` / `STATE` / `CONFIG` / `DERIVED` / `ENGINE`) and
  the epistemic ladder (`OBSERVED` > `DERIVED` > `INFERRED_BY_ORDER`), with the two standing
  rules: never collapse `DERIVED` and `ENGINE` even when equal; never render
  `INFERRED_BY_ORDER` as `OBSERVED`.
- **Recurring failure-mode checklist** to run against any new probe:
  1. Does every assert have an input that would make it fail?
  2. Am I recomputing something the engine already emits? If I must, do I check against it?
  3. Does my counterfactual override a field something *else* also reads? (`session_windows`
     also feeds `score_time` → `final_S`.)
  4. Am I snapshotting after a reset that already cleared the state? (`reset_to_range`.)
  5. Copy or reference — will later enrichment reach the object I stored?
  6. Is a "0 results" outcome real, or is my terminal-detection missing a silent path?
     (`build_trade` failure leaves `action="NONE"`.)
- **Pre-registration:** hand-compute expected outcomes before running; a run that confirms four
  predicted cells is evidence, a run you read afterwards is a lookup.
- **Scope discipline:** these artifacts are descriptive. They explain behavior; they grant no
  authority to change it.

## 2. Parameterization — `--instrument` on all three scripts

Mechanical and contained: each script has `INSTRUMENT = "XAUUSD"` used in ~4 places
(`load_prod_config_from_registry`, `HTFBuilder`, EngineRunner `input_data`/`context`, manifest).

- Replace the module constant with a value resolved in `main()` and threaded through
  `replay*()` / `run_gate_overlay()` / manifest builders as a parameter. No global mutation.
- Default corpus: `data/mt5/{INSTRUMENT}_M15.csv`; `--csv` / `--xlsx` still override.
- In `crt_episode_number_trace.py`, default `--feature-csv` to the corpus itself when it is a CSV
  (the XAUUSD xlsx/CSV twin was a special case, and the existing same-corpus assert stays).
- De-XAUUSD the logger names, report titles, and default output dirs.

## 3. Driver — `scripts/analysis/run_crt_trace_workflow.py`

```bash
venv/Scripts/python.exe scripts/analysis/run_crt_trace_workflow.py --instrument EURUSD
venv/Scripts/python.exe scripts/analysis/run_crt_trace_workflow.py \
    --instrument XAUUSD --corpus data/XAUUSD_M15_20260807_203705.xlsx
```

- **Preflight (fail fast, before any replay):** config resolves for the instrument; corpus exists;
  report bar count + first/last timestamp; print the resolved `allowed_sessions` /
  `session_windows` / `sl_atr_buffer` **and** the note that config is currently instrument-invariant.
- **Stages run in-process** by importing each module and calling `main(argv)` — already proven to
  work, since `crt_episode_number_trace` imports the other two. Each stage gets an explicit
  `--output-dir` under one workflow directory; the driver resolves the stamped subdir it created.
- **Fail loudly.** Any assert firing in any stage aborts the workflow with that stage named. A
  partial workflow must never look like a complete one.
- **`INDEX.md`** — one page per run: preflight block, per-stage headline numbers (bars, RETESTs,
  where they died, per-arm passes/trades, parity verdict), and links to every artifact.

## Critical files

| File | Change |
|---|---|
| `scripts/analysis/CRT_TRACE_WORKFLOW.md` | **new** — the playbook |
| `scripts/analysis/run_crt_trace_workflow.py` | **new** — preflight + 3-stage driver + `INDEX.md` |
| `scripts/analysis/xauusd_excel_feature_state_trace.py` | `--instrument`, corpus default, de-XAUUSD naming |
| `scripts/analysis/session_filter_funnel_probe.py` | same |
| `scripts/analysis/crt_episode_number_trace.py` | same + `--feature-csv` defaulting |

No `src/`, no config, no `ACTIVE_VERSION`.

## Verification

1. **Regression on the known case** — full driver, XAUUSD, 17-day corpus. Must reproduce exactly:
   1,195 bars; 2 `RETEST_CONFIRMED`; A0 0 session passes / 0 trades; A3 2 passes / 0 trades /
   2 inverted-SL; parity `|delta_sl| = 1.429e-06` PASS. Any drift means the parameterization
   changed behavior.
2. **Second instrument end-to-end** — run on EURUSD from `data/mt5/EURUSD_M15.csv`. Must complete
   and produce a coherent `INDEX.md`. **No expectation on the numbers** — that is a fresh
   measurement, not a target. If it finds 0 RETESTs, the workflow must say so plainly rather than
   emit an empty-looking success.
3. **Perturbation demo still bites** — the three-state check on the parity assert after
   parameterization: normal → PASS, perturbed → FAIL, restored → PASS.
4. **Failure propagation** — deliberately point the driver at a nonexistent instrument and at a
   missing corpus; both must abort in preflight naming the cause, not half-run.
5. **INDEX.md integrity** — every linked artifact exists; assert no dead links at write time.
6. **No side effects** — `git status` shows only the analysis scripts and the playbook.

## Scope

The workflow is a descriptive bug-hunting instrument. It explains engine behavior and surfaces
defects; it grants no authority to change the SL rule, the session windows, the RETEST acceptance
rule, or any config. Anything it finds that warrants a behavior change is a separate, separately
authorized decision.
