"""
Unified trading executor
Supports a unified interface for multiple exchanges/chains
"""

import asyncio
from typing import Dict, List, Optional, Any
from enum import Enum

from backend.core.logger import get_logger
from backend.core.config import get_config
from backend.data.models import Order, OrderStatus, OrderType, OrderSide, Position

# Import individual executors
from backend.execution.binance_futures import BinanceFuturesExecutor
from backend.execution.hyperliquid_executor import HyperliquidExecutor
from backend.execution.executor import MockExecutor

logger = get_logger("unified_executor")


class ExecutorType(str, Enum):
    """Executor type"""
    MOCK = "mock"                      # Mock executor
    BINANCE_FUTURES = "binance_futures"  # Binance Futures
    HYPERLIQUID = "hyperliquid"        # Hyperliquid on-chain


class UnifiedExecutor:
    """
    Unified trading executor
    
    Features:
    - Unified interface for multiple exchanges/chains
    - Automatic routing to the corresponding executor
    - Unified order and position management
    - Cross-platform risk control
    """
    
    def __init__(self):
        """Initialize the unified executor"""
        self.config = get_config()
        
        # Executor instances
        self.executors: Dict[ExecutorType, Any] = {}
        
        # Currently active executor
        self.active_executor_type: ExecutorType = ExecutorType.MOCK
        
        # Order and position cache
        self._orders: Dict[str, Order] = {}
        self._positions: Dict[str, Position] = {}
        
        logger.info("Unified Executor initialized")
    
    async def initialize(self):
        """Initialize all executors"""
        try:
            # 1. Initialize mock executor (always available)
            self.executors[ExecutorType.MOCK] = MockExecutor()
            logger.info("Mock executor initialized")
            
            # 2. Initialize Binance Futures executor
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
            
            # 3. Initialize Hyperliquid executor
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
            
            # 4. Set default executor
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
        Set the active executor
        
        Args:
            executor_type: Executor type
        """
        if executor_type not in self.executors:
            logger.error(f"Executor {executor_type} not available")
            return False
        
        self.active_executor_type = executor_type
        logger.info(f"Switched to executor: {executor_type.value}")
        return True
    
    def get_active_executor(self):
        """Get the currently active executor"""
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
        Place an order
        
        Args:
            symbol: Trading pair/asset
            side: Buy/sell direction
            order_type: Order type
            quantity: Quantity
            price: Price
            executor_type: Specified executor (None uses the currently active one)
            **kwargs: Additional parameters
        
        Returns:
            Order object
        """
        try:
            # Determine which executor to use
            target_executor_type = executor_type or self.active_executor_type
            executor = self.executors.get(target_executor_type)
            
            if not executor:
                logger.error(f"Executor {target_executor_type} not available")
                return None
            
            # Adjust parameters based on executor type
            if target_executor_type == ExecutorType.HYPERLIQUID:
                # Hyperliquid uses asset names (e.g. BTC)
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
                # Other executors use full trading pairs
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
        Cancel an order
        
        Args:
            symbol: Trading pair/asset
            order_id: OrderID
            executor_type: Specified executor
        
        Returns:
            Whether successful
        """
        try:
            target_executor_type = executor_type or self.active_executor_type
            executor = self.executors.get(target_executor_type)
            
            if not executor:
                logger.error(f"Executor {target_executor_type} not available")
                return False
            
            # Adjust parameters based on executor type
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
        Get position
        
        Args:
            symbol: Trading pair/asset
            executor_type: Specified executor
        
        Returns:
            Position object
        """
        try:
            target_executor_type = executor_type or self.active_executor_type
            executor = self.executors.get(target_executor_type)
            
            if not executor:
                return None
            
            # Adjust parameters based on executor type
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
        Get all positions
        
        Args:
            executor_type: Specified executor
        
        Returns:
            List of positions
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
        Close a position
        
        Args:
            symbol: Trading pair/asset
            executor_type: Specified executor
        
        Returns:
            Whether successful
        """
        try:
            target_executor_type = executor_type or self.active_executor_type
            executor = self.executors.get(target_executor_type)
            
            if not executor:
                return False
            
            # Adjust parameters based on executor type
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
        Get account balance
        
        Args:
            executor_type: Specified executor
        
        Returns:
            Balance information
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
        """Get list of available executors"""
        return list(self.executors.keys())
    
    async def close(self):
        """Close all executors"""
        for executor_type, executor in self.executors.items():
            try:
                if hasattr(executor, 'close'):
                    await executor.close()
                logger.info(f"Closed executor: {executor_type.value}")
            except Exception as e:
                logger.error(f"Failed to close executor {executor_type.value}: {e}")


# ==================== Global instance ====================

_unified_executor: Optional[UnifiedExecutor] = None


def get_unified_executor() -> UnifiedExecutor:
    """Get unified executor instance"""
    global _unified_executor
    if _unified_executor is None:
        _unified_executor = UnifiedExecutor()
    return _unified_executor


async def test_unified_executor():
    """Test the unified executor"""
    executor = get_unified_executor()
    
    try:
        # Initialize
        await executor.initialize()
        
        # View available executors
        available = executor.get_available_executors()
        logger.info(f"Available executors: {[e.value for e in available]}")
        
        # Get account balance (all executors)
        for executor_type in available:
            balance = await executor.get_account_balance(executor_type)
            logger.info(f"Balance ({executor_type.value}): {balance}")
        
        # Get all positions
        for executor_type in available:
            positions = await executor.get_all_positions(executor_type)
            logger.info(f"Positions ({executor_type.value}): {len(positions)}")
        
    finally:
        await executor.close()


if __name__ == '__main__':
    asyncio.run(test_unified_executor())
