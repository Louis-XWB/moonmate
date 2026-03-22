"""
Unified Data Models
Defines core data structures for market data, orders, positions, signals, etc.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
import uuid


# ==================== Market Data Models ====================

class Ticker(BaseModel):
    """Market ticker snapshot"""
    symbol: str = Field(..., description="Trading pair")
    last_price: float = Field(..., description="Latest price")
    bid_price: float = Field(default=0, description="Best bid price")
    ask_price: float = Field(default=0, description="Best ask price")
    bid_size: float = Field(default=0, description="Best bid size")
    ask_size: float = Field(default=0, description="Best ask size")
    volume_24h: float = Field(default=0, description="24h Volume")
    change_24h: float = Field(default=0, description="24h change percentage")
    high_24h: float = Field(default=0, description="24h high price")
    low_24h: float = Field(default=0, description="24h low price")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @property
    def spread(self) -> float:
        """Bid-Ask Spread"""
        if self.bid_price > 0:
            return (self.ask_price - self.bid_price) / self.bid_price * 100
        return 0


class OrderBookLevel(BaseModel):
    """Orderbook level"""
    price: float
    size: float


class OrderBook(BaseModel):
    """Orderbook"""
    symbol: str
    bids: List[OrderBookLevel] = Field(default_factory=list, description="Bid orders")
    asks: List[OrderBookLevel] = Field(default_factory=list, description="Ask orders")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @property
    def mid_price(self) -> float:
        """Mid price"""
        if self.bids and self.asks:
            return (self.bids[0].price + self.asks[0].price) / 2
        return 0
    
    @property
    def imbalance(self) -> float:
        """Orderbook imbalance (-1 to 1, positive means more buying pressure)"""
        if not self.bids or not self.asks:
            return 0
        bid_volume = sum(level.size for level in self.bids[:5])
        ask_volume = sum(level.size for level in self.asks[:5])
        total = bid_volume + ask_volume
        if total == 0:
            return 0
        return (bid_volume - ask_volume) / total


class Trade(BaseModel):
    """Trade record"""
    symbol: str
    price: float
    size: float
    side: str = Field(..., description="buy/sell")
    timestamp: datetime = Field(default_factory=datetime.now)
    trade_id: str = Field(default="")


class Kline(BaseModel):
    """Candlestick data"""
    symbol: str
    interval: str = Field(..., description="Time interval: 1m, 5m, 15m, 1h, 4h, 1d")
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: datetime
    quote_volume: float = Field(default=0, description="Trading volume (quote)")
    trades_count: int = Field(default=0, description="Number of trades")
    
    @property
    def is_bullish(self) -> bool:
        """Whether bullish candle"""
        return self.close > self.open
    
    @property
    def body_size(self) -> float:
        """Body size"""
        return abs(self.close - self.open)
    
    @property
    def upper_shadow(self) -> float:
        """Upper shadow"""
        return self.high - max(self.open, self.close)
    
    @property
    def lower_shadow(self) -> float:
        """Lower shadow"""
        return min(self.open, self.close) - self.low


# ==================== Order Data Models ====================

class OrderSide(str, Enum):
    """Order side"""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(str, Enum):
    """Order status"""
    PENDING = "pending"           # Pending
    SUBMITTED = "submitted"       # Submitted
    PARTIAL_FILLED = "partial_filled"  # Partially filled
    FILLED = "filled"             # Fully filled
    CANCELLED = "cancelled"       # Cancelled
    REJECTED = "rejected"         # Rejected
    EXPIRED = "expired"           # Expired


class Order(BaseModel):
    """Order"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    side: OrderSide
    type: OrderType = Field(default=OrderType.LIMIT)
    price: float = Field(default=0, description="Limit order price")
    size: float = Field(..., description="Order quantity")
    filled_size: float = Field(default=0, description="Filled quantity")
    avg_price: float = Field(default=0, description="Average fill price")
    status: OrderStatus = Field(default=OrderStatus.PENDING)
    
    # Stop-loss / Take-profit
    stop_loss: Optional[float] = Field(default=None)
    take_profit: Optional[float] = Field(default=None)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    filled_at: Optional[datetime] = Field(default=None)
    
    # Related information
    strategy_id: str = Field(default="", description="Strategy ID")
    signal_id: str = Field(default="", description="Signal ID")
    exchange_order_id: str = Field(default="", description="Exchange order ID")
    
    # Cost information
    fee: float = Field(default=0, description="Fee")
    fee_currency: str = Field(default="USDT")
    
    # Note
    reason: str = Field(default="", description="Order reason")
    error_msg: str = Field(default="", description="Error message")
    
    @property
    def remaining_size(self) -> float:
        """Remaining unfilled quantity"""
        return self.size - self.filled_size
    
    @property
    def is_active(self) -> bool:
        """Whether order is active"""
        return self.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL_FILLED]
    
    @property
    def notional(self) -> float:
        """Order notional value"""
        price = self.avg_price if self.avg_price > 0 else self.price
        return price * self.size
    
    class Config:
        use_enum_values = True


# ==================== Position Data Models ====================

class Position(BaseModel):
    """Position"""
    symbol: str
    side: OrderSide = Field(..., description="Position direction")
    size: float = Field(default=0, description="Position size")
    entry_price: float = Field(default=0, description="Average entry price")
    current_price: float = Field(default=0, description="Current Price")
    liquidation_price: float = Field(default=0, description="Liquidation price")
    leverage: int = Field(default=1, description="Leverage multiplier")
    
    # P&L
    unrealized_pnl: float = Field(default=0, description="Unrealized P&L")
    realized_pnl: float = Field(default=0, description="Realized P&L")
    
    # Time
    opened_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Stop-loss / Take-profit
    stop_loss: Optional[float] = Field(default=None)
    take_profit: Optional[float] = Field(default=None)
    
    @property
    def notional(self) -> float:
        """Position notional value"""
        return self.size * self.current_price
    
    @property
    def pnl_pct(self) -> float:
        """P&L percentage"""
        if self.entry_price == 0:
            return 0
        if self.side == OrderSide.BUY:
            return (self.current_price - self.entry_price) / self.entry_price * 100
        else:
            return (self.entry_price - self.current_price) / self.entry_price * 100
    
    def update_pnl(self, current_price: float):
        """Update P&L"""
        self.current_price = current_price
        if self.side == OrderSide.BUY:
            self.unrealized_pnl = (current_price - self.entry_price) * self.size
        else:
            self.unrealized_pnl = (self.entry_price - current_price) * self.size
        self.updated_at = datetime.now()
    
    class Config:
        use_enum_values = True


class Balance(BaseModel):
    """Account balance"""
    currency: str
    free: float = Field(default=0, description="Available balance")
    locked: float = Field(default=0, description="Frozen balance")
    total: float = Field(default=0, description="Total balance")
    updated_at: datetime = Field(default_factory=datetime.now)


# ==================== Signal Data Models ====================

class SignalDirection(str, Enum):
    """Signal direction"""
    LONG = "long"       # Long
    SHORT = "short"     # Short
    CLOSE = "close"     # Close position
    NEUTRAL = "neutral" # Neutral/Hold


class Signal(BaseModel):
    """Trading signal"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    direction: SignalDirection
    strength: float = Field(default=0.5, ge=0, le=1, description="Signal strength 0-1")
    confidence: float = Field(default=0.5, ge=0, le=1, description="Confidence 0-1")
    
    # Price recommendations
    entry_price: Optional[float] = Field(default=None, description="Suggested entry price")
    stop_loss: Optional[float] = Field(default=None, description="Suggested stop-loss price")
    take_profit: Optional[float] = Field(default=None, description="Suggested take-profit price")
    
    # Signal source
    source: str = Field(default="", description="Signal source: ai, momentum, reversal, orderbook")
    strategy_id: str = Field(default="", description="Strategy ID")
    
    # Time validity
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = Field(default=None, description="Expiration time")
    ttl: int = Field(default=300, description="TTL (seconds)")
    
    # Explanatory
    reason: str = Field(default="", description="Signal reason")
    evidence: List[str] = Field(default_factory=list, description="Evidence list")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @property
    def is_valid(self) -> bool:
        """Whether signal is valid"""
        if self.expires_at:
            return datetime.now() < self.expires_at
        return (datetime.now() - self.created_at).total_seconds() < self.ttl
    
    @property
    def is_actionable(self) -> bool:
        """Whether signal is actionable"""
        return self.is_valid and self.direction != SignalDirection.NEUTRAL
    
    class Config:
        use_enum_values = True
