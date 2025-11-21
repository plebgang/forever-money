"""
Backtester for simulating LP strategy performance.
"""
import logging
from typing import List, Dict, Any, Tuple
from decimal import Decimal
import math

from validator.models import Strategy, Position, PerformanceMetrics
from validator.database import PoolDataDB

logger = logging.getLogger(__name__)


class UniswapV3Math:
    """Uniswap V3 math utilities for liquidity calculations."""

    @staticmethod
    def get_sqrt_ratio_at_tick(tick: int) -> int:
        """Calculate sqrtPriceX96 from tick."""
        return int(1.0001 ** (tick / 2) * (2 ** 96))

    @staticmethod
    def get_tick_at_sqrt_ratio(sqrt_price_x96: int) -> int:
        """Calculate tick from sqrtPriceX96."""
        price = (sqrt_price_x96 / (2 ** 96)) ** 2
        return int(math.log(price) / math.log(1.0001))

    @staticmethod
    def get_liquidity_for_amounts(
        sqrt_price_x96: int,
        sqrt_price_a_x96: int,
        sqrt_price_b_x96: int,
        amount0: int,
        amount1: int
    ) -> int:
        """
        Calculate liquidity from token amounts and price range.
        """
        if sqrt_price_x96 <= sqrt_price_a_x96:
            # All liquidity in token0
            liquidity = (amount0 * sqrt_price_a_x96 * sqrt_price_b_x96) // (
                (sqrt_price_b_x96 - sqrt_price_a_x96) * (2 ** 96)
            )
        elif sqrt_price_x96 < sqrt_price_b_x96:
            # Liquidity in both tokens
            liquidity0 = (amount0 * sqrt_price_x96 * sqrt_price_b_x96) // (
                (sqrt_price_b_x96 - sqrt_price_x96) * (2 ** 96)
            )
            liquidity1 = (amount1 * (2 ** 96)) // (sqrt_price_x96 - sqrt_price_a_x96)
            liquidity = min(liquidity0, liquidity1)
        else:
            # All liquidity in token1
            liquidity = (amount1 * (2 ** 96)) // (sqrt_price_b_x96 - sqrt_price_a_x96)

        return liquidity

    @staticmethod
    def get_amounts_for_liquidity(
        sqrt_price_x96: int,
        sqrt_price_a_x96: int,
        sqrt_price_b_x96: int,
        liquidity: int
    ) -> Tuple[int, int]:
        """
        Calculate token amounts from liquidity and price range.
        Returns (amount0, amount1).
        """
        if sqrt_price_x96 <= sqrt_price_a_x96:
            amount0 = (liquidity * (sqrt_price_b_x96 - sqrt_price_a_x96) * (2 ** 96)) // (
                sqrt_price_a_x96 * sqrt_price_b_x96
            )
            amount1 = 0
        elif sqrt_price_x96 < sqrt_price_b_x96:
            amount0 = (liquidity * (sqrt_price_b_x96 - sqrt_price_x96) * (2 ** 96)) // (
                sqrt_price_x96 * sqrt_price_b_x96
            )
            amount1 = (liquidity * (sqrt_price_x96 - sqrt_price_a_x96)) // (2 ** 96)
        else:
            amount0 = 0
            amount1 = (liquidity * (sqrt_price_b_x96 - sqrt_price_a_x96)) // (2 ** 96)

        return (amount0, amount1)


class Backtester:
    """
    Simulates LP strategy performance using historical pool events.
    Compares strategy performance against HODL baseline.
    """

    def __init__(self, db: PoolDataDB):
        self.db = db
        self.math = UniswapV3Math()

    def calculate_hodl_baseline(
        self,
        pair_address: str,
        initial_amount0: int,
        initial_amount1: int,
        start_block: int,
        end_block: int
    ) -> float:
        """
        Calculate the value of simply holding the tokens (HODL).

        Args:
            pair_address: Pool address
            initial_amount0: Initial amount of token0
            initial_amount1: Initial amount of token1
            start_block: Starting block
            end_block: Ending block

        Returns:
            Final value in terms of token1
        """
        # Get price at start and end
        start_price = self.db.get_price_at_block(pair_address, start_block)
        end_price = self.db.get_price_at_block(pair_address, end_block)

        if start_price is None or end_price is None:
            logger.warning("Could not fetch prices for HODL baseline")
            return 0.0

        # Calculate initial value in token1
        initial_value = initial_amount0 * start_price + initial_amount1

        # Calculate final value in token1 (tokens unchanged)
        final_value = initial_amount0 * end_price + initial_amount1

        return final_value

    def simulate_position(
        self,
        pair_address: str,
        position: Position,
        start_block: int,
        end_block: int,
        current_price: float
    ) -> Dict[str, Any]:
        """
        Simulate a single LP position over a block range.

        Returns:
            Dictionary containing:
            - fees_collected: Total fees earned
            - final_amount0: Amount of token0 at end
            - final_amount1: Amount of token1 at end
            - impermanent_loss: IL incurred
        """
        # Convert tick bounds to prices
        price_lower = 1.0001 ** position.tickLower
        price_upper = 1.0001 ** position.tickUpper

        # Get swap events in this range
        swap_events = self.db.get_swap_events(pair_address, start_block, end_block)

        # Calculate liquidity from initial amounts
        initial_amount0 = int(position.allocation0)
        initial_amount1 = int(position.allocation1)

        # Track position state
        total_fees0 = 0.0
        total_fees1 = 0.0
        current_amount0 = initial_amount0
        current_amount1 = initial_amount1

        # Simulate each swap
        for event in swap_events:
            event_price = float(event['event_data'].get('price', current_price))

            # Check if position is in range
            if price_lower <= event_price <= price_upper:
                # Position earns fees proportional to its liquidity share
                # Simplified: assume we capture some fraction of swap volume
                swap_amount0 = abs(float(event['event_data'].get('amount0', 0)))
                swap_amount1 = abs(float(event['event_data'].get('amount1', 0)))

                # Fee tier (typically 0.05%, 0.3%, or 1%)
                fee_rate = 0.003  # 0.3% default

                total_fees0 += swap_amount0 * fee_rate * 0.01  # Assume 1% liquidity share
                total_fees1 += swap_amount1 * fee_rate * 0.01

        # Calculate impermanent loss
        final_price = self.db.get_price_at_block(pair_address, end_block) or current_price

        # Calculate final amounts if price changed
        if final_price != current_price:
            # Adjust amounts based on price movement within range
            if price_lower <= final_price <= price_upper:
                # Use constant product formula
                k = current_amount0 * current_amount1
                # Price = amount1 / amount0
                current_amount0 = math.sqrt(k / final_price)
                current_amount1 = math.sqrt(k * final_price)

        # Calculate IL
        hodl_value = initial_amount0 * final_price + initial_amount1
        lp_value = current_amount0 * final_price + current_amount1 + total_fees0 * final_price + total_fees1
        impermanent_loss = (hodl_value - lp_value) / hodl_value if hodl_value > 0 else 0

        return {
            'fees_collected': total_fees0 * final_price + total_fees1,
            'final_amount0': current_amount0,
            'final_amount1': current_amount1,
            'impermanent_loss': max(0, impermanent_loss),
            'fees0': total_fees0,
            'fees1': total_fees1
        }

    def backtest_strategy(
        self,
        pair_address: str,
        strategy: Strategy,
        initial_amount0: int,
        initial_amount1: int,
        start_block: int,
        end_block: int
    ) -> PerformanceMetrics:
        """
        Backtest a complete strategy with multiple positions.

        Args:
            pair_address: Pool address
            strategy: Strategy to test
            initial_amount0: Initial amount of token0
            initial_amount1: Initial amount of token1
            start_block: Starting block
            end_block: Ending block

        Returns:
            PerformanceMetrics object
        """
        # Get current price
        current_price = self.db.get_price_at_block(pair_address, start_block) or 1.0
        final_price = self.db.get_price_at_block(pair_address, end_block) or current_price

        # Calculate HODL baseline
        hodl_pnl = self.calculate_hodl_baseline(
            pair_address, initial_amount0, initial_amount1, start_block, end_block
        )
        initial_value = initial_amount0 * current_price + initial_amount1

        # Simulate each position
        total_fees = 0.0
        total_il = 0.0
        final_value = 0.0

        for position in strategy.positions:
            result = self.simulate_position(
                pair_address, position, start_block, end_block, current_price
            )

            total_fees += result['fees_collected']
            total_il += result['impermanent_loss']
            final_value += result['final_amount0'] * final_price + result['final_amount1']

        # Calculate PnL
        net_pnl = final_value + total_fees - initial_value
        net_pnl_vs_hodl = net_pnl - (hodl_pnl - initial_value)

        # Count rebalances (simplified - just check if rebalance_rule exists)
        num_rebalances = 0
        if strategy.rebalance_rule:
            # Estimate based on price volatility and cooldown
            price_range = abs(final_price - current_price) / current_price
            if price_range > 0.1:  # 10% price movement
                num_rebalances = min(
                    int(price_range / 0.05),  # Rebalance every 5% move
                    4  # Max rebalances
                )

        return PerformanceMetrics(
            net_pnl=net_pnl,
            hodl_pnl=hodl_pnl - initial_value,
            net_pnl_vs_hodl=net_pnl_vs_hodl,
            total_fees_collected=total_fees,
            impermanent_loss=total_il,
            num_rebalances=num_rebalances
        )
