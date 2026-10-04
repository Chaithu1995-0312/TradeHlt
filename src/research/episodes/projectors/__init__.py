"""Episode projectors — different sources, one canonical schema.

| Projector  | Input                                | Population        |
|------------|--------------------------------------|-------------------|
| detection  | opportunities.jsonl geometry + candles | DETECTION_STREAM  |
| hypothesis | research.contracts.Signal + candles    | HYPOTHESIS_SIGNAL |
| spine      | TradeRecord / journal + candles         | SPINE_TRADE       |

All are OFFLINE. Nothing in the live or backtest hot path may write episodes
(substrate §15) — the production ledger is read, never extended.
"""
