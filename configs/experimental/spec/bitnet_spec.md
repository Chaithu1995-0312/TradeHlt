# BitNet Trading System Specification

## Model Architecture
- Input: 6 features (gaussian_score, rr_ratio, sweep_flag, volume_spike, regime_score, liquidity_distance)
- Binary MLP with STE: Input → 16 → 8 → 1
- Activation: tanh (hidden), sigmoid (output)
- Weights constrained to {-1, +1} during training

## Data Pipeline
- Input JSONL: { "features": {...}, "pnl": float }
- Normalization: clamp, cap, scale
- Label: 1 if pnl > 0 else 0

## Inference (C++)
- Bit‑packed weights (uint64)
- XNOR + popcount for dot product
- Packed input (binary) per layer
- tanh activation, final sigmoid

## Online Learning
- Buffer size: 200 trades
- Retrain trigger: buffer size or daily
- Merge: last 800 old + all new
- Validation gate: new accuracy >= old

## Drift Detection
- Performance drift: rolling accuracy drop >10%
- Feature drift: mean shift beyond threshold (0.1)

## Regime Classification
- ranging: regime_score < 0.3
- mixed: 0.3 ≤ regime_score < 0.7
- trending: regime_score ≥ 0.7

## Hybrid Engine
- BitNet primary gate: reject if confidence < 0.6
- LLM called for 0.6 ≤ confidence < 0.8
- Fusion: deterministic rules (see config)

## Explainability
- Feature contribution via input perturbation
- Full decision trace stored in JSONL

## Portfolio Risk
- Total exposure ≤ 5%
- Correlation > 0.8 → treat as single exposure
- Sector limits: 2% per sector
- Directional bias cap: 70%
- Dynamic risk scaling: ±10% based on win rate

## Scaling
- Risk per trade: 0.5% (adjustable by tier)
- Max risk per trade: 1%
- Compounding: 50% reinvested

## Stealth Execution
- Account profiles: latency, offsets, size variation, execution probability
- Random delays, entry/exit variations
- True randomness (not seeded)

## AI CIO
- System states: AGGRESSIVE, NORMAL, CAUTIOUS, DEFENSIVE, HALTED
- State transitions based on sustained drawdown
- Output: risk multiplier, strategy weights, allow_trading flag