"""
执行器模块
负责将订单提交到交易所执行
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
    """执行器基类"""
    
    @abstractmethod
    async def submit_order(self, order: Order) -> Dict[str, Any]:
        """提交订单"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str, exchange_order_id: str) -> bool:
        """取消订单"""
        pass
    
    @abstractmethod
    async def get_order_status(self, exchange_order_id: str) -> Dict[str, Any]:
        """查询订单状态"""
        pass


class MockExecutor(Executor):
    """模拟执行器（用于测试和演示）"""
    
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
        """提交订单（模拟）"""
        self._order_counter += 1
        exchange_order_id = f"MOCK_{self._order_counter}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        logger.info(f"Submitting order: {order.id} -> {exchange_order_id}")
        
        # 模拟网络延迟
        await asyncio.sleep(self.fill_delay * random.uniform(0.5, 1.5))
        
        # 模拟成交
        if random.random() < self.fill_probability:
            # 计算成交价（加入滑点）
            slippage = random.uniform(*self.slippage_range)
            if order.type == OrderType.MARKET:
                fill_price = order.price * (1 + slippage) if order.price > 0 else 0
            else:
                fill_price = order.price
            
            # 模拟手续费（0.1%）
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
            # 模拟拒绝
            return {
                "success": False,
                "exchange_order_id": exchange_order_id,
                "status": OrderStatus.REJECTED,
                "error": "Insufficient liquidity (simulated)",
                "timestamp": datetime.now().isoformat()
            }
    
    async def cancel_order(self, order_id: str, exchange_order_id: str) -> bool:
        """取消订单（模拟）"""
        logger.info(f"Cancelling order: {order_id} ({exchange_order_id})")
        
        await asyncio.sleep(0.2)
        
        # 90%概率成功取消
        success = random.random() < 0.9
        
        if success:
            logger.info(f"Order cancelled: {order_id}")
        else:
            logger.warning(f"Failed to cancel order: {order_id}")
        
        return success
    
    async def get_order_status(self, exchange_order_id: str) -> Dict[str, Any]:
        """查询订单状态（模拟）"""
        await asyncio.sleep(0.1)
        
        return {
            "exchange_order_id": exchange_order_id,
            "status": OrderStatus.FILLED,
            "timestamp": datetime.now().isoformat()
        }
