# Pre-registration — Opportunity Episode Research Substrate (OE_L1)

> **Change id:** `CH-opportunity-episodes`
> **Date:** 2026-07-23
> **Protocol:** `OE_L1` (`src/research/episodes/protocol.py`)
> **Authority:** **NONE** (CLAUDE.md §6.5). Research infrastructure. `PRODUCTION_BEHAVIOR_CHANGED = NO`.
> **Design:** [`opportunity-episode-research-substrate.md`](../architecture/opportunity-episode-research-substrate.md)
> (wins on principle conflict) · [`opportunity-episode-platform-design.md`](../architecture/opportunity-episode-platform-design.md) (module layout)
> **Pattern precedent:** [`src/research/clean_labels/protocol.py`](../../src/research/clean_labels/protocol.py) (freeze + hash + builder + sidecars)

## 1. What is being built

A canonical **policy-independent post-entry observation timeline** per opportunity, so that
labels, events, annotations, flat tables and tensors become *derived* artifacts instead of being
re-simulated by the ~10 independent forward-walkers catalogued in substrate §5.

Package: `src/research/episodes/`. Artifacts: `results/research/episodes/…` (gitignored).

## 2. Frozen decisions (substrate §23 open decisions — all resolved before code)

| # | Decision | Resolution | Rationale |
|---|---|---|---|
| 1 | Root name | `OpportunityEpisode` | Broader than a filled trade; only some episodes execute |
| 2 | `t` convention | `t=0` = entry bar; policies walk `t≥1` only | Exactly `forward_walk`'s `bar.index > signal.entry_index` assertion |
| 3 | ATR placement | Entry ATR in the entry snapshot; per-step ATR = opt-in annotation, **not** Observation | ATR is rolling indicator FM-041 with a config-driven period (§6.5 exception 2026-07-18); pinning it per step would bind episodes to a config epoch |
| 4 | v1 Observation | `t, bar_index, timestamp, o/h/l/c, volume` — nothing else | Observation-minimal Tier 1; features joined by bar index |
| 5 | v1 policy set | `intrabar_fixed` (governing) · `trailing` · `close_only` | Exactly the three modes the audited kernel already has — see §4 |
| 6 | Query v1 surface | Library API; no string DSL | Avoids freezing a query language before the predicates are known |
| 7 | First population | `DETECTION_STREAM` | Statistical power; already the population `clean_labels` consumes, giving an immediate parity oracle |
| 8 | Artifact root | `results/research/episodes/{population}/{instrument}/` | Research-only, gitignored |

## 3. Invariants (mechanically enforced)

1. **The episode is policy-independent.** `exit_policy_hash` lives on the `LabelSet`, never on
   `EpisodeProvenance`. (Corrects platform-design §5.1, which contradicted its own Principle 3.)
2. **Canonical `Derived` excludes policy state.** No `stop`/`tp` fields — a trailing stop is a
   function of the exit policy. Only quantities computable from the entry snapshot + the
   observation prefix `0..t` are derived.
3. **Events are derived, never stored in the episode.**
4. **Observations immutable; annotations versioned.**
5. **No second exit kernel.** `PolicyEvaluator` wraps `research.measurement.forward_walk` only.
6. **F-022 discipline.** The detection stream's `outcome`/`rr_achieved`/`mfe`/`mae` may appear only
   under `metadata.diagnostics` and may never become a canonical or label field.

## 4. Declared non-goal — multi-level exits

`research.contracts.Signal` is frozen and expresses geometry as ATR multiples with a **single**
TP. The spine has TP1/TP2 + `partial_tp_fraction` (F-056). A `partial_tp_be` policy is therefore
**not implementable without a second exit simulator**, which substrate §18 rates a *Critical*
risk. Partial-TP is explicitly out of scope for `OE_L1` and requires its own pre-registration.

## 5. Acceptance gates (declared before measurement)

| # | Gate | Blocking? |
|---|---|---|
| 1 | Two builds of the same units → identical episode content hashes | yes |
| 2 | `PolicyEvaluator(episode,"intrabar_fixed")` field-identical to today's `clean_labels` `Outcome` | **yes** — proves no second kernel |
| 3 | Three LabelSets from one episode build, episode bytes unchanged | yes |
| 4 | Rulepack v2 EventSet written, episode bytes unchanged | yes |
| 5 | Measured corpus bytes recorded before the full DETECTION_STREAM build | yes |
| 6 | SpineProjector MFE/MAE ≡ `TradePathStats.mfe_price`/`mae_price` | **yes** |
| 7 | Each migrated consumer byte-identical to its pre-migration output before switch | yes |
| 8 | No diff outside `src/research/`, `scripts/research/`, `scripts/training/`, `tests/`, `docs/` | yes |

A failure at gate 2 or 6 is a build defect, not a finding.

## 6. What this pre-registration does NOT claim

No economic claim of any kind. Building a substrate is not evidence that a path-aware model has
an edge; the entry-information null (F-019…F-043) is untouched by this work. Any future model
trained on episodes earns authority only through demonstrated ΔG001 (§6.5 Authority Ladder).

## 7. Known related truth conflict (reported, not resolved here)

`src/research/clean_labels/protocol.py:35` declares `FEATURE_DIM = 38` while
`src/features/feature_schema.py:114` sets `CANONICAL_FEATURE_DIM = 39` (hard-asserted at import),
and `clean_labels/builder.py:101` validates vectors against the 39 constant. The `38` is stale
metadata inside a **frozen** protocol hash (`TN_ENV_CLEAN_L2`), so changing it would invalidate
that epoch's identity. Surfaced per §6.2 rule 3; **not** silently edited by this change.
