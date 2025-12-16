# SN98 ForeverMoney Test Suite

This directory contains comprehensive tests for the SN98 ForeverMoney subnet implementation, covering the WP-1 (Work Package 1) MVP requirements.

## Test Coverage

### Unit Tests

1. **`test_models.py`** - Data model validation
   - Tests all Pydantic models (ValidatorRequest, MinerResponse, Strategy, Position, etc.)
   - Validates field constraints and type checking
   - Ensures API format compatibility with spec.md
   - Coverage: Inventory, Position, Strategy, Constraints, Mode enum, serialization/deserialization

2. **`test_constraints.py`** - Constraint validation
   - Tests ConstraintValidator class
   - Validates tick width, rebalance rules, allocations
   - Tests performance metrics validation (IL, rebalances)
   - Ensures constraint violations are properly detected

3. **`test_backtester.py`** - Backtesting engine
   - Tests UniswapV3Math utilities (sqrtPrice, tick calculations)
   - Tests HODL baseline calculation
   - Tests position simulation (in-range and out-of-range)
   - Tests complete strategy backtesting
   - Coverage: Pool simulation, fee calculations, IL calculations

4. **`test_scorer.py`** - Scoring system
   - Tests 70/30 weighted scoring (performance + LP alignment)
   - Tests top-heavy performance scoring (top 3 strategies)
   - Tests pro-rata LP alignment scoring
   - Tests constraint violation handling (zero score)
   - Tests final score calculation and ranking
   - Tests winning strategy selection

5. **`test_validator.py`** - Validator integration
   - Tests SN98Validator class initialization
   - Tests round request generation
   - Tests miner querying (timeout, not serving)
   - Tests strategy evaluation pipeline
   - Tests score publishing to Bittensor network
   - Tests winning strategy publication
   - **NOTE**: Some tests for HTTP-based miner querying have been skipped as the system now uses Bittensor dendrite for communication

### Integration Tests

6. **`test_integration.py`** - End-to-end testing
   - Tests strategy generation from validator requests
   - Tests constraint validation in evaluation pipeline
   - Tests API format compatibility with specification
   - **NOTE**: Tests for HTTP endpoint communication have been skipped/updated as the system now uses Bittensor's native dendrite/axon protocol instead of HTTP

## Running Tests

### Prerequisites

```bash
# Install dependencies (requires Python 3.9+)
pip install -r requirements.txt
```

The `requirements.txt` includes:
- `pytest>=7.4.0` - Test framework
- `pytest-asyncio>=0.21.0` - Async test support
- `bittensor>=6.0.0` - Bittensor SDK
- All project dependencies

### Run All Tests

```bash
# Run all tests (Python 3.9+ required)
pytest tests/

# Or with specific Python version
~/.pyenv/versions/3.11.13/bin/python3 -m pytest tests/

# Run with verbose output
pytest -v tests/

# Run with coverage report
pytest --cov=validator --cov=miner --cov=protocol tests/

# Run specific test file
pytest tests/test_scorer.py

# Run specific test function
pytest tests/test_scorer.py::test_performance_scoring_top_heavy
```

### Test Results

As of the migration to Bittensor native communication:
- **47 tests passing** - All core functionality validated
- **5 tests skipped** - Legacy HTTP endpoint tests (no longer applicable)

### Test Organization

```
tests/
├── README.md                  # This file
├── __init__.py               # Test package marker
├── test_models.py            # Model validation (15 tests)
├── test_constraints.py       # Constraint validation (8 tests)
├── test_backtester.py        # Backtesting engine (6 tests)
├── test_scorer.py            # Scoring system (11 tests)
├── test_validator.py         # Validator integration (11 tests)
└── test_integration.py       # End-to-end integration (6 tests)

Total: ~57 tests
```

## WP-1 Requirement Coverage

### 1. Validator Requirements ✅

#### a. Provide simulated inventory to miners
- ✅ Tested in `test_validator.py::test_generate_round_request`
- ✅ Tested in `test_integration.py::test_validator_to_miner_integration`

#### b. Pool Simulation Engine
- ✅ Tested in `test_backtester.py::test_backtester_strategy_simulation`
- ✅ Tested in `test_backtester.py::test_position_simulation_in_range`
- ✅ Tests HODL baseline, IL calculation, fee collection

#### c. Miner Scoring
- ✅ Tested in `test_scorer.py` (comprehensive scoring tests)
- ✅ Tests 70% performance + 30% LP alignment
- ✅ Tests top-3 top-heavy performance scoring
- ✅ Tests constraint violation handling

### 2. Miner Requirements ✅

#### Request validator requests
- ✅ Tested in `test_integration.py::test_miner_strategy_generation`
- ✅ Tests strategy generation from ValidatorRequest
- ⚠️ HTTP endpoint tests skipped (migrated to Bittensor synapses)

#### Calculate and provide ranges
- ✅ Tested in `test_integration.py::test_miner_strategy_generation`
- ✅ Tests SimpleStrategyGenerator
- ✅ Validates position generation with constraints

### 3. Documentation ✅

#### Miner Data Model & API Format
- ✅ Tested in `test_models.py::test_validator_request_full_format`
- ✅ Tested in `test_models.py::test_miner_response_full_format`
- ✅ Tested in `test_integration.py::test_api_format_compatibility`
- ✅ All models match spec.md exactly

## Key Test Scenarios

### Constraint Validation
- ✅ Tick width enforcement (min 60 ticks)
- ✅ Rebalance limits (max 4 rebalances)
- ✅ Impermanent loss limits (max 10%)
- ✅ Allocation validation (non-zero, positive)

### Performance Scenarios
- ✅ Strategy outperforms HODL
- ✅ Strategy underperforms HODL
- ✅ Multiple positions per strategy
- ✅ Positions in-range vs out-of-range
- ✅ Fee collection during swaps

### Integration Scenarios
- ✅ Validator → Miner request/response
- ✅ Multiple miners responding
- ✅ Miner timeout handling
- ✅ Non-serving miner handling
- ✅ Score calculation and ranking
- ✅ Winning strategy selection

## Test Data

Tests use realistic data:
- ETH/USDC pair (0x...)
- 1 ETH = 2500 USDC price point
- Base chain (chainId: 8453)
- Typical tick ranges for 0.3% fee tier
- Realistic block numbers

## Continuous Integration

These tests are designed to run in CI/CD pipelines. They:
- Use mocks for external dependencies (database, Bittensor network)
- Are deterministic and repeatable
- Run quickly (<10 seconds total)
- Provide clear error messages

## Adding New Tests

When adding new features, follow this pattern:

```python
def test_new_feature():
    """Test description."""
    # 1. Setup - Create fixtures and mocks
    # 2. Execute - Run the feature
    # 3. Assert - Verify expected behavior
    # 4. Cleanup - Done automatically by pytest
```

## Troubleshooting

### Import Errors
If you see import errors, ensure you're running from the project root:
```bash
cd /path/to/forever-money
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/
```

### Database Connection Errors
Tests mock the database. If you see connection errors, check:
- Mock setup in test fixtures
- Database instantiation uses mocks


## Next Steps

After WP-1 MVP is complete:
- Add benchmarking tests for performance
- Add stress tests for large-scale scenarios
- Add property-based tests with Hypothesis
- Add mutation testing with mutmut
- Set up test coverage reporting in CI

## References

- [spec.md](../spec.md) - Complete specification
- [CLAUDE.md](../CLAUDE.md) - Project overview
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture
