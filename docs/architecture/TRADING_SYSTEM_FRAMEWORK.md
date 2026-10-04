# Trading System Framework: First-Principles Architecture

> **Purpose:** This document defines the *ideal* architecture for a multi-market, multi-style,
> multi-strategy trading system — derived from first principles, not from any existing codebase.
> It serves as the reference baseline for evaluating real-world implementations.
>
> **Status:** Reference framework (general knowledge, not codebase-specific).
> **Date:** 2026-06-15

---

## Hierarchy (Top to Bottom)

```
 Level 0: Universal Trading Kernel       (domain-independent plumbing)
 Level 1: Market Domain Layer            (crypto / forex / equities / futures / options)
 Level 2: Trading Style Layer            (trend / reversion / momentum / reaction / stat-arb / etc.)
 Level 3: Strategy Layer                 (concrete rule sets per style)
 Level 4: Intelligence / AI Layer        (regime / drift / optimization — optional, only after 1-3)
 Level 5: Risk Layer                     (pre-trade, in-trade, portfolio)
 Level 6: Execution Layer                (order dispatch, venue routing, slippage model)
```

---

# Level 0: Universal Trading Kernel

**Scope:** Everything that is *domain-independent*. These components should work identically for crypto, forex, equities, or futures with zero code changes.

## Components

### 0.1 Market Data Ingestion

```
Input:  Raw OHLCV (CSV, API, feed)
Output: Canonical Candle object (timestamp, open, high, low, close, volume)
```

Rules:
- Normalize all timestamps to UTC epoch ms
- Detect gaps > 2x expected bar interval → flag, don't fill silently
- Validate monotonic timestamps per instrument
- Reject bars with zero volume unless explicitly configured
- One canonical candle format for all domains

### 0.2 Feature Pipeline

```
Input:  Window of N candles + derived indicators
Output: Feature vector (float array) of fixed dimension D
```

Domain-independent features (examples):
- Log returns (1-bar, rolling mean/std)
- Normalized volume (z-score over window)
- ATR (Average True Range) — price-scaled
- Rolling min/max/range
- Gap detection (overnight/weekend normalized)
- Time-to-bar-close (normalized 0-1)

Rules:
- Feature pipeline is a **function of candle window only** — no domain-specific calendars
- NaN propagation: feature must return NaN or valid float, never array shape change
- Feature schema is versioned and hash-protected

### 0.3 Backtest Runner

```
Input:  Historical candles + feature window + strategy instance
Output: List of Trade objects (entry_time, entry_price, exit_time, exit_price, pnl)
```

Rules:
- Strict candle-by-candle streaming — no lookahead
- Deterministic: same config + same data → same trade list (byte-identical)
- Accepts any strategy implementing the canonical interface:
  ```python
  class Strategy:
      def compute(self, candle: Candle, features: np.ndarray, state: dict) -> Signal
  ```

### 0.4 Trade Object Schema

```python
@dataclass
class Trade:
    entry_time: int        # UTC epoch ms
    entry_price: float
    direction: int         # 1 = long, -1 = short
    sl_price: float
    tp_price: float
    exit_time: int
    exit_price: float
    pnl: float             # net after cost
    rr_achieved: float     # realized R multiple
    strategy_tag: str      # which strategy produced this
    domain_tag: str        # which domain
```

### 0.5 Evaluation Metrics

- Win rate, total trades, expectancy (mean R)
- Sharpe ratio (annualized, using trade returns series)
- Max drawdown (equity curve)
- Profit factor (gross win / gross loss)
- Average hold time
- Percent profitable in OOS
- Confidence interval on expectancy (bootstrapped)

### 0.6 Logging & Audit

- JSONL append-only per run
- Candle index → features → signal → trade → exit (full chain)
- No PII, no secrets in logs
- Structured fields for queryability

---

# Level 1: Market Domain Layer

**Scope:** Separates the system by market — each domain defines its own *physics*.

## Domain Contract

```python
class TradingDomain(ABC):
    @abstractmethod
    def calendar(self) -> TradingCalendar
    @abstractmethod
    def cost_model(self, instrument: str) -> CostModel
    @abstractmethod
    def leverage_model(self) -> LeverageModel
    @abstractmethod
    def position_rules(self) -> PositionRules
    @abstractmethod
    def risk_rules(self) -> RiskRules
    @abstractmethod
    def allowed_styles(self) -> list[str]
```

## 1.1 Trading Calendar

| Domain | Sessions | Gaps | Week |
|--------|----------|------|------|
| Crypto Spot | None — continuous | None | 24/7 |
| Crypto Futures | Funding events | None | 24/7 |
| Forex | Tokyo, London, NY, Overlap | Weekends only | 24/5 Sun 17:00 - Fri 17:00 |
| Equities (US) | Pre-market, Regular, After-hours | Overnight, weekends, holidays | Mon-Fri 9:30-16:00 |
| Futures (ES/NQ) | Nearly continuous | Maintenance break (30 min) | Sun 18:00 - Fri 17:00 |
| Options | Same as underlying | + Expiry day | Same as underlying |

**Implementation:**

```python
@dataclass
class TradingCalendar:
    session_bounds: list[SessionBound]  # [(start_hour, end_hour, timezone), ...]
    holidays: list[int]                  # UTC epoch ms of closed days
    gap_handling: str                   # "fill_flat" / "fill_previous" / "reject"
    weekly_break: Optional[tuple[int, int]]  # (start_hour_utc, end_hour_utc)
```

**Critical:** Calendar affects:
- Gap detection parameters (a 16-hour gap in crypto is abnormal; in equities it's just overnight)
- Session-specific feature computation (normalize volume by session, not by absolute time)
- Strategy availability (scalping strategies are disabled outside liquid sessions)

## 1.2 Cost Model

Each domain has different cost structure:

| Domain | Cost Components |
|--------|----------------|
| Crypto Spot | Taker fee (0.05-0.10%), spread, withdrawal cost |
| Crypto Futures | Taker fee, spread, funding rate (8h) |
| Forex | Spread only (no commission in retail), swap/rollover O/N |
| Equities | Commission per share, SEC fee, spread, short borrow cost |
| Futures | Commission per contract, exchange fees, NFA fees |

```python
@dataclass
class CostModel:
    taker_fee: float           # as fraction of notional
    maker_fee: float
    min_commission: float
    spread_bps: float          # estimated spread in bps
    periodic_cost: float       # per-hour holding cost (funding/swap)
    periodic_cost_interval_h: float  # hours between periodic costs
```

**Critical:** Cost model determines whether a strategy is viable. A strategy that makes 0.5R per trade in zero-cost backtest can lose money in real markets with 12bps cost.

## 1.3 Leverage Model

| Domain | Leverage | Margin Type |
|--------|----------|-------------|
| Crypto Spot | 1x (no leverage) | None |
| Crypto Futures | Up to 125x | Cross/Isolated |
| Forex | Up to 50x (retail) | Margin-based |
| Equities (US) | 2x (Reg T) for day trades | Margin |
| Futures | Varies (ES ~20x) | Initial + Maintenance margin |

```python
@dataclass
class LeverageModel:
    max_leverage: float
    margin_type: str           # "cash" / "cross" / "isolated" / "reg_t"
    maintenance_margin_pct: float
    liquidation_buffer_pct: float  # distance from liquidation price
```

## 1.4 Position Rules

```python
@dataclass
class PositionRules:
    allow_short: bool
    min_notional: float
    size_increment: float      # e.g., 0.001 for BTC
    price_precision: int       # decimal places
    max_positions_same_instrument: int
    max_positions_total: int
```

## 1.5 Domain-Specific Risk Rules

```python
@dataclass
class RiskRules:
    max_daily_loss_pct: float
    max_drawdown_pct: float
    max_correlation_exposure: float   # max fraction of capital in correlated bets
    volatility_scaling: bool          # size down when vol spikes
    gap_risk_buffer_pct: float        # reserved capital for gap risk
    liquidation_risk_monitoring: bool # only for leveraged domains
```

## 1.6 Domain Implementations (Stubs)

| Domain | Example Instruments | Python Class |
|--------|-------------------|-------------|
| Crypto Spot | BTCUSDT, ETHUSDT, SOLUSDT | `CryptoSpotDomain` |
| Crypto Futures | BTCUSDT_PERP, ETHUSDT_PERP | `CryptoFuturesDomain` |
| Forex | EURUSD, GBPUSD, AUDUSD | `ForexDomain` |
| US Equities | AAPL, SPY, QQQ | `EquityDomain` |
| Futures | ES, NQ, CL, GC | `FuturesDomain` |
| Options | SPY options, Nifty options | `OptionsDomain` |

---

# Level 2: Trading Style Layer

**Scope:** Behavioral philosophy — *how* the system interacts with price.

## Style Contract

```python
class TradingStyle(ABC):
    @abstractmethod
    def name(self) -> str
    @abstractmethod
    def allowed_strategies(self) -> list[str]
    @abstractmethod
    def preferred_instruments(self, domain: TradingDomain) -> list[str]
    @abstractmethod
    def max_hold_bars(self) -> int
    @abstractmethod
    def regime_preferences(self) -> list[str]  # "trending" / "ranging" / "volatile" etc.
```

## 2.1 Trend Following

**Belief:** Markets trend. The trend persists longer than the noise expects.

| Property | Value |
|----------|-------|
| Hold time | Hours to weeks |
| Signal frequency | Low (1-10 per month) |
| Win rate target | 30-45% |
| RR target | 2:1 to 5:1 |
| Edge source | Patience — ride the move |
| Best regime | Trending (ADX > 25) |
| Worst regime | Ranging (ADX < 20) |

**Domain compatibility:**
- Crypto: ✓ (24/7, strong trends, but violent pullbacks)
- Forex: ✓ (currency trends can last months)
- Equities: ✓ (sector rotation, macro trends)
- Futures: ✓ (commodity super-cycles)
- Options: ✗ (different paradigm)

## 2.2 Mean Reversion

**Belief:** Markets over-extend and snap back.

| Property | Value |
|----------|-------|
| Hold time | Minutes to days |
| Signal frequency | Medium (1-20 per day) |
| Win rate target | 55-75% |
| RR target | 1:1 to 2:1 |
| Edge source | Statistical extreme → snap-back |
| Best regime | Ranging (Bollinger squeeze, low vol) |
| Worst regime | Trending (can be run over) |

**Domain compatibility:**
- Crypto: ✓ with wide bands (0.5-1 ATR due to volatility)
- Forex: ✓ (range-bound during session overlaps)
- Equities: ✓ (VWAP deviation, overnight gaps)
- Futures: ✓ (mean reversion in ES common)
- Options: ✗ (time decay makes reversion expensive)

## 2.3 Momentum

**Belief:** Recent moves beget more moves (serial correlation).

| Property | Value |
|----------|-------|
| Hold time | Hours to days |
| Signal frequency | Medium |
| Win rate target | 40-55% |
| RR target | 1.5:1 to 3:1 |
| Edge source | Early recognition of acceleration |
| Best regime | Trending + high volume |
| Worst regime | Choppy / low volume |

**Domain compatibility:** Similar to trend following but shorter horizon.

## 2.4 Reaction-Based (ICT / Structure / Trap)

**Belief:** Price reacts to identifiable liquidity zones and structure.

| Property | Value |
|----------|-------|
| Hold time | Minutes to hours |
| Signal frequency | High (per session) |
| Win rate target | 50-65% |
| RR target | 1.5:1 to 3:1 |
| Edge source | Reading intent through price structure |
| Best regime | Any (structure-independent) |
| Worst regime | News-driven (structure breaks) |

**Domain compatibility:**
- Crypto: ✓ (structure respected, especially on majors)
- Forex: ✓ (ICT was designed for forex)
- Equities: ✗ (gap risk breaks structure)
- Futures: ✓ (ES respects structure)

## 2.5 Statistical Arbitrage

**Belief:** Related instruments converge.

| Property | Value |
|----------|-------|
| Hold time | Minutes to days |
| Signal frequency | Low |
| Win rate target | 60-80% |
| RR target | 1:1 to 2:1 |
| Edge source | Cointegration — temporary divergence |
| Best regime | Stable correlation |
| Worst regime | Correlation breakdown (macro shocks) |

**Domain compatibility:**
- Crypto: ✓ (BTC-ETH correlated)
- Forex: ✓ (EUR-GBP, AUD-NZD pairs)
- Equities: ✓ (sector pairs, ETF-constituents)
- Futures: ✓ (calendar spreads, commodity spreads)
- Options: ✓ (volatility surface arb)

## 2.6 Breakout / BOS

**Belief:** Structure breaks signal directional continuation.

| Property | Value |
|----------|-------|
| Hold time | Hours to days |
| Signal frequency | Low (1-5 per day) |
| Win rate target | 40-50% |
| RR target | 2:1 to 4:1 |
| Edge source | Genuine structure break vs fakeout |
| Best regime | Trending + expanding volatility |
| Worst regime | Choppy / fakeout-prone |

## 2.7 Pattern Recognition

**Belief:** Recurring candlestick/chart patterns have predictive value.

| Property | Value |
|----------|-------|
| Hold time | Minutes to hours |
| Signal frequency | Medium |
| Win rate target | 50-60% |
| RR target | 1.5:1 to 2.5:1 |
| Edge source | Statistical edge of pattern |
| Best regime | Medium volatility |
| Worst regime | Extremely low or high volatility |

## 2.8 Grid / Market Making

**Belief:** Price oscillates within a range. Collecting range-bound movement is profitable.

| Property | Value |
|----------|-------|
| Hold time | Seconds to hours |
| Signal frequency | High (continuous) |
| Win rate target | 70-90% |
| RR target | 0.5:1 to 1:1 |
| Edge source | Range capture + spread |
| Best regime | Ranging |
| Worst regime | Trending (grid gets blown) |

---

# Level 3: Strategy Layer

**Scope:** Concrete rule systems that implement a style.

## Strategy Contract

```python
class Strategy(ABC):
    @abstractmethod
    def name(self) -> str
    @abstractmethod
    def style(self) -> str          # which TradingStyle this belongs to
    @abstractmethod
    def compute(self, candle: Candle, features: np.ndarray, state: dict) -> Optional[Signal]
    @abstractmethod
    def config_schema(self) -> dict  # JSON schema for config validation
    @abstractmethod
    def warmup_bars(self) -> int     # minimum bars before producing signals
```

## 3.1 Strategies by Style

### Trend Following Strategies

| Strategy | Key Logic | Best Instruments |
|----------|-----------|-----------------|
| **MA Cross** | Fast MA crosses above slow MA → long | Any trending |
| **Ichimoku** | Price above cloud, TK cross, lagging span above price | Any |
| **ADX + DI** | ADX > 25, +DI > -DI → long | Any trending |
| **Parabolic SAR** | SAR flips → signal | Strong trends only |
| **Supertrend** | ATR-based trailing stop flip | Any |
| **Chandelier Exit** | Long exit = 22-bar high - 3x ATR | Not a signal, but an exit |

### Mean Reversion Strategies

| Strategy | Key Logic | Best Instruments |
|----------|-----------|-----------------|
| **RSI Band** | RSI(14) < 30 → long, > 70 → short (with band exit) | Crypto, FX |
| **Bollinger %B** | Price touches lower BB(20,2) → long, upper → short | Equities, FX |
| **VWAP Deviation** | Price > 2 std dev below VWAP → long | Equities (highly effective) |
| **Z-Score of Spread** | Pair spread Z > 2 → revert | Pairs |
| **Kalman Filter** | Estimated price diverges from actual → revert | Pairs |

### Momentum Strategies

| Strategy | Key Logic | Best Instruments |
|----------|-----------|-----------------|
| **MACD Histogram** | Histogram turns up from below zero → long | Any |
| **Rate of Change** | ROC(12) > threshold → long | Any |
| **KAMA** | Kaufman's adaptive MA slope → signal | Trending only |
| **Volume Weighted MACD** | MACD weighted by volume → signal | High volume |
| **Connor's RSI** | 3-line RSI combo → signal | Equities |

### Reaction-Based Strategies

| Strategy | Key Logic | Best Instruments |
|----------|-----------|-----------------|
| **CRT (ICT)** | Killzones → displacement → sweep of liquidity → retest → entry | FX, Crypto |
| **Supply/Demand** | Identify institutional zones → price returns → entry | Any |
| **Breaker Block** | Last bullish/bearish candle before displacement → entry | FX, Crypto |
| **Order Flow Imbalance** | Delta divergence → reversal | Futures, Equities |
| **Liquidity Sweep** | Sweep of previous high/low → rejection → counter-move | Any (needs liquidity) |

### Breakout Strategies

| Strategy | Key Logic | Best Instruments |
|----------|-----------|-----------------|
| **Donchian Channel** | Price closes above 20-bar high → long | Any |
| **BOS + Volume** | Structure break + volume > 1.5x avg → signal | Any |
| **ATR Channel Break** | Price breaks 2x ATR channel → signal | Crypto, FX |
| **Opening Range Breakout** | Break of first 30-min range → signal | Equities, Futures |
| **Triangle Breakout** | Ascending/descending/symmetrical triangle break | Any |

### Pattern Strategies

| Strategy | Key Logic | Best Instruments |
|----------|-----------|-----------------|
| **Single Candle** | Hammer, Shooting Star, Marubozu, Doji | Any |
| **Two Candle** | Bullish/Bearish Engulfing, Harami, Piercing | Any |
| **Three Candle** | Morning/Evening Star, 3 White Soldiers | Any |
| **Chart Patterns** | H&S, Double Top/Bottom, Wedge, Flag | Any (time-intensive) |
| **P&F Patterns** | Double Top/Bottom, Triple Top/Bottom, Bull/Bear Trap | Any (swing) |

### Statistical Arbitrage Strategies

| Strategy | Key Logic | Best Instruments |
|----------|-----------|-----------------|
| **Pair Z-Score** | Cointegrated pair, Z > 2 → short spread | Sector pairs |
| **Index Arbitrage** | ETF vs constituents divergence → basket trade | Equities |
| **Calendar Spread** | Same commodity, different expiry → convergence | Futures |
| **PCA Residual** | PCA on sector, trade residual mean-reversion | Equities |
| **Cross-Exchange** | Same asset, different venue → arbitrage | Crypto |

## 3.2 Strategy Configuration (JSON Schema)

Every strategy has a config block:

```json
{
  "s01_ma_cross": {
    "enabled": true,
    "fast_period": 10,
    "slow_period": 50,
    "min_volume_ratio": 1.0,
    "session_restriction": "london,new_york,overlap",
    "regime_restriction": "trending",
    "min_adx": 25,
    "max_spread_bps": 2.0,
    "warmup_bars": 60
  }
}
```

## 3.3 Strategy Selection (Runtime)

**Question:** Which strategy gets capital this bar?

Multiple approaches:
1. **Weighted ensemble** — all strategies vote, weight by past performance
2. **Meta strategy** — classifier selects which strategy is active per regime
3. **Competition** — strategies compete for capital daily (performance-weighted)
4. **Fixed priority** — defined priority order, first valid signal wins

**Best practice:** Regime-conditional selection. Strategy S1 may win in trending markets but lose in ranging. Strategy S2 wins in ranging. A regime classifier routes capital accordingly.

---

# Level 4: Intelligence / AI Layer

**Scope:** Optional — layered *above* domain/style/strategy. Only added after Levels 1-3 are verified.

## 4.1 Where AI Belongs (AND DOES NOT BELONG)

| Role | Belongs? | Why |
|------|----------|-----|
| Strategy signal generator | ✗ NO | Strategies are deterministic rule sets. AI predictions add black-box risk. Test the rules first. |
| Regime classifier | ✓ YES | Classify market state (trending/ranging/volatile) to route strategies |
| Execution quality model | ✓ YES | Predict slippage, optimal order type, venue routing |
| Drift detector | ✓ YES | Detect strategy decay, feature distribution shift, regime change |
| Research assistant | ✓ YES | Generate candidate strategies, parameter ranges to explore |
| Meta-optimizer | ✓ YES | Suggest config adjustments based on performance decay |
| **Primary trade decision** | **✗ NO** | Never let AI decide the final trade signal. AI is advisory, not executive. |

## 4.2 AI Modules

### Regime Model

```
Input:  Feature vector (returns, volatility, correlation, volume, adx, etc.)
Output: Regime label ["trending", "ranging", "high_vol", "low_vol", "breaking_down", etc.]
Use:    Route capital to appropriate strategies per regime
```

### Execution Model

```
Input:  Signal direction, instrument, current spread, order book state, volatility
Output: Predicted slippage, recommended order type (market/limit/iceberg)
Use:    Adjust TP/SL for expected slippage
```

### Drift Detector

```
Input:  Rolling window of features
Output: Drift Z-score per feature, overall drift alert (> 3.0 HARD, > 2.5 SOFT)
Use:    Pause strategies that rely on drifted features
```

### Performance Decay Monitor

```
Input:  Rolling win rate, expectancy, Sharpe over last N trades
Output: Performance trend (improving / stable / decaying / degraded)
Use:    De-weight decaying strategies, investigate root cause
```

## 4.3 Strict Constraints on AI

1. **AI NEVER makes the final trade decision.** Trade decisions are made by deterministic strategy rules. AI may *influence* sizing or routing, never the binary go/no-go.
2. **AI output is always advisory.** Every AI module has a fallback path (neutral 1.0, zero adjustment, etc.)
3. **All AI modules are optional.** The system runs without them at full functionality.
4. **AI models are versioned and promoted** through the same governance pipeline as strategy configs.
5. **No AI module has write-access to execution.** Only risk gates and the execution layer can change order parameters.

---

# Level 5: Risk Layer

**Scope:** Protect capital. Operates across domains, styles, and strategies.

## 5.1 Pre-Trade Risk (before a signal becomes an order)

```python
class PreTradeRiskGate:
    def evaluate(self, proposed_signal: Signal, portfolio_state: PortfolioState) -> GateResult
```

Checks:
1. **Max daily loss reached?** → REJECT all new trades
2. **Max drawdown reached?** → REJECT all new trades
3. **Max positions per instrument?** → REJECT if at limit
4. **Max positions total?** → REJECT if at limit
5. **Min time between trades?** → REJECT if too soon
6. **Correlation check?** → REJECT if new trade increases correlated exposure beyond threshold
7. **Sizing check?** → Validate position size ≤ max_position_size
8. **Volatility check?** → Size down if VIX / ATR spikes
9. **Regime check?** → REJECT if strategy style is incompatible with current regime

## 5.2 In-Trade Risk (after position is open)

```python
class InTradeRiskManager:
    def update(self, open_trades: list[OpenTrade], market_data: MarketData) -> list[RiskAction]
```

Actions:
1. **Breakeven** — Move SL to breakeven after price moves X% in favor
2. **Trailing stop** — Update SL to trail at N x ATR
3. **Partial take-profit** — Close X% at TP1, rest at TP2
4. **Time stop** — Close if hold time exceeds max
5. **Liquidation monitor** — For leveraged positions, check distance to liquidation
6. **Funding rate check** — For crypto futures, close if funding negative and holding direction is costly
7. **Gap protection** — If market gapped past SL, use market order to close

## 5.3 Portfolio Risk

```python
class PortfolioRiskManager:
    def check_exposure(self, portfolio: PortfolioState) -> dict
```

Metrics:
1. **Net exposure** = sum(direction * position_size) / total_capital
2. **Gross exposure** = sum(abs(position_size)) / total_capital
3. **Concentration** = max(position_size) / total_capital
4. **Sector exposure** = exposure_per_sector / total_capital
5. **Correlation risk** = portfolio variance under correlated moves
6. **Leverage check** = gross_exposure ≤ max_leverage

## 5.4 Risk Rules per Domain (from Level 1)

Control parameters from `Domain.risk_rules()` feed into all three risk sub-modules.

---

# Level 6: Execution Layer

**Scope:** Converting a trade plan into a filled order, accounting for real-world frictions.

## 6.1 Execution Model Contract

```python
class ExecutionModel(ABC):
    @abstractmethod
    def execute(self, plan: ExecutionPlan, market_state: MarketState) -> ExecutionResult
    @abstractmethod
    def cost_estimate(self, plan: ExecutionPlan, market_state: MarketState) -> CostEstimate
```

## 6.2 Execution Components

### Order Types

| Type | When to Use | Slippage Risk |
|------|------------|---------------|
| Market | Need immediate fill | Highest — pays spread + impact |
| Limit | Can wait, want best price | Highest — may not fill |
| Limit with offset | Improve fill probability over pure limit | Lower fill risk |
| Iceberg | Large order, avoid revealing size | Low (hidden) |
| TWAP | Large order spread over time | Medium |
| VWAP | Match benchmark execution | Medium |

### Venue Routing (when multiple exchanges)

1. Check liquidity at each venue
2. Compare fees (taker vs maker per venue)
3. Compare current spread
4. Route to lowest-cost-expected with highest fill probability

### Slippage Model

```python
@dataclass
class SlippageModel:
    fixed_bps: float           # base cost per trade
    volume_slippage_bps: float # additional per X% of daily volume traded
    spread_cost_bps: float     # half-spread if market order
    impact_cost_bps: float     # price impact from order size
```

### Fill Simulation (for backtest)

```python
def simulate_fill(
    signal_time: int,
    signal_price: float,
    direction: int,
    volume_ratio: float,    # order size / bar volume
    spread_bps: float,
    slippage_model: SlippageModel,
    bar: Candle
) -> float:  # filled price
    # 1. Start with signal price
    # 2. Add half spread if market order
    # 3. Add volume-dependent impact
    # 4. Add fixed cost
    # 5. Clamp within bar range (if backtesting on OHLC)
```

## 6.3 Execution Audit

Every execution generates a JSONL record:

```json
{
  "timestamp": "...",
  "instrument": "BTCUSDT",
  "signal_time": "...",
  "requested_price": 50000.0,
  "filled_price": 50012.5,
  "slippage_bps": 2.5,
  "order_type": "market_limit",
  "venue": "binance",
  "fee_paid": 0.05,
  "strategy_tag": "s03_breakout",
  "domain_tag": "crypto_spot"
}
```

---

# Complete End-to-End Flow

```
Market Domain (crypto_spot)
    │
    ├── calendar = continuous 24/7
    ├── cost_model = taker 0.075%, spread 0.03%
    ├── leverage = 1x (spot)
    └── position_rules = allow_short=false, min_notional=10 USDT
    │
    ▼
Trading Style (momentum + reaction_based)
    │
    ├── momentum → [MACD Histogram, ROC]
    └── reaction → [CRT, Liquidity Sweep, Breakout]
    │
    ▼
Strategy Layer (routed by regime)
    │
    ├── Regime = trending → MACD Histogram (S8) + Breakout (S3)
    ├── Regime = ranging → CRT (S1) + Liquidity Sweep (S10)
    └── Regime = volatile → all strategies disabled, capital protected
    │
    ▼
Signal Generator (per active strategy)
    │
    ├── Feature pipeline → feature vector
    ├── Strategy rules → direction + confidence
    └── Signal = (instrument, direction, confidence, strategy_tag, style_tag)
    │
    ▼
Pre-Trade Risk Gate
    │
    ├── Daily loss limit? → PASS
    ├── Drawdown limit? → PASS
    ├── Position limit? → PASS
    ├── Correlation check? → PASS
    ├── Sizing = risk * capital / (entry - sl)
    └── Decision: APPROVE with size=0.05 BTC
    │
    ▼
Signal → Execution Plan
    │
    ├── entry_price = current ask + slippage buffer
    ├── sl_price = entry - ATR * sl_atr_mult (momentum)
    ├── tp_price = entry + ATR * tp_atr_mult (momentum)
    └── ttl_seconds = 600
    │
    ▼
Execution Model
    │
    ├── order_type = market (immediate fill needed)
    ├── venue = binance (best liquidity)
    ├── filled_price = entry_price + slippage_model(fill)
    └── ExecutionResult = (filled, price, fee, timestamp)
    │
    ▼
In-Trade Risk Manager
    │
    ├── Bar 1: price +1.5% → move SL to breakeven
    ├── Bar 3: price +3% → trail SL at 1x ATR
    ├── Bar 6: price touches TP → partial close (50%), rest to TP2
    └── Bar 10: time stop → close at market
    │
    ▼
Trade Event
    │
    ├── Entry: (time, price, size, direction)
    ├── Exit: (time, price, pnl, rr)
    ├── Evaluation: (expectancy, sharpe, win_rate updated)
    └── Audit log: JSONL append
    │
    ▼
Meta-Layer
    │
    ├── Regime model: update regime label
    ├── Drift detector: update feature drifts
    ├── Performance decay: update strategy weights
    └── AI research: flag anomalies for investigation
```

---

# Universal Kernel vs Domain vs Style vs Strategy — Boundaries Summary

| Component | Kernel | Domain | Style | Strategy |
|-----------|--------|--------|-------|----------|
| Feature pipeline | ✓ Base | ✓ Extend | ✗ | ✗ |
| Candle schema | ✓ Fixed | ✗ | ✗ | ✗ |
| Backtest runner | ✓ | ✗ | ✗ | ✗ |
| Trade schema | ✓ | ✗ | ✗ | ✗ |
| Evaluation metrics | ✓ | ✗ | ✗ | ✗ |
| Calendar config | ✗ | ✓ | ✗ | ✗ |
| Cost model | ✗ | ✓ | ✗ | ✗ |
| Leverage rules | ✗ | ✓ | ✗ | ✗ |
| Position rules | ✗ | ✓ | ✗ | ✗ |
| Pre-trade risk base | ✓ | ✓ Overrides | ✗ | ✗ |
| In-trade risk | ✓ | ✓ Overrides | ✗ | ✗ |
| Style selection | ✗ | ✓ | ✗ | ✗ |
| Strategy selection | ✗ | ✗ | ✓ | ✗ |
| Signal rules | ✗ | ✗ | ✗ | ✓ |
| Signal config | ✗ | ✗ | ✗ | ✓ |
| Regime model | ✗ | ✗ | ✓ Input | ✗ |
| Execution model | ✓ | ✓ Overrides | ✗ | ✗ |
| AI advisory | ✗ | ✗ | ✓ | ✗ |

---

## Key Architectural Principles

1. **Domain-first.** Every component knows what market it serves. A strategy loaded for crypto is structurally different from the same strategy loaded for equities.

2. **Style constrains strategy.** Not all strategies can run simultaneously. Style defines the compatibility matrix. A system running Trend Following cannot also run Grid — they contradict.

3. **AI is a passenger, not the driver.** AI modules observe, advise, and optimize — they never decide the final trade.

4. **Risk gates are non-bypassable.** Every trade passes through all three risk stages (pre-trade, in-trade, portfolio). No skip, no override.

5. **Config governs behavior.** Strategies are parameterized through config, not hardcoded. New strategies can be added without touching engine code.

6. **Evidence before authority.** A strategy earns its weight by demonstrated performance, not by design elegance. Config-first, proof-first, production-last.

7. **Deterministic backtest.** Same config + same data = same trade list. AI uncertainty never enters the backtest path.

---

## Framework Registry (machine-readable map of this hierarchy)

This hierarchy is mapped to actual code by the **Framework Registry** — an append-only JSONL
file at [`data/framework_registry.jsonl`](../../data/framework_registry.jsonl), one record per
component, each linked to its code evidence, parent/children, status, and research findings.

- **Schema + contract:** [`docs/reference/framework_registry_schema.md`](../reference/framework_registry_schema.md) (authoritative — not duplicated here).
- **Module:** [`src/governance/framework_registry.py`](../../src/governance/framework_registry.py) (`FrameworkRegistry`).
- **Seed / query / report / gap-audit / update:** `scripts/governance/{seed,query,framework_registry_report,framework_gap_audit,update}_registry*.py`.
- **CI gate:** `python scripts/governance/query_registry.py --validate` (also run inside `tests/test_framework_registry.py`).

**Status is code-verified, not asserted.** Where this document's prose disagrees with the
registry, the registry (anchored to `path:line · Symbol` evidence) wins (CLAUDE.md §6.2). Example
reconciled this build: UltronRiskGate is `extant` + wired (`disabled=false` in the active config),
not "disabled."