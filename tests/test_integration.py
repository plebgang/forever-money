"""
End-to-end integration tests for SN98.

These tests verify the complete flow from validator to miner and back.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from validator.models import (
    ValidatorRequest,
    ValidatorMetadata,
    Constraints
)
from miner.models import MinerResponse
from protocol.models import Inventory, Mode, Strategy, Position, RebalanceRule, PerformanceMetrics
from miner.strategy import SimpleStrategyGenerator


def test_miner_strategy_generation():
    """Test that miner can generate a valid strategy from validator request."""
    # Create a validator request
    request = ValidatorRequest(
        pair_address="0x1234567890123456789012345678901234567890",
        chain_id=8453,
        target_block=12345678,
        mode=Mode.INVENTORY,
        inventory=Inventory(
            amount0="1000000000000000000",
            amount1="2500000000"
        ),
        metadata=ValidatorMetadata(
            round_id="test-round-001",
            constraints=Constraints(
                max_il=0.10,
                min_tick_width=60,
                max_rebalances=4
            )
        ),
        postgres_access=None
    )

    # Generate strategy
    generator = SimpleStrategyGenerator()
    strategy = generator.generate_strategy(request)

    # Verify strategy structure
    assert strategy is not None
    assert len(strategy.positions) > 0
    # rebalance_rule can be None (no rebalancing) or a RebalanceRule
    # Both are valid strategies - None means "hold position, don't rebalance"

    # Verify positions meet constraints
    for position in strategy.positions:
        tick_width = position.tick_upper - position.tick_lower
        assert tick_width >= 60  # min_tick_width


def test_constraint_validation_in_evaluation():
    """Test that constraint validation works during strategy evaluation."""
    from validator.validator import SN98Validator
    from miner.models import MinerMetadata

    # Setup validator
    wallet = Mock()
    wallet.hotkey.ss58_address = "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY"

    subtensor = Mock()
    metagraph = Mock()
    metagraph.netuid = 98
    metagraph.uids = [1, 2]
    metagraph.hotkeys = [
        "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
        "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty"
    ]

    db = Mock()

    config = {
        'chain_id': 8453,
        'max_il': 0.10,
        'min_tick_width': 60,
        'max_rebalances': 4,
        'performance_weight': 0.7,
        'lp_alignment_weight': 0.3,
        'top_n_strategies': 3,
        'postgres_access': {}
    }

    validator = SN98Validator(
        wallet=wallet,
        subtensor=subtensor,
        metagraph=metagraph,
        db=db,
        config=config
    )

    # Create one valid and one invalid strategy
    miner_responses = {
        1: MinerResponse(
            strategy=Strategy(
                positions=[
                    Position(
                        tick_lower=-10000,
                        tick_upper=-9900,  # Valid width: 100
                        allocation0='500000000000000000',
                        allocation1='1250000000',
                        confidence=0.9
                    )
                ],
                rebalance_rule=RebalanceRule(
                    trigger='price_outside_range',
                    cooldown_blocks=300
                )
            ),
            miner_metadata=MinerMetadata(version='1.0.0', model_info='valid-miner')
        ),
        2: MinerResponse(
            strategy=Strategy(
                positions=[
                    Position(
                        tick_lower=-10000,
                        tick_upper=-9970,  # Invalid width: 30 < 60
                        allocation0='500000000000000000',
                        allocation1='1250000000',
                        confidence=0.85
                    )
                ],
                rebalance_rule=None
            ),
            miner_metadata=MinerMetadata(version='1.0.0', model_info='invalid-miner')
        )
    }

    request = validator.generate_round_request(
        pair_address="0x1234567890123456789012345678901234567890",
        target_block=12345678,
        inventory=Inventory(amount0="1000000000000000000", amount1="2500000000"),
        mode=Mode.INVENTORY
    )

    # Mock backtester
    mock_metrics = PerformanceMetrics(
        net_pnl=500.0,
        hodl_pnl=400.0,
        net_pnl_vs_hodl=100.0,
        total_fees_collected=150.0,
        impermanent_loss=0.05,
        num_rebalances=2
    )

    validator.backtester.backtest_strategy = Mock(return_value=mock_metrics)

    # Evaluate strategies
    scores = validator.evaluate_strategies(
        miner_responses=miner_responses,
        request=request,
        start_block=12345000,
        end_block=12345678
    )

    # Miner 2 should have zero score due to constraint violation
    miner_2_score = next(s for s in scores if s.miner_uid == 2)
    assert miner_2_score.final_score == 0.0
    assert len(miner_2_score.constraint_violations) > 0

    # Miner 1 should have positive score
    miner_1_score = next(s for s in scores if s.miner_uid == 1)
    assert miner_1_score.final_score > 0.0
    assert len(miner_1_score.constraint_violations) == 0


def test_api_format_compatibility():
    """Test that API format matches specification exactly."""
    # This test ensures our models match the spec.md API format

    # Test ValidatorRequest format
    request = ValidatorRequest(
        pair_address="0x0000000000000000000000000000000000000000",
        chain_id=8453,
        target_block=12345678,
        mode=Mode.INVENTORY,
        inventory=Inventory(
            amount0="1000000000000000000",
            amount1="2500000000"
        ),
        current_positions=[],
        metadata=ValidatorMetadata(
            round_id="2025-02-01-001",
            constraints=Constraints(
                max_il=0.10,
                min_tick_width=60,
                max_rebalances=4
            )
        ),
        postgres_access=None
    )

    # Serialize to dict
    request_dict = request.model_dump()

    # Verify all required fields exist
    assert 'pair_address' in request_dict
    assert 'chain_id' in request_dict
    assert 'target_block' in request_dict
    assert 'mode' in request_dict
    assert 'inventory' in request_dict
    assert 'metadata' in request_dict

    # Test MinerResponse format
    from miner.models import MinerMetadata

    response = MinerResponse(
        strategy=Strategy(
            positions=[
                Position(
                    tick_lower=-9600,
                    tick_upper=-8400,
                    allocation0="500000000000000000",
                    allocation1="0",
                    confidence=0.82
                ),
                Position(
                    tick_lower=-8400,
                    tick_upper=-7200,
                    allocation0="0",
                    allocation1="1800000000",
                    confidence=0.78
                )
            ],
            rebalance_rule=RebalanceRule(
                trigger="price_outside_range",
                cooldown_blocks=300
            )
        ),
        miner_metadata=MinerMetadata(
            version="1.0.0",
            model_info="lstm-v3-swaps-optimized"
        )
    )

    # Serialize to dict
    response_dict = response.model_dump()

    # Verify all required fields exist
    assert 'strategy' in response_dict
    assert 'positions' in response_dict['strategy']
    assert 'miner_metadata' in response_dict
    assert 'version' in response_dict['miner_metadata']
    assert 'model_info' in response_dict['miner_metadata']

    # Verify position structure
    for pos in response_dict['strategy']['positions']:
        assert 'tick_lower' in pos
        assert 'tick_upper' in pos
        assert 'allocation0' in pos
        assert 'allocation1' in pos
        assert 'confidence' in pos
