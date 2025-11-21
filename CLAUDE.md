# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **SN98 (ForeverMoney/九八)** - a Bittensor subnet for competitive optimization of Aerodrome v3 LP (Liquidity Provider) strategies on Base (chainId: 8453). The subnet operates as a competition where Miners submit liquidity provision strategies and Validators score them based on performance metrics.

## System Architecture

### Core Components

1. **Validator**: Publishes round parameters, polls miners, enforces constraints, scores submissions using a backtester, and publishes the winning strategy
   - Scoring: 70% Net PnL vs HODL + 30% LP Fee Share
   - Top 3 strategies receive full weight for the 70% performance component
   - Relies on read-only Postgres DB (fed by subgraph) for price data
   - Does NOT use external oracles in MVP

2. **Miner**: HTTP endpoint that receives round parameters and returns optimal LP position configurations
   - Must query provided Postgres DB for historical pool events
   - Returns positions (tick ranges, allocations) and rebalance rules
   - Must comply with constraints: max_il (e.g., 0.10), min_tick_width (e.g., 60), max_rebalances (e.g., 4)

3. **Executor Bot** (Subnet Owner): Reads winning strategy from Validator and executes it as v3 NFT LP operations on Aerodrome Vault

### Data Flow

```
Validator → generates round parameters → Miners
              ↓
Miners query Postgres DB (subgraph data) → return strategies
              ↓
Validator backtests strategies → scores → publishes winner
              ↓
Executor Bot → executes winning strategy on-chain
```

## Key Technical Decisions

- **Price Feed**: Subgraph data via read-only Postgres (no external oracle in MVP)
- **Rewards**: Aerodrome farming rewards NOT included in PnL calculations
- **Slippage**: Handled implicitly through backtesting; validator doesn't handle on-chain execution failures
- **Default Mode**: `inventory` mode (managing existing positions, not deploying new liquidity)

## JSON API Format

### Validator Request to Miners
```json
{
  "pairAddress": "0x...",
  "chainId": 8453,
  "target_block": 12345678,
  "mode": "inventory",
  "inventory": {
    "amount0": "1000000000",
    "amount1": "2000000000"
  },
  "metadata": {
    "round_id": "uuid",
    "constraints": {
      "max_il": 0.10,
      "min_tick_width": 60,
      "max_rebalances": 4
    }
  },
  "postgres_access": { /* credentials */ }
}
```

### Miner Response Format
```json
{
  "strategy": {
    "positions": [
      {
        "tickLower": -9600,
        "tickUpper": -8400,
        "allocation0": "500000000",
        "allocation1": "1000000000",
        "confidence": 0.90
      }
    ],
    "rebalance_rule": {
      "trigger": "price_outside_range",
      "cooldown_blocks": 300
    }
  },
  "miner_metadata": {
    "version": "1.0.0",
    "model_info": "Strategy-Name"
  }
}
```

## Scoring Logic Implementation

1. **Pre-scoring Constraint Check**: Verify tick ranges, allocations, and rebalance rules comply with constraints (non-compliant = score 0)
2. **Backtester Class**: Simulate strategy performance against HODL baseline using Postgres historical data
3. **Performance Score (70%)**: Net PnL vs HODL with top-heavy weighting (top 3 strategies get full weight)
4. **LP Alignment Score (30%)**: Pro-rata based on miner's LP fee contributions
5. **Final Score**: `(Performance × 0.7) + (LP_Alignment × 0.3)`

## Development Status

This repository is in early specification phase. Implementation of Validator and reference Miner code is pending based on spec.md.
