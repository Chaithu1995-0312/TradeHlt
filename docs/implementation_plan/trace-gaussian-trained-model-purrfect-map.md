# Gaussian Trained Model — Trace Closure + Pivotality Ablation

## Context

**Why:** `active_models.yaml` and `docs/governance/gaussian_lineage_audit.md` describe the Gaussian
engine as "dual-track": a live 3-feature heuristic (Track A) plus a trained 35/38-dim Naive-Bayes
model that is `TRAINED_ARTIFACT = INERT` (Track B). The trace run this session confirms the
dual-track shape but finds the audit **understates it in one direction and misses a lineage entirely**.

**What the trace established** (verified against source, not comments):

1. **The live scorer has zero learned parameters.** `HeuristicGaussianEngine.compute`
   ([heuristic_gaussian_engine.py:325-333](src/engines/heuristic_gaussian_engine.py:325)) computes
   `exp(-(x-mu)^2 / 2*sigma^2)` where `x = (ema_diff + tanh(momentum))/2`. `mu`/`sigma` come from
   `GaussianRegistry` via `_normalize_registry_entry`
   ([heuristic_gaussian_engine.py:42-53](src/engines/heuristic_gaussian_engine.py:42)), which
   defaults `mu=0.0, sigma=1.0`. **I dumped all 11 entries of `models/gaussian_registry.json`: not
   one carries a `mu` or `sigma` key** (they carry `version`/`model_file`/`feature_schema`/
   `metrics`/`trained_at`/`active`). So the defaults fire unconditionally and the live score is
   `exp(-x^2/2)` — byte-identical to the no-registry-at-all path.
   → `gaussian_lineage_audit.md:76` ("registry active entries supply mu/sigma to the heuristic")
   is **DOC_DRIFT**. The registry read is a no-op, not a reduced-fidelity read.

2. **The audit names the wrong trainer.** It cites `train_pipeline.run_gaussian_update`
   ([gaussian_lineage_audit.md:68,185](docs/governance/gaussian_lineage_audit.md:68)). Every
   artifact actually on disk was produced by `scripts/training/phase5_calibration.py`
   (`run_calibration` `:623` → `train_gaussian` `:642`), which builds labels from
   `rec["rr_achieved"]` read straight off `opportunities.jsonl`
   ([phase5_calibration.py:434](scripts/training/phase5_calibration.py:434)) — **the F-022 stream**
   (36.8% self-consistent). No `forward_walk` re-derivation exists anywhere in the Gaussian
   training path. The docstring at `:387`/`:391` claiming "unbiased ground-truth labels" is
   contradicted by F-022/F-041B. The audit flags this contamination as a *possibility*
   (`:45`, `:162`); the trace confirms it as **actual**, on the only lineage that produced artifacts.

3. **Shape consequence, not yet a claim:** with `mu=0`, the score peaks at 1.0 when the market is
   flat and decays for strong moves in **either** direction, while entering fusion at
   `weight_gaussian: 0.2` ([v2_multi_2026_04.json:113](configs/production/v2_multi_2026_04.json:113))
   alongside directional channels. Whether that costs anything is exactly what Part B measures.

**Intended outcome:** correct the governance record to the verified truth, and settle by proof
whether the Gaussian channel changes any trade at all.

**Scope decision (user, this session):** governance record + marginal-value measurement.
Registry/dashboard hygiene (7 dangling entries, `v4_mirrored` shown ACTIVE in
`ui_kits/crt_dashboard/data.js`, `auto_train_from_opportunities.py:98` omitting `--gaussian`) and
`forward_walk` label re-derivation are **explicitly out of scope** — record them as residual, do
not fix.

---

## Part A — Governance record (doc + finding + floor)

### A1. Correct `docs/governance/gaussian_lineage_audit.md`

Surgical edits, preserving history per §6.2 rule 4 (mark `CORRECTED:`, never silent-delete):

- `:76` and `:160` — the mu/sigma claim. Replace with the verified fact: the registry read supplies
  **nothing**; `_normalize_registry_entry` defaults produce `mu=0.0/sigma=1.0` because no entry
  carries those keys. Live score = `exp(-x^2/2)`, zero learned parameters.
- Add the missing lineage: `scripts/training/phase5_calibration.py` is the builder of record for
  every on-disk artifact; `train_pipeline.run_gaussian_update` is a second, unexercised path.
- `:45`/`:162` — upgrade "may inherit F-022 contamination" to **confirmed**, citing
  `phase5_calibration.py:434`.
- Update the verdict block `:14-20`: keep `DUAL_TRACK` / `TRAINED_ARTIFACT = INERT`; add
  `LIVE_SCORER_PARAMETERIZED = NO` and `LABEL_INTEGRITY = F022_CONTAMINATED_CONFIRMED`.
- Append residual (out-of-scope) items so they are recorded, not lost.

### A2. Register the finding in `docs/current-findings.md`

New `F-0NN` (next free id), type `ARCH`, confidence `Certain` for the mechanical claims.
Conclusion, in the house style:

> The live Gaussian channel is an **unparameterized** kernel, not a reduced-fidelity trained model —
> `exp(-x^2/2)` over 3 of 38 features, with `mu=0/sigma=1` forced by the absence of those keys in
> every `gaussian_registry.json` entry (11/11 verified). Refines `gaussian_lineage_audit.md`'s
> `TRAINED_ARTIFACT = INERT` from "trained weights unused" to "**no learned parameter reaches the
> scoring path at all**". Separately, the artifact-producing trainer is
> `phase5_calibration.py` (not `train_pipeline.py` as audited), and it trains on raw
> `rr_achieved` from the F-022 stream — contamination **confirmed**, not merely possible.

Add the matching row to the CLAUDE.md §6.2 Repository Truths Index (enforced both ways by
`tests/test_current_findings.py`).

**E-001 pre-registration discipline:** claims 1 and 2 are mechanical/source-verified → `Certain`.
Any *economic* claim about the channel is **not** registered here; it depends on Part B and is
pre-committed below to a `Possible`-or-nothing ceiling.

### A3. Mechanical floor — `tests/test_gaussian_live_parameterization.py`

The lesson from `feedback_verify_source_not_comments`: when a class of drift recurs, add a
mechanical guard so prose can't drift back. Two assertions:

- Loading `models/gaussian_registry.json`, **no** entry carries `mu`/`sigma` → so the documented
  "zero learned parameters" statement is true *by artifact*, and the test **fails loudly the day
  someone adds them** (which would be a real behavior change needing its own governance).
- `HeuristicGaussianEngine` under the active config produces a score equal to `exp(-x^2/2)` for a
  synthetic feature dict — pinning the live math.

---

## Part B — Pivotality ablation (does the Gaussian channel change any trade?)

### B1. Method — reuse, don't build

`scripts/research/diagnose_zone_inertness.py` is the exact template (it is the F-036 gate-ON
fusion-channel ablation). Its docstring states the method verbatim
([diagnose_zone_inertness.py:11](scripts/research/diagnose_zone_inertness.py:11)):
*byte-identical trade ledger ⇒ that channel is NON-PIVOTAL — a proof, no statistics needed.*

Reuse directly:
- **Run primitive:** `qualify_zone_topk._run_spine_once(instrument, version, out_dir)`
  ([qualify_zone_topk.py:146](scripts/research/qualify_zone_topk.py:146)) → `(metrics, entries, trades_sha)`.
- **Comparator:** its `trades_sha` = sha256 of `{instrument}_trades.csv`
  ([qualify_zone_topk.py:191](scripts/research/qualify_zone_topk.py:191)).
- **Neutrality proof:** the `_selfcheck` pattern
  ([diagnose_zone_inertness.py:145-150](scripts/research/diagnose_zone_inertness.py:145)) —
  unpatched vs patched-at-baseline must be byte-identical, else `SystemExit`. Non-negotiable here.

### B2. New driver — `scripts/research/diagnose_gaussian_pivotality.py`

Modeled on `diagnose_zone_inertness.py`, ~200 lines.

**Injection seam — patch `HeuristicGaussianEngine.compute`, not the adapter or the weight.**
Rationale, and it matters:
- `weight_gaussian = 0` is *removal with renormalization over the remaining three channels*
  ([fusion_engine.py:487](src/core/fusion_engine.py:487)), which is a different intervention than a
  constant-0.5 vote — it changes the other channels' effective weights too.
- Patching `GaussianAdapter.score` ([fusion_engine.py:231](src/core/fusion_engine.py:231)) covers
  fusion but **misses** `engine_results["gaussian"]`, which is a *separate* call at
  [engine_runner.py:698](src/core/engine_runner.py:698) feeding the completeness gate and the
  P5 path at `:730-741`.
- Both seams funnel through the same object (`GaussianAdapter(self.gaussian)` at
  [engine_runner.py:382](src/core/engine_runner.py:382), same instance as `:698`). Patching
  `HeuristicGaussianEngine.compute` to return `{"score": 0.5, "reason": "ablation_pinned"}`
  therefore covers fusion **and** engine_results **and** the ConvergenceController stability term
  (the third channel the zone sweep explicitly deferred,
  [diagnose_zone_inertness.py:20-23](scripts/research/diagnose_zone_inertness.py:20)) in one hook.

**Cells:** `baseline` (unpatched) and `pinned_0p5`. Instruments BNBUSDT / ETHUSDT / BTCUSDT /
SOLUSDT from `data/{INSTR}_M15.csv`.

**Gate hygiene — decisive.** Gaussian only matters when fusion runs.
`backtest_v2.py:1899` reads `os.getenv("BACKTEST_ENGINE_GATE", "1")` — **code default ON** (F-058),
but F-037 and `active_models.yaml` document "OFF", and the value has historically come from an
untracked `.env`. Neither reused script sets it. So the driver **must** set
`os.environ["BACKTEST_ENGINE_GATE"] = "1"` explicitly (the `crt_guard_ablation_6m.py:139` idiom)
and record the effective value in its manifest. A gate-OFF run would measure literally nothing and
silently report "non-pivotal".

**Artifact:** `results/research/gaussian_pivotality/gaussian_pivotality.json` + a
`_manifest.json` carrying `body_sha256`, the gate value, config version, and per-instrument
`baseline_sha` / `pinned_sha`.

### B3. Pre-registered interpretation (write this into the driver docstring *before* running)

| Outcome | Verdict | Authority granted |
|---|---|---|
| All 4 ledgers byte-identical | `GAUSSIAN_NON_PIVOTAL` — proof, no statistics needed | Research/docs only |
| Any ledger differs | `GAUSSIAN_PIVOTAL_UNDERPOWERED` | **None** |

**The power ceiling is known in advance and must not be laundered.** Gate-ON trade counts from
F-037 are BNB 11 / ETH 4 / BTC 5 / SOL 6 → pooled **n≈26**, below the `min_samples: 30` floor.
So if ledgers differ, the honest result is *"the channel moves trades; its economic sign is
INSUFFICIENT"* — **no expectancy claim, no promote, no re-weight, no removal.** Per §6.5 Authority
Ladder: information ≠ value ≠ authority. Pre-committing this table is what stops a small-n
delta from being narrated into a verdict after the fact.

Either way the config is **untouched** — this is a measurement, not a change.
`PRODUCTION_BEHAVIOR_CHANGED = NO`.

---

## Files

**Modify:**
- `docs/governance/gaussian_lineage_audit.md` — corrections + missing lineage + residuals
- `docs/current-findings.md` — new finding row + full record
- `CLAUDE.md` §6.2 Truths Index — matching thin row
- `active_models.yaml` — gaussian block: align the mu/sigma narrative with A1
- `assistant_project.md` — §6 SESSION LOG entry

**Create:**
- `tests/test_gaussian_live_parameterization.py`
- `scripts/research/diagnose_gaussian_pivotality.py`

**Reuse (do not modify):** `scripts/research/qualify_zone_topk.py` (`_run_spine_once`),
`scripts/research/diagnose_zone_inertness.py` (injection + selfcheck pattern),
`scripts/update_config_hash.py` (not needed — no `params` edit, hash-neutral).

---

## Verification

1. `python -m pytest tests/test_gaussian_live_parameterization.py -v` — new floor green.
2. `python -m pytest tests/test_current_findings.py tests/test_closure_authority_index.py tests/test_doc_citations.py tests/test_topic_docs.py -v` — findings/index/citation floors green (these enforce the §6.2/§6.3 mandates the doc edits touch).
3. `python scripts/research/diagnose_gaussian_pivotality.py --instruments BNBUSDT --selfcheck-only`
   — injection neutrality proof must pass (unpatched sha == patched-at-baseline sha) **before** any
   real cell runs. If it fails: STOP, the hook is not neutral.
4. `python scripts/research/diagnose_gaussian_pivotality.py --instruments BNBUSDT ETHUSDT BTCUSDT SOLUSDT`
   — full run; inspect `results/research/gaussian_pivotality/gaussian_pivotality.json`.
   Confirm the manifest records `BACKTEST_ENGINE_GATE=1` and that baseline trade counts reproduce
   F-037's 11/4/5/6 (if they don't, the gate or corpus differs — investigate before reading the delta).
5. `python -m pytest tests/ -x -q` — no regression (doc/test-only + a new research script; nothing
   on the scoring path is edited).
6. §6 SESSION LOG entry appended to `assistant_project.md` with the `Belief Update / ROI / Goal` line.

---

## Flag (unrelated to this task, needs your call)

While searching for how `BACKTEST_ENGINE_GATE` is set, an Explore subagent read `.env` — which
CLAUDE.md §4 forbids — and reported that it contains a live `ANTHROPIC_API_KEY` and an Alpha
Vantage key in plaintext. **I have not reproduced or stored the values.** Worth confirming `.env`
is gitignored (`git log --all -- .env` settles whether it was ever committed) and rotating if it
was. Related open item: memory `project_pending_secret_ref_cleanup` tracks a prior compromised
Groq key on two local refs. Your call whether to act now or separately.
