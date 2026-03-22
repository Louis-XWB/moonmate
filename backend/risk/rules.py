"""
Risk control rule definitions
Defines base classes and concrete implementations of various risk control rules
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from backend.data.models import Order, Position, Signal


class RiskCheckResult(BaseModel):
    """Risk check result"""
    passed: bool = True
    rule_name: str = ""
    reason: str = ""
    severity: str = Field(default="info", description="info/warning/critical")
    suggested_action: str = Field(default="", description="Suggested action")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskRule(ABC):
    """Risk rule base class"""
    
    def __init__(self, name: str, enabled: bool = True, priority: int = 0):
        self.name = name
        self.enabled = enabled
        self.priority = priority  # Higher priority executes first
    
    @abstractmethod
    def check(
        self,
        signal: Signal,
        positions: List[Position],
        orders: List[Order],
        context: Dict[str, Any]
    ) -> RiskCheckResult:
        """Execute risk check"""
        pass
    
    def _pass(self, reason: str = "") -> RiskCheckResult:
        """Return a pass result"""
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
        """Return a fail result"""
        return RiskCheckResult(
            passed=False,
            rule_name=self.name,
            reason=reason,
            severity=severity,
            suggested_action=suggested_action,
            metadata=metadata or {}
        )


class PositionLimitRule(RiskRule):
    """Position limit rule"""
    
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
        # Check position count
        active_positions = [p for p in positions if p.size > 0]
        if len(active_positions) >= self.max_positions:
            # Check if this is a close signal
            existing = [p for p in active_positions if p.symbol == signal.symbol]
            if not existing:
                return self._fail(
                    f"Position count has reached the limit({len(active_positions)}/{self.max_positions})",
                    severity="warning",
                    suggested_action="Wait for existing positions to close before opening new ones"
                )
        
        # Check individual position size
        for pos in active_positions:
            if pos.symbol == signal.symbol and pos.notional > self.max_position_size:
                return self._fail(
                    f"{signal.symbol}position has reached the limit(${pos.notional:.2f}/${self.max_position_size})",
                    severity="warning",
                    suggested_action="Reduce position or wait"
                )
        
        return self._pass()


class DailyLossRule(RiskRule):
    """Daily loss limit rule"""
    
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
        # Get daily PnL
        daily_pnl = context.get("daily_pnl", 0)
        initial_balance = context.get("initial_balance", 10000)
        
        # Check absolute loss
        if daily_pnl < -self.max_daily_loss:
            return self._fail(
                f"Today's loss has reached the limit(${abs(daily_pnl):.2f}/${self.max_daily_loss})",
                severity="critical",
                suggested_action="Stop trading, wait until tomorrow"
            )
        
        # Check percentage loss
        loss_pct = abs(daily_pnl) / initial_balance * 100 if initial_balance > 0 else 0
        if daily_pnl < 0 and loss_pct > self.max_daily_loss_pct:
            return self._fail(
                f"Today's loss percentage has reached the limit({loss_pct:.1f}%/{self.max_daily_loss_pct}%)",
                severity="critical",
                suggested_action="Stop trading, wait until tomorrow"
            )
        
        return self._pass()


class DrawdownRule(RiskRule):
    """Drawdown limit rule"""
    
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
        # Get current drawdown
        current_drawdown = context.get("current_drawdown", 0)
        
        if current_drawdown > self.max_drawdown:
            return self._fail(
                f"Current drawdown has reached the limit({current_drawdown:.1f}%/{self.max_drawdown}%)",
                severity="critical",
                suggested_action="Reduce position or stop trading"
            )
        
        return self._pass()


class ConsecutiveLossRule(RiskRule):
    """Consecutive loss rule"""
    
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
        # Check cooldown period
        if self._cooldown_until and datetime.now() < self._cooldown_until:
            remaining = (self._cooldown_until - datetime.now()).seconds // 60
            return self._fail(
                f"In cooldown period, remaining minutes remaining",
                severity="warning",
                suggested_action=f"Wait remaining minutes before trading again"
            )
        
        # Get consecutive loss count
        consecutive_losses = context.get("consecutive_losses", 0)
        
        if consecutive_losses >= self.max_consecutive_losses:
            self._cooldown_until = datetime.now() + timedelta(minutes=self.cooldown_minutes)
            return self._fail(
                f"Consecutive losses {consecutive_losses} times, triggering cooldown",
                severity="warning",
                suggested_action=f"Entering self.cooldown_minutes-minute cooldown period"
            )
        
        return self._pass()
    
    def reset_cooldown(self):
        """Reset cooldown period"""
        self._cooldown_until = None


class PriceProtectionRule(RiskRule):
    """Price protection rule"""
    
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
        # Get current market data
        ticker = context.get("ticker")
        if not ticker:
            return self._pass()
        
        # Check spread
        spread_pct = ticker.spread
        if spread_pct > self.max_spread_pct:
            return self._fail(
                f"Bid-Ask Spread too wide({spread_pct:.2f}%>{self.max_spread_pct}%)",
                severity="warning",
                suggested_action="Wait for spread to narrow"
            )
        
        # Check deviation between signal price and current price
        if signal.entry_price:
            slippage = abs(signal.entry_price - ticker.last_price) / ticker.last_price * 100
            if slippage > self.max_slippage_pct:
                return self._fail(
                    f"Price deviation too large({slippage:.2f}%>{self.max_slippage_pct}%)",
                    severity="warning",
                    suggested_action="Re-fetch signal"
                )
        
        return self._pass()
