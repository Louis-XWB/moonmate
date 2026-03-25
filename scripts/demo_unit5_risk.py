#!/usr/bin/env python3
"""
==============================================
  Unit 5 Demo: Risk Management & Execution
==============================================

Demonstrates:
  1. Risk engine with pluggable rules
  2. Circuit breaker & cooldown mechanisms
  3. Order execution via mock executor
  4. Unified executor architecture

Run:
  cd moon_mate
  python3 -m scripts.demo_unit5_risk
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from scripts._helpers import (
    header, section, success, info, warn, error,
    GREEN, CYAN, YELLOW, RED, MAGENTA, BOLD, DIM, RESET,
)


async def demo_risk_engine():
    """Part 1: Risk engine with all rules"""
    section("1. Risk Engine - Rule Checks")

    from backend.risk.engine import RiskEngine
    from backend.data.models import Signal, SignalDirection, Order, OrderSide, OrderType, OrderStatus, Position

    engine = RiskEngine(config={
        "max_positions": 3,
        "max_position_size": 1000,
        "max_single_order": 500,
        "max_daily_loss": 100,
        "max_drawdown": 10.0,
        "max_consecutive_losses": 3,
    })

    # Set initial balance
    engine.update_balance(10000)

    print(f"\n  {BOLD}Risk Rules Loaded:{RESET}")
    for rule in engine.rules:
        info(f"{rule.name} (priority: {rule.priority})")

    # ── Test 1: Normal order passes ──
    print(f"\n  {BOLD}Test 1: Normal order ($100 BTC long){RESET}")
    signal = Signal(
        symbol="BTC/USDT",
        direction=SignalDirection.LONG,
        strength=0.7,
        confidence=0.8,
        source="demo",
        reason="Test signal",
        evidence=["momentum bullish"]
    )
    result = engine.check(signal, positions=[], orders=[])
    if result.passed:
        success(f"PASSED - {result.reason}")
    else:
        error(f"BLOCKED - [{result.rule_name}] {result.reason}")

    # ── Test 2: Oversized order blocked ──
    print(f"\n  {BOLD}Test 2: Oversized order ($2000 - exceeds $500 limit){RESET}")
    big_signal = Signal(
        symbol="BTC/USDT",
        direction=SignalDirection.LONG,
        strength=0.9,
        confidence=0.9,
        entry_price=88000,
        source="demo",
        reason="Big bet",
        evidence=[]
    )
    # Simulate a large order context
    big_order = Order(
        symbol="BTC/USDT", side=OrderSide.BUY, type=OrderType.MARKET,
        price=88000, size=2000/88000, status=OrderStatus.PENDING
    )
    result = engine.check(big_signal, positions=[], orders=[big_order])
    if result.passed:
        warn(f"PASSED - {result.reason}")
    else:
        success(f"BLOCKED as expected - [{result.rule_name}] {result.reason}")

    # ── Test 3: Too many positions ──
    print(f"\n  {BOLD}Test 3: Position limit (already have 3 positions){RESET}")
    existing_positions = [
        Position(symbol="BTC/USDT", side=OrderSide.BUY, size=0.001, entry_price=87000, current_price=88000),
        Position(symbol="ETH/USDT", side=OrderSide.BUY, size=0.01, entry_price=3100, current_price=3200),
        Position(symbol="SOL/USDT", side=OrderSide.SELL, size=0.5, entry_price=150, current_price=145),
    ]
    result = engine.check(signal, positions=existing_positions, orders=[])
    if result.passed:
        warn(f"PASSED - {result.reason}")
    else:
        success(f"BLOCKED as expected - [{result.rule_name}] {result.reason}")

    return engine


async def demo_circuit_breaker(engine):
    """Part 2: Circuit breaker and cooldown"""
    section("2. Circuit Breaker & Cooldown")

    from backend.data.models import Signal, SignalDirection

    signal = Signal(
        symbol="BTC/USDT",
        direction=SignalDirection.LONG,
        strength=0.7,
        confidence=0.8,
        source="demo",
        reason="Test",
        evidence=[]
    )

    # Simulate consecutive losses
    print(f"\n  {BOLD}Simulating 3 consecutive losses...{RESET}")
    for i in range(3):
        engine.update_pnl(-40)
        info(f"Loss #{i+1}: -$40  (cumulative: -${(i+1)*40})")

    state = engine.get_state()
    info(f"Daily P&L:          ${state.daily_pnl:,.2f}")
    info(f"Consecutive Losses: {state.consecutive_losses}")
    info(f"Circuit Breaker:    {'🔴 ACTIVE' if state.circuit_breaker_active else '🟢 Normal'}")

    # Try to place order now
    print(f"\n  {BOLD}Attempting to trade after losses...{RESET}")
    result = engine.check(signal, positions=[], orders=[])
    if not result.passed:
        success(f"Trading blocked: [{result.rule_name}] {result.reason}")
        info(f"Severity: {result.severity}")
        info(f"Action: {result.suggested_action}")
    else:
        warn(f"Order passed (unexpected)")

    # Reset
    print(f"\n  {BOLD}Resetting circuit breaker...{RESET}")
    engine.reset_circuit_breaker()
    state = engine.get_state()
    success(f"Circuit Breaker: {'🔴 ACTIVE' if state.circuit_breaker_active else '🟢 Normal'}")


async def demo_order_execution():
    """Part 3: Order execution via mock executor"""
    section("3. Order Execution (Mock Executor)")

    from backend.execution.executor import MockExecutor
    from backend.data.models import Order, OrderSide, OrderType, OrderStatus

    executor = MockExecutor(fill_probability=1.0, fill_delay=0.3)

    orders_to_place = [
        ("BTC/USDT", OrderSide.BUY, 88000, 0.001, "Momentum signal"),
        ("ETH/USDT", OrderSide.BUY, 3200, 0.03, "Breakout signal"),
        ("BTC/USDT", OrderSide.SELL, 88500, 0.001, "Take profit"),
    ]

    print(f"\n  {BOLD}Placing 3 orders...{RESET}\n")

    for symbol, side, price, size, reason in orders_to_place:
        order = Order(
            symbol=symbol,
            side=side,
            type=OrderType.MARKET,
            price=price,
            size=size,
            status=OrderStatus.PENDING,
            reason=reason
        )

        result = await executor.submit_order(order)
        side_color = GREEN if side == OrderSide.BUY else RED
        status = "✓ FILLED" if result.get("success") else "✗ FAILED"
        status_color = GREEN if result.get("success") else RED

        print(f"  {status_color}{status}{RESET}  "
              f"{side_color}{side.value:>4}{RESET}  "
              f"{symbol:<12}  "
              f"${result.get('avg_price', price):>10,.2f}  "
              f"Size: {size}  "
              f"Fee: ${result.get('fee', 0):.4f}  "
              f"{DIM}({reason}){RESET}")


async def demo_unified_executor():
    """Part 4: Unified executor architecture"""
    section("4. Unified Executor Architecture")

    try:
        from backend.execution.unified_executor import UnifiedExecutor, ExecutorType

        print(f"\n  {BOLD}Available Executor Types:{RESET}")
        for et in ExecutorType:
            status = "🟢" if et == ExecutorType.MOCK else "⚪"
            info(f"{status} {et.value}")

        unified = UnifiedExecutor()
        executors = unified.get_available_executors()

        print(f"\n  {BOLD}Initialized Executors:{RESET}")
        for name in executors:
            success(f"{name}")
    except ImportError as e:
        warn(f"Skipping unified executor demo (missing dependency: {e})")

    info(f"\nIn production, the unified executor routes orders")
    info(f"to the appropriate exchange (Binance/Hyperliquid)")
    info(f"based on configuration, with automatic fallback.")


async def main():
    header("Unit 5 Demo: Risk Management & Execution")

    print(f"  This demo shows the safety layer between signal and trade:\n")
    print(f"    1. {CYAN}Risk Rules{RESET}       → Position limits, loss limits, drawdown")
    print(f"    2. {CYAN}Circuit Breaker{RESET}   → Auto-halt on consecutive losses")
    print(f"    3. {CYAN}Order Execution{RESET}   → Fill simulation with slippage")
    print(f"    4. {CYAN}Unified Executor{RESET}  → Multi-exchange routing")

    engine = await demo_risk_engine()
    await demo_circuit_breaker(engine)
    await demo_order_execution()
    await demo_unified_executor()

    header("Demo Complete!")
    print(f"  Risk management is the difference between a toy and")
    print(f"  a production trading system. Unit 6 upgrades to")
    print(f"  multi-agent decision making.\n")


if __name__ == "__main__":
    asyncio.run(main())
