# Close-M15 Semantic Equivalence Gate (vs TradingView), before any HTF predictive/qualification role

## Context

`reports/monthly_tv_vs_active_production_semantic_comparison.md` row 1 records **MATCH (1,430/1,455 = 98.3%)** for candle/OHLC identity. That verdict is an **L1 sum over all four O/H/L/C fields against a single scalar `MATCH_TOLERANCE = 3.0`** (`tools/tv_forensic/engine_data.py:24, :317-322`). It therefore says nothing directly about the one field every CRT and HTF semantic decision actually reads: the **close**.

The exposure is structural, not hypothetical:

- `src/features/parent_candle.py:56` — the H4 parent's `close = children[-1].close`. **The H4 close IS an M15 close.** Any M15 close divergence propagates into the parent undamped.
- Every HTF decision is a strict close inequality:
  - `src/config_layer/parent_crt.py:154-155` — sweep: `close < h_ref` / `close > l_ref`
  - `src/config_layer/parent_crt.py:169-171` — F-074 impulse: `close > open AND close > sweep.price` (and the SHORT mirror)
  - `src/config_layer/htf_state.py:97-100` — classify: `curr.close > prev.high`, `curr.close < prev.low`, `prev.close > prev.open`
  - `src/config_layer/htf_state.py:126-137` — objective: `last_close >= target` / `< invalidate_at`
  - `src/config_layer/crt_engine_v2.py:3020-3021` — parent-bias veto: `candle.close` vs `_htf_mid`
- The M15 engine's own funnel is close-gated at the same points (`crt_engine_v2.py:892-893, 1141, 1167, 1196, 1222, 1491, 1512`).

So the aggregate MATCH is not the evidence needed. Before HTF is assigned any predictive or qualification role, the close field must be isolated and its measured divergence propagated through the decisions that read it.

**Read-only reconnaissance already run (this is the starting point, not the deliverable):**

| Measurement (from existing sidecars, n=1,260 M15 compared bars) | Value |
|---|---|
| M15 bars with non-zero close delta | **98.17%** (1,237/1,260) |
| Close delta: mean / median | **+0.0499 / +0.0450** (TV above engine) |
| Close abs delta: p50 / p95 / p99 / max | 0.07 / **0.22** / 0.32 / **0.99** |
| Same-bias check across fields (mean Δ) | O +0.0437, H +0.0498, L +0.0497, C +0.0499 → **feed-level quote offset, not close-specific** |
| Close dispersion vs other fields (max abs) | C **0.99** vs O 8.38 / H 9.73 / L 6.37 → **close is the best-behaved field** |
| Bar-boundary equivalence (own-slot TV close strictly closest) | **96.39%** (1,201/1,246); all 45 exceptions have own-slot \|ΔC\| ≤ 0.34 (noise scale, not a 15-min misalignment) |
| **M15-resolution coverage** | **15 of 23 corpus trading days**, 1,260/2,116 bars (59.5%). Blind: Jul 16, 17, 21, 22, 23, 24, 27, 31 |
| Bars where TV close falls outside engine `[low, high]` | **20/1,260 (1.59%)** — matters for the substitution policy below |

Two things follow. (1) The close is *systematically offset and never exact*, so "MATCH" must not be read as "equivalent." (2) The report's "**23 of 23** trading days with TradingView capture" is true for *any* capture but is **15 of 23 at M15 resolution** — a distinction row 1's M15 claims do not currently carry.

**Intended outcome:** a pre-registered, verdict-bearing artifact that either licenses or blocks HTF on the close-equivalence axis, with the criterion fixed before any measurement runs.

## Decisions already taken (user, this session)

1. **Coverage** — use the existing 15/23 M15 days and declare the gap. No new TradingView capture; no network/Playwright.
2. **Gate form** — pre-registered gate + verdict artifact. No new Closure & Authority Index row.
3. **Pass bar** — PASS iff close-only substitution flips **no** parent-CRT state/bias/objective and **no** M15 funnel transition on **non-daily-open** bars. F-080's daily-open bars are reported separately as a *bar-definition* divergence, not a close divergence. Knife-edge count is reported but not blocking.

## Scope guards (non-negotiable)

- Descriptive only. No `configs/production/` write, no `ACTIVE_VERSION` change (stays `v2_htfcrt_2026_08`), no promotion, no model retrain, no `objective_gate` flip, no CRT re-closure. Grants no authority (§6.5) — a PASS clears **one precondition**, it does not confer predictive value on HTF.
- No `src/` edit. All engine/parent-CRT decisions are exercised through their real code paths; the census records **distances to boundaries the feed already exposes**, never a second copy of a predicate (§3.3b: no local formula math, no duplicate geometry).
- Tolerances are **inherited**, not invented: `engine_data.MATCH_TOLERANCE`/`DECISIVE_RATIO` and the measured close envelope (p95 = 0.22, max = 0.99) are the perturbation budgets. Not widened after seeing results.

## Work

### Step 0 — Pre-registration (must land before any arm runs)

Write `docs/governance/build_manifests/CH-close-m15-equivalence-gate.impact.json`, following the `CH-monthly-tv-coverage-h4-recon.impact.json` precedent (same directory, same shape). It declares:

- every path the change touches (two new scripts, one report + machine twin, SITS registry artifacts);
- the change class per `docs/governance/change_contracts.json`;
- **the gate criterion verbatim** (decision 3 above), plus the three verdict tokens the report may emit: `CLOSE_EQUIVALENT_FOR_HTF` · `CLOSE_EQUIVALENT_EXCEPT_DAILY_OPEN` · `CLOSE_NOT_EQUIVALENT`;
- **the substitution policy, fixed up front**: when the TV close falls outside the engine bar's `[low, high]` (measured: 20/1,260 = 1.59%), expand that bar's high/low minimally to admit it (primary cell) — and report the clamp-to-range variant as a robustness cell. Both are declared now so neither can be selected after seeing which one is cleaner;
- **the new-finding precondition**: register an F-id only if a decision flip is found on non-daily-open bars, or if the daily-open flip count materially extends F-080. A clean result registers nothing.

### Step 1 — Arm A: close-field isolation (`scripts/research/close_m15_equivalence.py`, part 1)

Read-only over `tools/tv_forensic/shots/*.json` (excluding `*_ANNOTATED` and `*_PRE_*`, exactly as `htf_parent_telemetry_extract.py:130-133` already filters). Emit, per shot and pooled:

- per-field Δ decomposition (mean/median/mean-abs/p95/max) so the shared +0.05 bias is separated from close-specific dispersion;
- the close abs-Δ distribution and the exceedance table at 0.05/0.1/0.25/0.5/1.0;
- the **bar-boundary test**: engine close vs TV close at t, t−15m, t+15m; report own-slot-closest rate and, for every exception, the own-slot error magnitude (the discriminator between noise and misalignment);
- **honest coverage**: M15-covered days (15) vs corpus days (23), named blind days, bars covered vs corpus bars.

### Step 2 — Arm B: knife-edge margin census, month-complete (`scripts/research/close_margin_census.py`)

Needs no TradingView bars, so it covers all 2,116 bars — this is the arm that is *not* coverage-limited.

- **M15 side**: replay `CRTEngine` with guard hooks exactly as `scripts/analysis/crt_predicate_failure_census_6m.py:88-92` does (`CRTBaselineTraceHooks()`, `hooks.enabled = True`, `engine.baseline_trace = hooks`). Guard records carry `operands[].runtime_value` for both PASS and FAIL results, so every close-driven guard's margin is harvestable without touching `src/`. Filter to guards whose operands include `feature_id == "close"`.
- **HTF side**: drive `ParentCRTFeed.from_prod_config()` per `htf_parent_telemetry_extract.py:84-121` (including the `bt.guard_xauusd_csv_path` identity patch and the `feed._builder.parent_candle` read-back) and, at each H4 close, record the distance from the parent close to the boundaries the feed already exposes — `feed.track.range.h_ref` / `.l_ref`, `feed.track.sweep.price`, the previous parent's high/low, the objective `target` / `invalidate_at`, and `_htf_mid`.
- Output: for each decision family, the margin distribution and the count of evaluations whose margin sits inside **0.22** (p95) and inside **0.99** (max) — the knife-edge census. Reported, not blocking.

### Step 3 — Arm C: three-cell substitution replay (`scripts/research/close_m15_equivalence.py`, part 2)

Cell-based A/B in the established repo style (`htf_objective_gate_shadow.py`, `bitnet_shadow_diagnostic` lineage). Restricted to the 15 M15-covered days; parents with incomplete TV child coverage are marked `NOT_TESTABLE`, never silently included.

| Cell | Stream fed to the engine + feed | Question |
|---|---|---|
| **A0** | engine bars, unmodified | **Parity gate.** Must reproduce `results/monthly_tv_semantic_report/htf_parent_telemetry.jsonl` exactly and the published funnel (84/19/6/2/0). Abort on any mismatch — reuse the `EXPECTED_DISTRIBUTION_C3_CLOSES = 15` non-vacuity check (`htf_parent_telemetry_extract.py:76`). |
| **A1** | engine O/H/L, **TV close only** | **The user's question.** Isolates the close field's contribution. |
| **A2** | full TV O/H/L/C | Context / upper bound — how much of any flip is close vs the other three fields. |

Diff A1 and A2 against A0 on: `track_state` / `bias` / `htf_state` / `objective_status` per H4 close, and the M15 funnel transition sequence. Classify every flip as daily-open (F-080 bar-definition) or ordinary-bar, and **never pool the two**.

### Step 4 — Verdict artifact

`reports/close_m15_semantic_equivalence.md` + `reports/close_m15_semantic_equivalence.json` (machine twin, mirroring the existing monthly report's md/json pairing). Contents: the pre-registration restated, all three arms, the verdict token, the coverage statement, and an explicit §6.8 closing tag. Add a cross-link from `reports/monthly_tv_vs_active_production_semantic_comparison.md` row 1 noting that its MATCH is a 4-field L1 aggregate and pointing at this report for the close-only decomposition and the 15-of-23 M15 figure (§6.2 rule 6 synchronize; the existing text is not deleted).

### Step 5 — Registration + close-out

- **SITS** (both new scripts, same turn — `docs/reference/conventions.md:122-126`):
  ```bash
  python scripts/analysis/script_census.py --write-stubs docs/governance/script_registry_stubs.jsonl
  ```
  then add the required Python overlays in `scripts/governance/seed_script_registry.py` (a stub alone leaves `purpose = GRANDFATHER_UNCLASSIFIED` and fails the coverage floor), then `seed_script_registry.py`, then `generate_script_matrix.py`.
- `python scripts/governance/construction_protocol.py validate-completion docs/governance/build_manifests/CH-close-m15-equivalence-gate.impact.json`
- Finding in `docs/current-findings.md` **only if** the Step-0 precondition fires; §6.7 ground any new noun before asserting it.
- `📝 SESSION LOG ENTRY` appended to `assistant_project.md` (§6 — codebase log; this is governed-code-adjacent research, not workflow).

## Critical files

**Read (authorities, do not modify):** `src/features/parent_candle.py` · `src/config_layer/parent_crt.py` · `src/config_layer/htf_state.py` · `src/config_layer/crt_engine_v2.py` · `tools/tv_forensic/engine_data.py`

**Reuse (harnesses, copy the pattern):** `scripts/research/htf_parent_telemetry_extract.py` (ParentCRTFeed replay + sidecar filtering + non-vacuity gate) · `scripts/analysis/crt_predicate_failure_census_6m.py` (guard-hook attach + operand harvest) · `scripts/research/htf_objective_gate_shadow.py` (multi-cell comparison structure) · `src/runtime/crt_baseline_trace.py` (`CRTBaselineTraceHooks`)

**Create:** `scripts/research/close_m15_equivalence.py` · `scripts/research/close_margin_census.py` · `reports/close_m15_semantic_equivalence.{md,json}` · `docs/governance/build_manifests/CH-close-m15-equivalence-gate.impact.json`

**Edit (surgical):** `scripts/governance/seed_script_registry.py` (2 overlays) · `docs/governance/script_registry_stubs.jsonl` (generated) · `reports/monthly_tv_vs_active_production_semantic_comparison.md` (row-1 cross-link) · `docs/current-findings.md` (conditional) · `assistant_project.md`

## Verification

1. **Parity gates are the acceptance criteria, not the report prose.** A0 must reproduce `htf_parent_telemetry.jsonl` byte-for-byte on `track_state`/`bias`/`htf_state`/`objective_status` and hit `DISTRIBUTION_C3 == 15`; the guard-hook replay must reproduce the published M15 funnel (84/19/6/2/0). Either failing = harness bug, abort, do not report downstream numbers.
2. **Non-vacuity**: the substitution must actually bite — assert ≥1 substituted bar differs from engine on every covered day, so a silently-identical stream cannot masquerade as a PASS (the D-1/F-079 failure class).
3. **Read-only proof**: `git status` shows no change under `configs/`, `src/`, `models/`, `data/`; `configs/production/ACTIVE_VERSION` still reads `v2_htfcrt_2026_08`.
4. **Regression floors**: `python -m pytest tests/test_tv_forensic_smoke.py tests/test_script_registry.py tests/test_script_matrix_sync.py tests/test_current_findings.py tests/test_session_log.py -q` (add `tests/test_closure_authority_index.py` — the index must be *unchanged*, per decision 2).
5. **Both substitution policies reported** (expand + clamp), so the 1.59% incoherent-bar handling is visible rather than chosen.

## What this deliberately does not do

- Does not take new TradingView captures; the 8 blind M15 days stay blind and are named in the report.
- Does not adjudicate F-077's Romeo/Sujan non-equivalence, and does not touch F-080's daily-open characterization beyond citing it.
- A PASS clears the close-equivalence precondition **only**. Assigning HTF a predictive or qualification role remains a separate, separately-authorized program requiring measured ΔG001 (§6.5 Authority Ladder).
