# SN98 ForeverMoney - Quick Start Guide

This guide will get you up and running with SN98 in under 10 minutes.

## Prerequisites

- Python 3.9 or higher
- Bittensor wallet configured
- Access to the SN98 Postgres database (contact subnet owner)

## Quick Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your configuration:
- Add Postgres credentials (provided by subnet owner)
- Set your wallet name and hotkey
- Configure pair address for your target pool

### 3. Test Database Connection

```python
from validator.database import PoolDataDB
import os
from dotenv import load_dotenv

load_dotenv()

db = PoolDataDB(
    host=os.getenv('POSTGRES_HOST'),
    port=int(os.getenv('POSTGRES_PORT')),
    database=os.getenv('POSTGRES_DB'),
    user=os.getenv('POSTGRES_USER'),
    password=os.getenv('POSTGRES_PASSWORD')
)

# Test query
price = db.get_price_at_block("0x...", 12345678)
print(f"Price at block: {price}")
```

## Running as a Miner

### Step 1: Start Miner Server

```bash
python -m miner.miner
```

The server will start on port 8000 (configurable via `MINER_PORT`).

### Step 2: Test Your Miner

In another terminal:

```bash
python scripts/test_miner.py http://localhost:8000
```

You should see output showing your miner's response.

### Step 3: Register on Network

```bash
btcli subnet register --netuid 98 --wallet.name your_wallet
```

### Step 4: Serve Your Axon

Configure your axon to point to your miner's endpoint and ensure it's accessible by validators.

## Running as a Validator

### Step 1: Verify Validator Registration

```bash
btcli wallet overview --wallet.name your_wallet
```

Ensure you're registered on netuid 98.

### Step 2: Run a Test Round

```bash
python -m validator.main \
  --wallet.name your_wallet \
  --wallet.hotkey your_hotkey \
  --pair_address 0x... \
  --target_block 12345678 \
  --start_block 12300000
```

### Step 3: Monitor Output

The validator will:
1. Generate a round request
2. Poll all active miners
3. Backtest each strategy
4. Score and rank miners
5. Publish weights to the network
6. Save winning strategy to `winning_strategy.json`

## Customizing Your Miner Strategy

### Basic Customization

Edit `miner/strategy.py` and modify the `SimpleStrategyGenerator` class:

```python
def _create_positions(self, current_tick, amount0, amount1, min_tick_width):
    # Your custom logic here
    positions = []

    # Example: Create tighter ranges for higher fees
    narrow_width = min_tick_width * 2

    positions.append(Position(
        tickLower=current_tick - narrow_width // 2,
        tickUpper=current_tick + narrow_width // 2,
        allocation0=str(amount0),
        allocation1=str(amount1),
        confidence=0.95
    ))

    return positions
```

### Advanced: ML-Based Strategy

Create a new strategy class:

```python
from miner.strategy import SimpleStrategyGenerator
import numpy as np
import joblib

class MLStrategy(SimpleStrategyGenerator):
    def __init__(self, model_path: str):
        super().__init__()
        self.model = joblib.load(model_path)

    def generate_strategy(self, request):
        # Extract features from historical data
        features = self._extract_features(request)

        # Predict optimal ranges
        predictions = self.model.predict(features)

        # Convert predictions to positions
        positions = self._predictions_to_positions(predictions, request)

        return Strategy(positions=positions, rebalance_rule=...)
```

Update `miner/miner.py`:

```python
from miner.my_ml_strategy import MLStrategy

strategy_generator = MLStrategy(model_path='./models/my_model.pkl')
```

## Common Issues

### Database Connection Failed

- Verify Postgres credentials in `.env`
- Check firewall rules allow connection
- Confirm you're using the read-only user credentials

### Miner Not Responding

- Check miner is running: `curl http://localhost:8000/health`
- Verify port is not blocked by firewall
- Check logs for errors

### Constraint Violations

If your strategies consistently score 0:
- Check tick widths meet `min_tick_width` requirement
- Ensure IL stays under `max_il` threshold
- Verify rebalances don't exceed `max_rebalances`

## Next Steps

1. **Optimize Your Strategy**: Analyze winning strategies and improve your model
2. **Deploy Production Miner**: Use proper WSGI server (gunicorn) and reverse proxy
3. **Monitor Performance**: Track your scores and adjust strategy accordingly
4. **Contribute Liquidity**: Deploy a vault to earn the 30% LP Alignment score

## Resources

- Full documentation: `README.md`
- Technical spec: `spec.md`
- Development guide: `CLAUDE.md`
- API reference: See `validator/models.py` for complete schemas

## Support

Questions? Open an issue on GitHub or reach out to the subnet owner.

Happy mining! 🚀
