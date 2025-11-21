"""
Strategy generation logic for the sample miner.

This is a simple rule-based implementation. Miners should replace this
with their own models (ML, optimization, etc.).
"""
import logging
import math
from typing import List, Optional

from validator.models import (
    ValidatorRequest,
    Strategy,
    Position,
    RebalanceRule
)
from validator.database import PoolDataDB

logger = logging.getLogger(__name__)


class SimpleStrategyGenerator:
    """
    Simple rule-based strategy generator.

    This implementation uses basic heuristics:
    1. Create 2-3 positions around the current price
    2. Concentrate liquidity in narrower ranges
    3. Set conservative rebalance rules
    """

    def __init__(self, db: Optional[PoolDataDB] = None):
        """
        Initialize strategy generator.

        Args:
            db: Optional database connection for querying historical data
        """
        self.db = db

    def generate_strategy(self, request: ValidatorRequest) -> Strategy:
        """
        Generate an LP strategy for the given request.

        Args:
            request: ValidatorRequest from validator

        Returns:
            Strategy object
        """
        logger.info(f"Generating strategy for round {request.metadata.round_id}")

        # Extract constraints
        constraints = request.metadata.constraints
        min_tick_width = constraints.min_tick_width

        # Get inventory
        if request.inventory:
            amount0 = int(request.inventory.amount0)
            amount1 = int(request.inventory.amount1)
        else:
            logger.warning("No inventory provided")
            amount0 = 0
            amount1 = 0

        # Get current price estimate (would query DB in production)
        current_price = self._estimate_current_price(request)
        current_tick = self._price_to_tick(current_price)

        # Generate positions
        positions = self._create_positions(
            current_tick=current_tick,
            amount0=amount0,
            amount1=amount1,
            min_tick_width=min_tick_width
        )

        # Generate rebalance rule
        rebalance_rule = self._create_rebalance_rule(
            max_rebalances=constraints.max_rebalances
        )

        strategy = Strategy(
            positions=positions,
            rebalance_rule=rebalance_rule
        )

        logger.info(f"Generated strategy with {len(positions)} positions")
        return strategy

    def _estimate_current_price(self, request: ValidatorRequest) -> float:
        """
        Estimate current price for the pair.

        In production, this would query the database or an oracle.
        For this sample, we use a placeholder.
        """
        if self.db:
            price = self.db.get_price_at_block(
                request.pairAddress,
                request.target_block
            )
            if price:
                return price

        # Default fallback price (1 token1 = 2500 token0, e.g., ETH/USDC)
        return 2500.0

    def _price_to_tick(self, price: float) -> int:
        """Convert price to tick."""
        return int(math.log(price) / math.log(1.0001))

    def _tick_to_price(self, tick: int) -> float:
        """Convert tick to price."""
        return 1.0001 ** tick

    def _create_positions(
        self,
        current_tick: int,
        amount0: int,
        amount1: int,
        min_tick_width: int
    ) -> List[Position]:
        """
        Create LP positions around the current price.

        Strategy:
        - Position 1: Narrow range around current price (50% capital)
        - Position 2: Wider range for volatility (50% capital)
        """
        positions = []

        # Ensure tick width meets minimum requirement
        # Use wider ranges to be safe
        narrow_width = max(min_tick_width * 2, 120)  # ~1.2% range
        wide_width = max(min_tick_width * 10, 600)  # ~6% range

        # Position 1: Narrow range around current price
        # Concentrate 60% of capital here for higher fees
        tick_spacing = 60  # Typical Uniswap v3 tick spacing

        # Round to tick spacing
        lower_tick_1 = (current_tick - narrow_width // 2) // tick_spacing * tick_spacing
        upper_tick_1 = (current_tick + narrow_width // 2) // tick_spacing * tick_spacing

        # Ensure minimum width
        if upper_tick_1 - lower_tick_1 < min_tick_width:
            upper_tick_1 = lower_tick_1 + min_tick_width

        positions.append(Position(
            tickLower=lower_tick_1,
            tickUpper=upper_tick_1,
            allocation0=str(int(amount0 * 0.6)),
            allocation1=str(int(amount1 * 0.6)),
            confidence=0.85
        ))

        # Position 2: Wider range for volatility protection
        # Use remaining 40% of capital
        lower_tick_2 = (current_tick - wide_width // 2) // tick_spacing * tick_spacing
        upper_tick_2 = (current_tick + wide_width // 2) // tick_spacing * tick_spacing

        # Ensure minimum width
        if upper_tick_2 - lower_tick_2 < min_tick_width:
            upper_tick_2 = lower_tick_2 + min_tick_width

        positions.append(Position(
            tickLower=lower_tick_2,
            tickUpper=upper_tick_2,
            allocation0=str(int(amount0 * 0.4)),
            allocation1=str(int(amount1 * 0.4)),
            confidence=0.72
        ))

        logger.info(
            f"Created {len(positions)} positions: "
            f"narrow={upper_tick_1 - lower_tick_1} ticks, "
            f"wide={upper_tick_2 - lower_tick_2} ticks"
        )

        return positions

    def _create_rebalance_rule(self, max_rebalances: int) -> RebalanceRule:
        """
        Create a conservative rebalance rule.

        Trigger when price moves outside position ranges.
        Use a reasonable cooldown to avoid excessive rebalancing.
        """
        # Cooldown based on max_rebalances
        # If max 4 rebalances and we expect ~7200 blocks per day,
        # cooldown should be at least 1800 blocks (6 hours)
        cooldown_blocks = 1800

        return RebalanceRule(
            trigger="price_outside_range",
            cooldown_blocks=cooldown_blocks
        )


class MLStrategyGenerator(SimpleStrategyGenerator):
    """
    Placeholder for ML-based strategy generator.

    Miners can extend this to implement:
    - LSTM/Transformer models for price prediction
    - Reinforcement learning for optimal range selection
    - Historical pattern recognition
    - Multi-factor optimization
    """

    def __init__(self, model_path: Optional[str] = None, db: Optional[PoolDataDB] = None):
        super().__init__(db)
        self.model_path = model_path
        # Load ML model here
        logger.info("ML Strategy Generator initialized (placeholder)")

    def generate_strategy(self, request: ValidatorRequest) -> Strategy:
        """
        Generate strategy using ML model.

        In production:
        1. Query historical data from database
        2. Extract features (volatility, volume, fee rates, etc.)
        3. Run ML model to predict optimal ranges
        4. Construct positions based on predictions
        5. Apply constraints and risk management
        """
        # For now, fall back to simple rule-based
        logger.info("ML strategy generation not implemented, using rule-based")
        return super().generate_strategy(request)
