# Run M4 QualificationGate on crypto majors — and let it decide research vs architecture

## Context

**Goal.** Run the M4 `QualificationGate` on BTC/ETH/BNB/SOL (per-instrument + pooled) and use the
verdicts to allocate the next ~200 hours between *research* (hunting for a directional edge) and
*architecture* (the F-001 binding constraints: throughput / governance / consumption / execution).

**Why a re-run is justified (and not archaeology).** This analysis already ran on 2026-06-12 →
**F-019** (ZERO PROMOTE; toys ≈ random; spine throughput-starved). My first read was that re-running
is a deterministic replay with a pre-known verdict — **that was an overclaim.** F-019's reproducibility
is *not* git-pinned:

- Its manifest pins `git_commit=cfe4e16`, and `cfe4e16..HEAD` touches **zero committed M4 inputs** —
  but `src/research/` and `configs/research/` are **entirely untracked**, so that commit-diff is blind
  to the research layer.
- The **working tree is dirty on the spine inputs**: `configs/production/v2_multi_2026_04.json`
  (+74 lines — populates `regime_governor` / `convergence_controller` / `acceptance_controller` /
  `exit_model` / `breakout_disp_threshold`, hash `0cc891eb` vs HEAD `90a38c53`),
  `src/config_layer/crt_engine_v2.py` (+40), `src/runtime/backtest_v2.py` (+260).
- Current research-config file hashes differ from F-019's recorded SHAs (toy `c6fde62b` vs `04f4ba1a`;
  spine `ab2193d3` vs `c6a72dbe`) — though those recorded SHAs may be of the *normalized* config, so
  treat the raw-file mismatch as suggestive, not conclusive.

**Net:** provenance is unpinned, so replay-vs-drift cannot be predicted a priori. The **byte-comparison
of the new output against F-019's frozen `qualify_majors.json` is itself the experiment.** That is the
honest, high-ROI reason to run — it simultaneously (a) revalidates or overturns F-019 under the current
code/config and (b) produces the decision input the user asked for.

**Authority-Ladder guardrail (§6.5).** Even a non-null result does not auto-redirect 200h into research.
F-001 ("intelligence is NOT the binding constraint" — Certain) and the Program-1 closure (KILLED) set a
high bar: only a **PROMOTE**, or a **powered (n≥30) cell with E>0 that survives gates 4–7**, counts as
"research has a live lead." A lone positive *underpowered* cell (cf. F-019's spine/SOL n=7) is explicitly
*not* an edge.

## Files involved (read/run only — no source edits expected)

- `scripts/research/qualify_majors.py` — the driver. Run: `python scripts/research/qualify_majors.py --out <dir>`.
  Scopes `[BNBUSDT, ETHUSDT, BTCUSDT, SOLUSDT, POOLED]`, two families (toys + spine), intrabar_fixed + 12bps.
- `src/research/qualification.py` — the 7-gate `QualificationGate` (n≥30 · E≥0 · PF≥1 · beats winning control ·
  OOS retention≥0.5 · permutation p≤0.05 · cohort BH). Verdicts: PROMOTE / REJECT / INSUFFICIENT.
- `configs/research/research_config_majors.json` (toys), `configs/research/research_config_spine_majors.json`
  (spine, `prod_version=v2_multi_2026_04`).
- F-019 baseline (frozen, do not overwrite): `results/research/qualification/qualify_majors.json` +
  `..._manifest.json`; writeup `docs/analysis/qualify-majors-2026-06-12.md`.
- Truth/decision targets: `docs/current-findings.md` (F-019 row), CLAUDE.md §6.2 Truths Index.

## Plan

### Step 0 — ORIENT_RUNTIME + pre-flight load check (§4.0, blocking)
- Confirm `configs/production/ACTIVE_VERSION` = `v2_multi_2026_04` (verified) and that the **drifted
  working-tree** config loads: instantiate via `get_prod_config()` / `ConfigBuilder`. If the +74-line
  diff introduced an override key absent from `CRTConfig`, `_validate_override_keys` will raise
  `ValueError: unknown override key(s)` → **STOP, conclude "schema/version mismatch," surface per §6.2,
  do not migrate or force-run.**

### Step 1 — Capture provenance (reproducibility hazard mitigation)
The run executes against a dirty, partly-untracked tree, so its output cannot be pinned to a commit.
Before running, record into the run dir / finding: `git rev-parse HEAD`, `git status --porcelain`,
and `sha256sum` of the active prod config + both research configs. This makes the result auditable even
though it isn't git-clean. *(Recommended default: run against the working tree as-is — it measures the
current state, which is the user's intent. Committing the research layer + spine WIP first for a clean
git-pinned run is the stricter alternative; note it but don't block on it.)*

### Step 2 — Run the gate
`python scripts/research/qualify_majors.py --out results/research/qualification_2026_06_18`
(new dir — never clobber the F-019 baseline). Produces `qualify_majors.json` (deterministic body) +
`qualify_majors_manifest.json` (wall-clock + git + config SHAs).

### Step 3 — Byte-compare to F-019, per arm
Diff new `qualify_majors.json` against `results/research/qualification/qualify_majors.json`:
- **Toy arm** (`expansion_breakout`, `mean_reversion`): identical numbers ⇒ toy config/gate determinism
  intact; any delta ⇒ research-config drift is real and must be explained.
- **Spine arm**: this is the live signal — the drifted `crt_engine_v2` + prod config feed it. Compare
  per-instrument n / E / PF / verdict and the pooled cell.
Record which cells (if any) changed verdict tier.

### Step 4 — Decide research vs architecture (encode the Authority Ladder)
- **All cells REJECT/INSUFFICIENT again (most likely given throughput priors):** F-019 holds *under a
  refreshed code+config* → **stronger** than before → **architecture wins the 200h.** Concrete lane:
  F-010 (live-PnL verification — ExecutionPlanner + UltronRiskGate, the open OPEN finding), throughput /
  consumption / governance integrity (the F-001 constraints). Revalidate F-019 (refresh `Validated`,
  cite the new run).
- **A spine/toy cell flips to PROMOTE, or a powered n≥30 cell clears gates with E>0:** genuinely new
  information → register a **new finding** (do not silently revive Program 1; per Program-1 closure a
  parameter/config pass is not a reopen unless it constitutes a new ontology) and bring the result back
  to the user before reallocating — information ≠ authority (§6.5).
- **Underpowered positive cell only (e.g. spine/SOL n<30):** explicitly *not* an edge; note as an F-010
  lead, decision stays architecture.

### Step 5 — Findings + SESSION LOG (mandatory)
- Update the **F-019 row** in `docs/current-findings.md` the same turn (revalidate or flip per Step 4;
  never delete — mark SUPERSEDED if overturned). Run the E-001 6-question pre-registration check before
  registering any new finding.
- Append the `📝 SESSION LOG ENTRY` block to `assistant_project.md` (codebase log) including the
  `Belief Update / ROI / Goal` line and the self-correction (overclaimed deterministic-replay → corrected
  by working-tree provenance audit).

## Verification

1. **Loadability:** Step 0 config-load succeeds (no `unknown override key` raise).
2. **Determinism control:** the toy arm either matches F-019 byte-for-byte (confirms gate determinism) or
   the difference is fully explained by the research-config delta — no unexplained drift.
3. **Decision traceability:** the research-vs-architecture call in the SESSION LOG maps 1:1 to the Step-4
   rule and cites the new `qualify_majors.json` cells.
4. **No baseline clobber:** `results/research/qualification/qualify_majors.json` (F-019) is untouched;
   new output lives under `qualification_2026_06_18/`.
5. **Findings integrity:** `pytest tests/test_current_findings.py` green after the F-019 edit.
```
