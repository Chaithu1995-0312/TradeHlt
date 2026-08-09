# Runtime Benchmark Suite — Authority (2026-07-20)

| Field | Value |
|---|---|
| Suite ID | `RUNTIME-BENCHMARK-SUITE-2026-07-20` |
| Status token | **`RUNTIME_BENCHMARK_SUITE = AUTHORITY_ACTIVE`** |
| Effective | 2026-07-20 |
| Machine pin / manifest | [`runtime-benchmark-suite-pin-2026-07-20.json`](runtime-benchmark-suite-pin-2026-07-20.json) |
| Roadmap home | [`docs/implementation_plan/backtest-runtime-roadmap-2026-07-20.md`](../implementation_plan/backtest-runtime-roadmap-2026-07-20.md) R-1 / R-2 |
| Active config | `v2_multi_2026_04` |
| Floor | `tests/test_runtime_benchmark_suite.py` |

---

## 1. Separate authority (non-negotiable)

This suite is **not** the feature-layer freeze pin.

| Authority | Pin | What parity means |
|---|---|---|
| **Feature freeze** | `feature-layer-freeze-pin-2026-07-20.json` | XAUUSD feature matrix + schema + source SHAs |
| **Runtime suite** | `runtime-benchmark-suite-pin-2026-07-20.json` | Backtest/runtime admission paths, gate mode, ledgers, coverage |

**Invariant:** matching a feature-matrix SHA does **not** imply runtime benchmark parity, and
matching a runtime events hash does **not** unfreeze or re-certify features.

```text
FEATURE_LAYER_MUTATION_FREEZE  ≠  RUNTIME_BENCHMARK_SUITE
```

---

## 2. Why this suite exists (R-1.1)

F-037: research spines often run with `BACKTEST_ENGINE_GATE=0` (CRT-only). Live always runs
the EngineRunner fusion path. A result without an **explicit gate mode** is not comparable
evidence.

**R-1.1 rule:** every runtime benchmark run **must** record:

| Field | Required |
|---|---|
| `backtest_engine_gate` | `"0"` or `"1"` (process env at run start; not inferred from memory) |
| `active_config_version` | from `configs/production/ACTIVE_VERSION` |
| `instrument` + `csv_path` + `csv_sha256` | corpus identity |
| `cli_argv` | exact invocation |
| `scorer_mode` | e.g. `calibrated` |
| artifact hashes | `events.jsonl`, `summary.json` at minimum |

If gate mode is missing → run is **INADMISSIBLE** for suite acceptance.

---

## 3. Provenance model

Each **run record** in the suite pin carries:

1. **Input provenance** — CSV path, SHA-256, row count, instrument  
2. **Config provenance** — `ACTIVE_VERSION`, production config SHA, `BACKTEST_ENGINE_GATE`  
3. **Process provenance** — UTC start/end, argv, Python invocation note  
4. **Output provenance** — run directory, SHA-256 of key artifacts  
5. **Coverage** — what paths fired (filters, planner, partial TP, engine gate, …)  
6. **Metrics (non-authoritative for edge)** — n_trades, PF, etc. (descriptive only; §6.5)

**Append discipline:** do not rewrite past run records. New baselines get new `run_id`s;
`LATEST` pointers may move.

---

## 4. Coverage metadata (anti false-green)

Every accepted run **must** include `coverage` with at least:

```json
{
  "benchmark_class": "RUNTIME_BACKTEST",
  "backtest_engine_gate": "0|1",
  "exercises": {
    "backtest_v2": true,
    "crt_state_machine": true,
    "session_filter": true|false,
    "engine_runner_fusion_gate": true|false,
    "trade_opened": true|false,
    "partial_tp": true|false,
    "execution_planner_path": "unknown|exercised|not_reached",
    "ultron_risk_gate": "unknown|exercised|not_reached"
  },
  "filter_reject_reasons": {},
  "engine_reject_count": 0,
  "trade_count": 0,
  "notes": ""
}
```

**Interpretation rule:** two runs with equal `events_sha256` share ledger identity; two runs
with equal feature-matrix SHA share only feature emission. Coverage tells you which
**decision paths** were actually hit.

---

## 5. Acceptance criteria

### Suite-level

| Criterion | Rule |
|---|---|
| A1 Authority separation | Pin does not embed feature-layer vector SHAs as pass/fail gates |
| A2 Gate explicit | Every run has `backtest_engine_gate` ∈ {`0`,`1`} |
| A3 Corpus pinned | CSV SHA matches suite pin (or documented corpus authority decision) |
| A4 Config pinned | `active_config_version` == `ACTIVE_VERSION` at capture time |
| A5 Artifacts exist | `*_summary.json` + `*_events.jsonl` present and hashed |
| A6 Coverage present | `coverage` object with required keys |
| A7 No edge claim | Suite docs/tests never treat PF/expectancy as promotion authority |

### RB1 (BNB Gate ON/OFF) — first pair

| Criterion | Rule |
|---|---|
| B1 | Same CSV, instrument, scorer, config version for both arms |
| B2 | Arm A: `BACKTEST_ENGINE_GATE=0`; Arm B: `BACKTEST_ENGINE_GATE=1` |
| B3 | Both arms complete without dataset REJECT |
| B4 | Manifest records Δ(trade_count), both events SHAs, both summaries |
| B5 | Floor test can re-hash artifacts on disk and match pin (if artifacts retained) |

**Pass** = measurement honesty + reproducible fingerprints.  
**Not pass** = “BNB is profitable” or “gate should be ON in research.”

---

## 6. First members

| ID | Name | Status | Iteration cost |
|---|---|---|---|
| **RB1** | **XAUUSD 2-month window** · Gate OFF vs Gate ON | **primary** (R-1.1 / R-2.2) | ~minutes total for both arms |
| RB1-HEAVY | BNBUSDT full corpus (70k bars) · Gate OFF vs ON | **optional** / archival only | ~10–15 min **per arm** — do not use as default |
| RB2 | Multi-instrument execution | planned | — |
| RB3 | Trade ledger parity / determinism (2×) | planned | — |

### Iteration rule (binding)

**Default runtime analysis uses the XAUUSD 2-month window**  
(`data/XAUUSD_W2026-03-23-to-2026-05-21.csv`, ~3,949 M15 bars).

Full multi-year corpora (e.g. BNBUSDT 70k bars) are **RB-HEAVY**: run only when
explicitly needed for multi-instrument generality, never as the default pair for
every analysis. A full ON/OFF pair on BNB is ~20–30 minutes of wall clock — wrong
default for governance iteration.

---

## 7. Relationship to feature freeze

| Action | Allowed? |
|---|---|
| Change runtime code and re-run RB1 | Yes — update suite pin in same change set |
| Change feature math / ontology / periods | **No** without feature-layer freeze waiver; feature pin must stay green |
| Add BNB feature-matrix hash to feature freeze pin | **No** — user-scoped 2026-07-20b |
| Use RB1 for fusion/gate research discussion | Yes — descriptive only |

---

## 8. Mechanical enforcement

`tests/test_runtime_benchmark_suite.py`:

- policy + pin exist; status token present  
- authority separation (no feature freeze vector keys as suite gates)  
- RB1 both arms present with gate 0 and 1  
- required provenance + coverage fields  
- optional: re-hash local artifacts if `artifacts_retained: true`

---

## 9. Waiver / update procedure

1. Re-run with explicit `BACKTEST_ENGINE_GATE` in process env (never silent default in notes).  
2. Capture artifacts under `results/runtime_benchmarks/…`.  
3. Rebuild suite pin fields for that run (SHA + coverage).  
4. SESSION LOG entry citing suite ID + run_ids.  
5. Floor green.
