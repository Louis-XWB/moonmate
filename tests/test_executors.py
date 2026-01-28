"""
交易执行器测试脚本
测试币安永续和Hyperliquid执行器
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, '/home/ubuntu/auto-trading-agent')

from backend.core.logger import get_logger
from backend.execution.unified_executor import UnifiedExecutor, ExecutorType
from backend.data.models import OrderSide, OrderType

logger = get_logger("test_executors")


async def test_mock_executor():
    """测试模拟执行器"""
    logger.info("=" * 60)
    logger.info("Testing Mock Executor")
    logger.info("=" * 60)
    
    executor = UnifiedExecutor()
    await executor.initialize()
    
    try:
        # 设置为模拟模式
        executor.set_active_executor(ExecutorType.MOCK)
        
        # 获取账户余额
        balance = await executor.get_account_balance()
        logger.info(f"✓ Account Balance: {balance}")
        
        # 下单测试
        order = await executor.place_order(
            symbol="BTC/USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=0.001,
            price=50000
        )
        
        if order:
            logger.info(f"✓ Order Placed: {order.order_id}")
        else:
            logger.error("✗ Failed to place order")
        
        # 获取持仓
        positions = await executor.get_all_positions()
        logger.info(f"✓ Positions: {len(positions)}")
        
        logger.info("✓ Mock Executor Test Passed")
        
    except Exception as e:
        logger.error(f"✗ Mock Executor Test Failed: {e}")
    finally:
        await executor.close()


async def test_binance_futures_executor():
    """测试币安永续执行器"""
    logger.info("=" * 60)
    logger.info("Testing Binance Futures Executor")
    logger.info("=" * 60)
    
    # 检查环境变量
    api_key = os.getenv('BINANCE_API_KEY', '')
    api_secret = os.getenv('BINANCE_API_SECRET', '')
    
    if not api_key or not api_secret:
        logger.warning("⚠ Binance API credentials not set, skipping test")
        logger.info("To test Binance Futures, set BINANCE_API_KEY and BINANCE_API_SECRET")
        return
    
    from backend.execution.binance_futures import BinanceFuturesExecutor
    
    executor = BinanceFuturesExecutor(
        api_key=api_key,
        api_secret=api_secret,
        testnet=True,
        default_leverage=2
    )
    
    try:
        # 初始化
        await executor.initialize()
        logger.info("✓ Executor Initialized")
        
        # 获取账户余额
        balance = await executor.get_account_balance()
        logger.info(f"✓ Account Balance: ${balance.get('total_balance', 0):.2f}")
        
        # 获取持仓
        positions = await executor.get_all_positions()
        logger.info(f"✓ Current Positions: {len(positions)}")
        
        for pos in positions:
            logger.info(f"  - {pos.symbol}: {pos.quantity} @ ${pos.entry_price}")
        
        logger.info("✓ Binance Futures Executor Test Passed")
        
    except Exception as e:
        logger.error(f"✗ Binance Futures Executor Test Failed: {e}")
    finally:
        await executor.close()


async def test_hyperliquid_executor():
    """测试Hyperliquid执行器"""
    logger.info("=" * 60)
    logger.info("Testing Hyperliquid Executor")
    logger.info("=" * 60)
    
    # 检查环境变量
    private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY', '')
    
    if not private_key:
        logger.warning("⚠ Hyperliquid private key not set, skipping test")
        logger.info("To test Hyperliquid, set HYPERLIQUID_PRIVATE_KEY")
        return
    
    from backend.execution.hyperliquid_executor import HyperliquidExecutor
    
    executor = HyperliquidExecutor(
        private_key=private_key,
        testnet=True,
        default_leverage=2
    )
    
    try:
        # 初始化
        await executor.initialize()
        logger.info("✓ Executor Initialized")
        logger.info(f"  Address: {executor.address}")
        
        # 获取账户余额
        balance = await executor.get_account_balance()
        logger.info(f"✓ Account Balance: ${balance.get('account_value', 0):.2f}")
        logger.info(f"  Withdrawable: ${balance.get('withdrawable', 0):.2f}")
        
        # 获取持仓
        positions = await executor.get_all_positions()
        logger.info(f"✓ Current Positions: {len(positions)}")
        
        for pos in positions:
            logger.info(f"  - {pos.symbol}: {pos.quantity} @ ${pos.entry_price}")
        
        # 获取未成交订单
        open_orders = await executor.get_open_orders()
        logger.info(f"✓ Open Orders: {len(open_orders)}")
        
        logger.info("✓ Hyperliquid Executor Test Passed")
        
    except Exception as e:
        logger.error(f"✗ Hyperliquid Executor Test Failed: {e}")


async def test_unified_executor():
    """测试统一执行器"""
    logger.info("=" * 60)
    logger.info("Testing Unified Executor")
    logger.info("=" * 60)
    
    executor = UnifiedExecutor()
    
    try:
        # 初始化
        await executor.initialize()
        logger.info("✓ Unified Executor Initialized")
        
        # 查看可用执行器
        available = executor.get_available_executors()
        logger.info(f"✓ Available Executors: {[e.value for e in available]}")
        
        # 测试每个可用执行器
        for executor_type in available:
            logger.info(f"\n--- Testing {executor_type.value} ---")
            
            # 获取账户余额
            balance = await executor.get_account_balance(executor_type)
            logger.info(f"✓ Balance: {balance}")
            
            # 获取持仓
            positions = await executor.get_all_positions(executor_type)
            logger.info(f"✓ Positions: {len(positions)}")
        
        logger.info("\n✓ Unified Executor Test Passed")
        
    except Exception as e:
        logger.error(f"✗ Unified Executor Test Failed: {e}")
    finally:
        await executor.close()


async def main():
    """主测试函数"""
    logger.info("=" * 60)
    logger.info("Auto Trading Agent - Executor Tests")
    logger.info("=" * 60)
    
    # 1. 测试模拟执行器
    await test_mock_executor()
    
    print("\n")
    
    # 2. 测试币安永续执行器
    await test_binance_futures_executor()
    
    print("\n")
    
    # 3. 测试Hyperliquid执行器
    await test_hyperliquid_executor()
    
    print("\n")
    
    # 4. 测试统一执行器
    await test_unified_executor()
    
    logger.info("\n" + "=" * 60)
    logger.info("All Tests Completed")
    logger.info("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
