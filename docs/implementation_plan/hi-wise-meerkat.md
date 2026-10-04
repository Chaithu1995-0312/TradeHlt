# CRT Resolver — RETEST divergence diagnostic + LINK-001 (CHoCH) binding

## Context

Two findings from this session's grep-only investigation drive this work.

**1. RETEST recall is 0.0% in the resolver, and the threshold is not why.**
`scripts/research/e1_retest_depth_max_probe.py` already established that `resolver_n=0` for
RETEST at `retest_depth_max` ∈ {0.08, 0.15, 0.25} — unconfounded, 0 of 47,197 bars. The
adjudication recorded that as "the threshold is non-pivotal" and moved on. Source comparison
shows **four** independent divergences between the engine's gate and the resolver's, so
"non-pivotal threshold" is a true but incomplete explanation:

| # | Engine `try_expansion_to_retest` (`crt_engine_v2.py:1630-1653`) | Resolver `_continuous_gates_pass` (`crt_state_resolver.py:1597-1601`) |
|---|---|---|
| 1 | `depth_abs = close − rng.l_ref` (LONG) / `rng.h_ref − close` (SHORT) — price units off the frozen active range | `depth = raw.get("retest_depth")` — the pipeline FM-021 feature | 
| 2 | `static_ceiling = retest_depth_max * rng.size` — a **fraction of the range** | bare scalar compare, `* rng.size` absent |
| 3 | `adaptive_ceiling = max(static_ceiling, retest_atr_depth_fraction * atr)` | no ATR ceiling — `retest_atr_depth_fraction` is declared (`market_crt_states.yaml:311`) and **read nowhere** (0 grep matches) |
| 4 | floor: `depth_abs >= retest_min_depth_atr_fraction * atr` | no floor; key not declared at all |

Plus a funnel precondition: `self._memory.current_state not in ("EXPANSION","RETEST") → False`
(`:1603-1606`), which cannot be satisfied while EXPANSION itself only arrives by injection
(`continuous_disp_to_expansion: false`, single read site `:1500`).

We do not yet know which divergence is load-bearing. **Phase A measures that and changes
nothing.** Fixing the resolver gate (and any engine-side revisit) is deferred by explicit
user decision — see Deferred Queue.

**2. The mechanism to wire CHoCH already exists, fully built and default-off.**
`configs/formulas/crt_resolver_links.yaml` registers exactly the three vector-bound stateful
features that no `when:` clause names — LINK-001 `change_of_character`, LINK-002
`volatility_regime`, LINK-003 `volume_spike` — all `status: declared`, all
`supply_cost: none`. The clause grammar (`_clause_states_and_link`, `:273-302`), the filter
(`_apply_link_filter`, `:1254`), variant resolution (`:1217`), and a 20-test floor
(`tests/governance/test_crt_resolver_links.py`) are all in place. `crt_state_resolver.py:1274`
even anticipates the exact binding: *"13 features with LINK-001 off, 14 with it on."*

Scope decision (user): **LINK-001 only.** LINK-003 (`volume_spike`) is deliberately excluded —
on MT5 FX/metals, `volume` is `TICK_VOLUME_APPROXIMATE` with `real_volume=0` (F-099) and a
non-stationary tick-flag vocabulary (F-100), so a participation predicate on XAUUSD would
measure quote activity, not participation. LINK-001 is pure price structure and venue-agnostic.

Outcome: an evidence artifact explaining RETEST recall=0, and one link-gated variant that
measures whether the reversal-vs-continuation distinction changes where the resolver disagrees
with the engine. **Research/shadow only — no G001, no production authority (§6.5).**

---

## ⚠️ Blocker to resolve before Phase B writes anything

`tests/governance/test_crt_resolver_links.py:91-96`:

```python
def test_shipped_when_blocks_survive_filtering_unchanged():
    raw = {s["name"]: (s.get("when") or {}) for s in _states_cfg()["states"]}
    got = {s["name"]: (s.get("when") or {}) for s in CRTStateResolver()._config["states"]}
    assert raw == got
```

This asserts filtering is a **provable no-op against the raw YAML**. That holds only while
*zero* shipped clauses are link-tagged. The moment LINK-001 is bound in the shipped config,
`raw` carries the `{states, link}` mapping and `got` (link off) has the clause removed — the
test goes **RED**, and it is in `tests/governance/`, inside the GREEN_FLOOR.

The test encodes a real invariant ("the mechanism itself must not change behaviour"), so per
§6.8 it must not be deleted or inverted. The correct narrowing is: *untagged* clauses survive
filtering unchanged, and tagged clauses are absent exactly when their link is off. That is a
**floor-test change** and needs explicit approval — it is called out here rather than done as
a side effect. Phase B stops at this line until it is agreed.

---

## Phase A — RETEST divergence diagnostic (read-only, no config or src changes)

**New file:** `scripts/research/retest_divergence_probe.py`

Reuse the existing kernel — do **not** build a new harness. Import from
`scripts/research/crt_parity_sweep.py` exactly as `e1_retest_depth_max_probe.py:53-62` does:
`materialize_candidate`, `evaluate_candidate`, `anti_simpson_ok`, `per_state_summary`,
`DEFAULT_BASE_CONFIG`, `DEFAULT_EVENTS`, `DEFAULT_OHLCV`, plus `crt_state_confusion_matrix`.

Inputs verified present: `data/mt5/XAUUSD_M15.csv` (47,276 lines),
`results/run_20260724_104845_XAUUSD/XAUUSD_events.jsonl` (18,155 lines).

Write to its **own** scratch root `results/analysis/retest_divergence_probe/` — never append to
`results/analysis/crt_parity_sweep/ledger.jsonl`.

The probe answers one question: **of the four divergences, which one(s) hold `resolver_n` at 0?**
It is an *attribution* instrument, not a fix — it must not modify `crt_state_resolver.py`.
Where a divergence cannot be isolated through the config delta surface alone (2, 3 and 4 have
no config switch), record the raw quantities and compare distributions rather than inventing a
code path:

1. For every bar the engine labels RETEST (n=17), dump both quantities side by side — the
   engine's `depth_abs` / `adaptive_ceiling` / `min_depth`, and the resolver's `retest_depth`
   / `retest_depth_max`. This alone shows whether the two numbers are even on the same scale
   (divergence 1 + 2).
2. Report how many of those 17 bars the resolver's funnel precondition (`current_state in
   {EXPANSION, RETEST}`) admits at all — separating "gate rejected it" from "never reached
   the gate".
3. Record what `max(static, atr_ceiling)` *would* have been, and whether the floor would have
   excluded the bar — arithmetic on already-dumped values, no behaviour change.

**Deliverable:** `results/analysis/retest_divergence_probe/retest_divergence_probe.json` +
a short attribution table in the response. Explicitly state which divergence is decisive and
which are merely present — do not collapse them.

**Epistemic guard:** n=17 engine RETEST bars. That is a *mechanism* diagnostic, not a powered
economic measurement. No finding gets registered off this alone; if the mechanism is
ambiguous at n=17, say `INSUFFICIENT EVIDENCE` rather than picking a winner.

---

## Phase B — Bind LINK-001 (`change_of_character`) — **gated on the blocker above**

### B1. `configs/formulas/market_crt_states.yaml` — two edits

Both are required: `_validate_predicates:1182-1186` rejects a `when:` feature absent from the
`feature_states:` block.

1. Add to `feature_states:` (ontology-verified names, FM-083, idx 47):
   ```yaml
   change_of_character: [NoCHoCH, BullishCHoCH, BearishCHoCH]
   ```
2. Add **one** link-tagged clause. Placement matters — see the double-counting note below.

### B2. `configs/formulas/crt_resolver_links.yaml`

- `LINK-001.status: declared` → `bound` (two-sided floor test
  `test_link_status_matches_actual_clause_binding:123-141` requires status and binding to move
  together, in the same commit).
- Add one variant, `canonical: false`, with a rationale naming what the comparison tests:
  ```yaml
  choch:
    canonical: false
    links: [LINK-001]
    rationale: >
      ...what we learn from binding the reversal/continuation distinction...
  ```
  `max_live_variants: 8`; currently 1 variant, so headroom is fine.
- Amend LINK-003's rationale to record the F-099/F-100 tick-volume scope limit — so a later
  session does not enable it on an MT5 corpus without seeing the caveat. Rationale text only;
  status stays `declared`.

### B3. Where to place the clause (design decision, not mechanical)

`change_of_character` is **derived**: `break_of_structure × trend_bias`
(`src/features/smc/choch.py:20-31` — stateless algebra over FM-057 and FM-054, deliberately
not a new detection state machine).

`break_of_structure` is already a **baseline** clause in RANGE, RETEST and SWEEP;
`trend_bias` is one in EXECUTION. Tagging CHoCH onto any of those **double-counts BoS**.

**Recommended: DISPLACEMENT** — where BoS is *not* currently a clause, and where
reversal-vs-continuation is exactly the distinction F-074's directional contract cares about
(displacement must travel *away* from the swept side). The `when:` there today is a single
soft-corroboration clause (`displacement_flag: [Displacement]`), with hard authority in the
funnel — so an added predicate is legible rather than tangled.

### B4. Measure

Run the same `crt_parity_sweep` kernel, `base` vs `choch` variant, and report the confusion
matrix delta. Pass `variant="choch"` (not `links=[...]`) — `_resolve_enabled_links:1225-1228`
raises if both are given.

`required_when_features` moves 13 → 14, so **every caller must now supply
`change_of_character`** under this variant. It is vector-bound (idx 47), so `classify()`
already requires it — `supply_cost: none` holds for callers passing a full canonical vector.
Verify that against `src/features/resolver_supply.py` before running, not after.

**Report `base` unchanged as the control.** Per the links.yaml rationale, no variant is
canonical during the wiring phase; this measures *whether the disagreement set moves*, and
grants nothing regardless of result.

---

## Deferred queue — surface these when Phase A + B complete

The user asked to be reminded. Do not start either without a fresh go-ahead.

1. **RETEST resolver fix** (was option 1). Make the resolver read `retest_atr_depth_fraction`,
   apply `adaptive_ceiling = max(static, atr)`, add the min-depth floor, and decide whether
   `retest_depth_max` should multiply `rng.size` (the resolver does carry `range_h_ref` /
   `range_l_ref` / `range_ready` in `CRTStateMemory:169-176`, so range-relative depth is
   computable). Flips `retest_atr_depth_fraction` from `crtconfig_duplicate_dead` to consumed
   in the `threshold_refs` table. Research-shadow only. **Should be informed by Phase A's
   attribution, not run blind.**
2. **Engine-side RETEST revisit** (was option 3). `try_expansion_to_retest` is a **production
   execution path** — `BEHAVIOR_CHANGE_AUTHORIZED` territory under
   `TASK_CLASSIFICATION_BEHAVIOR_POLICY`, requiring parity proof and touching the live ledger.
   Highest bar of the three; do not fold into either phase above.

---

## Verification

**Phase A**
- `venv/Scripts/python.exe scripts/research/retest_divergence_probe.py` → exit 0, JSON written.
- `git status --porcelain` shows **only** the new script + its scratch root. No change to
  `configs/formulas/*.yaml`, `src/features/crt_state_resolver.py`, or
  `src/config_layer/crt_engine_v2.py`.
- SITS registration same turn (`CLAUDE.md §3.1b`): `script_census.py --write-stubs` →
  `seed_script_registry.py` → `generate_script_matrix.py`. An unregistered `scripts/**` path
  fails the GREEN_FLOOR coverage test.

**Phase B**
- `venv/Scripts/python.exe -m pytest tests/governance/test_crt_resolver_links.py -q` — all
  green, including the narrowed `test_shipped_when_blocks_survive_filtering_unchanged`.
- Parity: `CRTStateResolver()` (no variant) must be **byte-identical** to today —
  `required_when_features` still 13, every `when:` block unchanged with the link off.
  `test_base_variant_is_behaviourally_the_default:83-89` covers this; confirm it passes
  *before* trusting any `choch`-variant number.
- `CRTStateResolver(variant="choch").required_when_features` == 14, containing
  `change_of_character`.
- `venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all` —
  compare against the **baseline failure count captured before any edit** (§1.5: the green
  floor has pre-existing reds on this branch; a pre-existing red is reported, not fixed).

**Both**
- Worktree preflight first (`git status --porcelain`, `git stash list`) — concurrent Claude
  sessions write to this repo; uncommitted `src/` changes invalidate any comparison against
  recorded evidence.
- `SESSION LOG ENTRY` appended to `assistant_project.md` (§6) — this touches governed
  config + scripts, so it routes to the codebase log.
- No finding registered from either phase without the §6.2 pre-registration ritual.
