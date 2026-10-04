# Plan — Continue Finding Dependency Audit (F-038 correction + Phase B Economic Truth Audit)

## Context

`docs/governance/finding_dependency_audit.md` completed **Phase A** (static reachability of all 12
R1 findings): 11 PASS, 1 FLAG. "Continue" means closing out Phase A's open item and executing the
audit's documented next stage, **Phase B — Economic Truth Audit** (B1/F-023, B2/F-019, B3/F-021).

While verifying Phase A's single actionable item I found it is **wrong**: the audit's F-038 FLAG
(line 94 / Phase-A summary) claims `v2_multi_2026_04.json:50` overrides `rr_fusion.enabled` to
`true` ("fix NOT deployed"). I read the active config directly:

- `configs/production/ACTIVE_VERSION` = `v2_multi_2026_04`
- Runtime resolves it via `production_config.py:116` → `f"{version}.json"` → `v2_multi_2026_04.json`
  (the `v2_multi_2026_04 - deepdeektry.json` sibling, name contains a space, is **never** loaded)
- `v2_multi_2026_04.json:34` → `"enabled": false` (rr_fusion). Line 50 is `"ultron_gate_enabled": false`.

So the F-038 fix **IS** deployed in the active config; the FLAG is a misread (DOC_DRIFT per §6.2
rule 2 — code wins, fix the doc). The deepdeektry sibling carrying `enabled: true` is a separate,
non-loaded artifact (latent TruthConflict, noted but out of scope here).

Goal of this change: (1) correct the audit doc so its only "actionable" item reflects reality, and
(2) run the three Phase-B economic replays to answer the audit's central question — *is Epoch-3
(post-stabilization) merely cleanup (E2 findings survive) or a new economic universe?* (F-019 is the
detector.)

---

## Part 1 — Correct the F-038 DOC_DRIFT (doc-only, this turn)

Edit `docs/governance/finding_dependency_audit.md` (per §6.2 rule 4: mark `CORRECTED`, never
silent-delete):

1. **F-038 row (≈line 91-94)** — change `⚠ FLAG` → `✅ PASS (CORRECTED 2026-06-27)`. Replace the
   "Fix NOT deployed" detail with: active config `v2_multi_2026_04.json:34` has
   `rr_fusion.enabled: false` (verified via `ACTIVE_VERSION` → `production_config.py:116` filename
   resolution). The earlier claim cited line 50 (`ultron_gate_enabled`) and/or the non-loaded
   `… - deepdeektry.json` sibling. Note the sibling divergence as a latent TruthConflict.
2. **Phase A Summary table (≈line 121)** + **R1 table (≈line 163)** — F-038 `⚠ FLAG` → `✅ PASS`.
3. **"One actionable finding from Phase A" (≈line 125-127)** — replace: Phase A is now **12/12 PASS**;
   the F-038 fix is already deployed; no config flip required. Optionally add a one-line follow-up to
   reconcile/retire the `… - deepdeektry.json` sibling.
4. **Audit Log (≈line 226)** — change `11/12 PASS; 1 FLAG (F-038)` → `12/12 PASS (F-038 FLAG
   corrected — fix already deployed)`.

No code/config change. F-038 in `current-findings.md` already states "FIX SHIPPED" — consistent, no
finding edit needed. Add a SESSION LOG entry (§6) recording the E-001 correction (mandatory phrase:
"Caught me overclaiming; I owe you a correction" — applied to the prior audit's misread).

---

## Part 2 — Phase B Economic Truth Audit (execution; scope per user answer)

All three are **read-only re-measurements** that write to *new* output paths (existing baselines are
never overwritten). Each carries a pre-registered success criterion (= finding survives) and failure
mode (= Epoch-3 is a new economic universe). Run `ORIENT_RUNTIME` first (confirm `ACTIVE_VERSION`).

### B2 / F-019 — Epoch-3 detector (headline; run first)
```
python scripts/research/qualify_majors.py --out results/research/qualification_2026_06_27
```
- Driver `scripts/research/qualify_majors.py`; M4 gate `src/research/qualification.py`; cost
  `src/research/costs.py` (12 bps). Data: `data/{BNB,ETH,BTC,SOL}USDT_M15.csv` (all present, 70,080
  rows). Deterministic body; ~10 min.
- **Success:** still 0 PROMOTE; toy arm byte-identical to frozen baseline
  `results/research/qualification/qualify_majors.json` (no toy code changed). **Failure:** any
  hypothesis clears M4 → E3 = new economic universe.
- Note: backtests run CRT-only (`BACKTEST_ENGINE_GATE=0`, F-037), so the F-038 rr_fusion change is
  expected **not** to move the spine arm — a useful cross-check. Compare new vs frozen `qualify_majors.json`.

### B1 / F-023 — re-cluster on governing intrabar_fixed labels (P0 mandatory)
```
python scripts/analysis/bnbusdt_trade_anatomy.py --instrument BNBUSDT \
  --opportunities logs/BNBUSDT/20260530_011521/opportunities.jsonl \
  --candles data/BNBUSDT_M15.csv --out-dir results/research/bnbusdt_trade_anatomy_2026_06_27
```
- Driver already labels via `forward_walk(exit_model="intrabar_fixed")`
  (`src/research/measurement/forward_walk.py`) — does **not** trust the F-022-unreliable
  `opportunities.jsonl` outcome/rr fields. KMeans k=4 on 9 standardized morphology features.
- Output ~122 MB CSV + `anatomy_summary.json` (`morphology_clusters`). **Success:** all 4 clusters
  WR ≈ 0.34±0.01, mean_R ≈ 0.000±0.023. **Failure:** any cluster WR >0.40 or <0.28 → new universe.

### B3 / F-021 — reject-reason decomposition (SESSION/ZONE/SCORE)
```
python scripts/research/phase_s_selection_effect.py \
  --config configs/research/research_config_phase_s.json --out results/research/phase_s_2026_06_27
```
- Driver `scripts/research/phase_s_selection_effect.py`; runs spine backtests inline +
  `forward_walk(intrabar_fixed)` + 12 bps; folds reasons via `src/research/selection_effect.py`.
- **Success:** SESSION dominates (≥95%), ZONE 0 rejects, SCORE <5 (F-021 holds:
  SELECTION_IS_SESSION_ONLY). **Failure:** SCORE/ZONE materially binding → selection skill may exist.

### Post-run governance (every replay)
- **If all survive:** record E3 = stabilized E2; mark Phase B rows DONE in the audit's Audit Log +
  the R2 table; in `current-findings.md` set `Validated: 2026-06-27` / refresh `Revalidate-by` for
  F-019/F-021/F-023 (Findings Mandate, §6.2). No reversal.
- **If any breaks:** run the E-001 6-question pre-registration ritual *before* registering; surface
  as a finding flip with `Reversal:` + evidence (file:line / artifact); this is a major epoch event —
  pause and report to user before propagating.
- SESSION LOG entry each turn (§6). No new findings invented; replays only confirm/flip existing F-ids.

---

## Verification

- **Part 1:** `pytest tests/test_doc_citations.py tests/test_current_findings.py` (citation +
  findings-index consistency). Visual diff of the audit doc.
- **Part 2:** byte-compare new `qualify_majors.json` toy arm vs frozen baseline (determinism gate);
  confirm each replay's success criterion; outputs land in dated dirs (baselines untouched).
- Spot-check `results/research/*_2026_06_27/` artifacts exist and parse.

## Out of scope (flag, don't fix here)
- Reconciling/retiring `configs/production/v2_multi_2026_04 - deepdeektry.json` (latent TruthConflict
  — divergent `rr_fusion.enabled`, not loaded). Worth a separate cleanup.
- Phase C / R3 ontology replays (F-040, Programs 4/5/6) — only on new ontology/market.
