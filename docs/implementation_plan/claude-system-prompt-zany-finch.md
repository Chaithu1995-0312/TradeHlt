# Shadow CRT-State Pipeline — Consistency Audit & Remediation

## Context

The repo has a **complete parallel "semantic pipeline"** (Layers 1–5, built out over recent
days, culminating **today 2026-07-24**) that reinterprets the OHLCV→Features→Ontology→States flow:

```
OHLCV → feature_pipeline (39-dim v4.0) → market_ontology.yaml (WHAT + states)
      → feature_states.FeatureStateEncoder (values→declared states)
      → market_context / market_shape
      → crt_state_resolver.CRTStateResolver + market_crt_states.yaml  (9 CRT states)
```

This whole stack is **deliberately shadow/sidecar** — `feature_states.py:18` states plainly
"NOT on the decision path… nothing on the spine consumes this output," and
`crt_state_resolver.py:10` "runs alongside the CRT engine, not replacing it. The CRT engine
(`crt_engine_v2.py`) remains the execution authority." The resolver is a **hand-ported second
implementation** of the CRT state machine (SWEEP→DISPLACEMENT→EXPANSION funnel, continuous
gates, lifecycle HTF/gap resets, shadow-pending memory, TTL).

**Why validate it:** a shadow that silently diverges from the authority is worse than no shadow —
every research/validation artifact built on the resolver (`crt_state_confusion_matrix.py`,
`run_crt_state_on_mt5_xauusd.py`, `validate_crt_state_resolver.py`) then measures a *different*
state machine than the one that trades, and any conclusion drawn is contaminated. The scope of
this pass (user-selected): **semantic drift vs `crt_engine_v2`, dormancy, and fail-fast
violations** in the Layer-5 shadow. Governance is frozen for this session — deliverable is **code
fixes + a source-grounded divergence assessment reported in chat**, NOT audit/closure/governance
markdown.

## Confirmed defects (source-verified)

**D1 — v4.0 rename silently disables the DISPLACEMENT wick/ATR gate (semantic drift).**
`crt_state_resolver.py:763` reads `raw.get("wick_size")`. Schema v4.0 (`feature_schema.py:89`,
2026-07-22) renamed `wick_size`→`candle_range`; `_normalize_features` (`:551`) zips the canonical
vector with the v4.0 names, so `wick_size` is **absent** and the `if wick is not None` branch
(`:764`) is skipped → gate 4 never fires. The authoritative engine **does** enforce it
(`crt_engine_v2.py:1198`, `candle.wick_size < atr_multiplier_min * atr_abs`, where the engine's
`Candle.wick_size` ≡ FM-002 `candle_range` = high−low). Result: shadow DISPLACEMENT is looser than
the engine on the real vector path. Classification: **Semantic Drift + Wiring Drift**.

**D2 — Stale-dimension comments (DOC_DRIFT in code).** `market_crt_states.yaml:237` ("atr in the
38-dim vector") and `crt_state_resolver.py:766` region reference the 38-dim vector; schema is now
39-dim v4.0. Non-behavioral but misleading. Classification: **Semantic Drift (comment)**.

**D3 — Dead code in `_validate_predicates`.** `crt_state_resolver.py:518–522` builds
`declared_state_names` via `type("s", (), {"name": k})()` then discards it ("Rebuild properly").
Classification: **Dead Code**.

## Items to determine during the pass (grounded hypotheses, verify before fixing)

- **Systematic v4.0-rename sweep.** D1 may not be the only one. Grep the whole Layer-2→5 stack for
  pre-v4.0 canonical names (`wick_size`, `macd_hist`, and the {0..2}→{0..4} `session` domain
  change) to find every stale reference. Representative surfaces: `crt_state_resolver.py`,
  `feature_states.py`, `market_context.py`, `market_shape.py`, `market_crt_states.yaml`.
- **Fail-open continuous gates vs the stack's own fail-fast doctrine.** `_continuous_gates_pass`
  ("Missing values → pass", `:663`) contradicts `feature_states.py:20` ("no defaults, no
  fallbacks"). Catalog which engine gates are fail-open on the canonical path (D1 is the concrete
  instance) and decide fail-closed vs fail-open per gate against the engine's behavior.
- **`candle_range` unit.** When fixing D1, confirm whether the vector's `candle_range` is absolute
  price (high−low) or normalized — the engine compares absolute `wick_size` to `atr_abs`. The
  resolver's existing relative/absolute heuristic (`:766–770`) must stay unit-correct.
- **Divergence ledger: resolver gates/thresholds vs engine.** The core architectural exposure.
  Diff, per transition, the resolver's ported logic against `crt_engine_v2` `try_range_to_sweep` /
  `try_sweep_to_displacement` / `try_displacement_to_expansion` and the `thresholds` block vs
  `CRTConfig`. Report matches/divergences; do **not** rewrite the resolver to "match" without proof
  a given divergence is a defect (the header openly notes detector-geometry differences are
  intended). Minimal-change principle governs.
- **Reference-count provenance (dormancy/trust).** `market_crt_states.yaml:27–36` cites counts
  "from CRT engine run" (EXECUTION 5, RANGE 35,159…) with no instrument/config binding; the XAUUSD
  freeze slice produces 0 setups (memory: XAUUSD-only mandate). Establish which corpus produced
  them or mark them provisional — a tuning target pinned to an unnamed corpus is a silent trust
  hole.
- **`structural_states` dormancy.** FM-054..061 all declare `consumed_by: [UNKNOWN]`. Confirm the
  resolver/encoder is their only consumer and that the section is intentionally shadow (expected),
  vs. any claim of runtime consumption.

## Fixes (minimal, additive; only after the above are verified)

1. **D1:** read `candle_range` (v4.0) with `wick_size` fallback for pre-v4/synthetic dicts, keeping
   the unit heuristic correct. One-line-scope change at `crt_state_resolver.py:763`.
2. **Any other stale names** found by the sweep: same read-side reconciliation, name-anchored.
3. **D2:** correct the 38→39-dim comments.
4. **D3:** delete the dead block (`:518–522`), keep the real validation (`:522–529`).
5. **Fail-open gates:** where the engine is fail-closed on a value that IS present on the canonical
   path (D1-class), make the resolver fail-closed too; leave genuine synthetic-vector tolerance
   intact and documented.

## Verification (end-to-end, no governance ceremony)

- **Unit/floor:** run `tests/test_feature_states.py`, `tests/test_market_context.py`,
  `tests/test_market_shape.py`, and any `crt_state` resolver test — must stay green (D3/D2 are
  inert; D1 changes behavior only where the gate was silently off).
- **Behavioral proof for D1:** run `scripts/research/validate_crt_state_resolver.py` and
  `scripts/research/run_crt_state_on_mt5_xauusd.py` on `data/mt5/XAUUSD_M15.csv` (XAUUSD-only
  mandate) before/after; show the DISPLACEMENT/EXPANSION count delta and confirm it moves toward
  the engine's reference (looser→tighter). Compare against
  `scripts/research/crt_state_confusion_matrix.py` off-diagonal cells.
- **Consistency assertion:** the fixed gate must reproduce the engine's reject on a constructed bar
  where `candle_range < atr_multiplier_min*atr_abs` (previously passed by the shadow, rejected by
  the engine).
- Append the standard minimal `📝 SESSION LOG ENTRY` to `assistant_project.md` (§6). No new
  governance/audit/closure docs (session directive).

## Files in scope

- `src/features/crt_state_resolver.py` (primary — D1, D3, gate audit)
- `configs/formulas/market_crt_states.yaml` (D2, thresholds vs CRTConfig, ref-count provenance)
- `src/features/feature_states.py`, `src/features/market_context.py`,
  `src/features/market_shape.py` (rename sweep, fail-fast consistency)
- `src/config_layer/crt_engine_v2.py` (read-only — the authority being diffed against)
- `configs/formulas/market_ontology.yaml` (read-only — states/dormancy check)
- Verification drivers under `scripts/research/` (read-only; run, don't edit)
