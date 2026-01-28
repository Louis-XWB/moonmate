"""
策略基类
定义策略接口和通用功能
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from backend.data.models import Signal, SignalDirection, Ticker, Kline, Position


class StrategyState(BaseModel):
    """策略状态"""
    name: str
    enabled: bool = True
    last_signal: Optional[Signal] = None
    last_run: Optional[datetime] = None
    run_count: int = 0
    signal_count: int = 0
    params: Dict[str, Any] = Field(default_factory=dict)


class BaseStrategy(ABC):
    """策略基类"""
    
    def __init__(self, name: str, params: Optional[Dict[str, Any]] = None):
        self.name = name
        self.params = params or {}
        self.state = StrategyState(name=name, params=self.params)
        self._enabled = True
    
    @property
    def enabled(self) -> bool:
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        self.state.enabled = value
    
    @abstractmethod
    async def generate_signal(
        self,
        symbol: str,
        ticker: Ticker,
        klines: List[Kline],
        position: Optional[Position] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Signal:
        """生成交易信号"""
        pass
    
    async def run(
        self,
        symbol: str,
        ticker: Ticker,
        klines: List[Kline],
        position: Optional[Position] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Signal:
        """运行策略"""
        if not self._enabled:
            return Signal(
                symbol=symbol,
                direction=SignalDirection.NEUTRAL,
                strength=0,
                confidence=0,
                source=self.name,
                reason="Strategy disabled"
            )
        
        signal = await self.generate_signal(symbol, ticker, klines, position, context)
        
        # 更新状态
        self.state.last_signal = signal
        self.state.last_run = datetime.now()
        self.state.run_count += 1
        if signal.direction != SignalDirection.NEUTRAL:
            self.state.signal_count += 1
        
        return signal
    
    def get_state(self) -> StrategyState:
        """获取策略状态"""
        return self.state
    
    def update_params(self, params: Dict[str, Any]):
        """更新策略参数"""
        self.params.update(params)
        self.state.params = self.params
    
    def reset(self):
        """重置策略状态"""
        self.state = StrategyState(name=self.name, params=self.params)
