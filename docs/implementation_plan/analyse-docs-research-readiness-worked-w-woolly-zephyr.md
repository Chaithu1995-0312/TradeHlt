# Execution Plan — Freeze RVG + Register in ERP (U1/U2 folded in)

## Context

Owner granted: **freeze the Findings-Revalidation Gate (E4) prereg**, **register it in the ERP
program tracker**, then resolve **RVG-U1** and **RVG-U2**. I ran U1/U2 **first (read-only)** because
U2 can reclassify scope — and it did. The freeze must bake the U1/U2 results in, so it happens after
them. The prereg + JSON twin already exist in the repo as DRAFT
([findings-revalidation-gate-e4-preregistration.md](docs/research-readiness/findings-revalidation-gate-e4-preregistration.md) / `.json`);
this plan flips them to FROZEN and wires the program tracker.

## Investigation results (read-only, done)

**RVG-U1 — E3 baselines exist on disk → no E3 re-run needed as a prerequisite.**
- F-019: `results/research/qualification_2026_06_27/qualify_majors.json` (+ `_manifest.json`); determinism twin `qualification_run2/`
- F-021: `results/research/phase_s_2026_06_27/phase_s_selection_effect.json` (+ `phase_s_run2/`)
- F-020: `results/research/phase_b/phase_b_conditional_entropy.json` (+ `phase_b_run2/`)
- F-025: `results/research/phase_d/phase_d_exit_grid.json` (+ `phase_d_run2/`)
- F-027: `results/research/qualification_htf/qualify_htf_{H1,H4}.json`
- F-035: `results/research/qualification_fx_metals/qualify_fx_metals.json`
- F-023/024: `results/research/bnbusdt_trade_anatomy_2026_06_27/`

**RVG-U2 — Class B is feature-pipeline-independent (reclassify).**
- `src/research/hypotheses/expansion_breakout.py` + `mean_reversion.py`: `detect()` takes a
  `features` dict but **ignores it**; computes from raw OHLC via `research.indicators.atr/sma` +
  `bar.body_ratio` (F-046-benign, byte-identical) + raw `prior_high/low`.
- `src/research/indicators.py`: pure stdlib, self-contained, **no recent git history** (untouched by
  the feature-layer fixes); simple-mean TR chosen for determinism.
- `phase_b` (F-020) builds its own `research.measurement.bar_features` (session/vol-tercile/momentum);
  `phase_d` (F-025) uses `research.indicators.atr` + fixed toy entries + `forward_walk`.
- **Conclusion:** F-051 (centered swings) + F-054 (FM-040..046) live in `src/features/`, which the
  whole `src/research/` toy/measurement stack **never imports**. So the Class-B verification is a
  `src/research/` **drift check** (git-diff E3-commit→HEAD) + determinism re-confirm — **not** a
  feature re-derive. Genuine feature risk is confined to **Class C** (morphology / zone / RR /
  gaussian consume the production 38-dim vector).

## Changes to make (on approval)

### 1. Freeze the prereg — `docs/research-readiness/findings-revalidation-gate-e4-preregistration.md` (+ `.json`)
- Status banner `DRAFT — NOT FROZEN` → **`FROZEN 2026-07-16 (owner-accepted)`**; RVG-0 half (b) DONE.
- Add a **`protocol_hash`** to the JSON twin = `sha256` of the frozen `.md` (compute with
  `python scripts/maintenance/_compute_hash.py`-style or `sha256sum`); record it in the md header too.
- **Fold U1 in** (§8 RVG-U1 → RESOLVED, list the baseline paths; drop "else re-run E3").
- **Fold U2 in** (§2 scope table: Class B method → "determinism re-confirm + `src/research/` drift
  check (git-diff), NOT feature re-derive — toys run on the isolated `src/research/` stack"; §8
  RVG-U2 → RESOLVED with the evidence). This is a §18 pre-freeze amendment (allowed).
- Lock the §18 "cannot amend after freeze" list (M0/M1-equivalent: class definitions, verdict
  taxonomy, cost prior, exit truth, success/exit criteria).
- Keep authority boundary intact: FROZEN grants **no** run authority — RVG-1..5 still need grants.

### 2. Register in the ERP program tracker — `docs/research-readiness/edge-research-platform-program.{md,json}` (twin, same turn)
- **§6 Work items:** add row `WI-001 · WS-OUTCOME-FACTORY · Findings-Revalidation Gate E4 · DESIGN(frozen) · validation_flow_review=UNTRUSTED_RAW · Notes: prereg frozen 2026-07-16; RVG-1 next`.
- **§7 Conversation log:** append `CL-017 — 2026-07-16 — RVG E4 designed + frozen; U1 (baselines on disk) + U2 (Class B feature-independent) resolved; registered as P2.0`.
- **§9 / NA:** NA-002 (WS-OUTCOME-FACTORY design) → advanced; add NA "grant Implement RVG-1".
- **§11 / §12.4 + decision board D-16:** tag the findings anchors **`PROVISIONAL (pending E4)`** —
  annotation only, no finding flipped (this is the whole point of the gate).
- Mirror all of the above into `edge-research-platform-program.json` (`work_items`,
  `conversation_log`, `next_actions`).

### 3. SESSION LOG — append the §6 block to `assistant_project.md`
Freeze + registration + U1/U2 resolution; Belief/ROI line (U2 shrank the suspect set to Class C only).

## What this does NOT do
- No RUN, no harness (`scripts/research/revalidate_findings_e4.py` is RVG-1, still gated).
- No finding is flipped in `docs/current-findings.md` (freeze ≠ result).
- No production/config/capital change; hash-neutral to the active config.

## Verification (read-only, after edits)
- `grep -n "FROZEN" docs/research-readiness/findings-revalidation-gate-e4-preregistration.md` shows the freeze stamp; JSON `frozen:true` + `protocol_hash` present.
- Prereg ↔ JSON twin consistent (status, protocol_hash, U1/U2 tokens).
- ERP `program.md` §6 row ↔ `program.json` `work_items` entry match (twin discipline).
- `docs/current-findings.md` unchanged (no finding rows edited).
- Class-B drift check preview: `git diff --stat <E3-commit>..HEAD -- src/research/` (for RVG-3 later; not run now).
