# Resolve F-048 — RR ownership: DecisionEngine becomes semantic-approval only

## Context

**What prompted this.** The user articulated a clean separation of concerns and asked to "rewind
F-048" → *resolve the ownership call now*:

```
DecisionEngine  →  "Is this a valid market opportunity?"   (semantic evidence)
                   NOT "Will this make money?"             (economics)
```

DecisionEngine must never know fees / taxes / slippage / brokerage / portfolio / capital / RR.
The economic reward:risk question is owned downstream by UltronRiskGate; concrete SL/TP + sizing
by ExecutionPlanner.

**The current state is a half-measure.** F-048 (the RR gate consuming candle polarity ∈[0.5,1]
against `rr_threshold=1.5`, so `run()` executed 0/70,002) was patched in the working tree with a
*shim*: `_economic_rr_from_fusion` ([decision_engine.py:76](src/core/decision_engine.py:76)) that
teaches DecisionEngine to *recognize polarity and skip*. But DecisionEngine still holds
`rr_threshold` and still enforces an economic RR floor whenever `true_rr` is supplied. That is
DecisionEngine still knowing about economics — the exact mixing the user wants gone. The shim is
uncommitted and F-048's finding record still describes the pre-shim mechanism (a §6.2 drift).

**Intended outcome.** DecisionEngine's inputs become exactly {score, p_win, zone validity,
weak_component}. All RR — polarity (contract A, feeds FusionEngine averaging) and economic
(contract D, SL/TP-derived) — lives outside it. Economic RR is enforced solely by
`UltronRiskGate` Check 2 ([ultron_risk_gate.py:228](src/core/ultron_risk_gate.py:228),
`min_rr_ratio`, already cost-taxed by spread+slippage).

**Why this is safe (parity).** No production or backtest path supplies an economic RR to
DecisionEngine: `engine_runner` omits `true_rr` ([engine_runner.py:1035](src/core/engine_runner.py:1035))
and marks polarity; nothing else writes it. So the economic gate is already **dead-by-absence** on
every real path — removing it is *definitional, not behavioral*. On the sole XAUUSD candidate in
47,275 bars, the reject fires at `zone_gate_invalid` (evaluate line 159), three gates **before** the
RR gate (line 183), so the ledger cannot change. Behavior differs only in unit-test injectors that
feed economic RR directly.

**Governance note.** This is the one governance action being un-paused, because the user explicitly
asked to resolve F-048. Broader governance (State Consolidation, other findings) stays paused.

---

## Current state (verified this session, read-only)

| Fact | Evidence |
|---|---|
| Shim = skip-if-polarity, still enforces economic floor | [decision_engine.py:76-102,181-185](src/core/decision_engine.py:76) |
| `rr_threshold` is in the `decision_engine` section, **not** `params` | config grep → hash-neutral to remove |
| `decide_batch` routes through `evaluate()` — one gate site | [decision_engine.py:218](src/core/decision_engine.py:218) |
| Gate order: zone → score → p_win → **rr** | evaluate lines 159/164/169/183 |
| Only reader of `decision_engine.rr_threshold` is DecisionEngine | grep (live_engine_hook:474 is a comment; analytics/clustering `rr_threshold` is its own unrelated knob) |
| `low_rr` reject has a second, independent meaning | `analytics/clustering.py` post-hoc loss-cluster label — untouched |
| Economic RR already owned + reachable | UltronRiskGate Check 2, after ExecutionPlanner builds SL/TP |
| Only one test file has real dependencies | `tests/test_rr_contract_wiring.py` (imports the helper; asserts `low_rr`). `test_crt_fixes.py` injects `rr:2.0` > threshold → green either way |

---

## Changes

### 1. `src/core/decision_engine.py` — strip the economic RR gate (core change)

- Delete `_economic_rr_from_fusion` (lines 76-102).
- Delete `self.rr_threshold = _require_decision_cfg(config, "rr_threshold")` in `__init__` (line 119).
- Delete the local `rr_threshold` read (line 147) and the economic-RR gate block (lines 173-185).
- Result: `evaluate()` gates on zone validity → dynamic score → p_win → weak_component. No RR term.
- Update the module/class docstrings to state the ownership boundary explicitly (DecisionEngine =
  semantic approval; economic RR owned by UltronRiskGate).

### 2. `src/core/engine_runner.py` — drop the now-dead shim keys from `fusion_ctx`

The `fusion_ctx` built at [engine_runner.py:1031](src/core/engine_runner.py:1031) fed only the
deleted gate. Remove `"rr"` and `"rr_semantic"` (they were the shim's markers); keep
`"candle_polarity"` only if the collector audit record still wants it (harmless, non-decision).
Update the F-048 comment block to record the resolution. Parity-neutral — these keys were consumed
only by `DecisionEngine.evaluate`, which no longer reads them.

### 3. `configs/production/v2_multi_2026_04.json` — retire `decision_engine.rr_threshold`

Remove the orphaned key (line 133). **Hash-neutral** (not in `params`). A key that now gates
nothing is a config illusion (the F-056 class). This is an active-config edit → gated; approval is
via ExitPlanMode. Archived configs + baseline manifests keep their historical `rr_threshold: 1.5` —
do **not** touch those (they are point-in-time records).

### 4. `tests/test_rr_contract_wiring.py` — flip the C-contract tests

- Remove the `_economic_rr_from_fusion` import and `test_economic_rr_helper_skips_polarity_semantic`
  (helper deleted).
- `test_decision_engine_enforces_true_rr` → **invert**: assert DecisionEngine does **not** reject on
  `true_rr=1.0` (economics is not its job) → decision `execute`.
- `test_decision_engine_skips_polarity_rr_gate` → keep (polarity still yields `execute`), reframe
  comment (now trivially true — no RR gate exists).
- `test_true_rr_from_sl_tp_geometry_matches_tp1_mult` (contract D) + `test_active_config_rr_fusion_
  remains_disabled` (contract B) → keep unchanged.
- Add a test asserting `DecisionEngine` has no `rr_threshold` attribute (ownership guard), and a
  test that `UltronRiskGate` is the economic-RR owner (rr below `min_rr_ratio` → `rr_too_low_after_costs`).

### 5. Same-turn doc mandates (§6.2 / §6.3 / §6.4 Findings + Citation + Topic Sync)

- `docs/current-findings.md`: flip **F-048 → RESOLVED**, fill `Reversal:` (shim→full ownership
  separation; economic RR gate removed, not skipped), and update the **Repository Truths Index**
  row. Note the F-048 note that GD-001/002 body_ratio remediation was "BLOCKED behind this" — record
  that it is now unblocked (do not act on it here).
- `docs/topics/fusion-decision.md:23`: remove `rr_threshold` from the `decision_engine` key list.
- `docs/reference/config-reference.md:113`: retire the `rr_threshold` row.
- `src/runtime/live_engine_hook.py:474`: update the stale F-048 comment (mechanism resolved).
- SESSION LOG (`assistant_project.md`) + a Documentation Drift Protocol audit entry.

---

## Explicitly NOT in scope

- No TradeEconomicsEngine (layer 10) — the two unrelated cost models (`research/costs.py` 12bps vs
  UltronRiskGate spread+slippage) stay as-is; consolidating them is a separate future stage.
- No re-enabling `rr_fusion` (contract B stays `enabled:false`, §6.5 / F-038).
- No change to UltronRiskGate logic — it already owns economic RR; we only stop duplicating it.
- No State Consolidation, no other findings (governance stays paused beyond F-048).

---

## Verification

1. **Unit** — RR contract + decision surface:
```bash
python -m pytest tests/test_rr_contract_wiring.py tests/test_crt_fixes.py -q
```
2. **Config loads without the key** + validator passes:
```bash
python -c "import sys; sys.path.insert(0,'src'); from config_layer.production_config import get_prod_config; c=get_prod_config(); assert 'rr_threshold' not in c['decision_engine']; print('ok')"
```
3. **No remaining reader**:
```bash
python scripts/analysis/... # grep: no src/ reference to decision_engine.rr_threshold outside comments
```
4. **Ledger parity (the real proof)** — gate-ON XAUUSD backtest, before vs after, identical
   `total_setups` + `rejection_reasons` (expect 1 setup, reject `zone_gate_invalid`):
```bash
BACKTEST_ENGINE_GATE=1 python scripts/analysis/model_evidence_survey.py --csv data/mt5/XAUUSD_M15.csv --instrument XAUUSD
```
5. **Feature parity untouched** (no feature change — should be trivially identical):
   XAUUSD vector SHA `37f43f449af0720f…`.

**Completion criterion:** DecisionEngine has no RR/economic surface; `rr_threshold` gone from the
active config (hash unchanged); economic RR enforced only by UltronRiskGate; XAUUSD gate-ON ledger
byte-identical; F-048 recorded RESOLVED with the doc set synchronized; affected floors green.
