"""
风控引擎
管理和执行所有风控规则
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
    """风控状态"""
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
    """风控检查结果"""
    passed: bool = True
    rule_name: str = ""
    reason: str = ""
    severity: str = Field(default="info", description="info/warning/critical")
    suggested_action: str = Field(default="", description="建议操作")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskEngine:
    """风控引擎"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.rules: List[RiskRule] = []
        self.state = RiskState()
        self.event_bus = get_event_bus()
        
        # 初始化默认规则
        self._init_default_rules()
    
    def _init_default_rules(self):
        """初始化默认风控规则"""
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
        
        # 按优先级排序
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def add_rule(self, rule: RiskRule):
        """添加风控规则"""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def remove_rule(self, rule_name: str):
        """移除风控规则"""
        self.rules = [r for r in self.rules if r.name != rule_name]
    
    def check(
        self,
        signal: Signal,
        positions: List[Position],
        orders: List[Order],
        context: Optional[Dict[str, Any]] = None
    ) -> RiskCheckResult:
        """
        执行风控检查
        
        Args:
            signal: 交易信号
            positions: 当前持仓列表
            orders: 当前订单列表
            context: 额外上下文（包含账户信息、市场数据等）
            
        Returns:
            风控检查结果
        """
        context = context or {}
        
        # 添加风控状态到上下文
        context.update({
            "daily_pnl": self.state.daily_pnl,
            "current_drawdown": self.state.current_drawdown,
            "consecutive_losses": self.state.consecutive_losses
        })
        
        # 检查熔断状态
        if self.state.circuit_breaker_active:
            return RiskCheckResult(
                passed=False,
                rule_name="circuit_breaker",
                reason="熔断器已激活，禁止交易",
                severity="critical",
                suggested_action="等待熔断解除"
            )
        
        # 检查冷却期
        if self.state.cooldown_until and datetime.now() < self.state.cooldown_until:
            remaining = (self.state.cooldown_until - datetime.now()).seconds // 60
            return RiskCheckResult(
                passed=False,
                rule_name="cooldown",
                reason=f"冷却期中，剩余{remaining}分钟",
                severity="warning",
                suggested_action=f"等待{remaining}分钟"
            )
        
        # 执行所有规则检查
        failed_results = []
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            try:
                result = rule.check(signal, positions, orders, context)
                
                if not result.passed:
                    failed_results.append(result)
                    logger.warning(f"Risk check failed: {rule.name} - {result.reason}")
                    
                    # 如果是严重级别，立即返回
                    if result.severity == "critical":
                        self._handle_critical_failure(result)
                        return result
                        
            except Exception as e:
                logger.error(f"Risk rule {rule.name} error: {e}")
        
        # 如果有失败的检查
        if failed_results:
            # 返回最高优先级的失败结果
            self.state.failed_checks = [r.rule_name for r in failed_results]
            return failed_results[0]
        
        # 所有检查通过
        self.state.last_check_time = datetime.now()
        self.state.failed_checks = []
        
        return RiskCheckResult(
            passed=True,
            rule_name="all",
            reason="所有风控检查通过"
        )
    
    def _handle_critical_failure(self, result: RiskCheckResult):
        """处理严重级别的风控失败"""
        logger.critical(f"Critical risk failure: {result.reason}")
        
        # 发送风控事件
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
        """更新盈亏"""
        self.state.daily_pnl += pnl
        
        # 更新连续亏损
        if pnl < 0:
            self.state.consecutive_losses += 1
        else:
            self.state.consecutive_losses = 0
    
    def update_balance(self, balance: float):
        """更新账户余额"""
        # 更新峰值
        if balance > self.state.peak_balance:
            self.state.peak_balance = balance
        
        # 计算回撤
        if self.state.peak_balance > 0:
            self.state.current_drawdown = (self.state.peak_balance - balance) / self.state.peak_balance * 100
    
    def trigger_circuit_breaker(self, reason: str):
        """触发熔断"""
        self.state.circuit_breaker_active = True
        self.state.is_trading_allowed = False
        
        logger.critical(f"Circuit breaker triggered: {reason}")
        
        self.event_bus.publish_sync(Event(
            type=EventType.RISK_CIRCUIT_BREAK,
            source="risk_engine",
            data={"reason": reason}
        ))
    
    def reset_circuit_breaker(self):
        """重置熔断"""
        self.state.circuit_breaker_active = False
        self.state.is_trading_allowed = True
        
        logger.info("Circuit breaker reset")
    
    def start_cooldown(self, minutes: int):
        """开始冷却期"""
        from datetime import timedelta
        self.state.cooldown_until = datetime.now() + timedelta(minutes=minutes)
        logger.warning(f"Cooldown started for {minutes} minutes")
    
    def reset_daily(self):
        """重置每日统计"""
        self.state.daily_pnl = 0
        self.state.consecutive_losses = 0
        self.state.failed_checks = []
        logger.info("Daily risk stats reset")
    
    def get_state(self) -> RiskState:
        """获取风控状态"""
        return self.state
    
    def get_rules_status(self) -> List[Dict]:
        """获取所有规则状态"""
        return [
            {
                "name": rule.name,
                "enabled": rule.enabled,
                "priority": rule.priority
            }
            for rule in self.rules
        ]
