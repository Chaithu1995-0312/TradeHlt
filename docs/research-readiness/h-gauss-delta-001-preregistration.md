# H-GAUSS-DELTA-001 — Calibration gap Δ = ML − H as primary research signal

> **PRE-REGISTERED before any *protocol-primary* outcome measurement on this study.**  
> Status: **OPEN · EXPLORATORY_RESEARCH · RESEARCH_ONLY**  
> Date: 2026-07-21 · Branch: `feature/truth-registry-v2`  
> Trigger: Gaussian family shadow pilot (BNBUSDT) showed binary agreement@0.5 is
> non-informative, H and ML nearly uncorrelated, and consensus subsets are empty;
> continuous |Δ| strata did not clear E>0. User direction: **do not build a coordinator**;
> treat **signed Δ = ML − H** as the primary research signal and test whether the
> **calibration gap** (not consensus) carries incremental predictive information under
> geometry stratification.

| Field | Value |
|-------|--------|
| Program alias | **H-GAUSS-DELTA-001** |
| Working title | GAUSSIAN_CALIBRATION_GAP_DELTA_ML_MINUS_H |
| Task class | `EXPLORATORY_RESEARCH` |
| Authority | **RESEARCH_ONLY** (§6.5) — never auto-promotes config / fusion |
| Production behavior change | **NO** |
| GaussianCoordinator / family consensus product | **FORBIDDEN** in this program |
| `gaussian_impl` flip to `ml` | **FORBIDDEN** without separate ΔG001 + promote |
| Post-hoc threshold mining on Δ | **FORBIDDEN** |
| Binary agree@0.5 as primary metric | **FORBIDDEN** (known saturated on BNB pilot) |

Machine twin: [`h-gauss-delta-001-experiment-definition.json`](h-gauss-delta-001-experiment-definition.json)

Related (do not conflate):
- **Gaussian lineage AUDITED** — dual-track H live / ML inert on active config
- **Shadow pilot** `results/zone_maps/bnbusdt_gaussian_family_shadow.*` — exploratory only
- **F-019…F-025** — entry-information null prior; expect null economic unless Δ is special
- **F-022 / F-045** — label integrity; use `forward_walk`, not opportunity stream
- Market Geometry contexts from zone-mapping Phase-1 (rare / boundary / DISPLACEMENT)

---

## 0. Epistemic status of the BNBUSDT pilot (contamination boundary)

The BNBUSDT full-corpus shadow run (2026-07-21) is **EXPLORATORY_PILOT** only:

| Claim from pilot | Status for *this* prereg |
|---|---|
| Binary agree@0.5 rate = 1.0; thr non-informative | **Motivates protocol** (forbids binary primary) |
| Pearson(H, ML) ≈ −0.04 | **Motivates** treating H and ML as independent |
| mean Δ ≈ −0.27 (ML systematically below H) | **Motivates** signed Δ as object of study |
| \|Δ\| terciles / binary subsets E_net < 0 | **Does not** count as a primary null for H-GAUSS-DELTA-001 |
| H top-tercile least-bad on pilot candidates | **Diagnostic only** — not a frozen claim |

**Primary evidence** for H-GAUSS-DELTA-001 is produced **only** by runs that implement
§§3–8 of this document after the freeze timestamp. The pilot may be cited as motivation
and for instrument debugging (schema registration fix), never as the study’s economic verdict.

If BNBUSDT is re-used as a primary instrument, the **time-ordered OOS half** is the only
BNB-facing primary evidence; the full-sample pilot numbers stay non-primary.

---

## 1. Why this study exists

The repository has two Gaussian engines under one fusion *slot*:

| Engine | Role (intent) | Live on active config |
|---|---|---|
| **Gaussian-H** | Expert momentum kernel on 3 features | YES (`gaussian_impl=heuristic`) |
| **Gaussian-ML** | Trained NB → sigmoid(E[RR]) on full vector | NO (switchable; shadow via `shadow_ml`) |

They are **not** two implementations of one model. They answer different questions and, on
the pilot, produce **always-high scores** that make consensus trivial and empty.

The scientifically interesting residual is not “do they agree?” but:

> **When ML and H disagree in level, does the signed gap Δ = ML − H encode information
> about forward outcomes that neither score alone captures — and does that concentrate
> in specific Market Geometry contexts?**

That is a **calibration-gap / residual-information** question, not a coordinator design
question. A coordinator that averages or votes is **premature** until this is answered.

---

## 2. Hypotheses (frozen)

### Primary

**H1 (gap informative):** Within at least one pre-registered geometry stratum (§4), signed
Δ carries **incremental** predictive association with honest forward net-R beyond:

1. score_H alone, and  
2. score_ML alone,

after pre-registered multiple-testing control and the OOS rule (§6).

**H0 (gap null):** After MTC and OOS, no stratum shows incremental association of Δ with
net-R beyond H-alone and ML-alone (or all strata INSUFFICIENT).

### Secondary (descriptive only — never sole basis for promotion language)

**H2 (geometry modulates gap):** Distribution of Δ (mean, spread) differs across strata
(RARE / BOUNDARY / DISPLACEMENT vs complementary bars) in a pre-registered descriptive
sense. H2 is **not** an economic claim.

**H3 (signed > absolute):** Signed Δ outperforms \|Δ\| on the primary incremental test in
any stratum that passes H1. Reported only if H1 fires; never fished alone.

### Explicitly not hypothesized

- Consensus / agreement improves expectancy  
- Averaging H and ML improves expectancy  
- Enabling `gaussian_impl=ml` improves the spine  
- Building a GaussianCoordinator improves fusion  

---

## 3. Primary research signal (frozen)

```text
score_H  = HeuristicGaussianEngine.compute(...).score     ∈ (0, 1]
score_ML = MLGaussianEngine.compute(...).score            ∈ [0, 1]
Δ        = score_ML − score_H                             ∈ [-1, 1]
```

**Contract:** same dual-engine path as `EngineRunner` `gaussian_impl=shadow_ml`
(H primary + ML shadow). Schema registration under **version id** is required so ML is
not the 0.5 fail-closed constant (bug fixed 2026-07-21 in `MLGaussianEngine`).

**Forbidden transforms for primary tests:**

- Binary agree@0.5  
- max/min/mean of (H, ML) as the *primary* treatment  
- Post-hoc quantiles other than the frozen terciles below  
- Instrument-specific re-thresholding after seeing outcomes  

**Allowed primary encodings of Δ (closed set):**

| Id | Encoding | Use |
|---|---|---|
| D-CONT | continuous Δ | Spearman with net_R |
| D-TERC | terciles of Δ within stratum & split | top vs bottom E[net_R] |
| D-RES-H | residual of Δ after linear projection on score_H | Spearman with net_R |
| D-RES-ML | residual of Δ after linear projection on score_ML | Spearman with net_R |

D-RES-* operationalize “incremental.” Implementation: ordinary least squares residual on
the **IS** half only; apply coefficients to OOS (no OOS fit).

---

## 4. Geometry strata (frozen closed set)

Strata are **bar filters** applied after dual scoring. Definitions must match the zone-
mapping research stack:

| Stratum id | Definition | Primary? |
|---|---|---|
| **S-ALL** | All post-warmup bars with direction≠0 and atr_price>0 | Diagnostic only |
| **S-RARE_ZONE** | `zone_id ∈ RARE_ZONES` (`zone_1,4,5,6`) | **YES** |
| **S-RARE_ENTRY** | rare-zone *entry* (transition into rare; same as `find_zone_entries`) | **YES** |
| **S-BOUNDARY** | lowest quintile of `margin_best_second` (global edges fit on IS only, applied OOS) | **YES** |
| **S-DISPLACEMENT** | CRT state == `DISPLACEMENT` | **YES** |
| **S-RARE_ENTRY ∩ DISPLACEMENT** | intersection | Diagnostic (secondary) |
| **S-BOUNDARY ∩ DISPLACEMENT** | intersection | Diagnostic (secondary) |

**Complement diagnostics** (report occupancy only, not primary BH):  
non-rare, non-boundary, non-DISPLACEMENT mass.

**Frozen geometry knobs** (no retune):

- Zone registry / cluster knobs: active production `engine_runner` via `ZoneMapConfig.from_prod_engine_runner()`
- `RARE_ZONES = (zone_1, zone_4, zone_5, zone_6)`  
- Boundary: **Q1 of margin** among bars in the scoring population (IS edges → OOS labels)

Adding a new stratum after seeing results requires a **new** prereg, not an edit.

---

## 5. Population & measurement (frozen)

| Item | Value |
|------|--------|
| Primary universe | **CRYPTO_MAJORS M15:** BNBUSDT, BTCUSDT, ETHUSDT, SOLUSDT |
| CSV convention | `data/{INSTR}_M15.csv` (instrument must have active ML Gaussian registry entry; else **SKIP instrument** with reason, do not silent-0.5) |
| Timeframe | M15 |
| Dual scores | H + ML as §3; `GAUSSIAN_INSTRUMENT` / config instrument set |
| Direction | CRT direction if ±1 else EMA polarity (`ema_fast` vs `ema_slow`) else momentum sign |
| ATR price | `atr_feature * close` (canonical relative ATR) |
| Outcome | `forward_walk(exit_model="intrabar_fixed")` net of **12 bps** CostModel |
| Geometry exit | **SL=1.0 R, TP=2.0 R**, `max_forward=40` bars |
| OOS | **time-ordered 70/30** by bar timestamp (IS first 70%, OOS last 30%) — no shuffle |
| Min N (stratum × instrument, OOS) | **n ≥ 100** else **INSUFFICIENT** (no claim) |
| Min N pooled OOS (optional pool) | **n ≥ 200** for pooled row |
| Permutations | **n_perm = 1000**, seed **42**, shuffle Δ (or residual) within stratum on IS for null of Spearman; OOS uses IS-fit residual coeffs only |
| Multiple testing | Benjamini–Hochberg **q=0.10** over the **primary BH family** (§6) |

**ML readiness gate (per instrument):** after load, if `ml_fallback_rate > 0.01` on a 500-bar
smoke OR model version unregistered for schema hash → instrument **SKIP** (do not invent scores).

**XAUUSD:** diagnostic-only if ML model exists; **not** in primary BH cohort (geometry work
lived here; ML coverage is not guaranteed).

---

## 6. Primary tests & BH family (frozen)

### 6.1 Primary BH family (counts for H1)

For each **primary stratum** × each **primary instrument** (and optionally one **pooled
majors** row if all four instruments complete):

| Test id | Statistic | Null |
|---|---|---|
| T-SP-D | Spearman(Δ, net_R) on **OOS** | = 0 (perm on IS null calibration; report OOS point + IS perm p as sensitivity) |
| T-SP-RES-H | Spearman(D-RES-H, net_R) on **OOS** | = 0 |
| T-SP-RES-ML | Spearman(D-RES-ML, net_R) on **OOS** | = 0 |
| T-TERC-D | OOS E[net_R \| top Δ tercile] − E[net_R \| bot Δ tercile] | ≤ 0 |

**Primary claim rule for a stratum×instrument cell:**

1. Cell not INSUFFICIENT  
2. At least one of T-SP-RES-H or T-SP-RES-ML significant under BH (incremental)  
3. **AND** T-TERC-D > 0 on OOS (directionally useful ranking)  

**Consumable / authority language** (still research-only; still no fusion wire):

4. Additionally OOS E[net_R \| top Δ tercile] > 0  
5. And that top-Δ E beats both H-top-tercile and ML-top-tercile OOS E in the **same** cell  

Failing (4)–(5) but passing (1)–(3) → **INFORMATIVE_NOT_CONSUMABLE**.  
Failing (1)–(3) for all primary cells → **H0 upheld**, program **CLOSED null**.

### 6.2 Nested baselines (required in every cell)

Report OOS Spearman and tercile lift for:

- score_H alone  
- score_ML alone  
- \|Δ\| alone (secondary; not in BH)

Δ “wins incremental” only via residual tests, not by raw Spearman alone if collinear with H or ML.

### 6.3 Secondary tables (not in BH)

- Mean / p10 / p90 of Δ by stratum  
- H2 geometry modulation (KS or mean-diff Δ across strata) — descriptive  
- Full-sample (IS+OOS) diagnostics — never primary  

---

## 7. Stop / close / reopen rules

| Outcome | Action |
|---|---|
| All primary cells INSUFFICIENT | CLOSE — no claim; expand data only via new prereg |
| H0 upheld (no BH residual pass) | CLOSE null — **do not** build coordinator; do not flip `gaussian_impl` |
| INFORMATIVE_NOT_CONSUMABLE only | Document; **no** fusion authority; optional follow-up prereg for consumer design |
| Consumable (4)–(5) in ≥1 cell | Research authority to **propose** a consumer hypothesis (new prereg); still no auto-wire |
| Protocol violation (post-hoc thr, new stratum, coordinator built) | Run **INVALID** |

**Reopen** only if (a) ML artifact / feature schema / zone registry / CRT topology inside
the declared boundary changes, or (b) a mechanical invariant fails, or (c) new contradictory
evidence invalidates the null — default closed policy after H0.

---

## 8. Forbidden without a new preregistration

- GaussianCoordinator / family consensus product in fusion  
- Averaging H&ML into the live gaussian slot  
- Enabling `gaussian_impl=ml` on production  
- Retraining ML “to fix Δ” inside this program  
- Mining Δ thresholds, alternative R multiples, or new strata after seeing OOS  
- Using opportunity-stream / F-022 labels as outcomes  
- Claiming ΔG001 or promotion from this study alone  

---

## 9. E-001 six-question pre-registration ritual

1. **What artifact supports claims?** Dual engines + zone mapper + CRT joint labels +
   `forward_walk` / CostModel; code under `src/research/zone_mapping/gaussian_delta_gap_eval.py`
   (measure-only).  
2. **Could INSUFFICIENT explain nulls?** Yes — min n=100 OOS per cell; underpowered cells
   cannot claim H0 or H1.  
3. **Sign noise → meaning?** Residual tests + BH; pilot not primary.  
4. **Statistical vs economic?** Spearman/residual = Level-1 information; E>0 top tercile =
   Level-2 consumable **candidate only**, not authority.  
5. **Parent stronger than children?** H1 requires residual (incremental) not raw Δ alone.  
6. **Phrase after raw counts?** If residual p is weak but top tercile looks good, do **not**
   upgrade — INFORMATIVE_NOT_CONSUMABLE or null.

Mandatory phrase if overclaim detected during execution:  
> “Caught me overclaiming; I owe you a correction.”

---

## 10. Deliverables (when run)

| Artifact | Path pattern |
|---|---|
| Machine results | `results/zone_maps/{instr}_h_gauss_delta_001.json` |
| Human summary | `results/zone_maps/{instr}_h_gauss_delta_001.md` |
| Pooled rollup | `results/zone_maps/pooled_h_gauss_delta_001.{json,md}` |
| Run findings (after gate) | `docs/research-readiness/h-gauss-delta-001-run-findings.md` |

Implementation entry points (measure-only):

- `src/research/zone_mapping/gaussian_delta_gap_eval.py`  
- `scripts/research/build_gaussian_delta_gap_eval.py`  

Reuses dual-score collection from the shadow family harness; **does not** implement a coordinator.

---

## 11. One-sentence freeze

**We will test whether the signed calibration gap Δ = ML − H contains incremental
forward-outcome information inside pre-registered geometry strata (rare / boundary /
DISPLACEMENT), using honest OOS forward-walk economics and residual controls — and we
will not build a Gaussian coordinator, flip ML live, or promote fusion on this evidence alone.**
