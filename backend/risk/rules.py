"""
风控规则定义
定义各种风控规则的基类和具体实现
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from backend.data.models import Order, Position, Signal


class RiskCheckResult(BaseModel):
    """风控检查结果"""
    passed: bool = True
    rule_name: str = ""
    reason: str = ""
    severity: str = Field(default="info", description="info/warning/critical")
    suggested_action: str = Field(default="", description="建议操作")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskRule(ABC):
    """风控规则基类"""
    
    def __init__(self, name: str, enabled: bool = True, priority: int = 0):
        self.name = name
        self.enabled = enabled
        self.priority = priority  # 优先级越高越先执行
    
    @abstractmethod
    def check(
        self,
        signal: Signal,
        positions: List[Position],
        orders: List[Order],
        context: Dict[str, Any]
    ) -> RiskCheckResult:
        """执行风控检查"""
        pass
    
    def _pass(self, reason: str = "") -> RiskCheckResult:
        """返回通过结果"""
        return RiskCheckResult(
            passed=True,
            rule_name=self.name,
            reason=reason
        )
    
    def _fail(
        self,
        reason: str,
        severity: str = "warning",
        suggested_action: str = "",
        metadata: Optional[Dict] = None
    ) -> RiskCheckResult:
        """返回失败结果"""
        return RiskCheckResult(
            passed=False,
            rule_name=self.name,
            reason=reason,
            severity=severity,
            suggested_action=suggested_action,
            metadata=metadata or {}
        )


class PositionLimitRule(RiskRule):
    """持仓限制规则"""
    
    def __init__(
        self,
        max_positions: int = 3,
        max_position_size: float = 1000,
        max_single_order: float = 100
    ):
        super().__init__("position_limit", priority=100)
        self.max_positions = max_positions
        self.max_position_size = max_position_size
        self.max_single_order = max_single_order
    
    def check(
        self,
        signal: Signal,
        positions: List[Position],
        orders: List[Order],
        context: Dict[str, Any]
    ) -> RiskCheckResult:
        # 检查持仓数量
        active_positions = [p for p in positions if p.size > 0]
        if len(active_positions) >= self.max_positions:
            # 检查是否是平仓信号
            existing = [p for p in active_positions if p.symbol == signal.symbol]
            if not existing:
                return self._fail(
                    f"持仓数量已达上限({len(active_positions)}/{self.max_positions})",
                    severity="warning",
                    suggested_action="等待现有持仓平仓后再开新仓"
                )
        
        # 检查单个持仓大小
        for pos in active_positions:
            if pos.symbol == signal.symbol and pos.notional > self.max_position_size:
                return self._fail(
                    f"{signal.symbol}持仓已达上限(${pos.notional:.2f}/${self.max_position_size})",
                    severity="warning",
                    suggested_action="减仓或等待"
                )
        
        return self._pass()


class DailyLossRule(RiskRule):
    """日亏损限制规则"""
    
    def __init__(
        self,
        max_daily_loss: float = 100,
        max_daily_loss_pct: float = 5.0
    ):
        super().__init__("daily_loss", priority=90)
        self.max_daily_loss = max_daily_loss
        self.max_daily_loss_pct = max_daily_loss_pct
    
    def check(
        self,
        signal: Signal,
        positions: List[Position],
        orders: List[Order],
        context: Dict[str, Any]
    ) -> RiskCheckResult:
        # 获取今日盈亏
        daily_pnl = context.get("daily_pnl", 0)
        initial_balance = context.get("initial_balance", 10000)
        
        # 检查绝对亏损
        if daily_pnl < -self.max_daily_loss:
            return self._fail(
                f"今日亏损已达上限(${abs(daily_pnl):.2f}/${self.max_daily_loss})",
                severity="critical",
                suggested_action="停止交易，等待明日"
            )
        
        # 检查百分比亏损
        loss_pct = abs(daily_pnl) / initial_balance * 100 if initial_balance > 0 else 0
        if daily_pnl < 0 and loss_pct > self.max_daily_loss_pct:
            return self._fail(
                f"今日亏损百分比已达上限({loss_pct:.1f}%/{self.max_daily_loss_pct}%)",
                severity="critical",
                suggested_action="停止交易，等待明日"
            )
        
        return self._pass()


class DrawdownRule(RiskRule):
    """回撤限制规则"""
    
    def __init__(self, max_drawdown: float = 10.0):
        super().__init__("drawdown", priority=95)
        self.max_drawdown = max_drawdown
    
    def check(
        self,
        signal: Signal,
        positions: List[Position],
        orders: List[Order],
        context: Dict[str, Any]
    ) -> RiskCheckResult:
        # 获取当前回撤
        current_drawdown = context.get("current_drawdown", 0)
        
        if current_drawdown > self.max_drawdown:
            return self._fail(
                f"当前回撤已达上限({current_drawdown:.1f}%/{self.max_drawdown}%)",
                severity="critical",
                suggested_action="减仓或停止交易"
            )
        
        return self._pass()


class ConsecutiveLossRule(RiskRule):
    """连续亏损规则"""
    
    def __init__(self, max_consecutive_losses: int = 5, cooldown_minutes: int = 60):
        super().__init__("consecutive_loss", priority=85)
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_minutes = cooldown_minutes
        self._cooldown_until: Optional[datetime] = None
    
    def check(
        self,
        signal: Signal,
        positions: List[Position],
        orders: List[Order],
        context: Dict[str, Any]
    ) -> RiskCheckResult:
        # 检查冷却期
        if self._cooldown_until and datetime.now() < self._cooldown_until:
            remaining = (self._cooldown_until - datetime.now()).seconds // 60
            return self._fail(
                f"冷却期中，剩余{remaining}分钟",
                severity="warning",
                suggested_action=f"等待{remaining}分钟后再交易"
            )
        
        # 获取连续亏损次数
        consecutive_losses = context.get("consecutive_losses", 0)
        
        if consecutive_losses >= self.max_consecutive_losses:
            self._cooldown_until = datetime.now() + timedelta(minutes=self.cooldown_minutes)
            return self._fail(
                f"连续亏损{consecutive_losses}次，触发冷却期",
                severity="warning",
                suggested_action=f"进入{self.cooldown_minutes}分钟冷却期"
            )
        
        return self._pass()
    
    def reset_cooldown(self):
        """重置冷却期"""
        self._cooldown_until = None


class PriceProtectionRule(RiskRule):
    """价格保护规则"""
    
    def __init__(self, max_slippage_pct: float = 1.0, max_spread_pct: float = 0.5):
        super().__init__("price_protection", priority=80)
        self.max_slippage_pct = max_slippage_pct
        self.max_spread_pct = max_spread_pct
    
    def check(
        self,
        signal: Signal,
        positions: List[Position],
        orders: List[Order],
        context: Dict[str, Any]
    ) -> RiskCheckResult:
        # 获取当前市场数据
        ticker = context.get("ticker")
        if not ticker:
            return self._pass()
        
        # 检查价差
        spread_pct = ticker.spread
        if spread_pct > self.max_spread_pct:
            return self._fail(
                f"买卖价差过大({spread_pct:.2f}%>{self.max_spread_pct}%)",
                severity="warning",
                suggested_action="等待价差收窄"
            )
        
        # 检查信号价格与当前价格的偏差
        if signal.entry_price:
            slippage = abs(signal.entry_price - ticker.last_price) / ticker.last_price * 100
            if slippage > self.max_slippage_pct:
                return self._fail(
                    f"价格偏差过大({slippage:.2f}%>{self.max_slippage_pct}%)",
                    severity="warning",
                    suggested_action="重新获取信号"
                )
        
        return self._pass()
