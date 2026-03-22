"""
Alert manager
Unified management of alert rules, triggers, and notifications
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
    """Alert level"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(str, Enum):
    """Alert channel"""
    EMAIL = "email"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"
    CONSOLE = "console"


class AlertCategory(str, Enum):
    """Alert category"""
    TRADING = "trading"          # Trading-related
    RISK = "risk"                # Risk control-related
    SYSTEM = "system"            # System-related
    DATA = "data"                # Data-related
    SECURITY = "security"        # Security-related


@dataclass
class Alert:
    """Alert entity"""
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
    """Alert rule"""
    name: str
    condition: Callable[..., bool]
    level: AlertLevel
    category: AlertCategory
    title_template: str
    message_template: str
    cooldown_seconds: int = 300  # Cooldown period to avoid duplicate alerts
    channels: List[AlertChannel] = field(default_factory=lambda: [AlertChannel.CONSOLE])
    enabled: bool = True
    
    _last_triggered: Optional[datetime] = field(default=None, repr=False)
    
    def can_trigger(self) -> bool:
        """Check if can trigger (cooldown period)"""
        if self._last_triggered is None:
            return True
        elapsed = (datetime.now() - self._last_triggered).total_seconds()
        return elapsed >= self.cooldown_seconds
    
    def mark_triggered(self):
        """Mark as triggered"""
        self._last_triggered = datetime.now()


class AlertChannelHandler(ABC):
    """Alert channel handler base class"""
    
    @abstractmethod
    async def send(self, alert: Alert) -> bool:
        """Send alert"""
        pass
    
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if configured"""
        pass


class ConsoleChannelHandler(AlertChannelHandler):
    """Console alert channel handler"""
    
    LEVEL_COLORS = {
        AlertLevel.INFO: "\033[94m",      # Blue
        AlertLevel.WARNING: "\033[93m",   # Yellow
        AlertLevel.ERROR: "\033[91m",     # Red
        AlertLevel.CRITICAL: "\033[95m",  # Purple
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
    """Alert manager"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.rules: Dict[str, AlertRule] = {}
        self.handlers: Dict[AlertChannel, AlertChannelHandler] = {
            AlertChannel.CONSOLE: ConsoleChannelHandler()
        }
        self.alert_history: deque = deque(maxlen=1000)
        self.event_bus = get_event_bus()
        
        self._alert_counter = 0
        
        # Initialize default rules
        self._init_default_rules()
    
    def _init_default_rules(self):
        """Initialize default alert rules"""
        
        # Consecutive Losses Alert
        self.add_rule(AlertRule(
            name="consecutive_loss",
            condition=lambda losses: losses >= 3,
            level=AlertLevel.WARNING,
            category=AlertCategory.TRADING,
            title_template="Consecutive Losses Alert",
            message_template="Consecutive losses reached {losses} times, please check strategy",
            cooldown_seconds=1800,
            channels=[AlertChannel.CONSOLE, AlertChannel.TELEGRAM]
        ))
        
        # Large Loss Alert
        self.add_rule(AlertRule(
            name="large_loss",
            condition=lambda loss_pct: loss_pct >= 5,
            level=AlertLevel.ERROR,
            category=AlertCategory.RISK,
            title_template="Large Loss Alert",
            message_template="Single trade loss reached {loss_pct:.2f}%, risk control triggered",
            cooldown_seconds=300,
            channels=[AlertChannel.CONSOLE, AlertChannel.TELEGRAM, AlertChannel.EMAIL]
        ))
        
        # Circuit Breaker Alert
        self.add_rule(AlertRule(
            name="circuit_breaker",
            condition=lambda triggered: triggered,
            level=AlertLevel.CRITICAL,
            category=AlertCategory.RISK,
            title_template="Circuit Breaker Triggered",
            message_template="Risk circuit breaker triggered, trading paused. Reason: {reason}",
            cooldown_seconds=0,  # No cooldown for circuit breaker
            channels=[AlertChannel.CONSOLE, AlertChannel.TELEGRAM, AlertChannel.EMAIL]
        ))
        
        # Data Source Error
        self.add_rule(AlertRule(
            name="data_source_error",
            condition=lambda error_count: error_count >= 3,
            level=AlertLevel.WARNING,
            category=AlertCategory.DATA,
            title_template="Data Source Error",
            message_template="Data source {source} failed {error_count} consecutive requests",
            cooldown_seconds=600,
            channels=[AlertChannel.CONSOLE]
        ))
        
        # API Rate LimitAlert
        self.add_rule(AlertRule(
            name="rate_limit",
            condition=lambda limited: limited,
            level=AlertLevel.WARNING,
            category=AlertCategory.SYSTEM,
            title_template="API Rate Limit",
            message_template="API {api} rate limited, will retry in {retry_after}s",
            cooldown_seconds=60,
            channels=[AlertChannel.CONSOLE]
        ))
        
        # PriceExceptionAlert
        self.add_rule(AlertRule(
            name="price_anomaly",
            condition=lambda change_pct: abs(change_pct) >= 10,
            level=AlertLevel.WARNING,
            category=AlertCategory.DATA,
            title_template="Abnormal Price Movement",
            message_template="{symbol} price changed {change_pct:.2f}% in a short period",
            cooldown_seconds=300,
            channels=[AlertChannel.CONSOLE, AlertChannel.TELEGRAM]
        ))
        
        # Order Execution Failed
        self.add_rule(AlertRule(
            name="order_failed",
            condition=lambda failed: failed,
            level=AlertLevel.ERROR,
            category=AlertCategory.TRADING,
            title_template="Order Execution Failed",
            message_template="Order {order_id} execution failed: {error}",
            cooldown_seconds=60,
            channels=[AlertChannel.CONSOLE, AlertChannel.TELEGRAM]
        ))
        
        # API Key Expiring
        self.add_rule(AlertRule(
            name="key_expiring",
            condition=lambda days: days <= 7,
            level=AlertLevel.WARNING,
            category=AlertCategory.SECURITY,
            title_template="API Key Expiring Soon",
            message_template="API key will expire in {days} days, please renew promptly",
            cooldown_seconds=86400,  # Remind at most once per day
            channels=[AlertChannel.CONSOLE, AlertChannel.EMAIL]
        ))
    
    def add_rule(self, rule: AlertRule):
        """Add alert rule"""
        self.rules[rule.name] = rule
        logger.info(f"Alert rule added: {rule.name}")
    
    def remove_rule(self, name: str):
        """Remove alert rule"""
        if name in self.rules:
            del self.rules[name]
            logger.info(f"Alert rule removed: {name}")
    
    def register_handler(self, channel: AlertChannel, handler: AlertChannelHandler):
        """Register alert channel handler"""
        self.handlers[channel] = handler
        logger.info(f"Alert handler registered: {channel.value}")
    
    def _generate_alert_id(self) -> str:
        """Generate alert ID"""
        self._alert_counter += 1
        return f"ALERT_{datetime.now().strftime('%Y%m%d%H%M%S')}_{self._alert_counter}"
    
    async def check_rule(
        self,
        rule_name: str,
        **kwargs
    ) -> Optional[Alert]:
        """Check alert rule"""
        if rule_name not in self.rules:
            logger.warning(f"Alert rule not found: {rule_name}")
            return None
        
        rule = self.rules[rule_name]
        
        if not rule.enabled:
            return None
        
        if not rule.can_trigger():
            return None
        
        # Check condition
        try:
            # Get condition function parameter names
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
        
        # Create alert
        alert = Alert(
            id=self._generate_alert_id(),
            level=rule.level,
            category=rule.category,
            title=rule.title_template.format(**kwargs),
            message=rule.message_template.format(**kwargs),
            source=rule_name,
            metadata=kwargs
        )
        
        # Mark as triggered
        rule.mark_triggered()
        
        # Send alert
        await self.send_alert(alert, rule.channels)
        
        return alert
    
    async def send_alert(
        self,
        alert: Alert,
        channels: Optional[List[AlertChannel]] = None
    ):
        """Send alert"""
        if channels is None:
            channels = [AlertChannel.CONSOLE]
        
        # Record history
        self.alert_history.append(alert)
        
        # Publish event
        await self.event_bus.publish(Event(
            type=EventType.ALERT,
            data=alert.to_dict()
        ))
        
        # Send to channels
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
        """Trigger alert directly"""
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
        """Acknowledge alert"""
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
        """Get unacknowledged alerts"""
        alerts = [a for a in self.alert_history if not a.acknowledged]
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        if category:
            alerts = [a for a in alerts if a.category == category]
        
        return alerts
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics"""
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


# Global alert manager
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Get global alert manager"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
