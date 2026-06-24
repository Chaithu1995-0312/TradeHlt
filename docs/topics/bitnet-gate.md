# Topic: BitNet Gate

> **Topic-visibility unit.** The BitNet neural scorer and the LIVE hard rejection gate it drives.
> This is the topic behind finding **F-004** (BitNet is a live gate, its score is persisted).
>
> Created: 2026-06-05 · Updated: 2026-06-05 · Status: living

## In plain language
BitNet is a small quantized neural model that scores a candidate trade's features. It is **not
advisory** — on the live/backtest CRT path, if the BitNet score falls below `0.55` the trade is
**hard-rejected** before fusion even matters, and the score is persisted on the trade record. So
BitNet is a real gatekeeper in the decision path (this corrected an earlier belief that BitNet was
built-but-dormant). What *is* dormant is only an *adaptive, regime-aware* threshold — there is no
such function; the cutoff is the static `0.55`.

## Code covered
- [`src/bitnet/bitnet_inference.py:317`](../../src/bitnet/bitnet_inference.py) — `bitnet_score` — feature-dict → confidence score `[0,1]` (legacy forward pass).
- [`src/bitnet/bitnet_inference.py:174`](../../src/bitnet/bitnet_inference.py) — `BitNetModel` — two-schema model loader (legacy `model.json` + export format); `predict()` for the (24,) vector.
- [`src/config_layer/crt_engine_v2.py:1805`](../../src/config_layer/crt_engine_v2.py) — `bitnet_main_score` — the LIVE hard gate: `if bitnet_main_score < 0.55: return False, RejectReason.LOW_SCORE`.
- [`src/config_layer/crt_engine_v2.py:363`](../../src/config_layer/crt_engine_v2.py) — `bitnet_main_threshold` — static `0.55` default.
- [`src/runtime/backtest_v2.py:276`](../../src/runtime/backtest_v2.py) — `bitnet_score_at_entry` — the persisted score field on the trade record (also `bitnet_decision_at_entry`).

## Ins / Outs
- **Ins:** the CRT feature dict (BitNet reads a fixed legacy subset); model artifact (`model.json` / export schema) under `models/`; config `get_prod_section("crt_engine")` → `bitnet_main_threshold`.
- **Outs:** a `bitnet_main_score ∈ [0,1]`; a hard ACCEPT/REJECT branch in CRT; the score + decision persisted to the trade record (and CSV export) for later attribution.

## Entry points & validations
- **Reached via:** the CRT engine on the candle→order spine (`runtime.backtest_v2` replay and `runtime.live_engine_hook` live). The gate fires inside CRT before fusion.
- **Validated by:** persistence is verifiable in trade CSVs (`bitnet_score_at_entry`); parity between legacy and export schema paths is tested; the `<0.55` reject is exercised in backtests.

## Tests
- [`tests/test_bitnet_inference.py`](../../tests/test_bitnet_inference.py) — `predict()` shape/NaN validation, signal thresholds, determinism, model-file error handling.
- [`tests/test_bitnet_parity.py`](../../tests/test_bitnet_parity.py) — legacy (6-input) vs export (24-input) schema parity.

## Fits in architecture
BitNet sits *inside* the CRT stage of the spine (it gates before fusion), so it pairs with
[`crt-spine.md`](crt-spine.md) and [`scoring-engines.md`](scoring-engines.md). The economic verdict
lives in `docs/current-findings.md` **F-004**; capital posture for "BitNet V2" is **FROZEN** in the
Funding Ledger.

## Discussion (filled in-session)
- **Risks:** 2026-06-05 — a single static `0.55` gates the whole path; mis-set threshold or a model
  regression silently kills throughput. No adaptive/regime threshold exists despite the design intent.
- **Ambiguities:** 2026-06-05 — `bitnet_inference.py` uses JSON model schemas, **not** GGUF (despite
  "GGUF" language elsewhere in the docs); the GGUF path is for the separate zone/BitNet artifacts.
- **Enhancements:** 2026-06-05 — F-004 notes the regime-adaptive threshold is the dormant piece; any
  reopen must clear the Funding-Ledger FROZEN reopen conditions first.
