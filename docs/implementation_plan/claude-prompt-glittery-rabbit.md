# Repository-Wide Fallback Sweep — Ambiguity-Hiding Fallback Removal

## Context

**Why:** The repo accumulated hidden defaults and silent compatibility bridges
(`.get(key, default)`, `x or literal`, `try/except → neutral`, multi-key lookups, silent
coercion). *Some* of these mask corruption — malformed data, schema drift, and missing config
get silently "recovered" instead of surfaced. The goal is to restore **fail-fast truth** per
CLAUDE.md §6.2 (drift discipline) and §6.5 ("NO silent config defaults").

**Corrected objective (user-directed):** the target is
**"remove ambiguity-hiding fallbacks; escalate uncertainty to the user"** — *not* blanket
removal of every default. The discriminating question for every site is:

> **Was this fallback masking corruption?** — not — *Does a default exist?*

Most defaults are legitimate semantic contracts or documented resilience. Blanket fail-fast
would over-remove resilience and change repository behavior without improving truth. So this is
**not** an aggressive-everywhere sweep and it does **not** override the byte-identical
determinism / golden-ledger mandate. Unambiguous corruption-maskers are removed (byte-identical,
because their masked branch never legitimately fires); everything uncertain is **escalated**.

**Inventory baseline (live spine, already measured):** ~298 `.get(key, literal)`, ~80
coercion/truncation, 21 `try/except → neutral`, ~18 env-var defaults, 7 `x or literal`. Only a
*subset* are corruption-maskers; how large that subset is, is itself something the sweep
measures.

---

## Truth hierarchy (the doctrine this sweep enforces)

When resolving any fallback, prefer in this order:
1. **Explicit schema** (strict read against a known field/section)
2. **Explicit version branches** (`if schema_version == 1: … elif == 2: … else: raise`)
3. **User decision** (escalate via `AMBIGUITY_REPORT.md`)
4. **Documented resilience** (the ALLOWED set below — kept as-is)

**Never:** hidden migration · multiple names for one concept · sentinel values · silent repair ·
guessed semantics · new magic numbers · compatibility bridges.

---

## Classification rubric

### REMOVE — FORBIDDEN (unambiguous corruption-maskers)
Convert to explicit read / explicit version branch / explicit raise:
- **Multiple names for one concept** — `d.get("a", d.get("b"))`,
  `trade.get("symbol", trade.get("instrument", ""))`. Pick the canonical key; if both are real
  schema variants, that is a *version branch*, not a fallback.
- **Missing required config hidden by literal** — `cfg.get("rr_threshold", 1.5)`,
  `get_prod_section(...).get(key, literal)`. Replace with strict `_require` / `cfg[key]`.
- **Corruption-swallowing except** — `except Exception: return {}` / `return 0.0` around config
  load or data parse, where the empty/neutral value silently degrades a real computation.
- **Silent enum remapping** — unknown enum value → SAFE/default member without raising.

### KEEP — ALLOWED (documented resilience, leave untouched)
- LLM circuit breaker (`except Exception: return 1.0`, `llm_scorer.py`)
- Optional-import guards (`_*_AVAILABLE = False`)
- Console encoding fallback (`console_safe.py` cp1252)
- External API / network failure fallbacks, named circuit breakers
- Genuinely user-facing display values (`.get(x, "")` for log/CLI text)

### ESCALATE — AMBIGUOUS (Claude must NOT decide)
The canonical example: `score = engines.get(name, 0.5)`. This *may* be a semantic neutral-fusion
contract (`convergence_controller.py:197-201` documents "default 0.5 for missing engines" and
reports `missing_engines`). Claude does **not** convert it. STOP and record it (template below).

**Hard rule — never replace `.get(...)` mechanically.** `zone["id"]` may be correct where
`zone.get("id")` was lazy; but `trade["risk"]` may introduce hundreds of crashes if `risk` is
legitimately optional. The decision is per-site and evidence-based (does the masked branch ever
fire on the replay corpus? what invariant does the default protect?), never pattern-mechanical.

---

## Ambiguity report template (per escalated site)

```
AMBIGUITY_REPORT.md

File:
Line:
Current behavior:
Who consumes this?
Can it fire on replay? (BNBUSDT + SOLUSDT corpus)
What invariant does it protect?
Alternatives:
User decision required.
```

---

## Execution phases

### Phase 1 — Full inventory → `FALLBACK_AUDIT.md`
Repo-wide Grep for all six pattern families (counts per package + every concrete `src/` hit).
Produce the `| File | Line | Pattern | Category | Risk |` table. Read-only.

### Phase 2 — Classify every occurrence
Tag each row REMOVE-FORBIDDEN / KEEP-ALLOWED / ESCALATE-AMBIGUOUS using the rubric + the
"was it masking corruption?" test. AMBIGUOUS rows seeded into `AMBIGUITY_REPORT.md`.

### Phase 3 — Remove FORBIDDEN only, batched
Batch order (highest leverage first):
1. **Config layer** — `src/config_layer/` (incl. `rr/`). Targets: `rr_fusion.py:23-30` (stacked
   `try/except → 1.5` config mask), `crt_gaussian_scorer.py:14-18` (`except → {}`),
   `rr_pattern_miner.py:34-42` (6 chained soft config defaults). Convert config-load masks to
   strict reads **where the section/key is present in the active config** (byte-identical).
2. **Core** — `src/core/`. Remove FORBIDDEN multi-key lookups (`engine_runner.py:639`,
   `ultron_risk_gate.py:251`, `execution_planner.py:215/343`). The `0.5` fusion defaults
   (`convergence_controller.py`, `fusion_engine.py`) are **ESCALATED, not removed** — they are
   the documented neutral-fusion contract.
3. **Engines** — `src/engines/` (incl. `live_engine.py` env-var defaults → escalate or strict
   parse per site).
4. **Governance** — `src/governance/`.
5. **Tests** — `tests/` (mostly ALLOWED fixtures; convert only genuine corruption-maskers).

Each edit: explicit read / validated parse-and-raise / explicit version branch. Every diff →
`CLEANUP_PATCHES.md` with class + the corruption-masking justification + fire-test result
(byte-identical confirmation).

### Phase 4 — Ambiguity escalation (STOP)
Finalize `AMBIGUITY_REPORT.md`. For every AMBIGUOUS site, STOP and wait for the user. Do not
modify. No guessed semantics.

### Phase 5 — Verification (per batch + final)
Run the checklist below. Because FORBIDDEN removals are byte-identical (masked branch never
legitimately fires), the determinism, golden-ledger, and oracle-parity gates **must all stay
green** — any ledger drift means a removal was actually a semantic contract and must be reverted
+ escalated. Distinguish new reds from the known pre-existing baseline.

---

## Deliverables (repo root, doc-only — hash-neutral)
1. **`FALLBACK_AUDIT.md`** — full classified inventory table.
2. **`AMBIGUITY_REPORT.md`** — STOP items awaiting user decision (rich template above).
3. **`CLEANUP_PATCHES.md`** — every FORBIDDEN-removal diff + corruption-masking justification +
   byte-identical confirmation.
4. **Test results** — before/after pytest baselines + per-batch determinism/oracle output.
5. **List of removed fallbacks** — by package.
6. SESSION LOG entry appended to `assistant_project.md` (CLAUDE.md §6 mandate).

---

## Verification checklist (Windows PowerShell)

```powershell
# These MUST stay green — FORBIDDEN removals are byte-identical; drift = a contract was removed
python -m pytest tests/runtime/test_replay_determinism.py tests/research/test_runner_determinism.py -q
python -m pytest tests/analytics/test_metrics_oracle_parity.py -q
python -m pytest tests/analytics/test_golden_ledgers.py tests/analytics/test_metric_invariants.py -q

# Config-first enforcement
python scripts/analysis/behavior_census.py --check
python scripts/analysis/config_reachability.py --check
python -m pytest tests/test_behavior_census.py tests/test_config_integrity.py -q

# Full suite — capture before/after to separate new reds from the known baseline
python -m pytest tests/ -q --tb=line | Tee-Object fallback_sweep_after.txt
# (capture fallback_sweep_before.txt on the unmodified tree first; diff the summaries)

# Only if a params-block value changed (most edits are code, hash-neutral):
python scripts/maintenance/_compute_hash.py
```

**Pass criteria:** all determinism / golden / oracle / invariant gates **green** (zero ledger
drift — drift means an escalation was mis-removed); no documented fail-open removed; no new red
outside the known baseline; every AMBIGUOUS site escalated, none guessed.

---

## Critical files
- **Reuse (fail-fast helpers):** `_require` (`src/config_layer/goal_schema.py:45-52`),
  `get_prod_section` / `get_active_version` (`src/config_layer/production_config.py:60-387`),
  `_validate_override_keys` (`src/config_layer/config_builder.py:186-193`).
- **Keep (ALLOWED):** `src/config_layer/llm_scorer.py`, `src/utils/console_safe.py`,
  optional-import `_*_AVAILABLE` guards.
- **FORBIDDEN-removal targets:** `src/config_layer/rr/rr_fusion.py`,
  `src/config_layer/crt_gaussian_scorer.py`, `src/config_layer/rr/rr_pattern_miner.py`,
  `src/core/engine_runner.py:639`, `src/core/ultron_risk_gate.py:251`,
  `src/config_layer/execution_planner.py:215/343`.
- **ESCALATE (do NOT remove):** `src/core/convergence_controller.py:197-201`,
  `src/core/fusion_engine.py:375-381` (0.5 neutral-fusion contract);
  `src/engines/live_engine.py:374-382` (env-var live defaults — per-site decision).

## Risks
- **Over-removing a semantic contract disguised as a default** — the primary failure mode.
  Mitigated by: ESCALATE-not-decide on any `engines.get(name, 0.5)`-class site, the
  "was it masking corruption?" test, and the byte-identical gate (drift ⇒ revert + escalate).
- **Mechanical `.get` replacement** — explicitly forbidden; every site is evidence-based.
- **Scale** — batching by leverage keeps each step independently reviewable.
