"""
Risk Engine
Manages and executes all risk control rules
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from backend.data.models import Order, Position, Signal
from backend.core.logger import get_logger
from backend.core.events import EventBus, Event, EventType, get_event_bus
from .rules import (
    RiskRule, RiskCheckResult,
    PositionLimitRule, DailyLossRule, DrawdownRule,
    ConsecutiveLossRule, PriceProtectionRule
)

logger = get_logger("risk_engine")


class RiskState(BaseModel):
    """Risk control state"""
    is_trading_allowed: bool = True
    circuit_breaker_active: bool = False
    cooldown_until: Optional[datetime] = None
    daily_pnl: float = 0
    current_drawdown: float = 0
    consecutive_losses: int = 0
    peak_balance: float = 0
    last_check_time: Optional[datetime] = None
    failed_checks: List[str] = Field(default_factory=list)


class RiskCheckResult(BaseModel):
    """Risk check result"""
    passed: bool = True
    rule_name: str = ""
    reason: str = ""
    severity: str = Field(default="info", description="info/warning/critical")
    suggested_action: str = Field(default="", description="Suggested action")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskEngine:
    """Risk Engine"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.rules: List[RiskRule] = []
        self.state = RiskState()
        self.event_bus = get_event_bus()
        
        # Initialize default rules
        self._init_default_rules()
    
    def _init_default_rules(self):
        """Initialize default risk control rules"""
        self.rules = [
            PositionLimitRule(
                max_positions=self.config.get("max_positions", 3),
                max_position_size=self.config.get("max_position_size", 1000),
                max_single_order=self.config.get("max_single_order", 100)
            ),
            DailyLossRule(
                max_daily_loss=self.config.get("max_daily_loss", 100),
                max_daily_loss_pct=self.config.get("max_daily_loss_pct", 5.0)
            ),
            DrawdownRule(
                max_drawdown=self.config.get("max_drawdown", 10.0)
            ),
            ConsecutiveLossRule(
                max_consecutive_losses=self.config.get("max_consecutive_losses", 5),
                cooldown_minutes=self.config.get("cooldown_minutes", 60)
            ),
            PriceProtectionRule(
                max_slippage_pct=self.config.get("max_slippage_pct", 1.0),
                max_spread_pct=self.config.get("max_spread_pct", 0.5)
            )
        ]
        
        # Sort by priority
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def add_rule(self, rule: RiskRule):
        """Add risk control rule"""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def remove_rule(self, rule_name: str):
        """Remove risk control rule"""
        self.rules = [r for r in self.rules if r.name != rule_name]
    
    def check(
        self,
        signal: Signal,
        positions: List[Position],
        orders: List[Order],
        context: Optional[Dict[str, Any]] = None
    ) -> RiskCheckResult:
        """
        Execute risk control check
        
        Args:
            signal: Trading signal
            positions: Current positions list
            orders: Current orders list
            context: Additional context (account info, market data, etc.)
            
        Returns:
            Risk check result
        """
        context = context or {}
        
        # Add risk state to context
        context.update({
            "daily_pnl": self.state.daily_pnl,
            "current_drawdown": self.state.current_drawdown,
            "consecutive_losses": self.state.consecutive_losses
        })
        
        # Check circuit breaker status
        if self.state.circuit_breaker_active:
            return RiskCheckResult(
                passed=False,
                rule_name="circuit_breaker",
                reason="Circuit breaker is active, trading is prohibited",
                severity="critical",
                suggested_action="Wait for circuit breaker to reset"
            )
        
        # Check cooldown period
        if self.state.cooldown_until and datetime.now() < self.state.cooldown_until:
            remaining = (self.state.cooldown_until - datetime.now()).seconds // 60
            return RiskCheckResult(
                passed=False,
                rule_name="cooldown",
                reason=f"In cooldown period, {remaining} minutes remaining",
                severity="warning",
                suggested_action=f"Wait for {remaining} minutes"
            )
        
        # Execute all rule checks
        failed_results = []
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            try:
                result = rule.check(signal, positions, orders, context)
                
                if not result.passed:
                    failed_results.append(result)
                    logger.warning(f"Risk check failed: {rule.name} - {result.reason}")
                    
                    # If critical severity, return immediately
                    if result.severity == "critical":
                        self._handle_critical_failure(result)
                        return result
                        
            except Exception as e:
                logger.error(f"Risk rule {rule.name} error: {e}")
        
        # If there are failed checks
        if failed_results:
            # Return highest priority failure
            self.state.failed_checks = [r.rule_name for r in failed_results]
            return failed_results[0]
        
        # All checks passed
        self.state.last_check_time = datetime.now()
        self.state.failed_checks = []
        
        return RiskCheckResult(
            passed=True,
            rule_name="all",
            reason="All risk checks passed"
        )
    
    def _handle_critical_failure(self, result: RiskCheckResult):
        """Handle critical risk failure"""
        logger.critical(f"Critical risk failure: {result.reason}")
        
        # Send risk event
        self.event_bus.publish_sync(Event(
            type=EventType.RISK_CHECK_FAILED,
            source="risk_engine",
            data={
                "rule_name": result.rule_name,
                "reason": result.reason,
                "severity": result.severity
            }
        ))
    
    def update_pnl(self, pnl: float):
        """Update profit/loss"""
        self.state.daily_pnl += pnl
        
        # Update consecutive losses
        if pnl < 0:
            self.state.consecutive_losses += 1
        else:
            self.state.consecutive_losses = 0
    
    def update_balance(self, balance: float):
        """Update account balance"""
        # Update peak
        if balance > self.state.peak_balance:
            self.state.peak_balance = balance
        
        # Calculate drawdown
        if self.state.peak_balance > 0:
            self.state.current_drawdown = (self.state.peak_balance - balance) / self.state.peak_balance * 100
    
    def trigger_circuit_breaker(self, reason: str):
        """Trigger circuit breaker"""
        self.state.circuit_breaker_active = True
        self.state.is_trading_allowed = False
        
        logger.critical(f"Circuit breaker triggered: {reason}")
        
        self.event_bus.publish_sync(Event(
            type=EventType.RISK_CIRCUIT_BREAK,
            source="risk_engine",
            data={"reason": reason}
        ))
    
    def reset_circuit_breaker(self):
        """Reset circuit breaker"""
        self.state.circuit_breaker_active = False
        self.state.is_trading_allowed = True
        
        logger.info("Circuit breaker reset")
    
    def start_cooldown(self, minutes: int):
        """Start cooldown period"""
        from datetime import timedelta
        self.state.cooldown_until = datetime.now() + timedelta(minutes=minutes)
        logger.warning(f"Cooldown started for {minutes} minutes")
    
    def reset_daily(self):
        """Reset daily statistics"""
        self.state.daily_pnl = 0
        self.state.consecutive_losses = 0
        self.state.failed_checks = []
        logger.info("Daily risk stats reset")
    
    def get_state(self) -> RiskState:
        """Get risk state"""
        return self.state
    
    def get_rules_status(self) -> List[Dict]:
        """Get all rules status"""
        return [
            {
                "name": rule.name,
                "enabled": rule.enabled,
                "priority": rule.priority
            }
            for rule in self.rules
        ]
