# Feature-Math Decision-Flip Probe — GD-001/GD-002 (Gate-2 Step 7c)

_Generated 2026-07-08T02:16:15.777040+00:00 · BNBUSDT · v2_multi_2026_04 · 70002 events · read-only._

Branch A = current (body/total_wick) vs Branch B = canonical (body/candle_range), all else fixed; decision = real EngineRunner.run() APPROVE(execute)/REJECT.

## Decision flips
| mode | approve A (current) | approve B (canonical) | flips | flip rate | canonicalizing ADDS | REMOVES |
|---|---|---|---|---|---|---|
| adaptive (real boundary) | 0 | 0 | **0** | **0.000%** | 0 | 0 |
| frozen (fixed thresholds) | 0 | 0 | 0 | 0.000% | 0 | 0 |

Distance-to-threshold among adaptive flips — |final−0.25| median 0.0000 p95 0.0000; |final−dyn| median 0.0000 p95 0.0000

Flip by reject-stage: {}
Flip rate by regime: {'neutral': 0.0, 'range': 0.0, 'trend': 0.0, 'unknown': 0.0}
Flip rate by session: {'asia': 0.0, 'london': 0.0, 'newyork': 0.0}
Flip rate by score-decile: {'d0': 0.0, 'd3': 0.0, 'd4': 0.0, 'd5': 0.0, 'd6': 0.0, 'd7': 0.0, 'd8': 0.0, 'd9': 0.0}

> Decision-flip at the REAL fusion/decision boundary. NO P&L. live-hook path is F-010-unverified and backtests bypass it (F-037) → bounds potential impact only, NOT a production-loss claim.