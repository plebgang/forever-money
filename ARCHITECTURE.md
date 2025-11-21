# SN98 ForeverMoney - Architecture Documentation

## System Architecture Overview

SN98 is a decentralized Automated Liquidity Manager (ALM) built on Bittensor. The system optimizes Uniswap V3 / Aerodrome liquidity provision through competitive strategy proposals from miners.

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Bittensor Network                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Validator  │  │  Validator  │  │  Validator  │         │
│  │      1      │  │      2      │  │      N      │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                 │                 │                 │
│         └────────┬────────┴────────┬────────┘                │
│                  │                 │                          │
│         ┌────────▼────────┐        │                         │
│         │   Metagraph     │        │                         │
│         │   (Consensus)   │        │                         │
│         └─────────────────┘        │                         │
│                                    │                          │
│  ┌──────────────────────────────────▼─────────────────────┐ │
│  │              HTTP Polling Layer                        │ │
│  └──────────────────────────────────┬─────────────────────┘ │
│                                     │                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Miner 1   │  │   Miner 2   │  │   Miner N   │         │
│  │ /predict_   │  │ /predict_   │  │ /predict_   │         │
│  │  strategy   │  │  strategy   │  │  strategy   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Strategies
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Executor Bot                              │
│              (Subnet Owner Controlled)                       │
│  - Reads winning strategy                                    │
│  - Converts to v3 NFT LP operations                          │
│  - Executes via multisig (MVP) or automated (future)        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Aerodrome / Uniswap V3 Pools                    │
│                     (Base Chain)                             │
│  - Vaults deploy liquidity                                   │
│  - Generate LP fees                                          │
│  - Accrue value for token holders                           │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Round Generation (Validator)

```
┌─────────────────────────────────────────────────────────────┐
│ Validator generates round parameters                         │
│                                                              │
│  • Pair address (e.g., WETH/USDC)                           │
│  • Target block number                                       │
│  • Inventory (amount0, amount1)                             │
│  • Constraints (max_il, min_tick_width, max_rebalances)     │
│  • Round ID                                                  │
│  • Postgres access credentials (read-only)                  │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
                   ValidatorRequest JSON
```

### 2. Strategy Proposal (Miners)

```
┌─────────────────────────────────────────────────────────────┐
│ Miner receives request and generates strategy                │
│                                                              │
│  1. Query Postgres DB for historical pool events            │
│     - Swaps, mints, burns, fee collection                   │
│     - Price movements, liquidity distribution               │
│                                                              │
│  2. Run internal model/algorithm                            │
│     - ML predictions                                         │
│     - Optimization routines                                  │
│     - Risk management                                        │
│                                                              │
│  3. Generate positions                                       │
│     - Tick ranges (tickLower, tickUpper)                    │
│     - Allocations (amount0, amount1)                        │
│     - Confidence scores                                      │
│                                                              │
│  4. Define rebalance rules (optional)                       │
│     - Trigger conditions                                     │
│     - Cooldown periods                                       │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
                   MinerResponse JSON
```

### 3. Strategy Evaluation (Validator)

```
┌─────────────────────────────────────────────────────────────┐
│ Validator evaluates all miner strategies                     │
│                                                              │
│  Step 1: Constraint Validation                              │
│  ├─ Check tick widths >= min_tick_width                     │
│  ├─ Validate allocations > 0                                │
│  └─ Pre-check rebalance rules                               │
│                                                              │
│  Step 2: Backtesting (70% score component)                  │
│  ├─ Simulate strategy using historical data                 │
│  ├─ Calculate fees collected                                │
│  ├─ Measure impermanent loss                                │
│  ├─ Compare to HODL baseline                                │
│  ├─ Verify IL <= max_il                                     │
│  ├─ Count rebalances <= max_rebalances                      │
│  └─ Calculate Net PnL vs HODL                               │
│                                                              │
│  Step 3: LP Alignment (30% score component)                 │
│  ├─ Query vault fees from database                          │
│  ├─ Calculate pro-rata share per miner                      │
│  └─ Score based on fee contribution                         │
│                                                              │
│  Step 4: Final Scoring                                      │
│  ├─ Apply top-heavy weighting (top 3 get full weight)      │
│  ├─ Calculate: score = perf*0.7 + lp*0.3                   │
│  └─ Set score=0 for constraint violations                   │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
                List[MinerScore] (ranked)
```

### 4. Weight Publishing (Validator)

```
┌─────────────────────────────────────────────────────────────┐
│ Validator publishes results to network                       │
│                                                              │
│  1. Normalize scores to weights (sum = 1.0)                 │
│  2. Set weights on Bittensor chain                          │
│     subtensor.set_weights(uids, weights)                    │
│                                                              │
│  3. Save winning strategy to file                           │
│     winning_strategy.json                                   │
│     {                                                        │
│       "winner": { uid, hotkey, scores },                    │
│       "strategy": { positions, rebalance_rule },            │
│       "metadata": { version, model_info }                   │
│     }                                                        │
└─────────────────────────────────────────────────────────────┘
```

### 5. Strategy Execution (Subnet Owner)

```
┌─────────────────────────────────────────────────────────────┐
│ Executor Bot deploys winning strategy                        │
│                                                              │
│  MVP (Manual):                                               │
│  1. Read winning_strategy.json                              │
│  2. Convert positions to v3 NFT operations                  │
│  3. Submit to multisig for approval                         │
│  4. Execute on-chain (mint/burn/collect)                    │
│                                                              │
│  Future (Automated):                                         │
│  1. Automated validation and execution                      │
│  2. Real-time monitoring and adjustment                     │
│  3. Emergency stop mechanisms                               │
└─────────────────────────────────────────────────────────────┘
```

## Database Schema

### pool_events Table

The core data source for backtesting and strategy generation.

```sql
CREATE TABLE pool_events (
    id BIGSERIAL PRIMARY KEY,
    block_number BIGINT NOT NULL,
    transaction_hash VARCHAR(66) NOT NULL,
    log_index INTEGER NOT NULL,
    pool_address VARCHAR(42) NOT NULL,
    event_type VARCHAR(32) NOT NULL,    -- 'swap', 'mint', 'burn', 'collect'
    event_data JSONB NOT NULL,          -- Event-specific fields
    timestamp BIGINT NOT NULL,
    owner_address VARCHAR(42),          -- For tracking vault ownership
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Event Types and Data Structures

**Swap Event:**
```json
{
  "amount0": "-1000000000000000000",
  "amount1": "2500000000",
  "sqrtPriceX96": "1234567890123456789012345",
  "liquidity": "1000000000000000000",
  "tick": -9200
}
```

**Mint Event (Add Liquidity):**
```json
{
  "owner": "0x...",
  "tickLower": -10000,
  "tickUpper": -9000,
  "amount0": "1000000000000000000",
  "amount1": "2500000000",
  "liquidity": "1234567890"
}
```

**Collect Event (Claim Fees):**
```json
{
  "owner": "0x...",
  "tickLower": -10000,
  "tickUpper": -9000,
  "amount0": "10000000000000000",
  "amount1": "25000000"
}
```

## Scoring Algorithm Details

### Performance Score (70%)

```python
def calculate_performance_scores(miner_metrics):
    # 1. Extract Net PnL vs HODL for all miners
    pnl_scores = {uid: metrics.net_pnl_vs_hodl for uid, metrics in miner_metrics}

    # 2. Sort by PnL (descending)
    sorted_miners = sorted(pnl_scores.items(), key=lambda x: x[1], reverse=True)

    # 3. Top N get full weight (normalized 0.5-1.0)
    top_n = sorted_miners[:3]
    for uid, pnl in top_n:
        score = normalize(pnl, min_pnl, max_pnl)  # 0.5 to 1.0
        performance_scores[uid] = max(0.5, score)

    # 4. Remaining miners get exponential decay
    for rank, (uid, pnl) in enumerate(sorted_miners[3:], start=3):
        decay = 0.5 ** ((rank - 3) / 5)
        score = 0.4 * decay  # Max 0.4, decays quickly
        if pnl > 0:  # Bonus for positive PnL
            score = max(score, 0.1)
        performance_scores[uid] = score

    return performance_scores
```

### LP Alignment Score (30%)

```python
def calculate_lp_alignment_scores(vault_fees):
    total_fees = sum(vault_fees.values())

    if total_fees == 0:
        return {uid: 0.0 for uid in vault_fees}

    # Pro-rata based on fee contribution
    return {
        uid: fees / total_fees
        for uid, fees in vault_fees.items()
    }
```

### Final Score

```python
final_score = (performance_score * 0.7) + (lp_alignment_score * 0.3)

# Apply constraint violations
if has_violations:
    final_score = 0.0
```

## Uniswap V3 Math

### Tick to Price Conversion

```python
price = 1.0001 ** tick
```

### Price to Tick Conversion

```python
tick = log(price) / log(1.0001)
```

### Liquidity Calculation

For a position with tick range [tickLower, tickUpper]:

```python
# If current price < lower bound (all token0)
L = amount0 * sqrt(P_upper) * sqrt(P_lower) / (sqrt(P_upper) - sqrt(P_lower))

# If current price in range (both tokens)
L0 = amount0 * sqrt(P) * sqrt(P_upper) / (sqrt(P_upper) - sqrt(P))
L1 = amount1 / (sqrt(P) - sqrt(P_lower))
L = min(L0, L1)

# If current price > upper bound (all token1)
L = amount1 / (sqrt(P_upper) - sqrt(P_lower))
```

## Security Considerations

### Validator Security

1. **Database Access**: Read-only credentials, public data only
2. **Miner Requests**: Timeout mechanisms, rate limiting
3. **Weight Setting**: Verified on-chain, immutable once set
4. **Error Handling**: Graceful degradation, no partial states

### Miner Security

1. **Input Validation**: Validate all request fields
2. **Resource Limits**: Prevent DoS through computation limits
3. **Error Isolation**: Don't expose internal errors to validators
4. **Rate Limiting**: Protect against spam requests

### Executor Bot Security

1. **Multisig Control**: Multiple parties must approve (MVP)
2. **Validation**: Verify strategy before execution
3. **Limits**: Maximum position sizes, IL thresholds
4. **Emergency Stop**: Ability to pause system

## Performance Optimization

### Validator Optimization

- **Parallel Miner Polling**: Query all miners concurrently
- **Batch Database Queries**: Single query for all event data
- **Caching**: Cache price data and historical events
- **Incremental Backtesting**: Only compute new blocks

### Miner Optimization

- **Database Connection Pool**: Reuse connections
- **Feature Caching**: Cache frequently used features
- **Model Loading**: Load models once at startup
- **Async Processing**: Non-blocking request handling

## Monitoring and Observability

### Key Metrics

**Validator:**
- Round completion time
- Number of valid miner responses
- Database query latency
- Weight publishing success rate

**Miner:**
- Request latency (p50, p95, p99)
- Strategy generation time
- Database query count
- Constraint violation rate

**System:**
- Top miner scores over time
- Strategy diversity (position range distribution)
- Vault TVL and fee generation
- Network consensus rate

## Future Enhancements

1. **Multi-Chain Support**: Expand beyond Base to other chains
2. **Multiple Pairs**: Support multiple trading pairs simultaneously
3. **Dynamic Constraints**: Adjust constraints based on market conditions
4. **Advanced Scoring**: Incorporate risk-adjusted metrics
5. **Automated Execution**: Fully automated strategy deployment
6. **Public Vaults**: Open vault creation and deposits

## Development Guidelines

See `CLAUDE.md` for detailed development guidelines and coding standards.

## References

- Technical Specification: `spec.md`
- API Documentation: `validator/models.py`
- Quick Start: `QUICKSTART.md`
- User Guide: `README.md`
