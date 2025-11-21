"""
Data models for SN98 ForeverMoney Validator-Miner communication.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class Mode(str, Enum):
    """Operation mode for strategy request."""
    INVENTORY = "inventory"
    POSITION = "position"


class Inventory(BaseModel):
    """Inventory of tokens available for deployment."""
    amount0: str = Field(..., description="Amount of token0 in wei")
    amount1: str = Field(..., description="Amount of token1 in wei")


class CurrentPosition(BaseModel):
    """Existing v3 LP position."""
    tickLower: int = Field(..., description="Lower tick of position")
    tickUpper: int = Field(..., description="Upper tick of position")
    liquidity: str = Field(..., description="Liquidity amount")


class Constraints(BaseModel):
    """Validation constraints for strategies."""
    max_il: float = Field(0.10, description="Maximum impermanent loss allowed")
    min_tick_width: int = Field(60, description="Minimum tick width for positions")
    max_rebalances: int = Field(4, description="Maximum number of rebalances allowed")


class Metadata(BaseModel):
    """Metadata for the round."""
    round_id: str = Field(..., description="Unique round identifier")
    constraints: Constraints = Field(default_factory=Constraints)


class ValidatorRequest(BaseModel):
    """Request sent from Validator to Miner."""
    pairAddress: str = Field(..., description="Address of the trading pair")
    chainId: int = Field(8453, description="Chain ID (Base = 8453)")
    target_block: int = Field(..., description="Target block number for strategy")
    mode: Mode = Field(Mode.INVENTORY, description="Operation mode")
    inventory: Optional[Inventory] = Field(None, description="Available inventory")
    current_positions: Optional[List[CurrentPosition]] = Field(
        default_factory=list, description="Existing positions"
    )
    metadata: Metadata = Field(..., description="Round metadata and constraints")
    postgres_access: Optional[Dict[str, Any]] = Field(
        None, description="Database access credentials"
    )

    @validator('inventory', always=True)
    def validate_mode_inventory(cls, v, values):
        """Ensure inventory is provided when mode is INVENTORY."""
        if values.get('mode') == Mode.INVENTORY and v is None:
            raise ValueError("inventory must be provided when mode is INVENTORY")
        return v


class Position(BaseModel):
    """A single v3 LP position."""
    tickLower: int = Field(..., description="Lower tick bound")
    tickUpper: int = Field(..., description="Upper tick bound")
    allocation0: str = Field(..., description="Amount of token0 to allocate")
    allocation1: str = Field(..., description="Amount of token1 to allocate")
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Confidence score (0-1)"
    )

    @validator('tickUpper')
    def validate_tick_range(cls, v, values):
        """Ensure tickUpper > tickLower."""
        if 'tickLower' in values and v <= values['tickLower']:
            raise ValueError("tickUpper must be greater than tickLower")
        return v


class RebalanceRule(BaseModel):
    """Optional rebalance rule for the strategy."""
    trigger: str = Field(..., description="Trigger condition (e.g., 'price_outside_range')")
    cooldown_blocks: int = Field(..., description="Minimum blocks between rebalances")


class Strategy(BaseModel):
    """Complete strategy output from miner."""
    positions: List[Position] = Field(..., description="List of LP positions")
    rebalance_rule: Optional[RebalanceRule] = Field(
        None, description="Optional rebalance rule"
    )


class MinerMetadata(BaseModel):
    """Metadata about the miner's model."""
    version: str = Field(..., description="Miner version")
    model_info: str = Field(..., description="Model description")


class MinerResponse(BaseModel):
    """Response from Miner to Validator."""
    strategy: Strategy = Field(..., description="Proposed strategy")
    miner_metadata: MinerMetadata = Field(..., description="Miner metadata")


class PerformanceMetrics(BaseModel):
    """Performance metrics for a strategy."""
    net_pnl: float = Field(..., description="Net PnL in base currency")
    hodl_pnl: float = Field(..., description="HODL baseline PnL")
    net_pnl_vs_hodl: float = Field(..., description="Net PnL vs HODL")
    total_fees_collected: float = Field(..., description="Total LP fees collected")
    impermanent_loss: float = Field(..., description="Impermanent loss incurred")
    num_rebalances: int = Field(..., description="Number of rebalances executed")


class MinerScore(BaseModel):
    """Complete scoring for a miner."""
    miner_uid: int = Field(..., description="Miner UID")
    miner_hotkey: str = Field(..., description="Miner hotkey")
    performance_score: float = Field(..., description="Performance score (0-1)")
    lp_alignment_score: float = Field(..., description="LP alignment score (0-1)")
    final_score: float = Field(..., description="Final weighted score")
    performance_metrics: PerformanceMetrics = Field(..., description="Detailed metrics")
    constraint_violations: List[str] = Field(
        default_factory=list, description="List of constraint violations"
    )
    rank: Optional[int] = Field(None, description="Rank among all miners")
