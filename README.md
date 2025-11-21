# SN98 ForeverMoney - Decentralized Automated Liquidity Manager

SN98 is a Bittensor subnet that optimizes liquidity provision strategies for Aerodrome v3 pools on Base. Miners compete to provide the best LP strategies, earning rewards based on performance and liquidity alignment.

## Overview

As liquidity moves on-chain, SN98 aims to become the leading decentralized Automated Liquidity Manager (ALM). The subnet consists of:

- **Miners**: Propose optimal LP strategies and may contribute liquidity vaults
- **Validators**: Score strategies via backtesting (70% performance + 30% LP alignment)
- **Subnet Owner**: Executes winning strategies through multisig-controlled system
- **Vaults**: Hold and deploy liquidity according to winning strategies

## Architecture

### Scoring System

Validators evaluate miners using a weighted scoring system:

1. **Net PnL vs HODL (70%)**
   - Backtested performance against passive holding
   - Top-heavy scoring: only top 3 strategies receive full weight
   - Measured using historical pool data from Postgres

2. **LP Fee Share (30%)**
   - Fees generated from miner's own liquidity vaults
   - Scored pro-rata based on contribution

**Final Score = (Performance × 0.7) + (LP Alignment × 0.3)**

### Constraints

All strategies must comply with validator constraints:
- `max_il`: Maximum impermanent loss (default: 10%)
- `min_tick_width`: Minimum tick width for positions (default: 60 ticks)
- `max_rebalances`: Maximum rebalances per period (default: 4)

Non-compliant strategies receive a score of 0.

## Installation

### Requirements

- Python 3.9+
- Bittensor SDK
- PostgreSQL access (read-only, provided by subnet)

### Setup

```bash
# Clone repository
git clone <repository-url>
cd forever-money

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

## Running a Validator

### Configuration

Edit `.env` file with your validator configuration:

```env
# Postgres Database (provided by subnet)
POSTGRES_HOST=<provided-host>
POSTGRES_PORT=5432
POSTGRES_DB=sn98_pool_data
POSTGRES_USER=readonly_user
POSTGRES_PASSWORD=<provided-password>

# Validator Settings
NETUID=98
SUBTENSOR_NETWORK=finney
PAIR_ADDRESS=0x...  # Aerodrome pool address
CHAIN_ID=8453
```

### Run Validator

```bash
python -m validator.main \
  --wallet.name your_wallet \
  --wallet.hotkey your_hotkey \
  --pair_address 0x... \
  --target_block 12345678 \
  --start_block 12300000
```

## Running a Miner

### Basic Setup

```bash
# Configure miner
export MINER_PORT=8000
export MINER_VERSION=1.0.0
export MODEL_INFO="your-strategy-name"

# Run miner server
python -m miner.miner
```

### Implementing Your Strategy

Miners can customize strategy generation by extending the `SimpleStrategyGenerator` class:

```python
from miner.strategy import SimpleStrategyGenerator
from validator.models import ValidatorRequest, Strategy

class MyCustomStrategy(SimpleStrategyGenerator):
    def generate_strategy(self, request: ValidatorRequest) -> Strategy:
        # Your custom logic here
        # 1. Query historical data from database
        # 2. Run your model/algorithm
        # 3. Return optimized positions
        pass
```

Replace the strategy generator in `miner/miner.py`:

```python
from miner.my_strategy import MyCustomStrategy

strategy_generator = MyCustomStrategy()
```

### Strategy Requirements

Your miner must:
1. Host HTTP endpoint at `/predict_strategy`
2. Accept `ValidatorRequest` JSON
3. Return `MinerResponse` JSON with:
   - List of positions (tick ranges, allocations)
   - Optional rebalance rules
   - Miner metadata
4. Comply with all constraints from request

## API Format

### Validator Request to Miner

```json
{
  "pairAddress": "0x...",
  "chainId": 8453,
  "target_block": 12345678,
  "mode": "inventory",
  "inventory": {
    "amount0": "1000000000000000000",
    "amount1": "2500000000"
  },
  "metadata": {
    "round_id": "2025-02-01-001",
    "constraints": {
      "max_il": 0.10,
      "min_tick_width": 60,
      "max_rebalances": 4
    }
  }
}
```

### Miner Response

```json
{
  "strategy": {
    "positions": [
      {
        "tickLower": -9600,
        "tickUpper": -8400,
        "allocation0": "600000000000000000",
        "allocation1": "0",
        "confidence": 0.85
      },
      {
        "tickLower": -8400,
        "tickUpper": -7200,
        "allocation0": "400000000000000000",
        "allocation1": "2500000000",
        "confidence": 0.72
      }
    ],
    "rebalance_rule": {
      "trigger": "price_outside_range",
      "cooldown_blocks": 1800
    }
  },
  "miner_metadata": {
    "version": "1.0.0",
    "model_info": "lstm-v3-optimized"
  }
}
```

## Database Schema

Validators provide read-only access to a Postgres database containing pool events:

### Tables

- `pool_events`: All on-chain events (swaps, mints, burns, collects)
  - `block_number`: Block number
  - `transaction_hash`: Transaction hash
  - `pool_address`: Pool/pair address
  - `event_type`: Type of event (swap, mint, burn, collect)
  - `event_data`: JSONB data for the event
  - `timestamp`: Block timestamp

Miners can query this database to:
- Run backtests
- Calculate historical volatility
- Analyze fee generation patterns
- Build predictive models

## Development

### Project Structure

```
forever-money/
├── validator/           # Validator implementation
│   ├── models.py        # Pydantic data models
│   ├── database.py      # Postgres interface
│   ├── backtester.py    # Strategy backtesting
│   ├── constraints.py   # Constraint validation
│   ├── scorer.py        # Scoring system
│   ├── validator.py     # Main validator logic
│   └── main.py          # Entry point
├── miner/               # Sample miner implementation
│   ├── strategy.py      # Strategy generation
│   └── miner.py         # HTTP server
├── tests/               # Test suite
├── spec.md              # Technical specification
└── requirements.txt     # Python dependencies
```

### Testing

```bash
# Run tests
pytest tests/

# Run specific test
pytest tests/test_backtester.py
```

## Strategy Development Tips

1. **Use Historical Data**: Query the Postgres database for pool events to understand patterns
2. **Manage IL**: Stay within the `max_il` constraint by adjusting tick ranges
3. **Optimize Fees**: Balance narrow ranges (high fees) with wide ranges (stability)
4. **Test Thoroughly**: Backtest your strategy across different market conditions
5. **Monitor Performance**: Track your scores and adjust accordingly

## Production Deployment

### Validator

- Use systemd or supervisor for process management
- Set up monitoring and alerting
- Configure log rotation
- Ensure database connection reliability

### Miner

- Deploy behind reverse proxy (nginx/caddy)
- Use WSGI server (gunicorn/uwsgi) instead of Flask dev server
- Implement rate limiting and authentication
- Monitor uptime and response times

## Support

- GitHub Issues: [Report bugs or request features]
- Documentation: See `CLAUDE.md` for development guidelines
- Specification: See `spec.md` for detailed technical specification

## License

[To be determined]
# forever-money
