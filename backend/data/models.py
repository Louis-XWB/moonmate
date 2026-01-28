"""
统一数据模型
定义行情、订单、持仓、信号等核心数据结构
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
import uuid


# ==================== 行情数据模型 ====================

class Ticker(BaseModel):
    """行情快照"""
    symbol: str = Field(..., description="交易对")
    last_price: float = Field(..., description="最新价格")
    bid_price: float = Field(default=0, description="买一价")
    ask_price: float = Field(default=0, description="卖一价")
    bid_size: float = Field(default=0, description="买一量")
    ask_size: float = Field(default=0, description="卖一量")
    volume_24h: float = Field(default=0, description="24小时成交量")
    change_24h: float = Field(default=0, description="24小时涨跌幅")
    high_24h: float = Field(default=0, description="24小时最高价")
    low_24h: float = Field(default=0, description="24小时最低价")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @property
    def spread(self) -> float:
        """买卖价差"""
        if self.bid_price > 0:
            return (self.ask_price - self.bid_price) / self.bid_price * 100
        return 0


class OrderBookLevel(BaseModel):
    """订单簿档位"""
    price: float
    size: float


class OrderBook(BaseModel):
    """订单簿"""
    symbol: str
    bids: List[OrderBookLevel] = Field(default_factory=list, description="买单")
    asks: List[OrderBookLevel] = Field(default_factory=list, description="卖单")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    @property
    def mid_price(self) -> float:
        """中间价"""
        if self.bids and self.asks:
            return (self.bids[0].price + self.asks[0].price) / 2
        return 0
    
    @property
    def imbalance(self) -> float:
        """订单簿失衡度 (-1 到 1，正数表示买压大)"""
        if not self.bids or not self.asks:
            return 0
        bid_volume = sum(level.size for level in self.bids[:5])
        ask_volume = sum(level.size for level in self.asks[:5])
        total = bid_volume + ask_volume
        if total == 0:
            return 0
        return (bid_volume - ask_volume) / total


class Trade(BaseModel):
    """成交记录"""
    symbol: str
    price: float
    size: float
    side: str = Field(..., description="buy/sell")
    timestamp: datetime = Field(default_factory=datetime.now)
    trade_id: str = Field(default="")


class Kline(BaseModel):
    """K线数据"""
    symbol: str
    interval: str = Field(..., description="时间周期: 1m, 5m, 15m, 1h, 4h, 1d")
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: datetime
    quote_volume: float = Field(default=0, description="成交额")
    trades_count: int = Field(default=0, description="成交笔数")
    
    @property
    def is_bullish(self) -> bool:
        """是否阳线"""
        return self.close > self.open
    
    @property
    def body_size(self) -> float:
        """实体大小"""
        return abs(self.close - self.open)
    
    @property
    def upper_shadow(self) -> float:
        """上影线"""
        return self.high - max(self.open, self.close)
    
    @property
    def lower_shadow(self) -> float:
        """下影线"""
        return min(self.open, self.close) - self.low


# ==================== 订单数据模型 ====================

class OrderSide(str, Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(str, Enum):
    """订单状态"""
    PENDING = "pending"           # 待提交
    SUBMITTED = "submitted"       # 已提交
    PARTIAL_FILLED = "partial_filled"  # 部分成交
    FILLED = "filled"             # 完全成交
    CANCELLED = "cancelled"       # 已取消
    REJECTED = "rejected"         # 被拒绝
    EXPIRED = "expired"           # 已过期


class Order(BaseModel):
    """订单"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    side: OrderSide
    type: OrderType = Field(default=OrderType.LIMIT)
    price: float = Field(default=0, description="限价单价格")
    size: float = Field(..., description="下单数量")
    filled_size: float = Field(default=0, description="已成交数量")
    avg_price: float = Field(default=0, description="平均成交价")
    status: OrderStatus = Field(default=OrderStatus.PENDING)
    
    # 止损止盈
    stop_loss: Optional[float] = Field(default=None)
    take_profit: Optional[float] = Field(default=None)
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    filled_at: Optional[datetime] = Field(default=None)
    
    # 关联信息
    strategy_id: str = Field(default="", description="策略ID")
    signal_id: str = Field(default="", description="信号ID")
    exchange_order_id: str = Field(default="", description="交易所订单ID")
    
    # 成本信息
    fee: float = Field(default=0, description="手续费")
    fee_currency: str = Field(default="USDT")
    
    # 备注
    reason: str = Field(default="", description="下单原因")
    error_msg: str = Field(default="", description="错误信息")
    
    @property
    def remaining_size(self) -> float:
        """剩余未成交数量"""
        return self.size - self.filled_size
    
    @property
    def is_active(self) -> bool:
        """是否活跃订单"""
        return self.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIAL_FILLED]
    
    @property
    def notional(self) -> float:
        """订单名义价值"""
        price = self.avg_price if self.avg_price > 0 else self.price
        return price * self.size
    
    class Config:
        use_enum_values = True


# ==================== 持仓数据模型 ====================

class Position(BaseModel):
    """持仓"""
    symbol: str
    side: OrderSide = Field(..., description="持仓方向")
    size: float = Field(default=0, description="持仓数量")
    entry_price: float = Field(default=0, description="开仓均价")
    current_price: float = Field(default=0, description="当前价格")
    liquidation_price: float = Field(default=0, description="强平价格")
    leverage: int = Field(default=1, description="杠杆倍数")
    
    # 盈亏
    unrealized_pnl: float = Field(default=0, description="未实现盈亏")
    realized_pnl: float = Field(default=0, description="已实现盈亏")
    
    # 时间
    opened_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # 止损止盈
    stop_loss: Optional[float] = Field(default=None)
    take_profit: Optional[float] = Field(default=None)
    
    @property
    def notional(self) -> float:
        """持仓名义价值"""
        return self.size * self.current_price
    
    @property
    def pnl_pct(self) -> float:
        """盈亏百分比"""
        if self.entry_price == 0:
            return 0
        if self.side == OrderSide.BUY:
            return (self.current_price - self.entry_price) / self.entry_price * 100
        else:
            return (self.entry_price - self.current_price) / self.entry_price * 100
    
    def update_pnl(self, current_price: float):
        """更新盈亏"""
        self.current_price = current_price
        if self.side == OrderSide.BUY:
            self.unrealized_pnl = (current_price - self.entry_price) * self.size
        else:
            self.unrealized_pnl = (self.entry_price - current_price) * self.size
        self.updated_at = datetime.now()
    
    class Config:
        use_enum_values = True


class Balance(BaseModel):
    """账户余额"""
    currency: str
    free: float = Field(default=0, description="可用余额")
    locked: float = Field(default=0, description="冻结余额")
    total: float = Field(default=0, description="总余额")
    updated_at: datetime = Field(default_factory=datetime.now)


# ==================== 信号数据模型 ====================

class SignalDirection(str, Enum):
    """信号方向"""
    LONG = "long"       # 做多
    SHORT = "short"     # 做空
    CLOSE = "close"     # 平仓
    NEUTRAL = "neutral" # 中性/观望


class Signal(BaseModel):
    """交易信号"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    direction: SignalDirection
    strength: float = Field(default=0.5, ge=0, le=1, description="信号强度 0-1")
    confidence: float = Field(default=0.5, ge=0, le=1, description="置信度 0-1")
    
    # 价格建议
    entry_price: Optional[float] = Field(default=None, description="建议入场价")
    stop_loss: Optional[float] = Field(default=None, description="建议止损价")
    take_profit: Optional[float] = Field(default=None, description="建议止盈价")
    
    # 信号来源
    source: str = Field(default="", description="信号来源: ai, momentum, reversal, orderbook")
    strategy_id: str = Field(default="", description="策略ID")
    
    # 时效性
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = Field(default=None, description="过期时间")
    ttl: int = Field(default=300, description="有效期(秒)")
    
    # 解释性
    reason: str = Field(default="", description="信号原因")
    evidence: List[str] = Field(default_factory=list, description="证据列表")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @property
    def is_valid(self) -> bool:
        """信号是否有效"""
        if self.expires_at:
            return datetime.now() < self.expires_at
        return (datetime.now() - self.created_at).total_seconds() < self.ttl
    
    @property
    def is_actionable(self) -> bool:
        """信号是否可执行"""
        return self.is_valid and self.direction != SignalDirection.NEUTRAL
    
    class Config:
        use_enum_values = True
