"""
统一交易执行器
支持多个交易所/链的统一接口
"""

import asyncio
from typing import Dict, List, Optional, Any
from enum import Enum

from backend.core.logger import get_logger
from backend.core.config import get_config
from backend.data.models import Order, OrderStatus, OrderType, OrderSide, Position

# 导入各个执行器
from backend.execution.binance_futures import BinanceFuturesExecutor
from backend.execution.hyperliquid_executor import HyperliquidExecutor
from backend.execution.executor import MockExecutor

logger = get_logger("unified_executor")


class ExecutorType(str, Enum):
    """执行器类型"""
    MOCK = "mock"                      # 模拟执行器
    BINANCE_FUTURES = "binance_futures"  # 币安永续
    HYPERLIQUID = "hyperliquid"        # Hyperliquid链上


class UnifiedExecutor:
    """
    统一交易执行器
    
    功能：
    - 支持多个交易所/链的统一接口
    - 自动路由到对应的执行器
    - 统一的订单和持仓管理
    - 跨平台的风险控制
    """
    
    def __init__(self):
        """初始化统一执行器"""
        self.config = get_config()
        
        # 执行器实例
        self.executors: Dict[ExecutorType, Any] = {}
        
        # 当前激活的执行器
        self.active_executor_type: ExecutorType = ExecutorType.MOCK
        
        # 订单和持仓缓存
        self._orders: Dict[str, Order] = {}
        self._positions: Dict[str, Position] = {}
        
        logger.info("Unified Executor initialized")
    
    async def initialize(self):
        """初始化所有执行器"""
        try:
            # 1. 初始化模拟执行器（总是可用）
            self.executors[ExecutorType.MOCK] = MockExecutor()
            logger.info("Mock executor initialized")
            
            # 2. 初始化币安永续执行器
            try:
                binance_config = getattr(self.config, 'binance_futures', {})
                if isinstance(binance_config, dict) and binance_config.get('enabled', False):
                    api_key = binance_config.get('api_key', '')
                    api_secret = binance_config.get('api_secret', '')
                    testnet = binance_config.get('testnet', True)
                    leverage = binance_config.get('leverage', 1)
                    
                    if api_key and api_secret:
                        binance_executor = BinanceFuturesExecutor(
                            api_key=api_key,
                            api_secret=api_secret,
                            testnet=testnet,
                            default_leverage=leverage
                        )
                        await binance_executor.initialize()
                        self.executors[ExecutorType.BINANCE_FUTURES] = binance_executor
                        logger.info("Binance Futures executor initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Binance Futures executor: {e}")
            
            # 3. 初始化Hyperliquid执行器
            try:
                hyperliquid_config = getattr(self.config, 'hyperliquid', {})
                if isinstance(hyperliquid_config, dict) and hyperliquid_config.get('enabled', False):
                    private_key = hyperliquid_config.get('private_key', '')
                    testnet = hyperliquid_config.get('testnet', True)
                    leverage = hyperliquid_config.get('leverage', 1)
                    
                    if private_key:
                        hyperliquid_executor = HyperliquidExecutor(
                            private_key=private_key,
                            testnet=testnet,
                            default_leverage=leverage
                        )
                        await hyperliquid_executor.initialize()
                        self.executors[ExecutorType.HYPERLIQUID] = hyperliquid_executor
                        logger.info("Hyperliquid executor initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Hyperliquid executor: {e}")
            
            # 4. 设置默认执行器
            trading_config = getattr(self.config, 'trading', None)
            trading_mode = getattr(trading_config, 'mode', 'paper') if trading_config else 'paper'
            
            if trading_mode == 'paper':
                self.active_executor_type = ExecutorType.MOCK
            elif trading_mode == 'live_cex':
                if ExecutorType.BINANCE_FUTURES in self.executors:
                    self.active_executor_type = ExecutorType.BINANCE_FUTURES
                else:
                    logger.warning("Binance Futures not available, using mock")
                    self.active_executor_type = ExecutorType.MOCK
            elif trading_mode == 'live_dex':
                if ExecutorType.HYPERLIQUID in self.executors:
                    self.active_executor_type = ExecutorType.HYPERLIQUID
                else:
                    logger.warning("Hyperliquid not available, using mock")
                    self.active_executor_type = ExecutorType.MOCK
            
            logger.info(f"Active executor: {self.active_executor_type.value}")
            
        except Exception as e:
            logger.error(f"Failed to initialize executors: {e}")
            raise
    
    def set_active_executor(self, executor_type: ExecutorType):
        """
        设置激活的执行器
        
        Args:
            executor_type: 执行器类型
        """
        if executor_type not in self.executors:
            logger.error(f"Executor {executor_type} not available")
            return False
        
        self.active_executor_type = executor_type
        logger.info(f"Switched to executor: {executor_type.value}")
        return True
    
    def get_active_executor(self):
        """获取当前激活的执行器"""
        return self.executors.get(self.active_executor_type)
    
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: Optional[float] = None,
        executor_type: Optional[ExecutorType] = None,
        **kwargs
    ) -> Optional[Order]:
        """
        下单
        
        Args:
            symbol: 交易对/资产
            side: 买卖方向
            order_type: 订单类型
            quantity: 数量
            price: 价格
            executor_type: 指定执行器（None使用当前激活的）
            **kwargs: 其他参数
        
        Returns:
            订单对象
        """
        try:
            # 确定使用的执行器
            target_executor_type = executor_type or self.active_executor_type
            executor = self.executors.get(target_executor_type)
            
            if not executor:
                logger.error(f"Executor {target_executor_type} not available")
                return None
            
            # 根据执行器类型调整参数
            if target_executor_type == ExecutorType.HYPERLIQUID:
                # Hyperliquid使用资产名称（如BTC）
                asset = symbol.replace('/USDT', '').replace('USDT', '')
                order = await executor.place_order(
                    asset=asset,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    price=price,
                    **kwargs
                )
            else:
                # 其他执行器使用完整交易对
                order = await executor.place_order(
                    symbol=symbol,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    price=price,
                    **kwargs
                )
            
            if order:
                self._orders[order.order_id] = order
                logger.info(f"Order placed via {target_executor_type.value}: {order.order_id}")
            
            return order
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return None
    
    async def cancel_order(
        self,
        symbol: str,
        order_id: str,
        executor_type: Optional[ExecutorType] = None
    ) -> bool:
        """
        撤单
        
        Args:
            symbol: 交易对/资产
            order_id: 订单ID
            executor_type: 指定执行器
        
        Returns:
            是否成功
        """
        try:
            target_executor_type = executor_type or self.active_executor_type
            executor = self.executors.get(target_executor_type)
            
            if not executor:
                logger.error(f"Executor {target_executor_type} not available")
                return False
            
            # 根据执行器类型调整参数
            if target_executor_type == ExecutorType.HYPERLIQUID:
                asset = symbol.replace('/USDT', '').replace('USDT', '')
                success = await executor.cancel_order(asset, int(order_id))
            else:
                success = await executor.cancel_order(symbol, order_id)
            
            if success:
                logger.info(f"Order cancelled via {target_executor_type.value}: {order_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return False
    
    async def get_position(
        self,
        symbol: str,
        executor_type: Optional[ExecutorType] = None
    ) -> Optional[Position]:
        """
        获取持仓
        
        Args:
            symbol: 交易对/资产
            executor_type: 指定执行器
        
        Returns:
            持仓对象
        """
        try:
            target_executor_type = executor_type or self.active_executor_type
            executor = self.executors.get(target_executor_type)
            
            if not executor:
                return None
            
            # 根据执行器类型调整参数
            if target_executor_type == ExecutorType.HYPERLIQUID:
                asset = symbol.replace('/USDT', '').replace('USDT', '')
                position = await executor.get_position(asset)
            else:
                position = await executor.get_position(symbol)
            
            if position:
                self._positions[symbol] = position
            
            return position
            
        except Exception as e:
            logger.error(f"Failed to get position: {e}")
            return None
    
    async def get_all_positions(
        self,
        executor_type: Optional[ExecutorType] = None
    ) -> List[Position]:
        """
        获取所有持仓
        
        Args:
            executor_type: 指定执行器
        
        Returns:
            持仓列表
        """
        try:
            target_executor_type = executor_type or self.active_executor_type
            executor = self.executors.get(target_executor_type)
            
            if not executor:
                return []
            
            positions = await executor.get_all_positions()
            
            for position in positions:
                self._positions[position.symbol] = position
            
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get all positions: {e}")
            return []
    
    async def close_position(
        self,
        symbol: str,
        executor_type: Optional[ExecutorType] = None
    ) -> bool:
        """
        平仓
        
        Args:
            symbol: 交易对/资产
            executor_type: 指定执行器
        
        Returns:
            是否成功
        """
        try:
            target_executor_type = executor_type or self.active_executor_type
            executor = self.executors.get(target_executor_type)
            
            if not executor:
                return False
            
            # 根据执行器类型调整参数
            if target_executor_type == ExecutorType.HYPERLIQUID:
                asset = symbol.replace('/USDT', '').replace('USDT', '')
                success = await executor.close_position(asset)
            else:
                success = await executor.close_position(symbol)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return False
    
    async def get_account_balance(
        self,
        executor_type: Optional[ExecutorType] = None
    ) -> Dict[str, Any]:
        """
        获取账户余额
        
        Args:
            executor_type: 指定执行器
        
        Returns:
            余额信息
        """
        try:
            target_executor_type = executor_type or self.active_executor_type
            executor = self.executors.get(target_executor_type)
            
            if not executor:
                return {}
            
            balance = await executor.get_account_balance()
            return balance
            
        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            return {}
    
    def get_available_executors(self) -> List[ExecutorType]:
        """获取可用的执行器列表"""
        return list(self.executors.keys())
    
    async def close(self):
        """关闭所有执行器"""
        for executor_type, executor in self.executors.items():
            try:
                if hasattr(executor, 'close'):
                    await executor.close()
                logger.info(f"Closed executor: {executor_type.value}")
            except Exception as e:
                logger.error(f"Failed to close executor {executor_type.value}: {e}")


# ==================== 全局实例 ====================

_unified_executor: Optional[UnifiedExecutor] = None


def get_unified_executor() -> UnifiedExecutor:
    """获取统一执行器实例"""
    global _unified_executor
    if _unified_executor is None:
        _unified_executor = UnifiedExecutor()
    return _unified_executor


async def test_unified_executor():
    """测试统一执行器"""
    executor = get_unified_executor()
    
    try:
        # 初始化
        await executor.initialize()
        
        # 查看可用执行器
        available = executor.get_available_executors()
        logger.info(f"Available executors: {[e.value for e in available]}")
        
        # 获取账户余额（所有执行器）
        for executor_type in available:
            balance = await executor.get_account_balance(executor_type)
            logger.info(f"Balance ({executor_type.value}): {balance}")
        
        # 获取所有持仓
        for executor_type in available:
            positions = await executor.get_all_positions(executor_type)
            logger.info(f"Positions ({executor_type.value}): {len(positions)}")
        
    finally:
        await executor.close()


if __name__ == '__main__':
    asyncio.run(test_unified_executor())
