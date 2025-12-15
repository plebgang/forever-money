"""
Tests for data models and validation.
"""
import pytest
from pydantic import ValidationError
from validator.models import (
    ValidatorRequest,
    Constraints,
    ValidatorMetadata
)
from miner.models import MinerResponse, MinerMetadata
from protocol.models import (
    Strategy,
    Position,
    RebalanceRule,
    Inventory,
    Mode
)


def test_inventory_model():
    """Test Inventory model."""
    inventory = Inventory(
        amount0="1000000000000000000",
        amount1="2500000000"
    )

    assert inventory.amount0 == "1000000000000000000"
    assert inventory.amount1 == "2500000000"


def test_position_model_valid():
    """Test Position model with valid data."""
    position = Position(
        tick_lower=-10000,
        tick_upper=-9900,
        allocation0="1000000000000000000",
        allocation1="2500000000",
        confidence=0.9
    )

    assert position.tick_lower == -10000
    assert position.tick_upper == -9900
    assert position.confidence == 0.9


def test_position_invalid_tick_range():
    """Test that tick_upper must be greater than tick_lower."""
    with pytest.raises(ValidationError):
        Position(
            tick_lower=-9900,
            tick_upper=-10000,  # Invalid: upper < lower
            allocation0="1000000000000000000",
            allocation1="2500000000"
        )


def test_position_confidence_bounds():
    """Test confidence must be between 0 and 1."""
    # Valid confidence
    Position(
        tick_lower=-10000,
        tick_upper=-9900,
        allocation0="1000000000000000000",
        allocation1="2500000000",
        confidence=0.5
    )

    # Invalid: > 1
    with pytest.raises(ValidationError):
        Position(
            tick_lower=-10000,
            tick_upper=-9900,
            allocation0="1000000000000000000",
            allocation1="2500000000",
            confidence=1.5
        )

    # Invalid: < 0
    with pytest.raises(ValidationError):
        Position(
            tick_lower=-10000,
            tick_upper=-9900,
            allocation0="1000000000000000000",
            allocation1="2500000000",
            confidence=-0.1
        )


def test_strategy_model():
    """Test Strategy model."""
    strategy = Strategy(
        positions=[
            Position(
                tick_lower=-10000,
                tick_upper=-9900,
                allocation0="500000000000000000",
                allocation1="1250000000",
                confidence=0.9
            )
        ],
        rebalance_rule=RebalanceRule(
            trigger="price_outside_range",
            cooldown_blocks=300
        )
    )

    assert len(strategy.positions) == 1
    assert strategy.rebalance_rule is not None
    assert strategy.rebalance_rule.cooldown_blocks == 300


def test_strategy_without_rebalance_rule():
    """Test Strategy without rebalance rule (optional)."""
    strategy = Strategy(
        positions=[
            Position(
                tick_lower=-10000,
                tick_upper=-9900,
                allocation0="500000000000000000",
                allocation1="1250000000"
            )
        ],
        rebalance_rule=None
    )

    assert strategy.rebalance_rule is None


def test_miner_response_model():
    """Test MinerResponse model."""
    response = MinerResponse(
        strategy=Strategy(
            positions=[
                Position(
                    tick_lower=-10000,
                    tick_upper=-9900,
                    allocation0="500000000000000000",
                    allocation1="1250000000",
                    confidence=0.9
                )
            ]
        ),
        miner_metadata=MinerMetadata(
            version="1.0.0",
            model_info="test-model"
        )
    )

    assert response.strategy is not None
    assert response.miner_metadata.version == "1.0.0"


def test_validator_request_inventory_mode():
    """Test ValidatorRequest with inventory mode."""
    constraints = Constraints(
        max_il=0.10,
        min_tick_width=60,
        max_rebalances=4
    )

    metadata = ValidatorMetadata(
        round_id="test-round-001",
        constraints=constraints
    )

    request = ValidatorRequest(
        pair_address="0x1234567890123456789012345678901234567890",
        chain_id=8453,
        target_block=12345678,
        mode=Mode.INVENTORY,
        inventory=Inventory(
            amount0="1000000000000000000",
            amount1="2500000000"
        ),
        metadata=metadata
    )

    assert request.mode == Mode.INVENTORY
    assert request.inventory is not None
    assert request.metadata.constraints.max_il == 0.10


def test_validator_request_inventory_required():
    """Test that inventory is required when mode is INVENTORY."""
    constraints = Constraints(
        max_il=0.10,
        min_tick_width=60,
        max_rebalances=4
    )

    metadata = ValidatorMetadata(
        round_id="test-round-001",
        constraints=constraints
    )

    # Should raise error: inventory required for INVENTORY mode
    with pytest.raises(ValidationError):
        ValidatorRequest(
            pair_address="0x1234567890123456789012345678901234567890",
            chain_id=8453,
            target_block=12345678,
            mode=Mode.INVENTORY,
            inventory=None,  # Missing inventory
            metadata=metadata
        )


def test_validator_request_position_mode():
    """Test ValidatorRequest with position mode."""
    from validator.models import CurrentPosition

    constraints = Constraints(
        max_il=0.10,
        min_tick_width=60,
        max_rebalances=4
    )

    metadata = ValidatorMetadata(
        round_id="test-round-001",
        constraints=constraints
    )

    request = ValidatorRequest(
        pair_address="0x1234567890123456789012345678901234567890",
        chain_id=8453,
        target_block=12345678,
        mode=Mode.POSITION,
        current_positions=[
            CurrentPosition(
                tick_lower=-10000,
                tick_upper=-9900,
                liquidity="1000000000000000000"
            )
        ],
        metadata=metadata
    )

    assert request.mode == Mode.POSITION
    assert len(request.current_positions) == 1


def test_constraints_defaults():
    """Test Constraints model with default values."""
    constraints = Constraints()

    assert constraints.max_il == 0.10
    assert constraints.min_tick_width == 60
    assert constraints.max_rebalances == 4


def test_metadata_with_custom_constraints():
    """Test Metadata with custom constraints."""
    constraints = Constraints(
        max_il=0.15,
        min_tick_width=120,
        max_rebalances=6
    )

    metadata = ValidatorMetadata(
        round_id="custom-round-001",
        constraints=constraints
    )

    assert metadata.constraints.max_il == 0.15
    assert metadata.constraints.min_tick_width == 120
    assert metadata.constraints.max_rebalances == 6


def test_mode_enum():
    """Test Mode enum values."""
    assert Mode.INVENTORY == "inventory"
    assert Mode.POSITION == "position"


def test_model_serialization():
    """Test that models can be serialized to JSON."""
    position = Position(
        tick_lower=-10000,
        tick_upper=-9900,
        allocation0="1000000000000000000",
        allocation1="2500000000",
        confidence=0.9
    )

    # Serialize using pydantic
    position_dict = position.model_dump()

    assert position_dict['tick_lower'] == -10000
    assert position_dict['tick_upper'] == -9900
    assert position_dict['allocation0'] == "1000000000000000000"
    assert position_dict['confidence'] == 0.9


def test_model_deserialization():
    """Test that models can be deserialized from JSON."""
    position_dict = {
        'tick_lower': -10000,
        'tick_upper': -9900,
        'allocation0': '1000000000000000000',
        'allocation1': '2500000000',
        'confidence': 0.9
    }

    position = Position(**position_dict)

    assert position.tick_lower == -10000
    assert position.tick_upper == -9900
    assert position.confidence == 0.9


def test_miner_response_full_format():
    """Test full MinerResponse matches spec format."""
    response_dict = {
        "strategy": {
            "positions": [
                {
                    "tick_lower": -9600,
                    "tick_upper": -8400,
                    "allocation0": "500000000000000000",
                    "allocation1": "0",
                    "confidence": 0.82
                },
                {
                    "tick_lower": -8400,
                    "tick_upper": -7200,
                    "allocation0": "0",
                    "allocation1": "1800000000",
                    "confidence": 0.78
                }
            ],
            "rebalance_rule": {
                "trigger": "price_outside_range",
                "cooldown_blocks": 300
            }
        },
        "miner_metadata": {
            "version": "1.0.0",
            "model_info": "lstm-v3-swaps-optimized"
        }
    }

    # Should parse without errors
    response = MinerResponse(**response_dict)

    assert len(response.strategy.positions) == 2
    assert response.strategy.rebalance_rule.cooldown_blocks == 300
    assert response.miner_metadata.version == "1.0.0"


def test_validator_request_full_format():
    """Test full ValidatorRequest matches spec format."""
    request_dict = {
        "pair_address": "0x0000000000000000000000000000000000000000",
        "chain_id": 8453,
        "target_block": 12345678,
        "mode": "inventory",
        "inventory": {
            "amount0": "1000000000000000000",
            "amount1": "2500000000"
        },
        "current_positions": [],
        "metadata": {
            "round_id": "2025-02-01-001",
            "constraints": {
                "max_il": 0.10,
                "min_tick_width": 60,
                "max_rebalances": 4
            }
        }
    }

    # Should parse without errors
    request = ValidatorRequest(**request_dict)

    assert request.pair_address == "0x0000000000000000000000000000000000000000"
    assert request.chain_id == 8453
    assert request.mode == Mode.INVENTORY
    assert request.inventory.amount0 == "1000000000000000000"
    assert request.metadata.round_id == "2025-02-01-001"
