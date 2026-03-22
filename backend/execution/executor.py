"""
Executor module
Responsible for submitting orders to exchanges for execution
"""

import asyncio
import random
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any

from backend.data.models import Order, OrderStatus, OrderType
from backend.core.logger import get_logger

logger = get_logger("executor")


class Executor(ABC):
    """Executor base class"""
    
    @abstractmethod
    async def submit_order(self, order: Order) -> Dict[str, Any]:
        """Submit an order"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, exchange_order_id: str) -> bool:
        """Cancel an order"""
        pass
    
    @abstractmethod
    async def get_order_status(self, exchange_order_id: str) -> Dict[str, Any]:
        """Query order status"""
        pass


class MockExecutor(Executor):
    """Mock executor (for testing and demo purposes)"""
    
    def __init__(
        self,
        fill_probability: float = 0.95,
        fill_delay: float = 0.5,
        slippage_range: tuple = (-0.001, 0.001)
    ):
        self.fill_probability = fill_probability
        self.fill_delay = fill_delay
        self.slippage_range = slippage_range
        self._order_counter = 0
    
    async def submit_order(self, order: Order) -> Dict[str, Any]:
        """Submit an order (simulated)"""
        self._order_counter += 1
        exchange_order_id = f"MOCK_{self._order_counter}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        logger.info(f"Submitting order: {order.id} -> {exchange_order_id}")
        
        # Simulate network latency
        await asyncio.sleep(self.fill_delay * random.uniform(0.5, 1.5))
        
        # Simulate order fill
        if random.random() < self.fill_probability:
            # Calculate fill price (with slippage)
            slippage = random.uniform(*self.slippage_range)
            if order.type == OrderType.MARKET:
                fill_price = order.price * (1 + slippage) if order.price > 0 else 0
            else:
                fill_price = order.price
            
            # Simulate trading fee (0.1%)
            fee = order.size * fill_price * 0.001
            
            return {
                "success": True,
                "exchange_order_id": exchange_order_id,
                "status": OrderStatus.FILLED,
                "filled_size": order.size,
                "avg_price": fill_price if fill_price > 0 else order.price,
                "fee": fee,
                "timestamp": datetime.now().isoformat()
            }
        else:
            # Simulate rejection
            return {
                "success": False,
                "exchange_order_id": exchange_order_id,
                "status": OrderStatus.REJECTED,
                "error": "Insufficient liquidity (simulated)",
                "timestamp": datetime.now().isoformat()
            }
    
    async def cancel_order(self, order_id: str, exchange_order_id: str) -> bool:
        """Cancel an order (simulated)"""
        logger.info(f"Cancelling order: {order_id} ({exchange_order_id})")
        
        await asyncio.sleep(0.2)
        
        # 90% chance of successful cancellation
        success = random.random() < 0.9
        
        if success:
            logger.info(f"Order cancelled: {order_id}")
        else:
            logger.warning(f"Failed to cancel order: {order_id}")
        
        return success
    
    async def get_order_status(self, exchange_order_id: str) -> Dict[str, Any]:
        """Query order status (simulated)"""
        await asyncio.sleep(0.1)
        
        return {
            "exchange_order_id": exchange_order_id,
            "status": OrderStatus.FILLED,
            "timestamp": datetime.now().isoformat()
        }
