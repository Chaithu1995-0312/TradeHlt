# Plan — Lane 2: seal MC-VCRT before the detector runs

## Context

Lane 1 is complete: `SEM-012 VISUAL_CRT_TRADE_OBJECT` is registered, grounded, spec'd and
floored (23/23, AST isolation proved to fail on 4 evasion forms). Lane 2 is approved with one
binding condition — **the two-corpus separation must be encoded in the sealed measurement
contract before the detector executes** — plus a 17-dimension freeze list.

Two decisions taken this turn, both of which change the frozen object:

1. **Two pre-registered arms.** Lane 1 froze entry at the displacement bar's close, with no
   retest stage — a mismatch with the described `pool → sweep → displacement → retest`
   sequence. Resolved by measuring both, declared in advance: **Arm A** entry-at-displacement,
   **Arm B** entry-on-retest. `multiplicity.n_variants_preregistered = 2`, corrected.
2. **Duplicates:** one-shot per `(pool, direction)` until a newer closed parent replaces that
   pool, **and** one open trade at a time.

Deliverable of this lane is a **population and power answer**, not an economic verdict — see
§4.

---

## 1. Schema constraint (changes how the corpus split is encoded)

`docs/governance/measurement_contract.schema.json` is `additionalProperties: False` at root
**and** on every sub-object. New keys like `measurement_corpus` / `visual_validation_corpus`
cannot be added — the instance would fail
`test_mc_instances_validate_schema_and_cannot_claim_economics_while_unrun`, which
jsonschema-validates every `instances/MC-*.json`.

So the separation is encoded in existing fields, in four places, deliberately redundant:

| Where | What it says |
|---|---|
| `population.calendar_window` | `2024-05-22 → 2026-05-21` — the 2-year file, the **only** measured population |
| `population.exclusion_rule` | names `data/XAUUSD_M15.csv` (2026-07-07 → 2026-08-06) as **excluded from the population**, visual-audit only |
| `prohibited_substitutions[]` | new entry, `historical_class: FC-CORPUS-DENOMINATOR-MERGE` — forbids merging the audit corpus into the economic denominator |
| `metrics.forbidden_metric_substitutions[]` | `visual_audit_n_as_measured_n`, `screenshot_window_trades_as_measured_n` |

`population.population_hash_inputs` carries `corpus_path` + `corpus_sha256` so the fingerprint
records which file every unit came from. The two corpora do not overlap in time, so a merged
denominator is also mechanically detectable after the fact.

## 2. The freeze table → actual contract fields

| Dimension | Frozen as |
|---|---|
| Pool types | `PRIOR_H4_HIGH/LOW`, `PDH`, `PDL` (SEM-012 closed vocabulary) |
| Pool publication time | `formed_at_index < bar.index`, already enforced in `detect_pool_sweep` |
| Tolerance | exact numeric in `features.name_binding`; pools are exact levels, no fuzz band |
| Sweep | pierce + close back inside (`detect_pool_sweep`) |
| Direction | F-074 directional displacement (`detect_directional_displacement`) |
| Displacement threshold | `body_ratio_min 0.65`, `atr_multiplier_min 1.0`, `atr_min_displacement 1.2`, `max_sweep_age_candles 20` |
| Retest (Arm B only) | mirrors `try_expansion_to_retest`: `adaptive_ceiling = max(retest_depth_max × impulse, retest_atr_depth_fraction × atr_abs)`, `min_depth = retest_min_depth_atr_fraction × atr_abs`, `depth_abs = close − pool.price` (LONG) / `pool.price − close` (SHORT), fire when `min_depth ≤ depth_abs ≤ adaptive_ceiling`. `impulse = abs(displacement.close − sweep.sweep_price)` stands in for `rng.size`, since a pool is a level not a range — declared, not silently substituted |
| Entry | Arm A: displacement bar close. Arm B: retest bar close |
| SL | `sweep_price ∓ 0.2 × atr_abs` (beyond the swept extreme) |
| TP | `2.0 × atr_abs` |
| Costs | reuse `CM-XAUUSD-LEGACY-12BPS-UNCALIBRATED` verbatim for comparability with MC-CRT-SB, carrying its own caveat: 12bps is **not** a calibrated metals cost, so net figures are DIAGNOSTIC |
| Exit | `forward_walk(exit_model="intrabar_fixed")`, SL-before-TP same-bar |
| Timeout | 40 bars, explicit (not the implicit `max_forward` default) |
| Duplicates | one-shot per `(pool, direction)` until pool replaced; one open trade at a time |
| Supersession | rows carry `CURRENT`/`SUPERSEDED`; a definition change supersedes in place, never deletes |
| Corpus | 2-year `data/mt5/XAUUSD_M15.csv` |
| Visual audit | separate 1-month `data/XAUUSD_M15.csv`, excluded from the population |

## 3. Three inherited terms that must be resolved in-instance

`MP-METALS-MT5` is `lifecycle: DRAFT` with `unresolved_terms` carrying `blocks_freeze: true`.
The instance must resolve them explicitly rather than inherit a DRAFT default (MC instance
override precedence is already a floor: `test_relationship_declares_mc_instance_override_precedence`):

- **`population.gap_policy`** (F-035) — follow MC-CRT-SB: do **not** apply the FX holiday-gap
  REJECT; keep MT5 missing bars as absent rows, record the drop count in the fingerprint.
- **`features.session_timestamp_basis`** (F-066) — `broker_local`. SEM-012 uses no session
  input at all, so the known mislabel cannot reach this object; state that rather than imply
  the defect was fixed.
- **`features.point_in_time_rule`** (F-051) — SEM-012 consumes raw OHLC and closed parents
  only, not the centered-swing feature path, so the F-051 leak is **out of path** here. Declare
  it, do not claim it was cleaned.

## 4. The admissibility ceiling (state it before running, not after)

`trust_status` requires `mt00: PASS` and `mt01_matrix_coverage: COMPLETE` before
`economic_claims_allowed` can be true. Repo-wide that is `0/27` probes implemented and
`MEASUREMENT_LAYER_STATUS = OPEN`. So this instance seals with `economic_claims_allowed:
false`, exactly like `MC-CRT-SB-XAUUSD-M15-V1`.

**Lane 2 therefore answers:** does a mechanically-defined pool→sweep→displacement(→retest)
object produce a **measurable, sufficiently powered population** on 2 years of XAUUSD M15 —
with n, win rate, and expectancy reported as **DIAGNOSTIC**. It cannot return an admissible
economic verdict. Lane 3 stays gated behind the 27 probes.

`n_declared_min = 30` per arm. Below it the result is `INSUFFICIENT`, not `harmful` — the
authority-ladder distinction is already a required field.

## 5. Execution order (the seal is a hard gate)

1. Amend SEM-012 + spec for the two arms and the duplicate rule; bump node `version`.
2. Write `configs/research/measurement_contracts/instances/MC-VCRT-XAUUSD-M15-V1.json`.
3. **Seal gate:** `pytest tests/test_measurement_contract.py` green *before* any detector code
   runs. Record the corpus SHA-256 in the instance.
4. Only then: driver in `src/research/visual_crt/` emitting `Signal`s, resolved through
   `forward_walk`, writing only under `results/visual_crt/`.
5. Ledger + counts per arm, denominator named.
6. Visual audit as a separate, separately-labelled run on the 1-month corpus.

## 6. Explicit non-goals

No setup scoring, no A+/A/B/C grading, no "Primary CRT", no monthly/weekly alignment points,
no confluence weighting. If V1 returns zero, tiny n, or negative expectancy, that is a
**research closure to register**, not a reason to keep modifying the object until it trades.
Changing the object after seeing outcomes requires a new `MC-*` id, which the kill criteria
will say in as many words.

## Files

**New:** `configs/research/measurement_contracts/instances/MC-VCRT-XAUUSD-M15-V1.json` ·
`src/research/visual_crt/retest.py` (Arm B predicate) · `src/research/visual_crt/driver.py` ·
`docs/governance/build_manifests/CH-visual-crt-lane2.impact.json`

**Edited:** `docs/research/visual_crt_trade_object.md` (two arms, duplicate rule) ·
`configs/formulas/market_ontology.yaml` (SEM-012 version bump) ·
`tests/research/test_visual_crt_trade_object.py` (Arm B + duplicate-rule cases) ·
`.grok/PENDING.md` · `assistant_project.md`

**Untouched:** `configs/production/**`, `src/config_layer/**`, `src/runtime/**`, `models/**`.
`production_behavior_changed: NO`.

## Verification

```bash
python -m pytest tests/test_measurement_contract.py tests/research/test_visual_crt_trade_object.py -q
```

- Seal gate green **before** the detector exists (ordering is the point, not just the pass).
- Isolation test still fails on an injected `from config_layer import crt_engine_v2`.
- Duplicate rule proved on a synthetic double-sweep of one pool: second fire suppressed.
- Ledger determinism: same corpus + same sealed MC → byte-identical `results/visual_crt/`.
- Ledger rows carry `corpus_path`/`corpus_sha256`; assert no row from the 1-month audit corpus
  appears in the measured population.
- `configs/production/ACTIVE_VERSION` unchanged (`v2_htfcrt_2026_08`) start and end.

---

## Appendix A — Lane 1, delivered

`SEM-012` registered (`validate_semantic_registry() → []`, `GROUNDED`), owned by CN-011 not
CN-004; spec at `docs/research/visual_crt_trade_object.md`; pure geometry in
`src/research/visual_crt/{pools,geometry}.py` founding on chart-visible pools, never M15-SLR;
floor 23/23. Freeze-pin refreshed with a waiver-log entry after **measuring** that the file was
already drifted before this change set (`34f237f4…` with the SEM-012 block removed ≠ pinned
`3530782a…`); vector regression passed, bounding both deltas. Three other pin drifts
(`ACTIVE_VERSION`, `active_config`, `feature_schema.py` 39→48) left untouched as other
programs' surfaces.

**Answer to the original question, unchanged:** zero profitable trades on the screenshots —
one of 19 marks is trade-shaped, `SUPERSEDED` under F-074, and a loser (MFE 0.09R).

## Appendix B — CT-009 critique (earlier this session)

**Strong:** genuine cross-artifact non-transitivity enforcement; YAML↔function bidirectional
completeness; M15-SLR named without geometry change; report epistemics (pre-registered
tolerance not widened, 195 skipped checks never folded into 725 passes, five self-caught
overclaims).

**Weak:** `crt_engine_has_no_smc_import` asserts `"features.smc" not in text` — defeated by
`from features import smc`, a form `crt_engine_v2.py` already uses at `:30` and `:3310`;
8 declared relations against 7 checks; `text.index()` ordering as control-flow proof.

**Residue:** the block is untracked, including `terminals/` (7 files, 0 tracked) holding the
instruments behind F-080's headline numbers.
