# Domain Contract: Execution

## Purpose
Score every M15 candle through four independent engines, fuse the scores, decide whether to trade, plan the entry/SL/TP/RR/TTL, and approve/reject the plan through the risk gate.

## Why does this exist?
The user thought: *"I want four independent opinions (CRT/Gaussian/Zone/RR) fused into one decision, then a plan, then a risk check — not a black box that says 'buy' or 'sell'."* The execution spine is where trading decisions are made.

**Evidence:** goal.md:34–70 (happy flow); signal-flow.md:23–112 — Confidence: Certain

## Authority
- **Owns:** Every decision between candle ingestion and order dispatch.
- **Decides:** Whether to trade (DecisionEngine), how to trade (ExecutionPlanner), whether the trade is safe (UltronRiskGate).
- **Must NOT:** Allow any single engine's absence to produce a partial trade.
- **Must NOT:** Allow the LLM to influence the decision path (only advisory tap).

## Must (Required Behaviors)
1. All 4 engines must score every candle (EXPECTED_ENGINES completeness check).
2. Fusion must combine all 4 scores or reject (no partial fusion).
3. DecisionEngine must apply a config-governed threshold (score_threshold).
4. ExecutionPlanner must produce entry/SL/TP/RR/TTL for ACCEPTED decisions.
5. UltronRiskGate must evaluate every planned trade (7-check waterfall).
6. The CRT state machine (process_candle) must enforce VALID_TRANSITIONS — illegal state jumps are rejected.

## Must Never (Forbidden Behaviors)
1. Must NEVER fuse fewer than 4 engine scores.
2. Must NEVER allow the LLM to approve or reject a trade (advisory only, observed only).
3. Must NEVER skip UltronRiskGate (no bypass for any trade plan).
4. Must NEVER allow lookahead in backtest replay (candle-by-candle only).
5. Must NEVER produce a trade plan with invalid geometry (TP below entry on long, etc.).

## Failure Modes
| Failure | Detection | Severity |
|---------|-----------|----------|
| Missing engine | Hard reject (set diff) | LOW (designed behavior) |
| Gate divergence (backtest vs live) | F-010 (live PnL UNVERIFIED) | HIGH |
| CRT illegal transition | VALID_TRANSITIONS guard | HIGH |
| Score/zone gate non-binding (F-021) | Research measurement | MEDIUM (design issue, not runtime) |
| Slippage model differs between backtest and live | Not currently measurable | MEDIUM |

## Economic Meaning
The execution spine is the production system's core value proposition. However, the research program (F-019/020/021/025) has shown that under intrabar_exit + 12bps cost, the spine produces NO positive-expectancy edge on crypto majors. The spine IS correct code that faithfully implements the chosen market ontology — but that ontology has been empirically falsified for its target universe.

**Evidence:** F-019, F-020, F-021, F-025 — Confidence: Likely

## Unknowns
- Whether a different instrument class (FX, equities) or timeframe (H1, D1) would show edge.
- Whether the spine's performance under realistic slippage (12bps flat vs seeded random) differs materially.
- Whether the live UltronRiskGate (not exercised in backtest) would change the spine's net economics.
- Score isolation: Gaussian/Zone/RR engines were NEVER individually measured — the F-002/F-021 edge attribution may change if they are.

## Evidence
- signal-flow.md:23–112 (Steps 1–7) — Confidence: Certain
- codebase-state-map.md:84–93 (decision spine stages) — Confidence: Certain
- F-002 (edge is in PROCESS, not features) — Confidence: Likely
- F-021 (selection = session only) — Confidence: Likely
- F-025 (exit/cost is risk lever, not expectancy) — Confidence: Likely