# Design: XAUUSD Gaussian — From Registry Promote to Economics

**Date:** 2026-07-23  
**Status:** DESIGN — **E0 + E1 + E2 IMPLEMENTED**; **xau_metals_protocol_v1 EXECUTED** (20260722T211010Z, n_perm=200 CLI; primary INSUFFICIENT; no economic authority)  
**Authority:** Grants **no** production wire, **no** `gaussian_impl=ml`, **no** G001 claim until Phase E passes  
**Primary artifact (today):** `xauusd_nb_20260722T194904Z`  
**Semantic journal:** `results/gaussian_xauusd_train/gaussian_xauusd_train_20260722T194904Z/bar_semantic_journal.jsonl`  
**Hashes:** `results/gaussian_xauusd_train/HASHES_AND_CLOSURE.json`

---

## 0. Problem statement (why we are not economic yet)

| What we have | What economics requires |
|---|---|
| Registry **Promoted: Yes** (XAUUSD active pointer) | **ΔG001 / book E[R] / PF** under governing exit |
| Labels from **CRT SWEEP** + fixed 1R/1R `forward_walk` | Entries that map to a **decision consumer** (or pre-registered candidate set) |
| mean labeled `y_rr` ≈ **−1.06 R** (journal) | Net expectancy ≥ 0 OOS, beats controls, M4 gates |
| Score surface on 2m bars (mean ~0.62) | **Conditional** economics: high-score vs low-score units |
| Live `gaussian_impl=heuristic` | Optional later: shadow ML consumer A/B (still not authority until ΔG001) |

**Authority Ladder (non-negotiable):**

```text
Information (corr, scores)
    → Economic usefulness (measured NET E[R], PF, ΔG001 vs control)
        → Authority (allowed to influence production)
            → Architecture (complexity justified)
```

Today we sit at **Information + registry hygiene**. This design moves to **Economic usefulness measurement**. Authority is a later, evidence-gated decision.

---

## 1. North star (one sentence)

**Build a pre-registered, journal-grounded measurement chain that answers: does the XAUUSD Gaussian NB improve selection economics vs controls under `forward_walk(intrabar_fixed)+cost`, and only then discuss production authority.**

---

## 2. Design principles

1. **Reuse existing gates** — M4 `QualificationGate` (`src/research/qualification.py`); do not invent a parallel promote standard.  
2. **Reuse existing shadow eval** — `scripts/research/build_gaussian_family_shadow_eval.py` already supports XAUUSD + `candidate-mode` + econ stride.  
3. **Journal is the entry ontology** — every candidate must be reconcilable to `bar_semantic.v1` kinds (`SWEEP_CANDIDATE`, `LABEL_ACCEPTED`, `HOLDOUT`).  
4. **Holdout discipline** — train already excluded trailing 2m (`HOLDOUT` in journal); economics OOS must respect chronology.  
5. **Config-first consumer knobs** — any threshold on NB score is config-declared if it ever influences a path; research scripts may use explicit CLI first.  
6. **No silent live flip** — `gaussian_impl` stays `heuristic` until a separate, measured shadow → optional config PR.  
7. **Negative results are success** — 0 PROMOTE is a valid closed experiment (per qualification module doctrine).

---

## 3. Enhancement architecture (layers)

```text
┌─────────────────────────────────────────────────────────────┐
│  E3  Authority decision (OPTIONAL, human + ΔG001)           │
│      promote consumer / gaussian_impl=ml|shadow_ml          │
└──────────────────────────▲──────────────────────────────────┘
                           │ only if E2 PROMOTE + ΔG001
┌──────────────────────────┴──────────────────────────────────┐
│  E2  M4 QualificationGate on score-conditioned candidates   │
│      PROMOTE | REJECT | INSUFFICIENT                        │
└──────────────────────────▲──────────────────────────────────┘
                           │ outcomes + controls
┌──────────────────────────┴──────────────────────────────────┐
│  E1  Economic measurement harness (NET R ledger)            │
│      high-score / low-score / random / long-only controls   │
│      forward_walk + CostModel (same as M4)                  │
└──────────────────────────▲──────────────────────────────────┘
                           │ candidates + scores
┌──────────────────────────┴──────────────────────────────────┐
│  E0  Candidate + score layer (journal-aligned)              │
│      SWEEP units from journal OR re-stream with same codes  │
│      score via promoted XAUUSD NB (name-anchored 39-dim)    │
└─────────────────────────────────────────────────────────────┘
         ▲
┌────────┴────────┐
│ bar_semantic.v1 │  already closed (label_build proof)
└─────────────────┘
```

---

## 4. Phase plan

### Phase E0 — Candidate + score contract (1–2 days)

**Goal:** Deterministic table: one row per economic unit with features, NB score, direction, bar_index, train/holdout flag.

| Field | Source |
|---|---|
| `bar_index`, `timestamp`, `direction` | Journal `LABEL_ACCEPTED` / `SWEEP_CANDIDATE` or CRT re-stream |
| `split` | `train` if ts < holdout_start else `oos` (match journal HOLDOUT) |
| `score`, `expected_rr` | `load_gaussian_model(xauusd_nb_…194904Z)` name-anchored |
| `reason_code_origin` | journal lineage for LLM explain |

**Deliverables:**

- `scripts/research/xauusd_gaussian_econ_units.py`  
  - Input: Phase-1 corpus + model version + journal path  
  - Output: `results/gaussian_xauusd_econ/units_<ts>.jsonl` + manifest with hashes  
- Unit tests: holdout boundary matches journal `HOLDOUT` count (~267); score dim = 39  

**Exit:** N_train + N_oos units with scores; no economics yet.

**Reuse:** Journal already encodes accept/holdout; avoid redefining entry mid-flight.

**E0 SHIPPED (2026-07-23):**

| Item | Path / value |
|---|---|
| Script | `scripts/research/xauusd_gaussian_econ_units.py` |
| Tests | `tests/test_xauusd_gaussian_econ_units_e0.py` (4 passed) |
| Units | `results/gaussian_xauusd_econ/units_LATEST.jsonl` (n=3247 = 2980 train + 267 oos) |
| Manifest | `results/gaussian_xauusd_econ/e0_manifest_LATEST.json` |
| Pins | HOLDOUT=267, LABEL_ACCEPTED=2980, dim=39, score fails=0 |
| Authority | still RESEARCH_ONLY / no E1 economics |

---

### Phase E1 — Economic ledger (2–3 days)

**Goal:** Net R for each unit under **governing** exit (same family as train labels, but report economics honestly).

| Choice | Default | Rationale |
|---|---|---|
| Exit | `intrabar_fixed` | Governing research truth |
| Cost | 12 bps (or FX/gold-appropriate if config exists) | Align clean_labels / M4 |
| SL/TP | **Two arms:** (A) fixed 1R/1R as train; (B) production planner mults if available | Separates “fit the training label” from “planner-realistic” |
| Entry set | Sweep-only first (journal ontology) | No silent switch to TRADE_OPENED until Phase E1b |

**Arms (pre-register before run):**

| Arm ID | Rule | Control peers |
|---|---|---|
| `nb_top_decile` | Take unit if score ≥ p90 (train-calibrated quantile) | — |
| `nb_bottom_decile` | score ≤ p10 | anti-skill check |
| `random_match_n` | Random subset size-matched to top decile | permutation peer |
| `all_sweeps` | All units | baseline detection set |
| `long_only` / `short_only` | Direction filters | direction bias |

**Metrics (per arm, IS/OOS chronological):**

- n, mean net R, PF, win rate, max DD (optional), bootstrap CI if n allows  

**Deliverables:**

- Extend or call `build_gaussian_family_shadow_eval.py --instrument XAUUSD` with  
  `--candidate-mode sweep` and explicit score thresholds from E0 model  
- Output: `results/gaussian_xauusd_econ/ledger_<ts>.json` + per-arm tables  
- Link each arm back to journal `reason_code` vocabulary in the report  

**Exit:** Written E[R] for top-decile vs controls on **OOS (2m holdout + earlier OOS slice)**.  
**Still no authority** even if E[R] > 0 (need M4).

**Kill criteria (pre-registered):**

- Top-decile OOS E[R] ≤ all_sweeps E[R] **and** ≤ random → **no skill** → stop, freeze model as registry-only.  
- n_oos top-decile < `QualConfig.min_samples` → INSUFFICIENT, do not invent denser entries without new design.

**E1 SHIPPED (2026-07-23):**

| Item | Value |
|---|---|
| Script | `scripts/research/xauusd_gaussian_econ_ledger.py` |
| Tests | `tests/test_xauusd_gaussian_econ_ledger_e1.py` (6 passed) |
| Ledger | `results/gaussian_xauusd_econ/ledger_LATEST.jsonl` |
| Manifest | `results/gaussian_xauusd_econ/e1_manifest_LATEST.json` |
| Train p10 / p90 | 0.500014 / 0.622459 (train-only) |
| OOS all_units E[R] | **−0.532** (n=267, PF 0.31) |
| OOS top_decile E[R] | **−0.451** (n=174, PF 0.37) |
| OOS random E[R] | **−0.638** (n=174) |
| OOS bottom_decile | **n=0** (train floor ≈ p10; OOS scores sit above floor) |
| Kill verdict | **SKILL_SIGNAL_RESEARCH_ONLY** — top beats all & random on OOS **but all E[R]<0** |
| Economic authority | **NO** — negative expectancy; not M4 |

---

### Phase E1b — Optional entry upgrade (only if E1 kill or underpowered)

If sweep set is economically dead or underpowered:

| Option | When | Cost |
|---|---|---|
| B1 RETEST/EXECUTION-only candidates | Journal/CRT can emit denser structure nearer entries | New journal kinds or CRT state filter |
| B2 Spine `TRADE_OPENED` only | Honest live path; likely n≪30 on XAU | Expect INSUFFICIENT; still valuable null |
| B3 Planner-true SL/TP from `ExecutionPlannerV1_2` | Closer to live R geometry | Config-driven mults; parity tests |

**Rule:** One new entry ontology at a time; new `bar_semantic` reason codes if stream changes.

### Pre-registration superseding v0 (2026-07-23) — NOT YET EXECUTED

After conversation falsification, a **new frozen protocol** was pre-registered (do not edit after OOS):

| Piece | v0 (done) | **v1 pre-reg** |
|---|---|---|
| Cost | 12 bps flat | **Fixed USD RT 0.40** (+ sensitivity grid diagnostic) |
| Entry | SWEEP | **RETEST enter edge** |
| Control | broken multi-tag random | **Per-split size-match + acceptance_test** |
| Model | trained once | **No retrain** (same weights) |

- Machine: `configs/research/xau_metals_protocol_v1.json`  
- Human: `docs/research/xau_metals_protocol_v1_preregistration.md`  
- Loader: `src/research/xau_metals_protocol.py`  
- Status: `PRE_REGISTERED_NOT_EXECUTED` until a runner is implemented and run  


---

### Phase E2 — M4 QualificationGate (1–2 days)

**Goal:** Binary research verdict under unified gate.

Wire E1 outcomes into `QualificationGate`:

1. min_samples  
2. expectancy NET  
3. PF NET  
4. beats winning control  
5. OOS retention  
6. permutation vs control  
7. BH if multi-hypothesis cohort (multiple thresholds/arms)

**Deliverables:**

- `scripts/research/xauusd_gaussian_m4_qualify.py`  
- Artifact: `results/gaussian_xauusd_econ/m4_<ts>.json`  
- Finding row candidate only if PROMOTE (else document REJECT/INSUFFICIENT in session log + optional analysis note — **no** silent F-id)

**Exit:**

| Verdict | Action |
|---|---|
| PROMOTE | Proceed to E3 discussion (still not auto-wire) |
| REJECT | Close program for this entry/label protocol; journal remains research gold |
| INSUFFICIENT | Either stop or E1b with pre-registered plan |

**E2 SHIPPED (2026-07-23):**

| Item | Value |
|---|---|
| Script | `scripts/research/xauusd_gaussian_m4_qualify.py` |
| Tests | `tests/test_xauusd_gaussian_m4_e2.py` (3 passed) |
| Manifest | `results/gaussian_xauusd_econ/e2_m4_manifest_LATEST.json` |
| Cohort | **any_PROMOTE=False** · economic_authority=False |
| `nb_top_decile` | **REJECT** gate2_expectancy E[R]=−0.25 |
| `all_units` | **REJECT** gate2_expectancy E[R]=−0.96 |
| `long_only` / `short_only` / `nb_bottom_decile` | **REJECT** (all E[R]<0) |
| Program close | Research protocol on sweep+1R/1R+12bps is **economically rejected** under M4; registry pointer may remain; no E3 |

---

### Phase E3 — Toward authority (gated; optional)

Only if E2 = PROMOTE **and** measured consumer ΔG001 vs baseline:

| Step | Action | Forbidden without evidence |
|---|---|---|
| E3a | Shadow config: `gaussian_impl=shadow_ml` or instrument-scoped ML load for XAUUSD only | Editing active production to `ml` |
| E3b | Gate-ON A/B ledger sha + trade count (F-036 method) on XAU if spine admits trades | Claiming pivotality without byte-diff |
| E3c | Human approve: authority to influence fusion weight / veto | Auto-promote economic claim into findings Certain |

**Config-first:** new knobs (`score_accept_quantile`, instrument ML path) via strict `_require` sections; rehash if `params` touched.

**Default recommendation if E2 PROMOTE but spine n tiny:** keep **research consumer** (filter research candidates only); do **not** force live complexity.

---

## 5. What we explicitly will not do (anti-scope)

- Treat registry promote as economic promote  
- Train on F-022 contaminated opportunity streams as “production labels” without flagging  
- Silent truncate 39→38 or ambient vector hacks  
- Flip `gaussian_impl=ml` on active `v2_multi_2026_04` without E2+E3  
- Optimize score thresholds after seeing OOS (pre-register quantiles on train only)  
- Claim gold FX cost model is free — cost_bps must be declared and sensitivity-noted  

---

## 6. Semantic journal’s permanent role

The journal is the **epistemic substrate** for economics, not a side log:

| Economics question | Journal answer |
|---|---|
| What was an entry? | `SWEEP_CANDIDATE` / `LABEL_ACCEPTED` only |
| What was excluded from fit? | `HOLDOUT` |
| Why no live trade semantics? | No `TRADE_OPENED` kind exists in this run |
| Why mean R negative? | Aggregate `LABEL_ACCEPTED.payload.y_rr` |
| LLM explanation of a unit | `reason_code` + `narrative` + payload |

**Enhancement E0+:** append optional kinds (research-only, additive):

- `ECON_UNIT_SCORED`  
- `ECON_ARM_DECISION` (taken/skipped + arm_id)  
- `ECON_OUTCOME` (net R, exit_reason)  

Same `bar_semantic.v1` or bump to `v1.1` with backward-compatible readers.

---

## 7. Success metrics (program level)

| Milestone | Success |
|---|---|
| E0 | Units JSONL + hash; holdout parity with journal |
| E1 | Pre-registered arms; OOS table published |
| E2 | M4 verdict file; 0 PROMOTE is success if honest |
| E3 | Only if PROMOTE + ΔG001; otherwise program CLOSED research-only |

---

## 8. Suggested first implementation PR (minimal)

**PR-1 (E0 only):**

1. `scripts/research/xauusd_gaussian_econ_units.py` — journal → scored units  
2. Manifest + SHA under `results/gaussian_xauusd_econ/`  
3. Tests: holdout count, feature dim 39, model load of promoted version  
4. No config edits, no promote changes  

**PR-2 (E1):** economic arms + report  
**PR-3 (E2):** M4 wrapper  

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| Sweep set has no skill (likely given mean y_rr −1) | Pre-registered kill at E1; stop without entry fishing |
| Threshold fishing | Quantiles frozen on train; OOS read-only |
| Confusing registry promote with econ promote | Every report header: `REGISTRY_ACTIVE ≠ ECONOMIC_AUTHORITY` |
| Underpowered OOS 2m | Report INSUFFICIENT; optional longer OOS in E1b with pre-reg |
| Live path never uses NB | Document as intentional until E3 |

---

## 10. Decision for user

**Recommended next step:** Implement **Phase E0** only (scored units from journal + promoted model).  

Then run **E1** with pre-registered arms before any threshold tuning.

---

## 11. Closure of this design doc

This design **moves toward economics** without claiming economics.  
It preserves:

- Journal truth (why not economic today)  
- Authority Ladder  
- Existing M4 / shadow-eval machinery  
- Config-first and no premature live wire  

**Current state after design:** still **REGISTRY_ACTIVE / RESEARCH_ONLY**.  
**Next state after E0–E2:** either **ECONOMICALLY_REJECTED (closed)** or **M4_PROMOTE_CANDIDATE → E3 discussion**.
