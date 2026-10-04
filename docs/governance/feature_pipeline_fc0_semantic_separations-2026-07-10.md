# FC-0 Semantic Separation Decisions

**Contract-level intent only.** Production code is unchanged until FC-1.

| ID | Legacy (frozen) | Canonical intent (FC-1 target) |
|---|---|---|
| **SEP-A** Swing | `center=True`, publish flag at bar `t` before `t+k` confirmation; `TRUST_SWING_CAUSAL` env optional | One causal path: `available_at = t+k`; no env flag as production authority; batch ≡ runtime availability |
| **SEP-B** Volume | T-003 may set `volume = high-low` under same name when all-zero | `volume` = source semantic (XAU = `TICK_VOLUME`); proxy = `FEAT-VOLUME_RANGE_PROXY` with `is_synthetic=true`; consumers declare accepted semantic; fail closed on mismatch |
| **SEP-C** Formula IDs | Pipeline `disp_strength`/`retest_depth` = FM-020/021; CRT/BitNet aliases map FM-028/027 onto same names | Distinct feature_ids: keep FM-020/021 names for pipeline math; CRT uses `FEAT-DISPLACEMENT_ATR_RATIO` / `FEAT-DISPLACEMENT_RETRACE`; models bind IDs not aliases |
| **SEP-D** Vol regime | Global `atr_14.rank(pct=True)` over full frame; env expanding/rolling | Causal regime only; **expanding vs rolling chosen in FC-1 design** (not env); global rank remains LEGACY only |

## Non-decisions deferred to FC-1

- Final causal regime formula (expanding vs rolling window length)
- Whether `volume_range_proxy` remains in the default vector or is opt-in only
- BitNet retrain schedule (FC-6)

## Evidence

- `docs/governance/feature_semantic_adjudication_pass_a-2026-07-10.json`
- `docs/governance/feature_availability_graph-2026-07-10.json`
- `docs/governance/feature_formula_callsite_binding-2026-07-10.json`
