# SN98 ForeverMoney - Development Plan (5 Days)

**Created:** November 26, 2025
**Status:** Active Development
**Goal:** Fix all critical issues and get validator + miner working end-to-end

---

## Executive Summary

### Current Status
- ✅ Validator runs and connects to Bittensor testnet
- ✅ Validator queries local miner successfully
- ✅ Miner responds with strategy (2 positions)
- ⚠️ Database price fetching fails (returns None)
- ⚠️ Backtester produces unrealistic numbers (PnL: 84836045481663671566336)
- ⚠️ LP alignment scoring uses mock data (not real vault fees)
- ❌ Cannot publish weights (NeuronNoValidatorPermit - needs subnet owner)

### Critical Issues Identified

| # | Issue | Severity | Component | Status |
|---|-------|----------|-----------|--------|
| 1 | Cannot publish weights to chain | BLOCKER | Validator | Needs subnet owner |
| 2 | Database price fetching fails | HIGH | Database | To fix |
| 3 | Backtester IL calculation is wrong | HIGH | Backtester | To fix |
| 4 | Scorer division by zero possible | MEDIUM | Scorer | To fix |
| 5 | Mock vault fees in LP scoring | MEDIUM | Validator | To fix |
| 6 | Miner doesn't connect to database | MEDIUM | Miner | To fix |
| 7 | Sequential miner polling (slow) | LOW | Validator | Future |

---

## Day 1: Fix Database & Price Fetching

### Priority: HIGH

**Goal:** Get database queries working correctly so backtester has real price data.

### Tasks

#### 1.1 Debug Database Connection
- [ ] Add debug logging to `database.py` to trace queries
- [ ] Test direct database query with the pool address
- [ ] Verify pool address format (with/without 0x prefix)

```python
# Test script to run:
from validator.database import PoolDataDB
import os
from dotenv import load_dotenv

load_dotenv()
db = PoolDataDB(connection_string=os.getenv('DB_CONNECTION_STRING'))

# Test queries
pair = "0x1024c20c048ea6087293f46d4a1c042cb6705924"
price = db.get_price_at_block(pair, 38634763)
print(f"Price at block 38634763: {price}")

swaps = db.get_swap_events(pair, 38600000, 38634763)
print(f"Swaps in range: {len(swaps)}")
if swaps:
    print(f"Sample swap: {swaps[0]}")
```

#### 1.2 Fix Price Query
- [ ] Check if `sqrt_price_x96` is being returned correctly
- [ ] Verify the block number range has swap data
- [ ] Add fallback to find closest swap if exact block not found

**File:** `validator/database.py` - `get_price_at_block()` method

```python
# Current issue: Returns None when no swap at exact block
# Fix: Find closest swap before or at block
def get_price_at_block(self, pair_address: str, block_number: int) -> Optional[float]:
    # Add logging
    logger.debug(f"Querying price for {pair_address} at block {block_number}")

    clean_address = pair_address.lower().replace('0x', '')

    with self.get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = """
                SELECT sqrt_price_x96, evt_block_number
                FROM swaps
                WHERE evt_address = %s
                    AND evt_block_number <= %s
                ORDER BY evt_block_number DESC
                LIMIT 1
            """
            cursor.execute(query, [clean_address, block_number])
            result = cursor.fetchone()

            if result:
                logger.debug(f"Found price at block {result['evt_block_number']}")
                sqrt_price = int(result['sqrt_price_x96'])
                price = (sqrt_price / (2 ** 96)) ** 2
                return price
            else:
                logger.warning(f"No swaps found for {pair_address} before block {block_number}")
                return None
```

#### 1.3 Create Database Test Script
- [ ] Create `scripts/test_db.py` to verify all database methods
- [ ] Test with actual pool address and block range
- [ ] Document working block ranges

### Expected Outcome
- Database queries return actual price data
- Backtester can calculate real HODL baseline
- No more "Could not fetch prices" warnings

---

## Day 2: Fix Backtester Math

### Priority: HIGH

**Goal:** Fix IL calculation and ensure realistic PnL numbers.

### Tasks

#### 2.1 Fix HODL Baseline Calculation
- [ ] Handle case when price is None (currently returns 0)
- [ ] Add validation for price values
- [ ] Use first available price if start_block price missing

**File:** `validator/backtester.py` - `calculate_hodl_baseline()`

```python
def calculate_hodl_baseline(self, pair_address, amount0, amount1, start_block, end_block):
    start_price = self.db.get_price_at_block(pair_address, start_block)
    end_price = self.db.get_price_at_block(pair_address, end_block)

    # Better handling of missing prices
    if start_price is None:
        logger.warning("Start price not found, using first available swap")
        # Query first swap in range
        swaps = self.db.get_swap_events(pair_address, start_block, end_block)
        if swaps and swaps[0].get('sqrt_price_x96'):
            sqrt_price = int(swaps[0]['sqrt_price_x96'])
            start_price = (sqrt_price / (2 ** 96)) ** 2

    if end_price is None:
        logger.warning("End price not found, using last available swap")
        swaps = self.db.get_swap_events(pair_address, start_block, end_block)
        if swaps and swaps[-1].get('sqrt_price_x96'):
            sqrt_price = int(swaps[-1]['sqrt_price_x96'])
            end_price = (sqrt_price / (2 ** 96)) ** 2

    if start_price is None or end_price is None:
        logger.error("Cannot calculate HODL baseline - no price data")
        return None  # Return None instead of 0

    initial_value = amount0 * start_price + amount1
    final_value = amount0 * end_price + amount1
    return final_value
```

#### 2.2 Fix IL Calculation (Known Bug)
- [ ] Replace simplified constant product with proper V3 concentrated liquidity math
- [ ] Use position's tick bounds for IL calculation
- [ ] Handle out-of-range positions correctly

**Current (Wrong):**
```python
# Uses constant product: k = x*y (Uniswap V2 math)
k = current_amount0 * current_amount1
current_amount0 = math.sqrt(k / final_price)
current_amount1 = math.sqrt(k * final_price)
```

**Fixed (Correct V3 Math):**
```python
def calculate_position_value_at_price(self, position, liquidity, target_price):
    """Calculate position value using proper V3 concentrated liquidity math."""
    sqrt_price = math.sqrt(target_price)
    sqrt_price_lower = math.sqrt(1.0001 ** position.tickLower)
    sqrt_price_upper = math.sqrt(1.0001 ** position.tickUpper)

    if target_price <= 1.0001 ** position.tickLower:
        # Price below range - all in token0
        amount0 = liquidity * (1/sqrt_price_lower - 1/sqrt_price_upper)
        amount1 = 0
    elif target_price >= 1.0001 ** position.tickUpper:
        # Price above range - all in token1
        amount0 = 0
        amount1 = liquidity * (sqrt_price_upper - sqrt_price_lower)
    else:
        # Price in range
        amount0 = liquidity * (1/sqrt_price - 1/sqrt_price_upper)
        amount1 = liquidity * (sqrt_price - sqrt_price_lower)

    return amount0 * target_price + amount1
```

#### 2.3 Add Input Validation
- [ ] Validate all numeric inputs before calculation
- [ ] Add bounds checking for tick values
- [ ] Log warnings for suspicious values

### Expected Outcome
- Realistic PnL numbers (not 10^22)
- Accurate IL calculations
- Better error handling when data missing

---

## Day 3: Fix Scorer & Constraint Validation

### Priority: MEDIUM

**Goal:** Fix scoring edge cases and improve constraint validation.

### Tasks

#### 3.1 Fix Division by Zero in Scorer
- [ ] Handle case when all PnL values are equal
- [ ] Handle case when max_pnl equals min_pnl
- [ ] Add defensive checks

**File:** `validator/scorer.py` - `calculate_performance_scores()`

```python
# Current issue (line 69-75):
if max_pnl - min_pnl > 0:
    score = (pnl - min_pnl) / (max_pnl - min_pnl)
else:
    score = 1.0  # All equal - give full score

# Better handling:
def calculate_performance_scores(self, miner_metrics):
    if not miner_metrics:
        return {}

    # Single miner case
    if len(miner_metrics) == 1:
        uid = list(miner_metrics.keys())[0]
        pnl = miner_metrics[uid].net_pnl_vs_hodl
        return {uid: 1.0 if pnl >= 0 else 0.5}

    # ... rest of logic with better edge case handling
```

#### 3.2 Remove Mock Vault Fees
- [ ] Query actual collect events from database
- [ ] Match vault addresses to miner UIDs (may need registry)
- [ ] Add fallback for MVP (equal LP scores if no vault data)

**File:** `validator/validator.py` - `_get_vault_fees()` method

```python
def _get_vault_fees(self, miner_uids, start_block, end_block):
    """Query actual vault fees from database."""
    # For MVP: If we don't have vault registry, use equal scoring
    # This means 30% LP component gives everyone equal weight

    if not hasattr(self, 'vault_registry') or not self.vault_registry:
        logger.info("No vault registry - using equal LP alignment scores")
        return {uid: 1.0 for uid in miner_uids}

    # With vault registry:
    vault_addresses = [self.vault_registry.get(uid) for uid in miner_uids]
    vault_addresses = [v for v in vault_addresses if v]  # Filter None

    if not vault_addresses:
        return {uid: 1.0 for uid in miner_uids}

    fees = self.db.get_miner_vault_fees(vault_addresses, start_block, end_block)
    # Map back to UIDs...
```

#### 3.3 Improve Constraint Validation Messages
- [ ] Add more descriptive violation messages
- [ ] Include actual vs expected values
- [ ] Log all violations for debugging

### Expected Outcome
- No division by zero errors
- Clear violation messages
- MVP-compatible LP scoring

---

## Day 4: Fix Miner & Integration

### Priority: MEDIUM

**Goal:** Connect miner to database and test full integration.

### Tasks

#### 4.1 Connect Miner to Database
- [ ] Add DB connection to miner configuration
- [ ] Pass DB credentials from validator request
- [ ] Use real price data for strategy generation

**File:** `miner/miner.py`

```python
# Add database initialization
from validator.database import PoolDataDB
import os

# Initialize DB from environment or request
db = None

def get_db_connection(postgres_access=None):
    global db
    if db is None:
        if postgres_access:
            # Use credentials from validator request
            db = PoolDataDB(
                host=postgres_access.get('host'),
                port=postgres_access.get('port'),
                database=postgres_access.get('database'),
                user=postgres_access.get('user'),
                password=postgres_access.get('password')
            )
        elif os.getenv('DB_CONNECTION_STRING'):
            db = PoolDataDB(connection_string=os.getenv('DB_CONNECTION_STRING'))
    return db

@app.route('/predict_strategy', methods=['POST'])
def predict_strategy():
    request_data = request.json
    validator_request = ValidatorRequest(**request_data)

    # Get DB connection
    db_conn = get_db_connection(request_data.get('postgres_access'))

    # Pass to strategy generator
    strategy_generator = SimpleStrategyGenerator(db=db_conn)
    strategy = strategy_generator.generate_strategy(validator_request)
    # ...
```

#### 4.2 Add Integration Test Script
- [ ] Create `scripts/test_integration.py`
- [ ] Test full flow: validator → miner → scoring
- [ ] Verify all data passes correctly

```python
#!/usr/bin/env python3
"""Integration test for validator + miner."""

import subprocess
import time
import requests
import json

def test_full_integration():
    # 1. Start miner in background
    miner_process = subprocess.Popen(
        ['python', '-m', 'miner.miner'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(3)  # Wait for startup

    # 2. Check miner health
    resp = requests.get('http://localhost:8000/health')
    assert resp.status_code == 200
    print(f"Miner healthy: {resp.json()}")

    # 3. Run validator with test miner
    result = subprocess.run([
        'python', '-m', 'validator.main',
        '--wallet.name', 'test_validator',
        '--wallet.hotkey', 'test_hotkey',
        '--subtensor.network', 'test',
        '--netuid', '98',
        '--pair_address', '0x1024c20c048ea6087293f46d4a1c042cb6705924',
        '--target_block', '38634763',
        '--start_block', '38600000',  # Smaller range for faster test
        '--test-miner', 'http://localhost:8000',
        '--dry-run'
    ], capture_output=True, text=True)

    print(f"Validator output:\n{result.stdout}")

    # 4. Check winning strategy
    with open('winning_strategy.json') as f:
        strategy = json.load(f)
    print(f"Winning strategy: {json.dumps(strategy, indent=2)}")

    # 5. Cleanup
    miner_process.terminate()

    # 6. Verify results
    assert strategy['winner']['final_score'] > 0
    assert len(strategy['strategy']['positions']) > 0
    print("\n✅ Integration test passed!")

if __name__ == '__main__':
    test_full_integration()
```

#### 4.3 Test with Different Block Ranges
- [ ] Find block range with most swap data
- [ ] Test with narrow (100 blocks) and wide (1M blocks) ranges
- [ ] Document optimal testing parameters

### Expected Outcome
- Miner uses real price data
- Full integration test passes
- Documented testing parameters

---

## Day 5: Documentation & Validator Permit

### Priority: HIGH (Permit) + LOW (Docs)

**Goal:** Get validator permit and finalize documentation.

### Tasks

#### 5.1 Request Validator Permit from Subnet Owner
- [ ] Contact subnet owner (founder)
- [ ] Provide validator hotkey: `5HnPJfR6uDCXCg4DJNoFA3yBuXDcwhzGGAf2huu9iR23dZ6Q`
- [ ] Request `NeuronValidatorPermit` for subnet 98

**What is needed:**
The subnet owner needs to run:
```python
import bittensor as bt

subtensor = bt.subtensor(network='test')
wallet = bt.wallet(name='subnet_owner_wallet')

# Grant validator permit
subtensor.add_stake(
    wallet=wallet,
    hotkey_ss58='5HnPJfR6uDCXCg4DJNoFA3yBuXDcwhzGGAf2huu9iR23dZ6Q',
    amount=1.0,  # Minimum stake for validator
    netuid=98
)
```

Or use btcli:
```bash
btcli stake add --wallet.name subnet_owner --hotkey 5HnPJfR6uDCXCg4DJNoFA3yBuXDcwhzGGAf2huu9iR23dZ6Q --amount 1 --netuid 98 --network test
```

#### 5.2 Test Without Dry-Run (After Permit)
- [ ] Remove `--dry-run` flag
- [ ] Run validator
- [ ] Verify weights published to chain
- [ ] Check metagraph for updated weights

#### 5.3 Update Documentation
- [ ] Update DEPLOYMENT_GUIDE.md with fixes
- [ ] Document actual working block ranges
- [ ] Add troubleshooting for common issues
- [ ] Update CODE_REVIEW_ISSUES.md with fixed items

#### 5.4 Create Runbook
- [ ] Step-by-step guide to run validator in production
- [ ] Monitoring and alerting setup
- [ ] Recovery procedures

### Expected Outcome
- Validator can publish weights
- Complete documentation
- Production-ready setup

---

## Summary: Daily Goals

| Day | Focus | Key Deliverable |
|-----|-------|-----------------|
| 1 | Database | Working price queries |
| 2 | Backtester | Realistic PnL & IL numbers |
| 3 | Scorer | Fixed edge cases, no mock data |
| 4 | Integration | Full e2e test passing |
| 5 | Production | Validator permit + docs |

---

## Blockers & Dependencies

### External Dependencies
1. **Validator Permit** - Requires subnet owner action
2. **Database Access** - Requires working AWS RDS connection

### Internal Dependencies
1. Day 2 depends on Day 1 (need prices for backtester)
2. Day 4 depends on Days 1-3 (need all fixes for integration)
3. Day 5 depends on all previous days

---

## Quick Fixes to Apply Now

These can be done immediately:

### 1. Add Debug Logging
```python
# In database.py, add at top:
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 2. Test Database Connection
```bash
# Quick test
python -c "
from validator.database import PoolDataDB
import os
from dotenv import load_dotenv
load_dotenv()

db = PoolDataDB(connection_string=os.getenv('DB_CONNECTION_STRING'))
print('Testing connection...')
swaps = db.get_swap_events('1024c20c048ea6087293f46d4a1c042cb6705924', 38600000, 38634763)
print(f'Found {len(swaps)} swaps')
if swaps:
    print(f'First swap: {swaps[0]}')
"
```

### 3. Verify Block Range
```bash
# Check what blocks have data
python -c "
from validator.database import PoolDataDB
import os
from dotenv import load_dotenv
load_dotenv()

db = PoolDataDB(connection_string=os.getenv('DB_CONNECTION_STRING'))

# Get block range from swaps table
with db.get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute('''
            SELECT MIN(evt_block_number), MAX(evt_block_number), COUNT(*)
            FROM swaps
            WHERE evt_address = %s
        ''', ['1024c20c048ea6087293f46d4a1c042cb6705924'])
        result = cur.fetchone()
        print(f'Block range: {result[0]} - {result[1]}')
        print(f'Total swaps: {result[2]}')
"
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `validator/database.py` | Add debug logging, fix price query |
| `validator/backtester.py` | Fix HODL baseline, fix IL math |
| `validator/scorer.py` | Fix division by zero |
| `validator/validator.py` | Remove mock vault fees |
| `miner/miner.py` | Add DB connection |
| `miner/strategy.py` | Use real prices |

---

## Success Criteria

By end of Day 5:
- [ ] `python -m validator.main` runs without errors
- [ ] Database queries return real price data
- [ ] PnL numbers are realistic (not astronomical)
- [ ] Miner generates strategies based on real data
- [ ] Weights can be published to chain (with permit)
- [ ] Full integration test passes
- [ ] Documentation updated
