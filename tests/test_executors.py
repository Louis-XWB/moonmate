"""
Trade executor test script
Tests Binance perpetual futures and Hyperliquid executors
"""

import asyncio
import sys
import os

# Add project path
sys.path.insert(0, '/home/ubuntu/auto-trading-agent')

from backend.core.logger import get_logger
from backend.execution.unified_executor import UnifiedExecutor, ExecutorType
from backend.data.models import OrderSide, OrderType

logger = get_logger("test_executors")


async def test_mock_executor():
    """Test mock executor"""
    logger.info("=" * 60)
    logger.info("Testing Mock Executor")
    logger.info("=" * 60)
    
    executor = UnifiedExecutor()
    await executor.initialize()
    
    try:
        # Set to simulation mode
        executor.set_active_executor(ExecutorType.MOCK)
        
        # GetAccount balance
        balance = await executor.get_account_balance()
        logger.info(f"✓ Account Balance: {balance}")
        
        # Place order test
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
        
        # GetPosition
        positions = await executor.get_all_positions()
        logger.info(f"✓ Positions: {len(positions)}")
        
        logger.info("✓ Mock Executor Test Passed")
        
    except Exception as e:
        logger.error(f"✗ Mock Executor Test Failed: {e}")
    finally:
        await executor.close()


async def test_binance_futures_executor():
    """Test Binance perpetual futures executor"""
    logger.info("=" * 60)
    logger.info("Testing Binance Futures Executor")
    logger.info("=" * 60)
    
    # Check environment variables
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
        # Initialize
        await executor.initialize()
        logger.info("✓ Executor Initialized")
        
        # GetAccount balance
        balance = await executor.get_account_balance()
        logger.info(f"✓ Account Balance: ${balance.get('total_balance', 0):.2f}")
        
        # GetPosition
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
    """Test Hyperliquid executor"""
    logger.info("=" * 60)
    logger.info("Testing Hyperliquid Executor")
    logger.info("=" * 60)
    
    # Check environment variables
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
        # Initialize
        await executor.initialize()
        logger.info("✓ Executor Initialized")
        logger.info(f"  Address: {executor.address}")
        
        # GetAccount balance
        balance = await executor.get_account_balance()
        logger.info(f"✓ Account Balance: ${balance.get('account_value', 0):.2f}")
        logger.info(f"  Withdrawable: ${balance.get('withdrawable', 0):.2f}")
        
        # GetPosition
        positions = await executor.get_all_positions()
        logger.info(f"✓ Current Positions: {len(positions)}")
        
        for pos in positions:
            logger.info(f"  - {pos.symbol}: {pos.quantity} @ ${pos.entry_price}")
        
        # GetUnfilledOrder
        open_orders = await executor.get_open_orders()
        logger.info(f"✓ Open Orders: {len(open_orders)}")
        
        logger.info("✓ Hyperliquid Executor Test Passed")
        
    except Exception as e:
        logger.error(f"✗ Hyperliquid Executor Test Failed: {e}")


async def test_unified_executor():
    """Test unified executor"""
    logger.info("=" * 60)
    logger.info("Testing Unified Executor")
    logger.info("=" * 60)
    
    executor = UnifiedExecutor()
    
    try:
        # Initialize
        await executor.initialize()
        logger.info("✓ Unified Executor Initialized")
        
        # View available executors
        available = executor.get_available_executors()
        logger.info(f"✓ Available Executors: {[e.value for e in available]}")
        
        # Test each available executor
        for executor_type in available:
            logger.info(f"\n--- Testing {executor_type.value} ---")
            
            # GetAccount balance
            balance = await executor.get_account_balance(executor_type)
            logger.info(f"✓ Balance: {balance}")
            
            # GetPosition
            positions = await executor.get_all_positions(executor_type)
            logger.info(f"✓ Positions: {len(positions)}")
        
        logger.info("\n✓ Unified Executor Test Passed")
        
    except Exception as e:
        logger.error(f"✗ Unified Executor Test Failed: {e}")
    finally:
        await executor.close()


async def main():
    """Main test function"""
    logger.info("=" * 60)
    logger.info("Auto Trading Agent - Executor Tests")
    logger.info("=" * 60)
    
    # 1. Test mock executor
    await test_mock_executor()
    
    print("\n")
    
    # 2. Test Binance perpetual futures executor
    await test_binance_futures_executor()
    
    print("\n")
    
    # 3. Test Hyperliquid executor
    await test_hyperliquid_executor()
    
    print("\n")
    
    # 4. Test unified executor
    await test_unified_executor()
    
    logger.info("\n" + "=" * 60)
    logger.info("All Tests Completed")
    logger.info("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
