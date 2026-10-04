# Program 9 — M5-base Multi-TF Expansion Forecasting (Non-Directional Ontology)

## Context

The M5 corpus landed (Binance crypto 2-yr M5/M15/H1/H4 ladders, 210,240 bars × 6 majors, zero missing; MT5 FX/metals ~270-day ladders), closing F-040's "no M5 on disk" scope gap. Program 4 is KILLED with an explicit reopen clause — *new data (the M5 corpus), new market domain, or new non-directional ontology; never parameter archaeology*. F-040's unresolved question: the expansion forecast is real (Stage-1 PASS, universal, persistent) but spot directional long/short cannot express the long-vol payoff (Stage-2 FAIL). This program satisfies **both** reopen keys and answers that question directly.

**User decisions (2026-07-03):** Stage-2 = **non-directional straddle proxy** (both-sided stop entries at compression box edges, OCO, first touch wins), gated on Stage-1 PASS · Stage-1 must test **incremental** info vs the M15-base result with a redundancy control (avoid the F-043 redundancy trap) · Universe = **crypto primary** (6 Binance majors) + **FX robustness** (6 MT5 symbols) · Pre-registration frozen BEFORE any run · **unchanged M4 gate** (intrabar_fixed + 12bps + permutation + BH).

## Resolved mechanisms (verified against code)

### 1. Both-sided payoff — additive OCO walk, legacy kernel byte-untouched
`forward_walk` ([forward_walk.py:26-75](src/research/measurement/forward_walk.py:26)) assumes the entry is already filled at `signal.entry` and rejects any direction outside `("long","short")` at :57. No stop-entry semantics exist. So:

- **New pure function `forward_walk_oco()`** appended to [forward_walk.py](src/research/measurement/forward_walk.py) — the existing `forward_walk` body is not touched. Signature: `forward_walk_oco(signal, future, *, max_forward, entry_ttl, exit_model="intrabar_fixed") -> Outcome | None`. Contract: `signal.direction == "oco"`, box edges in `signal.meta["box_high"/"box_low"]`.
  - **Phase A (pending, bars 1..entry_ttl):** both edges touched same bar → **CANCEL, return None** (reject-bar tie rule, pre-reg D1 — intrabar touch order unknowable); else high ≥ box_high → long fills at box_high; low ≤ box_low → short fills at box_low; no touch within TTL → None.
  - **Phase B (fill bar):** resolve via `dataclasses.replace(signal, direction=..., entry=edge, entry_index=...)`. Fill bar: SL checked by full-range touch; **TP never credited on the fill bar** (pre-reg D2, consistent with the kernel's SL-before-TP convention). Then **delegate `future[j+1:]` to the unchanged `forward_walk`**, merging fill-bar MFE/MAE and offsetting duration/time_to_tp by 1; `bars_to_fill` recorded in meta.
- **Runner routing per-SIGNAL** in `run_instrument` ([runner.py:86-93](src/research/runner.py:86)), after the `apply_signal_defaults` replace: `if s.direction == "oco":` slice `future = candles[i+1 : i+1+cfg.max_forward+cfg.entry_ttl]`, call `forward_walk_oco`, append only if not None; `else:` existing lines verbatim. **`collect()` delegates to `run_instrument` (runner.py:108) so this one branch covers both the edge-report and M4-qualification paths.** Controls (`always_long`, `random_baseline`) emit long/short → flow through the legacy path untouched; a misrouted "oco" signal fails loudly at forward_walk.py:57.
- **Config:** optional `forward_walk.entry_ttl` in [config.py](src/research/config.py). Load-bearing: `sha256()` canonicalization must include the key **only when present in the JSON**, so every existing config's `config_sha256` (stamped into all published edge reports) stays byte-identical.
- **New hypothesis** `src/research/hypotheses/compression_box_straddle.py` (`@register_hypothesis`, family="transition", registered in `hypotheses/__init__.py`): precondition = M5 vol==COMPRESSION at setup **and** prior bar NOT COMPRESSION (fire only on the first bar of a compression run — no overlapping straddles, pre-reg D4); box = trailing 5-bar high/low (mirrors [compression_breakout.py:62-64](src/research/hypotheses/compression_breakout.py:62)); emits one `Signal(direction="oco", sl_atr_mult=1.0, tp_atr_mult=2.0, atr=ATR(14), meta={box_high, box_low})`. `Signal` dataclass unchanged (direction is a plain str).
- **Parity guarantee (testable):** legacy `forward_walk` source unchanged · all existing config sha256 unchanged · long/short signals execute pre-existing statements verbatim ⇒ `run_result_to_dict` byte-identical for every registered hypothesis (golden fixture test). Cancelled straddles return None ⇒ excluded from n; fill-rate/cancel counts are reporting-only telemetry.

### 2. Stage-1 incremental-info — within-coarse-cell permutation (F-043 pattern)
Per M5 bar: **K5** = `"M5=<tok>|M15=<tok>|H1=<tok>|H4=<tok>"` (last-closed HTF states, causal) and **K15** = K5 with the M5 part stripped (the causally-available M15-base info at the same instant). New additive kernel `within_coarse_permutation_p(cells_fine, cells_coarse, target, valid, *, n_permutations, name)` — seeded (`seed_for`) shuffle of the target **within each K15 cell**, recomputing IG(target|K5) per draw (reuses the `partition_stat`/IG wrappers in [info_robustness.py:30-37](src/research/candle_state/info_robustness.py:30)); add-one p-value. This null preserves all K15-level information and destroys only the M5 refinement = conditional-MI significance by stratified permutation.

**Frozen PASS rule:** Stage-1 PASS = **Gate A** (raw: perm p ≤ 0.05 ∧ half-life ≥ 12 M5 bars ∧ MI retention ≥ 0.5 ∧ n ≥ 30) **∧ Gate B** (incremental: within-K15 perm p ≤ 0.05). A-pass + B-fail ⇒ verdict **`M15_REDUNDANT`** = Stage-1 FAIL. Cross-market verdict logic unchanged, applied to A∧B.

**Stability split (forced change, pre-reg D5):** the 2024/2025 calendar split is impossible for FX (data starts 2025-10-06) → per-instrument **chronological 50/50 split** of valid decision bars.

### 3. Horizon rescale (wall-clock-matched, frozen in pre-reg)
| F-040 (M15) | Program 9 (M5) | Wall-clock |
|---|---|---|
| horizons {1,2,4,8} | **{3,6,12,24}** | 15m/30m/1h/2h |
| k_decision 4 | **12** | 1 h |
| half-life ≥ 4 | **≥ 12** | ≥ 1 h |
| max_forward 40 | **120** | 10 h |
| — | **entry_ttl 12** | 1 h |

θ=1.5, ATR 14, retention ≥ 0.5, α=0.05, 2000 seeded perms, n≥30 unchanged. `info_half_life` ([info_robustness.py:66-85](src/research/candle_state/info_robustness.py:66)) gains an optional `min_bars` kwarg (default = current constant, existing callers unchanged).

### 4. M5→M15 resample + corpus parity gate
[resample.py](src/research/resample.py): keep `_RULE_HOURS` (:46) and `_bucket_start` (:52) byte-untouched (imported by mtf_conjunction.py:24). Add `_RULE_MINUTES={"M15":15,"H1":60,"H4":240}`, `_bucket_start_minutes()`, public `bucket_floor(ts, rule)` dispatcher; additive `elif` branch in `resample()` for "M15". Associativity tests: `M5→M15→H1 == M5→H1`, `M5→M15→H4 == M5→H4`.

**Corpus parity gate (must be green before any run):** for all 12 symbols, `resample(M5, rule)` must equal the fetched on-disk M15/H1/H4 rows **minus the final row** (the resampler drops the trailing bucket; verified: M5 ends 23:55, M15 ends 23:45). OHLC exact; volume Decimal-exact with pre-registered rel-1e-8 fallback. Driver `scripts/research/verify_m5_resample_parity.py` → `results/research/m5_mtf/resample_parity.json`, plus a skipif-data-missing pytest.

### 5. Wiring — NEW drivers + configs; frozen 4bcd artifacts untouched
`transition_information.py`/`qualify_transitions.py` are the frozen instruments of the closed 4bcd pre-registration — do not extend them. Program 9 gets mirrored thin CLIs and its own configs. `MultiTFConjunctionBuilder` gains additive `base_label="M15"` ctor param (replacing the hardcoded label at [mtf_conjunction.py:73,126](src/research/candle_state/mtf_conjunction.py:73)) and uses `bucket_floor` at :119; default output byte-identical (golden test).

## Milestones

### M0 — Pre-registration (write + freeze BEFORE any run)
Create **`docs/research/preregistration-program-9.md`** mirroring [preregistration-program-4bcd.md](docs/research/preregistration-program-4bcd.md) (context/scope, hypotheses, frozen thresholds, closure rule, E-001 6-question pre-check, priors).
- Hypotheses (non-directional, cell = M5∧M15∧H1∧H4 key, targets from `transition_target.py` unchanged): **9a** vol-expansion (θ=1.5) · **9b** range-expansion (θ=1.5) · **9c** compression→expansion transition.
- Frozen decisions: D1 reject-bar CANCEL · D2 no fill-bar TP · D3 unfilled TTL ⇒ excluded from n · D4 first-compression-bar gating · D5 chronological 50/50 stability split · D6 M15_REDUNDANT verdict rule. Universe: crypto BTC/ETH/SOL/BNB/XRP/DOGE (`data/binance/{SYM}_M5.csv`), FX EURUSD/GBPUSD/AUDUSD/USDJPY/EURCAD/XAUUSD (`data/mt5/{SYM}_M5.csv`; F-035 cost-caveat + XAUUSD noted).
- Closure rule: Program 9 CLOSED when 9a∧9b∧9c each resolve to (Stage-1 FAIL incl. M15_REDUNDANT) ∨ (Stage-1 PASS + Stage-2 verdict); no parameter variants after.
- Priors: M15_REDUNDANT ≈40% · other Stage-1 FAIL ≈20% · S1 PASS + S2 FAIL ≈30% · full PASS ≈10%.

### M1 — Kernel extensions + tests (additive, parity-proved; no runs)
Modify: `src/research/resample.py` (minute rules) · `src/research/candle_state/mtf_conjunction.py` (`base_label`, `bucket_floor`) · `src/research/measurement/forward_walk.py` (append `forward_walk_oco`) · `src/research/runner.py:86-93` (per-signal oco branch) · `src/research/config.py` (optional `entry_ttl`, conditional sha inclusion) · `src/research/candle_state/info_robustness.py` (`min_bars` kwarg).
Create: `src/research/candle_state/m5_incremental.py` (frozen constants `M5_HORIZONS/M5_K_DECISION/M5_HALF_LIFE_MIN_BARS`, `coarse_key()`, `within_coarse_permutation_p()`, `stage1_verdict()`) · `src/research/hypotheses/compression_box_straddle.py` · `scripts/research/verify_m5_resample_parity.py`.
New tests (tests/research/, mirroring existing synthetic-Candle conventions): `test_resample_m5.py`, `test_resample_corpus_parity.py`, `test_mtf_conjunction_m5.py` (incl. default-label golden parity + M15-bucket no-lookahead), `test_forward_walk_oco.py` (fills, reject-bar, TTL, fill-bar SL yes/TP no, post-fill delegation ≡ forward_walk, determinism), `test_runner_oco_routing.py` (golden byte-parity for market-direction hypotheses), `test_config_entry_ttl.py` (all existing config sha256 unchanged), `test_m5_incremental.py` (null-uniform p, planted-signal detection, seed determinism), `test_compression_box_straddle.py`.
**Exit:** full existing suite green + corpus parity green.

### M2 — Stage-1 driver + run
New `scripts/research/m5_mtf_information.py` (mirrors transition_information.py): 6+6 universe, `MultiTFConjunctionBuilder(CandleStateEncoder(atr_period=14), base_label="M5", rules=("M15","H1","H4"))`, per-program/horizon IG, decision-horizon `permutation_p` + **`within_coarse_permutation_p`**, 50/50 `mi_stability`, `info_half_life(min_bars=12)`, per-instrument + pooled + cross_market → `results/research/m5_mtf/m5_mtf_information.json` + manifest. Run twice, byte-compare bodies.

### M3 — Gate decision (no code)
Record verdicts per pre-reg. Gate A pass + Gate B fail ⇒ `M15_REDUNDANT`, stop. Only cross_market ≠ REJECTED under A∧B proceeds to M4; if nothing survives → M5 closure finding.

### M4 — Stage-2 consumer + run (only on Stage-1 PASS)
New configs `configs/research/research_config_m5_mtf_crypto.json` (`data_dir "data/binance"`, 6 instruments, `max_forward 120`, `entry_ttl 12`, intrabar_fixed, 12bps, sl 1.0/tp 2.0, qualification block copied from research_config_majors.json) + `research_config_m5_mtf_fx.json` (`data_dir "data/mt5"`). New `scripts/research/qualify_m5_straddle.py` (line-for-line mirror of qualify_transitions.py, `CANDIDATE="compression_box_straddle"`) → `results/research/m5_mtf/qualify_m5_straddle.json`; unchanged evaluate_pre_bh → BH → finalize + controls; fill-rate/cancel counts reporting-only. Double-run byte-compare.

### M5 — Reporting / findings
Next F-number entry in `docs/current-findings.md` + CLAUDE.md §6.2 index row, citing both deterministic artifacts; `results/research/m5_mtf/EDGE_SUMMARY.md`; Funding Ledger update (Program 9 registered; Program 4 reopen clause consumed). No spine/config/authority changes regardless of outcome (Authority Ladder: research/docs only). SESSION LOG + memory file per §6/§6.1.

## Verification
1. `verify_m5_resample_parity.py`: resampled M5→{M15,H1,H4} == fetched files (minus trailing bucket), all 12 symbols.
2. Config-sha parity test over every existing `configs/research/*.json`.
3. Golden runner parity: `run_result_to_dict` byte-identical for a long/short hypothesis before/after the runner branch.
4. Full existing pytest suite green (research + candle_state + resample + qualification + runner determinism).
5. Stage-1/Stage-2 artifacts byte-identical across two runs (seeded perms, no wall-clock in bodies).
6. Pre-reg doc committed and cited in both drivers' docstrings before any M2/M4 run.
