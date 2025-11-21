"""
Database utilities for querying pool events from Postgres.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Optional
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PoolDataDB:
    """
    Interface to the read-only Postgres database containing pool events.
    The database is fed by a subgraph and contains all on-chain events
    for Aerodrome pools (swaps, mints, burns, fee growth, etc.).
    """

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str
    ):
        self.connection_params = {
            'host': host,
            'port': port,
            'database': database,
            'user': user,
            'password': password
        }

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            conn = psycopg2.connect(**self.connection_params)
            yield conn
        except psycopg2.Error as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def get_pool_events(
        self,
        pair_address: str,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None,
        event_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch pool events for a specific pair within a block range.

        Args:
            pair_address: The pool/pair address
            start_block: Starting block (inclusive)
            end_block: Ending block (inclusive)
            event_types: List of event types to filter (e.g., ['swap', 'mint', 'burn'])

        Returns:
            List of event dictionaries
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    SELECT
                        block_number,
                        transaction_hash,
                        event_type,
                        event_data,
                        timestamp
                    FROM pool_events
                    WHERE pool_address = %s
                """
                params = [pair_address.lower()]

                if start_block is not None:
                    query += " AND block_number >= %s"
                    params.append(start_block)

                if end_block is not None:
                    query += " AND block_number <= %s"
                    params.append(end_block)

                if event_types:
                    query += " AND event_type = ANY(%s)"
                    params.append(event_types)

                query += " ORDER BY block_number ASC, transaction_hash"

                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

    def get_swap_events(
        self,
        pair_address: str,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch swap events specifically."""
        return self.get_pool_events(
            pair_address, start_block, end_block, event_types=['swap']
        )

    def get_price_at_block(
        self,
        pair_address: str,
        block_number: int
    ) -> Optional[float]:
        """
        Get the price (token1/token0) at a specific block.
        Uses the most recent swap before or at the block.
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    SELECT event_data->>'sqrtPriceX96' as sqrt_price
                    FROM pool_events
                    WHERE pool_address = %s
                        AND block_number <= %s
                        AND event_type = 'swap'
                    ORDER BY block_number DESC, transaction_hash DESC
                    LIMIT 1
                """
                cursor.execute(query, [pair_address.lower(), block_number])
                result = cursor.fetchone()

                if result and result['sqrt_price']:
                    # Convert sqrtPriceX96 to actual price
                    sqrt_price = int(result['sqrt_price'])
                    price = (sqrt_price / (2 ** 96)) ** 2
                    return price
                return None

    def get_fee_growth(
        self,
        pair_address: str,
        start_block: int,
        end_block: int
    ) -> Dict[str, float]:
        """
        Calculate fee growth between two blocks.

        Returns:
            Dictionary with 'fee0' and 'fee1' keys
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    SELECT
                        SUM(CAST(event_data->>'amount0' AS NUMERIC)) as total_fee0,
                        SUM(CAST(event_data->>'amount1' AS NUMERIC)) as total_fee1
                    FROM pool_events
                    WHERE pool_address = %s
                        AND block_number >= %s
                        AND block_number <= %s
                        AND event_type = 'collect'
                """
                cursor.execute(query, [pair_address.lower(), start_block, end_block])
                result = cursor.fetchone()

                return {
                    'fee0': float(result['total_fee0'] or 0),
                    'fee1': float(result['total_fee1'] or 0)
                }

    def get_tick_liquidity_distribution(
        self,
        pair_address: str,
        block_number: int
    ) -> List[Dict[str, Any]]:
        """
        Get the liquidity distribution across ticks at a specific block.
        Useful for understanding where liquidity is concentrated.
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    SELECT
                        event_data->>'tickLower' as tick_lower,
                        event_data->>'tickUpper' as tick_upper,
                        event_data->>'liquidity' as liquidity
                    FROM pool_events
                    WHERE pool_address = %s
                        AND block_number <= %s
                        AND event_type IN ('mint', 'burn')
                    ORDER BY block_number DESC
                """
                cursor.execute(query, [pair_address.lower(), block_number])
                return [dict(row) for row in cursor.fetchall()]

    def get_miner_vault_fees(
        self,
        vault_addresses: List[str],
        start_block: int,
        end_block: int
    ) -> Dict[str, float]:
        """
        Calculate total fees collected by miner vaults in a period.
        Used for the 30% LP Alignment score.

        Returns:
            Dictionary mapping vault_address to total fees collected (in USD equivalent)
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                query = """
                    SELECT
                        owner_address,
                        SUM(CAST(event_data->>'amount0' AS NUMERIC)) as total_fee0,
                        SUM(CAST(event_data->>'amount1' AS NUMERIC)) as total_fee1
                    FROM pool_events
                    WHERE owner_address = ANY(%s)
                        AND block_number >= %s
                        AND block_number <= %s
                        AND event_type = 'collect'
                    GROUP BY owner_address
                """
                cursor.execute(query, [vault_addresses, start_block, end_block])
                results = cursor.fetchall()

                # Convert to dictionary
                vault_fees = {}
                for row in results:
                    # TODO: Convert to USD using price oracle
                    # For now, use raw amounts
                    vault_fees[row['owner_address']] = {
                        'fee0': float(row['total_fee0'] or 0),
                        'fee1': float(row['total_fee1'] or 0)
                    }

                return vault_fees
