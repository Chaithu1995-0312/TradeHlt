# 4 · Intent → Code Gap Report (Phase D)

> Point-in-time audit, 2026-06-02. For each major planned initiative: how much is built, whether its output
> is actually *used*, what's missing, the risk, and the ROI signal. `Used` is strict (consumed by the
> decision/execution path).

| Initiative (plan) | Planned | Impl % | Used | Missing | Risk | ROI |
|-------------------|:---:|:---:|:---:|---------|------|-----|
| **Per-coin session overrides** (`v3`, `from-foamy-swan`) | YES | **100%** | **NO (parked)** | governed cutover (flip ACTIVE_VERSION + PROMOTED entry) | LOW (validated APPROVE) | **HIGH — measured +4.91%→+20.59% BNB** |
| **Governance integrity guards** (`config_integrity.py`, P1 lineage) | YES | ~90% | **NO (not enforced)** | wire as hard gate; extend `config_hash` to summary lineage | HIGH (bypass live now) | HIGH (protects all future ROI) |
| **Probability Surface advisory** (`probability-surface-advisory`) | YES | **0%** | NO | re-home to sync path; weight-0.0 measure | LOW | **UNKNOWN — edge ≤+0.09R, marginal** |
| **TradeNet v2 (3-head)** (`jazzy-lemur`) | YES | ~10% (designed) | **NO (stub slot)** | training script, inference class, per-instrument registry | MED | UNKNOWN (v1 not even consumed) |
| **BitNet adaptive threshold** (`adaptive-ritchie`) | YES | ~20% | **NO** | persist `bitnet_score_at_entry` (backtest_v2.py:200); threshold lookup; adapter | MED | UNKNOWN (no data captured) |
| **Feedback loop close** (`velvety-gosling`) | YES | ~60% | **partial** | Break 2 (live feature vector), Break 3 (hot reload), Break 1/4/5 | HIGH (loop inert for live) | MED (compounding) |
| **Regime-aware fusion weights** (`rosy-waterfall`) | YES | config-present | **NO** | compute() uses static weights, not regime map | LOW | UNKNOWN |
| **Phase-integrity hardening** (`inherited-tulip`) | YES | ~30% (Phase 1) | partial | fail-visible spine; Phases 2-3 | HIGH (silent fails) | MED |
| **Concept drift → action** (`live_engine_hook.py:676`) | implied | detect-only | **NO (no gate)** | size-down/skip on HARD drift | MED (capital) | **HIGH — protects money** |
| **Execution memory / log_query** (`snowglobe`) | YES | 0% | NO | `_ctx` envelope, `logs/index/`, `log_query.py` | LOW | LOW-MED (agent legibility) |
| **Gaussian versioning per-instrument** (`glistening-river`) | YES | partial | partial | `__active__` per-instrument isolation | MED | MED |
| **Correlation Engine v2** (`tingly-finch`) | YES | 0% | NO | rolling Pearson + TTL cache | LOW | LOW (portfolio sizing) |
| **Strategy orchestrator consensus** (S1–S10) | YES | wired | **NO (inert)** | consensus path doesn't alter decisions (byte-identical) | LOW | UNKNOWN until consumed |
| **Zone EXPECTANCY weighting** | implied | stored | **NO (ignored)** | feed mean_rr into fusion/decision | LOW | UNKNOWN (possible lever) |
| **23 pre-existing test fixes** (`splendid-biscuit`) | YES | audited | n/a | 14 are real bugs (LLM 0.5→1.0; gaussian_shadow init) | HIGH (hot-path) | MED (correctness) |

## Pattern across the gaps

The recurring shape is **built but not consumed** (Probability Surface, TradeNet, BitNet score, regime
weights, orchestrator consensus, zone expectancy, drift action). Very little is "documented but not built";
the gap is overwhelmingly **intent → *consumption*, not intent → *code*.** This is the codebase evidence for
the central thesis: the intelligence largely *exists* — it just isn't wired into the decision that makes
money, or it's parked behind a governance step.

The one **fully-built, validated, high-ROI, unused** item is the per-coin session override (v3) — the
clearest "free" return in the system.
