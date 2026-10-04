# Findings-Revalidation Gate — Epoch E4 (Preregistration)

> **Status:** `DESIGN` · **FROZEN 2026-07-16 (owner-accepted)** — `protocol_hash` recorded in the JSON twin (sha256 of this file at freeze). RVG-1…5 still require explicit grants.
> **Task class:** `EXPLORATORY_RESEARCH_DESIGN_ONLY`
> **Machine twin:** [`findings-revalidation-gate-e4-preregistration.json`](findings-revalidation-gate-e4-preregistration.json)
> **Branch scope:** `feature/truth-registry-v2` · `ACTIVE_VERSION = v2_multi_2026_04`
> **Authority:** research/governance only. Grants **no** production, promotion, or capital authority (CLAUDE.md §6.5).
> **Program:** `EDGE_RESEARCH_PLATFORM` — this is **WS-OUTCOME-FACTORY's first deliverable (P2.0)**.
> **Companions:** [phased plan P0–P7](edge-research-platform-phased-plan.md) · [decision board](erp-decision-board-and-story-authority.md) · [program](edge-research-platform-program.md)
>
> **No code / no run without an explicit owner grant** (RVG-0…RVG-5, §7). Writing this document
> runs nothing and flips no finding.

---

## 1. Motivation — the untested epoch

The Edge Research Platform's priority stack, its "do not fund first" list (D-16), and its
"known nulls / do not reopen" list (ERP program §12.4) all rest on the economic findings
**F-019…F-035** (plus the closed programs F-030/32/33/34/42/43). Those verdicts were produced on a
State + Feature layer that has since been bug-fixed:

| Fix | Finding | Effect on the feature substrate |
|---|---|---|
| Centered-swing → causal (FC1-A/FC1-D) | **F-051** | Removed a **non-PIT lookahead** that contaminated **10/38 canonical dims** (~63% of bars differed). RR/Zone artifacts tagged `PIT_UNCLEAN_CENTERED_SWINGS`. |
| Feature-DAG re-certification | **F-054** | ATR/RSI/EMA promoted to first-class (FM-040..046); **legacy FM-022/023 SUPERSEDED**; FM-030/031 promoted as intended identity; **explicit STALE cascade over rr_model / gaussian / dual_engine / backtests / evidence records**. |
| candle_math / ontology / emission | **F-046/047/050** | `body_ratio`/`wick_size` unified; CRT emission → FM-027/FM-028. |

**The key nuance (this is what makes the gate targeted, not a full re-run):** the findings were
*last* revalidated at **Epoch E3** (2026-06-27, `finding_dependency_audit` Phase B — F-019/021/023
re-ran and **survived byte-identically**). **But E3 was BEFORE F-051 and F-054.** No epoch has yet
been run on the fixed feature layer. Call it:

```
E4 = post-F-051 (causal swings) + post-F-054 (re-certified feature DAG)
```

The gate's job: establish the trust status of each priority-stack-gating finding **at E4**, so the
ideology can stop tagging D-16 / §12.4 / §11 `PROVISIONAL`.

**Prior-art constraint that bounds cost:** F-029 + F-051 already establish that the centered-swing
leak left **CRT trade *generation* byte-identical** ("F-029 gate-OFF trade-generation refined not
reversed"). So findings whose entries are pure CRT-state-machine (F-037 gate-OFF spine) are
*expected* robust and need only a cheap byte-identity confirm — the expensive re-derive is reserved
for findings that **consume the contaminated/re-certified dims directly**.

---

## 2. Scope — findings in the gate, classified by feature dependency

The classification is the design's core. Each finding's **measurement path** is inspected for
whether it consumes any of the 10/38 F-051-contaminated dims or any F-054-superseded ID.

| Class | What it consumes | Expected E4 outcome | Method | Findings (driver) |
|---|---|---|---|---|
| **A — CRT-state entries only** | Spine entries from `crt_engine_v2` state machine; no direct feature-vector consumption for entry | **ROBUST** (F-029/F-051 byte-identical generation) | **Cheap confirm**: re-run driver on E4, assert entry set + sha256 byte-identical to E3 baseline | F-019 spine arm (`qualify_majors.py`), F-021 (`phase_s_selection_effect.py`), F-037 (architectural — no economic re-run) |
| **B — toy directional arms** *(RVG-U2: feature-pipeline-INDEPENDENT — reclassified)* | The isolated `src/research/` stack ONLY (`research.indicators.atr/sma`, `research.measurement.bar_features`, raw OHLC, `bar.body_ratio` F-046-benign). **Never imports `src/features/`** where F-051/F-054 live. | **EXPECTED BYTE-IDENTICAL** (the fixed feature layer cannot reach these detectors) | **`src/research/` drift check** (git-diff E3-commit→HEAD) + determinism re-confirm vs E3 baseline + `*_run2` twins — **NOT** a feature re-derive | F-019 toy arm, F-020 (`phase_b_conditional_entropy.py`), F-025 (`phase_d_exit_grid.py`), F-027 (`qualify_htf.py`), F-028 (`qualify_interpreter.py`), F-035 (`qualify_fx_metals.py`) |
| **C — feature-consuming models** | The 10/38 contaminated dims **directly** (morphology clusters, zone membership, RR/gaussian inputs) | **GENUINELY SUSPECT** — must re-derive from scratch on E4 | **Full re-derive**: rebuild feature inputs from certified IDs, re-fit/re-score, re-run outcome via `forward_walk` | F-023 morphology (`feature_region_oos_study.py` / clustering), F-036 + F-041B zone (`diagnose_zone_inertness.py`, `discover_zones.py`), F-045 RR-model shadow (`rr_shadow_value.py`), gaussian lineage |
| **D — closed programs** | Regime / cross-sectional / carry / weekly | **DEFERRED** — re-derive only if a Class-C dependency of theirs flips | Confirm feature-dependency; re-run only on trigger | F-030/32/33/34/42/43 |

**Out of scope:** anything not gating the priority stack (metrics-oracle parity, determinism gates,
config-reachability — those are machinery, unaffected by feature-value changes).

---

## 3. Method

### 3.1 Epoch pinning (the frozen input contract)

Before any run, freeze the E4 feature authority so results are attributable:

- **Feature source:** post-F-054 certified IDs only — pull the canonical set from
  `configs/formulas/market_ontology.yaml` + `src/features/feature_certification_state.py`
  (`PROMOTED_PRODUCTION` frontier: ATR/RSI/EMA FM-040..046, FM-030/031, FM-027/028; legacy FM-022/023
  **excluded**).
- **Swing definition:** causal delayed swings (FC1-A/FC1-D), **not** centered.
- **Exit truth:** `forward_walk(exit_model="intrabar_fixed")` — the governing exit
  (`src/research/measurement/forward_walk.py:27`), SL-before-TP tie-break. No `close_only`.
- **Cost prior:** 12 bps round-trip (unchanged from the baselines, for comparability; ERP A-008).
- **Lens:** name it per run — research default is CRT-only gate-OFF (`BACKTEST_ENGINE_GATE=0`, F-037).

Record all of the above in a `PROTOCOL_HASH.txt` + `epoch_manifest.json` so E4 is reproducible.

### 3.2 Re-derive procedure (per finding)

```
for each finding F in scope:
  1. Load E3 baseline artifact (results/research/.../<F>.json) — the frozen comparison evidence.
  2. Re-run F's existing driver UNCHANGED, pointed at the E4 feature layer.
       (drivers already exist — §2 table; do NOT rewrite the science, only re-point the inputs.)
  3. Emit E4 artifact + run_manifest (command, cwd, flags, ACTIVE_VERSION, feature epoch, sha256).
  4. Compare E4 vs E3:
       - Class A: assert byte-identical entry set (sha256).  Any diff => escalate to re-derive.
       - Class B/C: compare verdict token + effect size + power.
  5. Assign E4 trust token (§4).
```

**Do not change any pre-registered protocol** (gates, costs, permutations, family lists). The gate
re-runs the *same experiment on new inputs* — it is not a new experiment. This preserves the
falsification discipline (Program 1 lesson: reopen via new ontology, not a parameter pass).

### 3.3 Determinism discipline (reuse the E3 pattern)

Every E4 artifact must reproduce byte-identically across two independent runs (the E3 audit proved
`qualify_majors` and `regime_conditioning` byte-identical via sha256 — reuse that exact gate). A
non-deterministic body is a `PROTOCOL_FAILURE`, not a result.

---

## 4. Verdict taxonomy (per finding, at E4)

| Token | Meaning | Consequence for the ideology |
|---|---|---|
| `SURVIVES_E4` | Same verdict + effect within tolerance on E4 features | Un-tag the finding `PROVISIONAL`; D-16/§12.4 anchor restored |
| `SURVIVES_E4_BYTE_IDENTICAL` | Class A: entry set unchanged | Strongest — leak provably didn't touch it |
| `OVERTURNED_E4` | Verdict flips (e.g. a null becomes non-null, or vice versa) | **Reversal** — file a finding flip (§6.2 Findings Mandate); may reorder the priority stack |
| `UNDERPOWERED_E4` | N or power insufficient at E4 to conclude | No claim; note the throughput starvation (F-019/F-022 class) |
| `SCOPE_CHANGED_E4` | Survives but the honest scope narrows/widens | Amend the finding's scope note, keep the row |
| `PROTOCOL_FAILURE` | Non-deterministic / leakage / wrong lens | Fix the harness before trusting anything |

**Nothing here grants production authority** — a `SURVIVES_E4` finding is still research-record,
not capital authority (§6.5 Authority Ladder).

---

## 5. Outputs (artifact schema — when RUN granted)

```
results/research/findings_revalidation_e4/
  RUN_AUTHORIZATION.json          # owner grant stamp
  PROTOCOL_HASH.txt               # frozen E4 protocol
  epoch_manifest.json             # certified feature IDs, swing def, exit/cost, lens
  per_finding/<F-0NN>.json        # E4 artifact + run_manifest + E3-vs-E4 compare
  trust_ledger.json               # F-id -> E4 token (§4)
  REVALIDATION_FINDINGS.md        # narrative + any finding flips
  DECISION_LEDGER_ENTRY.json      # ERP four-kinds: DECISION (retire/repair/replicate)
```

Plus the doc-side synchronization (§6.2 Findings Mandate): each finding row gets an E4 line
(`Revalidated: 2026-…-E4 <token>`), never deleted; the ERP program §11/§12.4/D-16 lose their
`PROVISIONAL` tags for `SURVIVES_E4` items.

---

## 6. Success / exit criteria

The gate is **complete** when:

1. Every Class-A and Class-B finding has an E4 token (Class A byte-identity confirmed or escalated).
2. Every Class-C finding is either re-derived to an E4 token or explicitly deferred with a written
   reason (owner-acknowledged).
3. `trust_ledger.json` exists and is deterministic (two-run sha256 match).
4. Any `OVERTURNED_E4` has a filed finding flip + priority-stack impact note.
5. The ERP program doc's provisional tags are resolved (removed for survivors, kept+annotated for
   overturned/deferred).

**This unblocks:** ERP P3 (demotion — now on trusted feature inputs) and P4 (new-info search — now
knowing "OHLCV direction exhausted" is a *current* claim, not a 2026-06 claim).

---

## 7. Work items (DESIGN → grants)

| ID | Item | Phase | Needs grant |
|---|---|---|---|
| RVG-0 | Materialize this package as a repo prereg (+ json twin); owner freezes protocol | DESIGN → freeze | Owner "freeze RVG" |
| RVG-1 | Build the thin **epoch-pinning harness** (`scripts/research/revalidate_findings_e4.py`): loads certified feature set, re-points a driver at E4, emits run_manifest + compare | IMPLEMENTATION | "Implement RVG-1" |
| RVG-2 | Run **Class A** (cheap byte-identity confirm) — highest signal/cost | RUN | "Run RVG Class A" |
| RVG-3 | Run **Class B** (toy re-derive through unchanged M4) | RUN | "Run RVG Class B" |
| RVG-4 | Run **Class C** (feature-consuming re-derive) — the genuinely suspect set | RUN | "Run RVG Class C" |
| RVG-5 | Synchronize findings docs + ERP provisional tags; DECISION ledger entry | REVIEW | part of each run's close |

> **Doc-status note:** RVG-0 COMPLETE — (a) document placed in repo and (b) **FROZEN 2026-07-16 on
> owner acceptance** (`protocol_hash` in the JSON twin). The frozen items in §18 can no longer be
> amended. Freeze establishes the comparison contract only — it grants **no** run authority; E4
> tokens become evidence only after RVG-2…4 runs under §2/§14 review.

**Sequencing rationale (§6.5 evidence-quality-over-quantity):** Class A first (cheapest, likely
confirms the spine is untouched), Class C is where the real risk lives (RR/zone/morphology consume
the contaminated dims) — but it's also the most work, so it's gated last and explicitly.

---

## 8. Open questions / unknowns

| ID | Unknown | Resolution |
|---|---|---|
| RVG-U1 | Are the E3 baseline artifacts still on disk for byte-compare? | **RESOLVED 2026-07-16** — present: `results/research/qualification_2026_06_27/qualify_majors.json` (+manifest, `qualification_run2/` twin), `phase_s_2026_06_27/`, `phase_b/` (+`_run2`), `phase_d/` (+`_run2`), `qualification_htf/qualify_htf_{H1,H4}.json`, `qualification_fx_metals/`, `bnbusdt_trade_anatomy_2026_06_27/`. No E3 re-run needed. |
| RVG-U2 | Do the Class-B toy drivers read swing/structure dims, or only ATR/EMA/breakout? | **RESOLVED 2026-07-16 — feature-pipeline-INDEPENDENT.** `expansion_breakout`/`mean_reversion` `detect()` ignore the `features` dict; compute from raw OHLC via `research.indicators.atr/sma` + `bar.body_ratio` (F-046-benign). `phase_b` uses `research.measurement.bar_features`; `phase_d` uses `research.indicators`. The whole `src/research/` stack never imports `src/features/` (where F-051/F-054 live); `src/research/indicators.py` has no recent git history. → Class B reclassified (see §2): drift-check + determinism, not feature re-derive. |
| RVG-U3 | Did F-041B's honest re-derive already use certified (post-F-051) features, or pre-fix? | OPEN — check `zonegate_lineage_audit.md` provenance; if pre-fix, F-041B is a Class-C item |
| RVG-U4 | Who signs the E4 trust tokens / any finding flip? | OPEN — Owner co-sign per ERP AMB-02/AMB-12 (executor drafts, never sole-signs) |

---

## 9. Authority & stop boundary

```
TASK_CLASS = EXPLORATORY_RESEARCH_DESIGN_ONLY (until RUN grant)
AUTHORITY = RESEARCH_ONLY even after SURVIVES_E4 / OVERTURNED_E4
PRODUCTION_AUTHORITY = NO
CAPITAL = NO
Freeze stop: protocol FROZEN 2026-07-16 (owner-accepted) → RVG-1 harness + RVG-2…4 runs require explicit grants.
```

## 10. Verification (read-only)

- Re-derive machinery exists: `src/research/measurement/forward_walk.py:27` (`intrabar_fixed`),
  drivers under `scripts/research/` (`qualify_majors.py`, `phase_d_exit_grid.py`,
  `phase_s_selection_effect.py`, `qualify_htf.py`, `qualify_interpreter.py`, `qualify_fx_metals.py`,
  `diagnose_zone_inertness.py`).
- E3 precedent: `docs/current-findings.md` F-019 "Update: 2026-06-27 (E3 revalidation …)".
- Certified feature surface: `configs/formulas/market_ontology.yaml` (FM-040..046, FM-030/031,
  FM-027/028), `src/features/feature_certification_state.py`, F-054 in the CLAUDE.md Truths Index.
- Contamination scope: F-051 (10/38 dims) + F-054 (STALE cascade) in `docs/current-findings.md`.

---

*Design only. No experiment is run and no finding is flipped by this document. Implementation and
each RUN require explicit owner grants (RVG-0…RVG-5).*
