"""
事件总线模块
支持事件驱动架构，解耦各层之间的通信
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Callable, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class EventType(str, Enum):
    """事件类型"""
    # 行情事件
    TICKER_UPDATE = "ticker_update"
    DEPTH_UPDATE = "depth_update"
    TRADE_UPDATE = "trade_update"
    KLINE_UPDATE = "kline_update"
    
    # 信号事件
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_EXPIRED = "signal_expired"
    
    # 策略事件
    STRATEGY_SIGNAL = "strategy_signal"
    STRATEGY_ERROR = "strategy_error"
    
    # 风控事件
    RISK_CHECK_PASSED = "risk_check_passed"
    RISK_CHECK_FAILED = "risk_check_failed"
    RISK_CIRCUIT_BREAK = "risk_circuit_break"
    RISK_COOLDOWN_END = "risk_cooldown_end"
    
    # 订单事件
    ORDER_CREATED = "order_created"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_PARTIALLY_FILLED = "order_partially_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    ORDER_ERROR = "order_error"
    
    # 持仓事件
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_UPDATED = "position_updated"
    
    # 系统事件
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    SYSTEM_ERROR = "system_error"
    HEARTBEAT = "heartbeat"


class Event(BaseModel):
    """事件基类"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType
    timestamp: datetime = Field(default_factory=datetime.now)
    source: str = Field(default="system", description="事件来源")
    data: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


class EventBus:
    """事件总线"""
    
    def __init__(self):
        self._handlers: Dict[EventType, List[Callable]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running: bool = False
        self._history: List[Event] = []
        self._max_history: int = 1000
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """订阅事件"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def unsubscribe(self, event_type: EventType, handler: Callable):
        """取消订阅"""
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)
    
    async def publish(self, event: Event):
        """发布事件"""
        await self._queue.put(event)
        
        # 保存历史
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
    
    def publish_sync(self, event: Event):
        """同步发布事件（用于非异步上下文）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.publish(event))
            else:
                loop.run_until_complete(self.publish(event))
        except RuntimeError:
            # 没有事件循环时直接处理
            self._process_event_sync(event)
    
    def _process_event_sync(self, event: Event):
        """同步处理事件"""
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    # 如果是协程，创建任务
                    asyncio.create_task(result)
            except Exception as e:
                print(f"Event handler error: {e}")
    
    async def _process_event(self, event: Event):
        """处理事件"""
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                print(f"Event handler error: {e}")
    
    async def start(self):
        """启动事件处理循环"""
        self._running = True
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._process_event(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Event bus error: {e}")
    
    def stop(self):
        """停止事件处理"""
        self._running = False
    
    def get_history(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        """获取事件历史"""
        if event_type:
            events = [e for e in self._history if e.type == event_type]
        else:
            events = self._history
        return events[-limit:]


# 全局事件总线实例
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """获取全局事件总线"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
