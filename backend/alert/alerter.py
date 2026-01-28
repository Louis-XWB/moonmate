"""
告警管理器
统一管理告警规则、触发和通知
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import deque

from backend.core.logger import get_logger
from backend.core.events import EventBus, Event, EventType, get_event_bus

logger = get_logger("alerter")


class AlertLevel(str, Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(str, Enum):
    """告警渠道"""
    EMAIL = "email"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"
    CONSOLE = "console"


class AlertCategory(str, Enum):
    """告警类别"""
    TRADING = "trading"          # 交易相关
    RISK = "risk"                # 风控相关
    SYSTEM = "system"            # 系统相关
    DATA = "data"                # 数据相关
    SECURITY = "security"        # 安全相关


@dataclass
class Alert:
    """告警实体"""
    id: str
    level: AlertLevel
    category: AlertCategory
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "level": self.level.value,
            "category": self.category.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "metadata": self.metadata,
            "acknowledged": self.acknowledged
        }


@dataclass
class AlertRule:
    """告警规则"""
    name: str
    condition: Callable[..., bool]
    level: AlertLevel
    category: AlertCategory
    title_template: str
    message_template: str
    cooldown_seconds: int = 300  # 冷却时间，避免重复告警
    channels: List[AlertChannel] = field(default_factory=lambda: [AlertChannel.CONSOLE])
    enabled: bool = True
    
    _last_triggered: Optional[datetime] = field(default=None, repr=False)
    
    def can_trigger(self) -> bool:
        """检查是否可以触发（冷却时间）"""
        if self._last_triggered is None:
            return True
        elapsed = (datetime.now() - self._last_triggered).total_seconds()
        return elapsed >= self.cooldown_seconds
    
    def mark_triggered(self):
        """标记已触发"""
        self._last_triggered = datetime.now()


class AlertChannelHandler(ABC):
    """告警渠道处理器基类"""
    
    @abstractmethod
    async def send(self, alert: Alert) -> bool:
        """发送告警"""
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """检查是否已配置"""
        pass


class ConsoleChannelHandler(AlertChannelHandler):
    """控制台告警处理器"""
    
    LEVEL_COLORS = {
        AlertLevel.INFO: "\033[94m",      # 蓝色
        AlertLevel.WARNING: "\033[93m",   # 黄色
        AlertLevel.ERROR: "\033[91m",     # 红色
        AlertLevel.CRITICAL: "\033[95m",  # 紫色
    }
    RESET = "\033[0m"
    
    async def send(self, alert: Alert) -> bool:
        color = self.LEVEL_COLORS.get(alert.level, "")
        print(f"{color}[{alert.level.value.upper()}] {alert.title}{self.RESET}")
        print(f"  {alert.message}")
        print(f"  Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        return True
    
    def is_configured(self) -> bool:
        return True


class AlertManager:
    """告警管理器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.rules: Dict[str, AlertRule] = {}
        self.handlers: Dict[AlertChannel, AlertChannelHandler] = {
            AlertChannel.CONSOLE: ConsoleChannelHandler()
        }
        self.alert_history: deque = deque(maxlen=1000)
        self.event_bus = get_event_bus()
        
        self._alert_counter = 0
        
        # 初始化默认规则
        self._init_default_rules()
    
    def _init_default_rules(self):
        """初始化默认告警规则"""
        
        # 连续亏损告警
        self.add_rule(AlertRule(
            name="consecutive_loss",
            condition=lambda losses: losses >= 3,
            level=AlertLevel.WARNING,
            category=AlertCategory.TRADING,
            title_template="连续亏损告警",
            message_template="已连续亏损 {losses} 次，请检查策略",
            cooldown_seconds=1800,
            channels=[AlertChannel.CONSOLE, AlertChannel.TELEGRAM]
        ))
        
        # 大额亏损告警
        self.add_rule(AlertRule(
            name="large_loss",
            condition=lambda loss_pct: loss_pct >= 5,
            level=AlertLevel.ERROR,
            category=AlertCategory.RISK,
            title_template="大额亏损告警",
            message_template="单笔亏损达到 {loss_pct:.2f}%，触发风控",
            cooldown_seconds=300,
            channels=[AlertChannel.CONSOLE, AlertChannel.TELEGRAM, AlertChannel.EMAIL]
        ))
        
        # 熔断告警
        self.add_rule(AlertRule(
            name="circuit_breaker",
            condition=lambda triggered: triggered,
            level=AlertLevel.CRITICAL,
            category=AlertCategory.RISK,
            title_template="熔断触发",
            message_template="风控熔断已触发，交易暂停。原因：{reason}",
            cooldown_seconds=0,  # 熔断不设冷却
            channels=[AlertChannel.CONSOLE, AlertChannel.TELEGRAM, AlertChannel.EMAIL]
        ))
        
        # 数据源异常
        self.add_rule(AlertRule(
            name="data_source_error",
            condition=lambda error_count: error_count >= 3,
            level=AlertLevel.WARNING,
            category=AlertCategory.DATA,
            title_template="数据源异常",
            message_template="数据源 {source} 连续 {error_count} 次请求失败",
            cooldown_seconds=600,
            channels=[AlertChannel.CONSOLE]
        ))
        
        # API 限频告警
        self.add_rule(AlertRule(
            name="rate_limit",
            condition=lambda limited: limited,
            level=AlertLevel.WARNING,
            category=AlertCategory.SYSTEM,
            title_template="API 限频",
            message_template="API {api} 触发限频，将在 {retry_after}s 后重试",
            cooldown_seconds=60,
            channels=[AlertChannel.CONSOLE]
        ))
        
        # 价格异常告警
        self.add_rule(AlertRule(
            name="price_anomaly",
            condition=lambda change_pct: abs(change_pct) >= 10,
            level=AlertLevel.WARNING,
            category=AlertCategory.DATA,
            title_template="价格异常波动",
            message_template="{symbol} 价格在短时间内变动 {change_pct:.2f}%",
            cooldown_seconds=300,
            channels=[AlertChannel.CONSOLE, AlertChannel.TELEGRAM]
        ))
        
        # 订单执行失败
        self.add_rule(AlertRule(
            name="order_failed",
            condition=lambda failed: failed,
            level=AlertLevel.ERROR,
            category=AlertCategory.TRADING,
            title_template="订单执行失败",
            message_template="订单 {order_id} 执行失败：{error}",
            cooldown_seconds=60,
            channels=[AlertChannel.CONSOLE, AlertChannel.TELEGRAM]
        ))
        
        # 密钥即将过期
        self.add_rule(AlertRule(
            name="key_expiring",
            condition=lambda days: days <= 7,
            level=AlertLevel.WARNING,
            category=AlertCategory.SECURITY,
            title_template="API 密钥即将过期",
            message_template="API 密钥将在 {days} 天后过期，请及时更换",
            cooldown_seconds=86400,  # 每天最多提醒一次
            channels=[AlertChannel.CONSOLE, AlertChannel.EMAIL]
        ))
    
    def add_rule(self, rule: AlertRule):
        """添加告警规则"""
        self.rules[rule.name] = rule
        logger.info(f"Alert rule added: {rule.name}")
    
    def remove_rule(self, name: str):
        """移除告警规则"""
        if name in self.rules:
            del self.rules[name]
            logger.info(f"Alert rule removed: {name}")
    
    def register_handler(self, channel: AlertChannel, handler: AlertChannelHandler):
        """注册告警渠道处理器"""
        self.handlers[channel] = handler
        logger.info(f"Alert handler registered: {channel.value}")
    
    def _generate_alert_id(self) -> str:
        """生成告警ID"""
        self._alert_counter += 1
        return f"ALERT_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self._alert_counter}"
    
    async def check_rule(
        self,
        rule_name: str,
        **kwargs
    ) -> Optional[Alert]:
        """检查告警规则"""
        if rule_name not in self.rules:
            logger.warning(f"Alert rule not found: {rule_name}")
            return None
        
        rule = self.rules[rule_name]
        
        if not rule.enabled:
            return None
        
        if not rule.can_trigger():
            return None
        
        # 检查条件
        try:
            # 获取条件函数的参数名
            import inspect
            sig = inspect.signature(rule.condition)
            condition_kwargs = {
                k: v for k, v in kwargs.items()
                if k in sig.parameters
            }
            
            if not rule.condition(**condition_kwargs):
                return None
        except Exception as e:
            logger.error(f"Error checking rule condition: {e}")
            return None
        
        # 创建告警
        alert = Alert(
            id=self._generate_alert_id(),
            level=rule.level,
            category=rule.category,
            title=rule.title_template.format(**kwargs),
            message=rule.message_template.format(**kwargs),
            source=rule_name,
            metadata=kwargs
        )
        
        # 标记已触发
        rule.mark_triggered()
        
        # 发送告警
        await self.send_alert(alert, rule.channels)
        
        return alert
    
    async def send_alert(
        self,
        alert: Alert,
        channels: Optional[List[AlertChannel]] = None
    ):
        """发送告警"""
        if channels is None:
            channels = [AlertChannel.CONSOLE]
        
        # 记录历史
        self.alert_history.append(alert)
        
        # 发布事件
        await self.event_bus.publish(Event(
            type=EventType.ALERT,
            data=alert.to_dict()
        ))
        
        # 发送到各渠道
        for channel in channels:
            handler = self.handlers.get(channel)
            if handler and handler.is_configured():
                try:
                    await handler.send(alert)
                    logger.info(f"Alert sent via {channel.value}: {alert.title}")
                except Exception as e:
                    logger.error(f"Failed to send alert via {channel.value}: {e}")
    
    async def trigger_alert(
        self,
        level: AlertLevel,
        category: AlertCategory,
        title: str,
        message: str,
        channels: Optional[List[AlertChannel]] = None,
        **metadata
    ):
        """直接触发告警"""
        alert = Alert(
            id=self._generate_alert_id(),
            level=level,
            category=category,
            title=title,
            message=message,
            metadata=metadata
        )
        
        await self.send_alert(alert, channels)
    
    def acknowledge_alert(self, alert_id: str, by: str = "system"):
        """确认告警"""
        for alert in self.alert_history:
            if alert.id == alert_id and not alert.acknowledged:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.now()
                alert.acknowledged_by = by
                logger.info(f"Alert acknowledged: {alert_id} by {by}")
                return True
        return False
    
    def get_active_alerts(
        self,
        level: Optional[AlertLevel] = None,
        category: Optional[AlertCategory] = None
    ) -> List[Alert]:
        """获取未确认的告警"""
        alerts = [a for a in self.alert_history if not a.acknowledged]
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        if category:
            alerts = [a for a in alerts if a.category == category]
        
        return alerts
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """获取告警统计"""
        total = len(self.alert_history)
        unacknowledged = len([a for a in self.alert_history if not a.acknowledged])
        
        by_level = {}
        by_category = {}
        
        for alert in self.alert_history:
            by_level[alert.level.value] = by_level.get(alert.level.value, 0) + 1
            by_category[alert.category.value] = by_category.get(alert.category.value, 0) + 1
        
        return {
            "total": total,
            "unacknowledged": unacknowledged,
            "by_level": by_level,
            "by_category": by_category
        }


# 全局告警管理器
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """获取全局告警管理器"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
