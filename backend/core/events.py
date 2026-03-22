"""
Event bus module
Supports event-driven architecture, decoupling communication between layers
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Callable, Any, Optional
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class EventType(str, Enum):
    """Event type"""
    # Market data events
    TICKER_UPDATE = "ticker_update"
    DEPTH_UPDATE = "depth_update"
    TRADE_UPDATE = "trade_update"
    KLINE_UPDATE = "kline_update"
    
    # Signal events
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_EXPIRED = "signal_expired"
    
    # Strategy events
    STRATEGY_SIGNAL = "strategy_signal"
    STRATEGY_ERROR = "strategy_error"
    
    # Risk control events
    RISK_CHECK_PASSED = "risk_check_passed"
    RISK_CHECK_FAILED = "risk_check_failed"
    RISK_CIRCUIT_BREAK = "risk_circuit_break"
    RISK_COOLDOWN_END = "risk_cooldown_end"
    
    # Order events
    ORDER_CREATED = "order_created"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_PARTIALLY_FILLED = "order_partially_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    ORDER_ERROR = "order_error"
    
    # Position events
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_UPDATED = "position_updated"
    
    # System events
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    SYSTEM_ERROR = "system_error"
    HEARTBEAT = "heartbeat"


class Event(BaseModel):
    """Event base class"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType
    timestamp: datetime = Field(default_factory=datetime.now)
    source: str = Field(default="system", description="Event source")
    data: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


class EventBus:
    """Event bus"""
    
    def __init__(self):
        self._handlers: Dict[EventType, List[Callable]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running: bool = False
        self._history: List[Event] = []
        self._max_history: int = 1000
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """Subscribe to event"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    def unsubscribe(self, event_type: EventType, handler: Callable):
        """Unsubscribe from event"""
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)
    
    async def publish(self, event: Event):
        """Publish event"""
        await self._queue.put(event)
        
        # Save history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
    
    def publish_sync(self, event: Event):
        """Publish event synchronously (for non-async context)"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.publish(event))
            else:
                loop.run_until_complete(self.publish(event))
        except RuntimeError:
            # Process directly when no event loop
            self._process_event_sync(event)
    
    def _process_event_sync(self, event: Event):
        """Process event synchronously"""
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    # If it's a coroutine, create a task
                    asyncio.create_task(result)
            except Exception as e:
                print(f"Event handler error: {e}")
    
    async def _process_event(self, event: Event):
        """Process event"""
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
        """Start event processing loop"""
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
        """Stop event processing"""
        self._running = False
    
    def get_history(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        """Get event history"""
        if event_type:
            events = [e for e in self._history if e.type == event_type]
        else:
            events = self._history
        return events[-limit:]


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get global event bus"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
