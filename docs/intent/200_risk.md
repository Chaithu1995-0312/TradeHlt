# Domain Contract: Risk

## Purpose
Protect capital from catastrophic loss through multiple independent gates: position-level (UltronRiskGate), account-level (KillSwitch), portfolio-level (correlation engine, drawdown caps), and drift-level (FeatureMonitor).

## Why does this exist?
The user thought: *"I want to survive a string of losses. One bad trade should not end the account; one bad week should pause trading; one regime change should be detected, even if not yet acted upon."*

**Evidence:** goal.md:25–30 (priorities); assistant_project.md:1500–1527 (KillSwitch, MonteCarlo) — Confidence: Certain

## Authority
- **Owns:** trade-level approval (UltronRiskGate), daily/weekly loss limits (KillSwitch), drift detection (FeatureMonitor).
- **Decides:** APPROVE/REJECT per trade; TRIPPED/RESET for kill switch; WARNING for drift.
- **Must NOT:** Allow a trade to execute without UltronRiskGate approval.
- **Must NOT:** Allow LLM override of any risk gate.

## Must (Required Behaviors)
1. UltronRiskGate.evaluate() must be called for every ExecutionPlan BEFORE dispatch.
2. KillSwitch must track daily and weekly realized PnL with date rollover.
3. KillSwitch must block new trades when daily or weekly limit is exceeded (TRIPPED state).
4. FeatureMonitor must detect HARD drift (Z > 3.0) and log WARNING.
5. Config-driven risk parameters (max_risk_per_trade_pct, max_drawdown, etc.) must be read from the active governed config.

## Must Never (Forbidden Behaviors)
1. Must NEVER allow an LLM to bypass or override a risk gate decision.
2. Must NEVER silently reset KillSwitch state (must be explicit reset()).
3. Must NEVER let a HARD drift event silently pass without at least a WARNING log.
4. Must NEVER hot-swap risk parameters mid-session (requires restart + governed config change).

## Failure Modes
| Failure | Detection | Severity |
|---------|-----------|----------|
| FeatureMonitor drift detected but not acted on (no block/size-down) | F-008 | HIGH |
| KillSwitch file path hardcoded (ultron_risk_gate.py:44) | codebase-state-map.md §3 | MEDIUM (blocks multi-instance) |
| UltronRiskGate NOT exercised in backtest spine | F-010 | HIGH (backtest-vs-live divergence) |
| Correlation engine + PortfolioAllocator built but NOT wired into live path | F-013 | MEDIUM |

## Economic Meaning
Risk gates are the LAST line of defense — they prevent the worst-case scenario (account destruction) but cannot create alpha. The research program (F-025) confirmed that risk management (wider stops, lower position sizes) reduces drawdown and cost drag but does NOT produce positive expectancy. Risk is a hygiene function, not an alpha source.

**Evidence:** F-010, F-025 — Confidence: Likely

## Unknowns
- Whether drift detection → position size-down would improve live outcomes (currently detected but unacted).
- Whether KillSwitch integration with the research spine would change research outcomes.

## Evidence
- F-008 (drift detected not acted on) — Confidence: Certain
- F-010 (live PnL UNVERIFIED) — Confidence: Likely
- F-013 (portfolio risk NOT enforced live) — Confidence: Certain
- F-025 (exit/cost is risk lever, not expectancy) — Confidence: Likely
- codebase-state-map.md §3 item 5 — Confidence: Certain