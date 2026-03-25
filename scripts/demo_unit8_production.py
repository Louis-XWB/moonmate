#!/usr/bin/env python3
"""
==============================================
  Unit 8 Demo: Production System Integration
==============================================

Demonstrates:
  1. Configuration management & hot reload
  2. Event bus architecture
  3. Logging & monitoring
  4. Full end-to-end trading pipeline
     (Data → AI → Risk → Execute → Log)

Run:
  cd moon_mate
  python3 -m scripts.demo_unit8_production
"""

import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from scripts._helpers import (
    header, section, success, info, warn, error,
    GREEN, CYAN, YELLOW, RED, MAGENTA, BOLD, DIM, RESET,
    get_data_provider,
)


async def demo_config():
    """Part 1: Configuration management"""
    section("1. Configuration Management")

    from backend.core.config import Config

    print(f"\n  {BOLD}Loading config from config/dev.yaml...{RESET}")
    config = Config.load_from_file("config/dev.yaml")

    success(f"Environment:   {config.env.value}")
    success(f"Debug Mode:    {config.debug}")
    info(f"Trading Mode:  {config.trading.mode}")
    info(f"Symbols:       {', '.join(config.trading.symbols)}")
    info(f"Max Position:  ${config.trading.max_position_size}")
    info(f"AI Model:      {config.ai.model}")
    info(f"AI Confidence: {config.ai.confidence_threshold}")

    print(f"\n  {BOLD}Risk Configuration:{RESET}")
    info(f"Max Daily Loss:       ${config.risk.max_daily_loss}")
    info(f"Max Drawdown:         {config.risk.max_drawdown}%")
    info(f"Stop Loss:            {config.risk.stop_loss_pct}%")
    info(f"Take Profit:          {config.risk.take_profit_pct}%")
    info(f"Max Consecutive Loss: {config.risk.max_consecutive_losses}")

    return config


async def demo_event_bus():
    """Part 2: Event bus architecture"""
    section("2. Event Bus (Decoupled Communication)")

    from backend.core.events import EventBus, EventType, Event

    bus = EventBus()
    received_events = []

    # Register handlers
    async def on_signal(event):
        received_events.append(("signal", event.data))
        direction = event.data.get("direction", "N/A")
        color = GREEN if direction == "long" else RED if direction == "short" else YELLOW
        print(f"    {MAGENTA}[Signal Handler]{RESET} Received: {color}{direction.upper()}{RESET} signal for {event.data.get('symbol')}")

    async def on_order(event):
        received_events.append(("order", event.data))
        print(f"    {MAGENTA}[Order Handler]{RESET}  Order {event.data.get('status', 'unknown')}: {event.data.get('symbol')} {event.data.get('side')}")

    async def on_risk(event):
        received_events.append(("risk", event.data))
        print(f"    {MAGENTA}[Risk Handler]{RESET}   Alert: {event.data.get('message', 'N/A')}")

    bus.subscribe(EventType.SIGNAL_GENERATED, on_signal)
    bus.subscribe(EventType.ORDER_FILLED, on_order)
    bus.subscribe(EventType.RISK_CHECK_FAILED, on_risk)

    print(f"\n  {BOLD}Registered 3 event handlers{RESET}")
    info("SIGNAL_GENERATED → Signal Handler")
    info("ORDER_FILLED     → Order Handler")
    info("RISK_CHECK_FAILED→ Risk Handler")

    # Start event loop in background
    loop_task = asyncio.create_task(bus.start())

    print(f"\n  {BOLD}Publishing events...{RESET}\n")

    await bus.publish(Event(type=EventType.SIGNAL_GENERATED, data={
        "symbol": "BTC/USDT",
        "direction": "long",
        "strength": 0.8,
        "confidence": 0.75,
    }))

    await bus.publish(Event(type=EventType.ORDER_FILLED, data={
        "symbol": "BTC/USDT",
        "side": "BUY",
        "status": "filled",
        "price": 88000,
    }))

    await bus.publish(Event(type=EventType.RISK_CHECK_FAILED, data={
        "message": "Daily loss at 80% of limit",
        "severity": "warning",
    }))

    # Wait for events to be processed
    await asyncio.sleep(0.5)
    bus.stop()
    loop_task.cancel()
    try:
        await loop_task
    except asyncio.CancelledError:
        pass

    success(f"All {len(received_events)} events delivered successfully")
    info("Event bus decouples components - handlers don't know about each other")


async def demo_logging():
    """Part 3: Logging & monitoring"""
    section("3. Logging & Monitoring")

    import logging

    # Configure a demo logger
    logger = logging.getLogger("demo.trading")
    logger.setLevel(logging.DEBUG)

    # Console handler with color
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)

    class ColorFormatter(logging.Formatter):
        COLORS = {
            logging.DEBUG: DIM,
            logging.INFO: GREEN,
            logging.WARNING: YELLOW,
            logging.ERROR: RED,
            logging.CRITICAL: f"{RED}{BOLD}",
        }

        def format(self, record):
            color = self.COLORS.get(record.levelno, RESET)
            timestamp = self.formatTime(record, "%H:%M:%S")
            return f"    {color}[{record.levelname:>8}]{RESET} {timestamp} | {record.getMessage()}"

    handler.setFormatter(ColorFormatter())
    logger.addHandler(handler)

    print(f"\n  {BOLD}Simulating production log output:{RESET}\n")

    logger.info("System startup - loading configuration")
    logger.info("Data provider connected: OKX (BTC/USDT, ETH/USDT)")
    logger.debug("WebSocket connection established")
    logger.info("AI model loaded: gemini-3-flash-preview (temp=0.3)")
    logger.info("Risk engine initialized: 5 rules active")
    logger.info("Signal generated: LONG BTC/USDT (strength=0.78, confidence=0.82)")
    logger.info("Risk check PASSED: all 5 rules satisfied")
    logger.info("Order submitted: BUY 0.001 BTC @ $88,000 (market)")
    logger.info("Order filled: avg_price=$87,995.50, fee=$0.088")
    logger.warning("Daily PnL approaching limit: -$85 / -$100 (85%)")
    logger.info("Position update: BTC/USDT LONG, unrealized PnL: +$12.50")
    logger.error("API rate limit hit (OKX) - backing off 2s")
    logger.info("Recovered from rate limit - resuming data feed")
    logger.critical("Circuit breaker triggered: 3 consecutive losses")

    # Remove handler to avoid duplicate output
    logger.removeHandler(handler)

    print(f"\n  {BOLD}Log Levels in Production:{RESET}")
    info(f"{DIM}DEBUG{RESET}    → Internal state, WebSocket frames")
    info(f"{GREEN}INFO{RESET}     → Normal operations, trades, signals")
    info(f"{YELLOW}WARNING{RESET}  → Approaching limits, degraded performance")
    info(f"{RED}ERROR{RESET}    → API failures, recoverable issues")
    info(f"{RED}{BOLD}CRITICAL{RESET} → Circuit breakers, system halts")


async def demo_full_pipeline():
    """Part 4: Full end-to-end trading pipeline"""
    section("4. Full End-to-End Pipeline")

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key == "sk-xxx":
        error("OPENAI_API_KEY not configured - skipping LLM-dependent pipeline")
        return

    print(f"\n  {BOLD}Running the complete trading loop:{RESET}")
    print(f"  Data → AI Signal → Risk Check → Execute → Log\n")

    steps = [
        ("📡", "Data", "Fetching real-time BTC data from OKX"),
        ("🤖", "AI", "Generating trading signal via LLM"),
        ("🛡️", "Risk", "Running risk checks (5 rules)"),
        ("⚡", "Execute", "Placing paper order"),
        ("📝", "Log", "Recording trade result"),
    ]

    # Step 1: Data
    print(f"  {BOLD}📡 Step 1: Data Layer{RESET}")
    t0 = time.time()

    provider, source = await get_data_provider()

    try:
        ticker = await provider.get_ticker("BTC/USDT")
        klines = await provider.get_klines("BTC/USDT", interval="1h", limit=50)
        t1 = time.time()
        success(f"BTC ${ticker.last_price:,.2f} | {len(klines)} candles | {t1-t0:.1f}s")
    finally:
        if hasattr(provider, 'close'):
            await provider.close()

    # Step 2: AI Signal
    print(f"\n  {BOLD}🤖 Step 2: AI Signal Generation{RESET}")
    t2 = time.time()

    from backend.ai.signal_generator import AISignalGenerator
    generator = AISignalGenerator(model="gemini-3-flash-preview", temperature=0.3)

    signal = await generator.generate_signal(
        symbol="BTC/USDT",
        ticker=ticker,
        klines=klines,
    )
    t3 = time.time()

    dir_val = signal.direction.value if hasattr(signal.direction, 'value') else str(signal.direction)
    dir_color = GREEN if dir_val == "long" else RED if dir_val == "short" else YELLOW
    success(f"Signal: {dir_color}{dir_val.upper()}{RESET} "
            f"(strength={signal.strength:.0%}, confidence={signal.confidence:.0%}) | {t3-t2:.1f}s")
    info(f"Reason: {signal.reason}")

    # Step 3: Risk Check
    print(f"\n  {BOLD}🛡️ Step 3: Risk Check{RESET}")
    t4 = time.time()

    from backend.risk.engine import RiskEngine
    risk_engine = RiskEngine(config={
        "max_positions": 3, "max_position_size": 1000,
        "max_single_order": 500, "max_daily_loss": 100,
        "max_drawdown": 10.0, "max_consecutive_losses": 5,
    })
    risk_engine.update_balance(10000)

    risk_result = risk_engine.check(signal, positions=[], orders=[])
    t5 = time.time()

    if risk_result.passed:
        success(f"Risk check PASSED | {t5-t4:.3f}s")
    else:
        error(f"Risk check FAILED: [{risk_result.rule_name}] {risk_result.reason}")

    # Step 4: Execute
    print(f"\n  {BOLD}⚡ Step 4: Order Execution{RESET}")
    t6 = time.time()

    if dir_val in ("long", "short") and risk_result.passed:
        from backend.execution.executor import MockExecutor
        from backend.data.models import Order, OrderSide, OrderType, OrderStatus

        executor = MockExecutor(fill_probability=1.0, fill_delay=0.2)
        side = OrderSide.BUY if dir_val == "long" else OrderSide.SELL

        order = Order(
            symbol="BTC/USDT", side=side, type=OrderType.MARKET,
            price=ticker.last_price, size=100/ticker.last_price,
            stop_loss=signal.stop_loss, take_profit=signal.take_profit,
            status=OrderStatus.PENDING, reason=signal.reason
        )

        result = await executor.submit_order(order)
        t7 = time.time()

        if result.get("success"):
            success(f"Order FILLED @ ${result.get('avg_price', 0):,.2f} | Fee: ${result.get('fee', 0):.4f} | {t7-t6:.1f}s")
        else:
            error(f"Order failed")
    else:
        info(f"No trade needed (signal={dir_val}, risk_passed={risk_result.passed})")
        t7 = time.time()

    # Step 5: Summary
    print(f"\n  {BOLD}📝 Step 5: Trade Log{RESET}")
    total_time = t7 - t0

    print(f"\n  {BOLD}{'═'*50}{RESET}")
    print(f"  {BOLD}  Pipeline Summary{RESET}")
    print(f"  {BOLD}{'═'*50}{RESET}")
    print(f"    Data fetch:      {t1-t0:>6.1f}s")
    print(f"    AI analysis:     {t3-t2:>6.1f}s")
    print(f"    Risk check:      {t5-t4:>6.3f}s")
    print(f"    Order execution: {t7-t6:>6.1f}s")
    print(f"    {'─'*30}")
    print(f"    {BOLD}Total:           {total_time:>6.1f}s{RESET}")
    print(f"  {BOLD}{'═'*50}{RESET}")


async def main():
    header("Unit 8 Demo: Production System Integration")

    print(f"  Putting it all together - a production-grade system:\n")
    print(f"    1. {CYAN}Configuration{RESET}  → YAML config with hot reload")
    print(f"    2. {CYAN}Event Bus{RESET}      → Decoupled component communication")
    print(f"    3. {CYAN}Logging{RESET}        → Structured production logging")
    print(f"    4. {CYAN}Full Pipeline{RESET}   → End-to-end trading in one loop")

    config = await demo_config()
    await demo_event_bus()
    await demo_logging()
    await demo_full_pipeline()

    header("Demo Complete!")
    print(f"  This is the complete MoonMate trading system!")
    print(f"  Run './start.sh' to launch the full web UI.\n")
    print(f"  {BOLD}Congratulations on completing the course! 🎉{RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
