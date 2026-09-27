# Continuing the user investigation: gathered context and proposed next step

## Context
The user asked to continue the investigation and gather the required context. They then pointed at
`D:\Tradelatest\userinvestigation\`. Everything below was read this turn (read-only). Items I did not
verify against source are marked UNVERIFIED.

## What the investigation is (one thread, four documents)
`userinvestigation/` holds the design record of the model-layer rewrite. It feeds the K23 table work
recorded in `assistant_project.md` (entries dated 2026-09-24).

| File | What it establishes |
|---|---|
| `model_layer_tracker.md` | Phase 0 (model registry join) CLOSED (K17). K1-K5 CLOSED. Pending: Phase 1 model contract, Phase 2 shadow harness (blocked on K12, a JSONL `CC-*` class), Phase 3 specialists, **Phase 4 conditional-expectancy table**, Phase 5 re-founds. |
| `linkcostmodelstateengineschema.txt` | State-machine workflow with reference-run counts (47,275 bars). Every stage dies on a clock or filter, not on a market condition. Nine proposed fixes. Cost model as a market-state signal (M8 cross-tab). |
| `RRModelAnalysis.md` | "RR" names three objects. Gates 1-4 to enable rr_fusion. No 48-dim RR artifact exists (widest is 39-dim), so a flag flip is inert today. |
| `session_conversation_20260923_0229.md` | Gaussian design. Live Gaussian is `exp(-x^2/2)` (0/14 registry entries carry mu/sigma). Option B (density model) chosen. All 3 Gaussians run in parallel as shadow models. |
| `TradenetModel.txt`, `CANONICAL_FEATURES.html`, `enriched_df.html`, `session_conversation*.{html,jsonl}` | Schema v6.0, 48 dims, hash `d40e7c7d...`. Feature DAG layers. The 2026-09-22 XAUUSD run: 3 trades, net -1.69R. |

## Where the work stands (session log and design doc, 2026-09-24)
- **K23** = the Phase-4 table (heuristics x quartiles x direction, about 150 cells). Design is parked at `docs/implementation_plan/k23-block-heuristic-table-design.md`.
- **Fix-first list, all 4 implemented as code, flags OFF everywhere:**
  - F1 `retrace_reset_pct` 0.618: config-only, NOT yet applied.
  - F2 exact per-date exchange session windows (`backtest.session_window_basis`).
  - F3 oracle `sweep_extreme` SL arm plus `reference_level` stamping fix.
  - F4 SWEEP exempt from the HTF-flip reset (`backtest.htf_reset_exempt_sweep`).
- **K24 closed:** the engine HTF clock is 16 bars, not 4. It kills 76.6% of sweeps (1,372/1,792). The "4" in the state-machine document above is the resolver default plus a YAML comment (DOC_DRIFT). Treat the `linkcostmodelstateengineschema.txt` numbers as pre-correction for that point.
- **Next step recorded:** build a shadow config (F1 0.618 + F2 exchange_local + TOKYO admission + F3 + F4), then run the spine, then `build_bar_matrix --lt-id`, labeler (+F3 arm), decision atlas, then the table.
- **Verified this turn:** `ACTIVE_VERSION` = `v2_htfcrt_2026_08`. Its JSON has no F2/F4 key and `retrace_reset_pct` is still 0.5. No K23 shadow config exists in `configs/production/` (only older shadow configs).
- The latest run (`run_20260923_072728_...7de09f62`) is pre-fix: 3 setups, PF 0.27, G001 FAIL.

## Caveats to carry forward
- The tree is dirty (348 paths; `crt_engine_v2.py` and `backtest_v2.py` carry other sessions' edits). CLAUDE.md preflight says STOP and report before measuring against recorded findings. Any new run is an observation on the working tree, not a comparison with HEAD.
- Last recorded governance floor: 14 failed / 586 passed. No baseline was captured before the F2/F3 turn, so attribution is UNVERIFIED.
- `test_doc_citations` has drift in `crt_engine_v2.py` citations (CLAUDE.md 6.3 sync not done).
- Open decisions: TOKYO admission in `allowed_sessions`; London/NY overlap resolves first-declared; INFORMATION/CONSUMABLE tier split and BH-FDR (recommended, not agreed); the Gaussian and RR open questions in their documents.
- No economic claim, no authority change. `use_bitnet` and `rr_fusion.enabled` stay false.

## Proposed next step (needs the user's go-ahead; nothing below is executed)
1. Capture a governance-floor baseline first (background, logged).
2. Write the shadow config `v2_htfcrt_k23_shadow_2026_09.json` as a clone of `v2_htfcrt_2026_08`. It carries F1 = 0.618, `session_window_basis: exchange_local` with `exchange_session_windows` (Tokyo 09-18 JST, London 08-17, NY 08-17) and TOKYO in `allowed_sessions`, `htf_reset_exempt_sweep: true`, and `sl_anchor: sweep_extreme`. It is not promoted and leaves `ACTIVE_VERSION` alone. Re-hash only if a `params` key changes, via `scripts/maintenance/_compute_hash.py`.
3. Run the XAUUSD spine on it, then `build_bar_matrix --lt-id <new>`, then the labeler with `sweep_lookback=16`, then `build_decision_atlas` (args UNVERIFIED).
4. Run the fidelity checks from design doc section 10b (feature columns and the two existing label arms byte-identical to pre-fix). STOP and report on any difference.
5. Pre-register, then run the table with the planted-signal gate first (F-086 pattern).
6. Append the SESSION LOG entry to `assistant_project.md`.

## Verification
- Flag-off parity: the shadow run's F-flags OFF reproduces the recorded 2026-09-23 run.
- The F3 parity test (oracle vs spine) is green.
- Governance floor no worse than the captured baseline.
