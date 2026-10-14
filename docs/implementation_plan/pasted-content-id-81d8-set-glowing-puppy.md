# Set 4 audit plan — review verdict + corrections

## Context
Review of the pasted Set 4 (market structure) read-only audit plan. The anchors were spot-checked against source. The plan is sound; below are corrections and gaps to fold in before executing. Execution is read-only: no production/config/schema/model edits, no Set 5.

## Anchors verified (OBSERVED)
- `src/features/feature_pipeline.py:782-889` `compute_structure_liquidity`: pivot = centered `w=2k+1` with ties qualifying (`high == roll_high`); production `swing_high/low` = centered pivot `.shift(k)` (causal delayed). Centered identity lives only on `*_centered_batch` columns.
- Active config `v2_htfcrt_2026_08.json`: `swing_window=2`, `sweep_semantics="latest_unconsumed"` (so the E01 lifecycle identity is NOT the active one), `normalization_basis=atr_absolute`.
- `smc/choch.py:20-31`: stateless `f(break_of_structure, trend_bias)`; no detector.
- `strategy_backtest.py:302-303` maps `swing_high/low` to `last_swing_*_price` (price, not flag) — a real identity remap, confirmed.
- `active_models.yaml:1343` (main tree, not a worktree) marks CHoCH `fusion_weight inert:0, role unused`.
- Oracle `tests/helpers/fc1a_swing_oracle.py` and `causal_structure.py` exist.

## Corrections / gaps to add
1. **Audit only `D:\Tradelatest\src` and `tests`.** Duplicate copies of `causal_structure.py`, `choch.py`, `predicates.py`, oracle tests exist under `.claude/worktrees/*` and `msip_1_verification_package/`. Exclude them or they will pollute the competing-implementation census (cite them only as UNKNOWN-drift if they differ).
2. **`higher_high`/`lower_low` are not swing-vs-swing classifications.** Source: `high > ref_high` / `low < ref_low` where `ref = last_swing_price.shift(1)` — a per-bar wick-breach flag against the last *published* swing, with an extra 1-bar lag on top of the k-bar delay. The task's Step 5 wording ("compare prior swing / attached to pivot") needs a NEEDS-DEFINITION note: attached to the *current bar*, not the pivot. Plan should state this as repository identity, not a failure.
3. **Total delay budget.** Swing flag lags the pivot by k=2; HH/LL/BOS/sweep reference `shift(1)` on top, so a pivot at bar p first constrains structure at p+k+1. Reference + future-mutation test must model both shifts separately.
4. **Equality/plateau semantics are explicit in code:** ties qualify as pivots (multiple adjacent flagged bars possible); BOS is strict `close > ref_high`; sweep is `high > ref & close <= ref` (inclusive), so `close == ref` is sweep not BOS. Edge battery must pin these exactly, plus NaN behaviour of `ref_*` before first swing (comparisons yield 0).
5. **Centered `min_periods=w` tail:** last k rows of the centered series are NaN→0; prefix-vs-full must show prefix(t) equals full(t) for all t ≥ warmup, with the shift hiding the tail. Test at several prefix lengths including ones ending mid-plateau.
6. **Corpus identity precondition (CLAUDE.md preflight):** record `git status --porcelain` (dirty `src/core/engine_runner.py`, strategies, config), echo exact data path + row count (47,275 raw / 47,197 emitted), interpreter `venv\Scripts\python.exe`, freeze-pin SHA before measuring. The dirty tree means findings are tied to this working tree, not a commit.
7. **E01 identity is non-active:** measure it only as a competing-identity side-arm (via a non-promoted config clone), never as the production verdict. `double_sweep` active identity = signed-slot legacy read.
8. **Historical/PIT step:** anchor on existing F-051 (centered swings non-PIT, RR/Zone artifacts `PIT_UNCLEAN_CENTERED_SWINGS`), F-107, F-112, FC1-A freeze. Classify, do not repair; `crt_engine_v2` local sweep geometry and `structure/predicates.py` strict sweep (`close < ref`) are separate non-FM-058 identities — keep them in the drift ledger, not the vector verdict.
9. **Decision-influence probe:** CHoCH is `consumers: all false` in `active_models.yaml`; probe must separate CONSUMED-BUT-INERT from NOT_REACHED (backtest never reaches planner/Ultron per F-103). Use `crt_engine.compute` → `scoring_engine.compute_scores` for `sweep_detected/double_sweep`.
10. **Logging:** per CLAUDE.md §6, append a SESSION LOG entry; findings registration (F-id) only if user asks — scope control §1.2.

## Execution outline (after approval)
1. Preflight + corpus identity. 2. Authority map. 3. Independent oracle (reuse `fc1a_swing_oracle`, extend to BOS/sweep/CHoCH/double_sweep from raw OHLC). 4. Full-corpus ref-vs-production per feature with mismatch specimens. 5. Prefix-vs-full + future-mutation. 6. Edge battery on synthetic frames. 7. Vector slot check (6/20/21/22/23/24/25/26/47). 8. Consumer + decision probes. 9. Historical/PIT + drift ledger. 10. Verdict table. Production changes = NONE; probe scripts in scratchpad only.

## Verification
Re-run oracle parity tests (`tests/test_fc1a_swing_oracle_parity.py`, `tests/test_fc1a_swing_causal.py`) via `venv\Scripts\python.exe -m pytest` as the floor; confirm freeze-pin vector SHA unchanged after the audit (proves read-only).
