# Visual CRT Re-measurement — MC-VCRT-XAUUSD-M15-V2

**Prior phase (complete):** F-082 shipped the corrected cost model (SEM-015) + honest stop fills (SEM-016), config-gated and parity-proved. User has since agreed UNK-COST-02 (broker decomposition supersedes the volatility proxy) and authorised this re-measurement.

**Lane:** research measurement. **Authority:** diagnostic only — no G001, no promotion, no `ACTIVE_VERSION` change, `economic_claims_allowed` stays false.

---

## Context

### Why now

F-081 measured the Visual CRT trade object and returned 0 PROMOTE on both arms. Its net figures were **cost-dominated by a constant we have since proved wrong for XAUUSD by ~11x**. With the ruler fixed, the question "is this null information-driven or cost-artifact-driven?" is finally answerable.

### What the sealed contract requires

`MC-VCRT-XAUUSD-M15-V1.json` `metrics.kill_criteria` names this explicitly:

> Changing ANY frozen dimension after seeing outcomes (… **cost model, exit model** …) requires a NEW `MC-*` id, a new hypothesis and a new pre-registration (V2) — never an edit to this instance.

So a new instance is the *sanctioned* path, not a workaround. V1 stays sealed and registered.

### The second problem, found while reading V1

V1's contract declares two things its run never produced:

| Declared in the sealed contract | Actually executed |
|---|---|
| `splits.scheme: single_holdout_chronologic`, embargo 96 bars, purge overlapping horizons, seed 20260817, "exact dates locked in `split_manifest` at run time" | **No split at all.** No `split_manifest` artifact exists. |
| `metrics.success_gate`: "…AND beats the pre-registered controls (`random_entry`, `long_only`)" | **No controls run.** |

`src/research/visual_crt/driver.py` contains **zero** occurrences of `control`, `random_entry`, `long_only`, `oos`, `holdout`, `embargo`, `purge`, or `split`; the ledger rows carry no split or control fields.

**This does not undermine F-081's verdict.** Controls and OOS are gates a *positive* result must clear; an arm rejected at the absolute-expectancy stage never reaches them. The gap matters precisely when something comes back positive — which is exactly the case this re-run could produce. So V2 implements them.

### A third find, load-bearing for the implementation

`driver.py:140-150` has its own `_net_r` with a hardcoded `ROUND_TRIP_BPS = 12.0`. It **never imports `research.costs`**. F-082's `cost_model` selector therefore does not reach this driver at all — a fourth independent cost site. Fixing this is what makes the re-run possible.

### Intended outcome

A complete, contract-faithful V2 measurement that isolates the effect of the corrected measurement basis, with V1 preserved and byte-reproducible.

---

## Pre-registration (write and seal BEFORE running anything)

V1 earned its credibility by sealing the contract before the detector existed. V2 keeps that discipline: the contract, the predicted outcome, and the decision rules below are committed **before** the controls/OOS code is written and before any V2 number is produced.

### Predicted outcome

Both arms **still REJECT**. Net expectancy moves from decisively negative to mildly negative; gross stays indistinguishable from zero.

| Arm | V1 gross | V1 net | V2 predicted gross | V2 predicted net |
|---|---|---|---|---|
| A (displacement close) | +0.0080R | −0.5559R | ≈ 0.000 … +0.007R | **≈ −0.03 … −0.08R** |
| B (retest close) | −0.0835R | −1.2617R | ≈ −0.09 … −0.12R | **≈ −0.15 … −0.30R** |

Reasoning: cost in R falls ~10x (Arm B benefits most — its median risk is 0.78 ATR vs Arm A's 2.64, so it was far more cost-sensitive); the adverse fill pushes *gross* slightly **more** negative (Arm A 42% stop rate, Arm B 71%). The two corrections partially offset, which is why they must never be described as one "costs were too high" fix.

### Decision rules (fixed in advance)

1. **Prediction confirmed (both REJECT)** → register as confirmatory. The null is information-driven, not a cost artifact. This is the expected result and grants nothing.
2. **Either arm turns positive** → **investigate in the same turn** (user decision). Treat as a defect hypothesis first, in this order: cost-model sign/leg error → adverse-fill sign error → V1-reproduction drift → look-ahead in the new split/control code. Report the diagnosis with the numbers. A positive that survives investigation is **still not registrable as an edge**: it would require a fresh pre-registered test on unseen data, because a second look at the same corpus under a better ruler cannot license an economic claim.
3. **Controls not beaten** → the arm fails the success gate regardless of expectancy sign.
4. **OOS retention below IS** → report; do not retune. Retuning any frozen dimension after seeing V2 outcomes requires a V3.

### Multiplicity

V2 is a **measurement-basis replication** of V1's two pre-registered arms, not two new hypotheses. It inherits V1's Bonferroni α=0.025 and spends no new alpha. It cannot "rescue" V1: a null that stays null is confirmatory.

---

## Approach

### Step 1 — Governance pre-flight

- BUILD_IMPACT_MANIFEST `CH-vcrt-remeasure-v2` against `docs/governance/change_contracts.json`; classes `SCRIPT_LIFECYCLE_CHANGE` (new runner) + `DOCUMENTATION_ONLY`, carrying **UNK-COST-01** forward as a non-blocking unknown (still no registered class for the research measurement harness).
- Ground every new noun via `scripts/governance/query_semantic_os.py --ground` (§6.7).

### Step 2 — Seal `MC-VCRT-XAUUSD-M15-V2.json`

New file in `configs/research/measurement_contracts/instances/`. Copy V1 and change **exactly two** frozen dimensions:

| Surface | V1 | V2 |
|---|---|---|
| `costs.cost_model_id` | `CM-XAUUSD-LEGACY-12BPS-UNCALIBRATED` | `CM-XAUUSD-COMPONENT-MEASURED-V1` (SEM-015, sourced from the manifest sha256 `6ce4abf5…`, per-leg, `entry_slippage_basis=PROXY_FROM_STOP`) |
| `exits.exit_model_id` | `EX-VCRT-INTRABAR-V1` | `EX-VCRT-INTRABAR-ADVERSE-V2` (SEM-016 `AdverseFill(stop_slippage=0.09, model_gaps=True)`) |

**Byte-frozen from V1:** `population` (same corpus, same sha256 `4d73f5ce…`, 47,275 bars), `features`, `labels`, all geometry constants, horizon 40, duplicate rule, both arm definitions, multiplicity.

Also carried forward verbatim: `authority.economic_admissible: false`, `trust_status.economic_claims_allowed: false`, every `prohibited_substitutions` entry, and the `kill_criteria`. Add a `supersedes_note` recording that V2 exists because V1's cost and exit models are superseded — and that V1's *verdict* is not.

Add to `trust_status.open_risks_non_blocking`: stop slippage rests on n=7 demo fills; entry slippage is a declared proxy; V1 did not execute its declared splits/controls.

### Step 3 — Make the driver contract-bindable (V1 stays byte-reproducible)

`src/research/visual_crt/driver.py`:

- Replace the hardcoded `_net_r` with an injected cost function. Default = today's exact 12bps arithmetic, so **V1 reproduces byte-identically**.
- Thread an `adverse_fill` parameter into the `forward_walk` call at `:279`; default `None` = V1 behaviour.
- Add `contract_id` as a parameter rather than the module constant, so the ledger stamps the right id.
- Extend `LedgerRow` additively with `split` (`"is"`/`"oos"`), `cost_model_id`, `fill_model_id`. V1 re-runs must still produce byte-identical rows — so write the V1 ledger through a compatibility path that omits the new fields, or regenerate V1's expected artifact and diff against the committed one explicitly.

**Reuse, do not reimplement:** `research.costs.ComponentCostModel` (+ `.from_manifest`, `.cost_r(exit_kind=…)`), `research.measurement.forward_walk.AdverseFill`, `research.provenance.provenance_block(cost_model=…, fill_model=…)`.

### Step 4 — Implement the declared splits and controls

New module `src/research/visual_crt/controls.py` (keeps `driver.py` focused, mirrors the package's existing one-concern-per-file layout):

- **`single_holdout_chronologic`** — per arm, sort entries by `entry_ts`, last 20% = OOS; drop IS entries whose 40-bar exit horizon overlaps the OOS start (purge); enforce the 96-bar (24h) embargo. Emit `split_manifest.json` with the exact locked dates, as the contract requires.
- **`random_entry` control** — same n, same direction mix, same SL/TP geometry, entry bars drawn uniformly from the corpus. Seeded; declare the seed in the contract.
- **`long_only` control** — same entry bars and geometry as the arm, direction forced long. This is the control that matters most here: gold trended up across 2024-2026, so an arm must beat passive long exposure, not just zero.

Both controls resolve through the **same** `forward_walk` + cost model as the arm — otherwise the comparison is rigged.

### Step 5 — Runner script (SITS-registered)

`scripts/research/vcrt_remeasure_v2.py` — thin `argparse` wrapper (no business logic per §3.3), taking `--contract` and `--out-dir`. Register the same turn: `script_census.py --write-stubs` → `seed_script_registry.py` → `generate_script_matrix.py`.

Outputs to `results/visual_crt/mc_vcrt_xauusd_m15_v2/`: `ledger_arm_{A,B}.jsonl`, `controls_{random_entry,long_only}_{A,B}.jsonl`, `split_manifest.json`, `metrics.json`, `summary.json` — each carrying the full provenance block.

### Step 6 — Findings

Two findings, different types, registered per the E-001 six-question ritual:

- **F-083 (GOVERNANCE)** — V1 declared an OOS split and two controls in its sealed contract and executed neither; V2 closes the gap. Explicitly state that F-081's REJECT is unaffected (a null never reaches those gates) and why the gap still mattered.
- **F-084 (ECONOMIC)** — the V2 re-measurement result under the corrected basis, scoped to whatever actually comes back.

Both rows added to `docs/current-findings.md` **and** the CLAUDE.md Truths Index (the test enforces both). Add a forward pointer on F-081; never edit its verdict.

---

## Verification

**Gate 1 — V1 reproduction (must pass before any V2 number is trusted).** Re-run the driver under V1 bindings and diff against the committed artifacts:

```bash
venv/Scripts/python.exe -m pytest tests/research/test_visual_crt_trade_object.py -q
```

Then byte-diff regenerated `ledger_arm_A.jsonl` / `ledger_arm_B.jsonl` against `results/visual_crt/mc_vcrt_xauusd_m15_v1/`. A refactor that cannot reproduce V1 invalidates V2 — stop and fix.

**Gate 2 — the V2 run.**

```bash
venv/Scripts/python.exe scripts/research/vcrt_remeasure_v2.py --contract MC-VCRT-XAUUSD-M15-V2
```

Check against the pre-registered prediction table above, then apply the decision rules — including the same-turn investigation if either arm turns positive.

**Gate 3 — floors and governance.**

```bash
venv/Scripts/python.exe -m pytest tests/research/test_visual_crt_trade_object.py tests/test_component_cost_model.py tests/test_forward_walk_adverse_fill.py tests/test_measurement_contract.py tests/test_current_findings.py tests/test_topic_docs.py tests/test_script_registry.py -q
```

Plus a new floor `tests/research/test_vcrt_v2_contract.py`: V2 differs from V1 in exactly the two declared surfaces; controls run through the same cost model as the arms; the OOS split respects embargo and purge; `economic_claims_allowed` is false.

**Known-failing, out of scope:** the 9 pre-existing GREEN_FLOOR failures recorded under F-071, and `test_session_log.py` entry-count (81 vs cap 30 — rotation rewrites a file other sessions append to concurrently, so it stays flagged for the user, not run unilaterally).

---

## Explicitly not doing

- **No edit to `MC-VCRT-XAUUSD-M15-V1.json`** or to F-081's verdict.
- **No retuning of any frozen dimension** after seeing V2 outcomes — that requires a V3.
- **No economic claim** whatever V2 returns; `mt00`/`mt01` remain UNRUN, 0/27 probes.
- **No production activation** — `ACTIVE_VERSION` (`v2_htfcrt_2026_08`) untouched, UltronRiskGate cost tax still declared-but-inert.
- **No re-measurement of any other finding** — this turn is Visual CRT only.
