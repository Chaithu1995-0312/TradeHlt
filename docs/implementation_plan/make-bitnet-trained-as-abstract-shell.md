# BitNet Enablement — Shadow-Diagnostic-First (reframed)

## Context

**Request:** "Make BitNet trained as true, trace the intent behind BitNet, come up with a design plan"
→ then "understand what and how BitNet is doing it."

**What BitNet is (mechanism):** a tiny fully-connected net (`6→16→8→1`, ~233 weights) — NOT an
LLM/GGUF. It answers *"is this market state acceptable?"* and outputs a confidence in [0,1].
Forward pass ([bitnet_inference.py:294](src/bitnet/bitnet_inference.py:294)):
`l1=clip₋₁,₁(W1·x+b1) → l2=clip₋₁,₁(W2·l1+b2) → out=W_o·l2+b_o → sigmoid(out)`.
Inputs (harvested at the CRT RETEST cache): `body_ratio`, `retest_depth`(←FM-027),
`disp_strength`(←FM-028), raw `atr`, `candles_since_retest`, `double_sweep`.
**Used as a hard-reject VETO** ([crt_engine_v2.py:1960](src/config_layer/crt_engine_v2.py:1960)):
when `use_bitnet=true`, `score<0.55` → `RejectReason.LOW_SCORE`, trade killed. It can only reject,
never boost; not part of fusion. `use_bitnet:false` on active `v2_multi_2026_04` (F-004).

**Why the naive flip is wrong (3 blockers):** (1) F-050 train/serve skew — trained on pipeline
FM-020/021, served CRT FM-027/028 under the same names; (2) `atr` fed raw/unnormalized → not
scale-invariant across instruments; (3) Authority Ladder §6.5 — no ΔG001 ever measured, empty
promotion registry, weak bullish-only ATR-race label.

**Reframe (user-approved):** the strong entry-gate null prior (F-019…F-041: entry information is
economically null; binding constraint = execution model, not predictability) + tiny spine
throughput (~5-13 entries/instrument) means a faithful retrain isn't even trainable. So run the
**cheap decisive measurement first** — shadow-measure the EXISTING model gate-ON vs OFF — before
any retrain. Research authority only; **no promotion, no active-config change, `use_bitnet` stays
false on active.**

---

## COMPLETED
- **Shadow config** `configs/production/v2_multi_bitnet_shadow_2026_07.json` — clone of active with
  `crt_engine.use_bitnet=true`. Hash-neutral (flag is in `crt_engine`, not `params`); loads clean
  via `load_prod_config_from_registry`, resolves `use_bitnet=True`. NOT active, NOT promoted.
- **Shadow spine research config** `configs/research/research_config_spine_bitnet_shadow.json`
  (`spine.prod_version` → shadow) — the gate-ON arm; OFF arm = `research_config_spine_majors.json`.
- **Diagnostic** `scripts/research/bitnet_shadow_diagnostic.py` — runs `ProductionSpineSource` OFF
  vs ON per instrument, compares at the BOOK level (entry sets are NOT nested: a reject resets the
  CRT state machine → divergent trajectory). Expectancy from the spine's own governed ledger
  (`SpineEntry.meta.backtest_pnl_rr_net`).
- **BNB result** (`results/bitnet/shadow_diagnostic_bnb.json`): gate fired **50 rejections**, net
  trades **11→11**, the 2 swapped-out entries averaged **+0.43R (winners)** → book leaning HARMFUL;
  OFF book already net-negative (E=−0.39R, PF 0.51). Confirms the entry-gate null.

## REMAINING (finish the completed pieces)
1. **Finish the 4-majors run** (`results/bitnet/shadow_diagnostic_majors.json`, in flight) — BNB +
   ETH + BTC + SOL book-level A/B; get pooled ΔE.
2. **Register finding F-0NN** in `docs/current-findings.md` + Repository Truths Index in `CLAUDE.md`:
   *enabling the EXISTING (F-050-skewed) BitNet on the active spine is economically non-additive
   (leaning harmful) and behaves as a state-machine-perturbing veto, not a filter; keep
   `use_bitnet:false`.* Cite evidence (script + result JSON). Confidence per pooled result.
3. **Governance sync:** append a dated entry to `docs/governance/bitnet_lineage_audit.md` (shadow
   measurement + the raw-`atr`/scale-invariance mechanical note); update `active_models.yaml` bitnet
   block; §7.4 SESSION LOG to `assistant_project.md`; save a `project` memory of the ΔG001 belief.
4. **Escalation gate:** only if the pooled result is *surprisingly positive* do we revisit the
   governed retrain (RETEST-candidate harvester + forward_walk labels). Otherwise STOP — null with a
   clear conclusion is high knowledge-ROI (§6.1).

## Critical files
- `scripts/research/bitnet_shadow_diagnostic.py` (built) · `src/research/adapters/spine_signal_source.py` (reused)
- `configs/production/v2_multi_bitnet_shadow_2026_07.json`, `configs/research/research_config_spine_bitnet_shadow.json` (built, non-active)
- `src/config_layer/crt_engine_v2.py:1960` (gate, read-only) · `src/bitnet/bitnet_inference.py:294,317` (net, read-only)
- Governance sync targets: `docs/current-findings.md`, `CLAUDE.md` Truths Index, `active_models.yaml`, `docs/governance/bitnet_lineage_audit.md`

## Verification
- Both configs load; `use_bitnet` resolves False (active) / True (shadow) — DONE.
- Diagnostic writes `results/bitnet/shadow_diagnostic_majors.json` with per-instrument + pooled
  book-level E_off/E_on/delta and reject/add counts.
- `configs/production/ACTIVE_VERSION` still `v2_multi_2026_04`; active hash unchanged.
- New finding ↔ Truths Index consistent (`pytest tests/test_current_findings.py`).
