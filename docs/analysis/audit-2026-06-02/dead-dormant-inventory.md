# 7 · Dead / Dormant / Sidecar Inventory — Constraint 3

> Point-in-time audit, 2026-06-02. Components that exist but don't affect PnL today, with a
> keep / remove / wire-and-measure call for each. The through-line: **enablement ≠ consumption.**
>
> **⚠ SUPERSEDED IN PART by 2026-06-03 findings (do not action the calls below without checking the living docs):**
> (1) The TradeNet v2 "**designed-not-built**" call (Orphaned table) is **reversed by F-005** — TradeNet v2 is *BUILT but unwired* (`training/trade_net_v2.py` complete; fusion slot stub `fusion_engine.py:8`). (2) The ReplayMemory "**wire-and-measure later via probability-surface-advisory**" call predates the **2026-06-03 KILL** of Probability Surface V2 (Funding Ledger, evidence F-001/F-012). See [`docs/current-findings.md`](../../current-findings.md) for current truth; this archived analysis is kept dated for replay.

## Dormant (Exists=YES, Wired=YES, Active=NO)

| Component | Why dormant | Recommendation |
|-----------|-------------|----------------|
| **CognitiveBus** | gated by absent `cognitive_layer` in ACTIVE config; emits DecisionSnapshot telemetry only (`engine_runner.py:439-446,1059`) | **Keep** (designed advisory-only; cheap). Document as telemetry; do not credit with ROI. |
| **ReplayMemory (RME)** | consumed only via CognitiveBus (off); schema repaired 2026-06-02; registries wired in v1 only | **Wire-and-measure later** via `probability-surface-advisory` (weight 0.0 first). Edge marginal (≤+0.09R) — measure before trusting. |

## Orphaned (Exists=YES, Wired=NO)

| Component | Status | Recommendation |
|-----------|--------|----------------|
| **TradeNet v2 / TradeNetMetaEngine** | never in `engine_results`; fusion neural slot is a **stub** (`fusion_engine.py:8`); v2 3-head designed-not-built | **Decide:** either build+wire v1 consumption first (prove the slot adds edge) or **shelve** v2. Do not carry as "intelligence we have." |
| **Scanner / SignalPool** | not imported in any live path | **Remove or move to `tools/`** unless a multi-symbol scan roadmap is active. |
| **ForwardTester (×2: bitnet, llm_research)** | offline validation only | **Keep in training/tooling**, document as non-production. |
| **DecisionEngine FIX-4 force-accept** | only in `decide_batch()` (`decision_engine.py:185-196`); batch path = orphaned scanner | **Largely inert**; remove the fallback or document it can't fire in the live per-candle path. |

## Built-but-not-consumed signals (the core C3 pattern)

| Signal | Built | Consumed? | The gap |
|--------|-------|-----------|---------|
| **BitNet score @ entry** | yes (compute) | **NO** | not persisted to `TradeRecord` (`backtest_v2.py:200`; CSV 70 cols, 0× `bitnet_*`) → adaptive-threshold loop has no data; threshold stuck at `0.5` (`bitnet_runner.py:130`) |
| **Zone EXPECTANCY (mean_rr)** | yes (stored on zones) | **NO** | spine uses zone *geometry* only; expectancy ignored |
| **Concept drift** | yes (detected) | **NO (no gate)** | `live_engine_hook.py:676` logs "Trade signal unreliable" — trade proceeds |
| **Regime fusion weights** | yes (config map) | **NO** | `compute()` uses static 0.4/0.2/0.2/0.2; regime map unused on the live path |
| **Strategy orchestrator consensus** | yes (wired) | **NO (inert)** | enabling it = byte-identical backtest; consensus path doesn't alter decisions |
| **Probability Surface** | **NO (not built)** | — | plan SCOPED only |

## Feedback loop — built but operationally inert for live (`velvety-gosling`)

| Break | Effect | Severity |
|-------|--------|----------|
| Break 2 | live `TradeRecord` lacks the 35-dim feature vector → can't build a training dataset from live trades | **HIGH** |
| Break 3 | no in-session hot reload → a promoted model takes effect only on **process restart** | **HIGH** |
| Break 1 | `discover_zones.py` orphaned from `auto_train_from_opportunities.py` (manual 2nd step) | MED |
| Break 4 | promotion failure logged to Python log, not `integrity_events.jsonl` | MED |
| Break 5 | no programmatic/drift trigger (CLI-only) | MED |

## Read of the inventory

The system is **rich in built intelligence and poor in consumption**. Almost nothing here is "missing
code" — it is code whose output never reaches the decision. That is precisely why **adding more
intelligence is low-ROI**: there is a backlog of *already-built* signals waiting to be wired and measured.
The disciplined path is **wire-and-measure (weight 0.0 → earn weight)**, starting with the one that protects
capital (drift → size-down). → [top-10-roi-actions.md](top-10-roi-actions.md) #3.
