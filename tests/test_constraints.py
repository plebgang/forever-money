"""
Tests for constraint validation.
"""
import pytest
from validator.constraints import ConstraintValidator
from validator.models import Strategy, Position, RebalanceRule, Constraints


@pytest.fixture
def constraints():
    """Create default constraints."""
    return Constraints(
        max_il=0.10,
        min_tick_width=60,
        max_rebalances=4
    )


@pytest.fixture
def validator(constraints):
    """Create constraint validator."""
    return ConstraintValidator(constraints)


def test_valid_strategy(validator):
    """Test a valid strategy passes all constraints."""
    strategy = Strategy(
        positions=[
            Position(
                tickLower=-10000,
                tickUpper=-9900,  # Width = 100, > 60
                allocation0="1000000000000000000",
                allocation1="2500000000",
                confidence=0.9
            )
        ],
        rebalance_rule=RebalanceRule(
            trigger="price_outside_range",
            cooldown_blocks=300
        )
    )

    is_valid, violations = validator.validate_strategy(strategy)
    assert is_valid
    assert len(violations) == 0


def test_tick_width_violation(validator):
    """Test tick width below minimum."""
    strategy = Strategy(
        positions=[
            Position(
                tickLower=-10000,
                tickUpper=-9950,  # Width = 50, < 60
                allocation0="1000000000000000000",
                allocation1="2500000000",
                confidence=0.9
            )
        ]
    )

    is_valid, violations = validator.validate_strategy(strategy)
    assert not is_valid
    assert len(violations) > 0
    assert "tick width" in violations[0].lower()


def test_zero_allocation_violation(validator):
    """Test position with zero allocations."""
    strategy = Strategy(
        positions=[
            Position(
                tickLower=-10000,
                tickUpper=-9900,
                allocation0="0",
                allocation1="0",  # Both zero
                confidence=0.9
            )
        ]
    )

    is_valid, violations = validator.validate_strategy(strategy)
    assert not is_valid
    assert len(violations) > 0
    assert "zero" in violations[0].lower()


def test_aggressive_cooldown_warning(validator):
    """Test aggressive rebalance cooldown generates warning."""
    strategy = Strategy(
        positions=[
            Position(
                tickLower=-10000,
                tickUpper=-9900,
                allocation0="1000000000000000000",
                allocation1="2500000000",
                confidence=0.9
            )
        ],
        rebalance_rule=RebalanceRule(
            trigger="price_outside_range",
            cooldown_blocks=50  # Too aggressive
        )
    )

    is_valid, violations = validator.validate_strategy(strategy)
    assert not is_valid
    assert "cooldown" in violations[0].lower()


def test_performance_metrics_validation(validator):
    """Test validation of performance metrics after backtesting."""
    # Test IL violation
    is_valid, violations = validator.validate_performance_metrics(
        impermanent_loss=0.15,  # 15%, exceeds 10% max
        num_rebalances=3
    )
    assert not is_valid
    assert "impermanent loss" in violations[0].lower()

    # Test rebalance violation
    is_valid, violations = validator.validate_performance_metrics(
        impermanent_loss=0.05,
        num_rebalances=5  # Exceeds max of 4
    )
    assert not is_valid
    assert "rebalances" in violations[0].lower()

    # Test valid metrics
    is_valid, violations = validator.validate_performance_metrics(
        impermanent_loss=0.08,
        num_rebalances=3
    )
    assert is_valid
    assert len(violations) == 0


def test_multiple_positions(validator):
    """Test strategy with multiple positions."""
    strategy = Strategy(
        positions=[
            Position(
                tickLower=-10000,
                tickUpper=-9900,
                allocation0="500000000000000000",
                allocation1="1250000000",
                confidence=0.9
            ),
            Position(
                tickLower=-9900,
                tickUpper=-9800,
                allocation0="500000000000000000",
                allocation1="1250000000",
                confidence=0.85
            )
        ]
    )

    is_valid, violations = validator.validate_strategy(strategy)
    assert is_valid
