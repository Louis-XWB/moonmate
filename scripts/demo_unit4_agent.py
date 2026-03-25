#!/usr/bin/env python3
"""
==============================================
  Unit 4 Demo: Simple Trading Agent
==============================================

Demonstrates:
  1. Fetch real market data (OKX)
  2. AI generates a trading signal
  3. Paper trade execution based on signal

Run:
  cd moon_mate
  python3 -m scripts.demo_unit4_agent
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
    get_data_provider,
)


async def main():
    header("Unit 4 Demo: Simple Trading Agent")

    print(f"  The complete single-agent trading loop:\n")
    print(f"    1. {CYAN}Fetch Data{RESET}     → Real market data from OKX")
    print(f"    2. {CYAN}AI Analysis{RESET}    → LLM generates trading signal")
    print(f"    3. {CYAN}Paper Trade{RESET}    → Execute signal on mock account")

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key == "sk-xxx":
        error("OPENAI_API_KEY not configured in .env")
        return

    # ── Step 1: Fetch real market data ──
    section("Step 1: Fetch Real Market Data")

    provider, source = await get_data_provider()

    try:
        symbol = "BTC/USDT"
        print(f"\n  {BOLD}Fetching {symbol} data...{RESET}")

        ticker = await provider.get_ticker(symbol)
        klines = await provider.get_klines(symbol, interval="1h", limit=50)

        success(f"Ticker: ${ticker.last_price:,.2f} ({ticker.change_24h:+.2f}%)")
        success(f"K-lines: {len(klines)} bars loaded")

        # Quick technical snapshot
        closes = [k.close for k in klines]
        sma5 = sum(closes[-5:]) / 5
        sma20 = sum(closes[-20:]) / 20

        info(f"SMA(5):  ${sma5:,.0f}")
        info(f"SMA(20): ${sma20:,.0f}")
        info(f"Trend:   {'Bullish (SMA5 > SMA20)' if sma5 > sma20 else 'Bearish (SMA5 < SMA20)'}")

    finally:
        if hasattr(provider, 'close'):
            await provider.close()

    # ── Step 2: AI Signal Generation ──
    section("Step 2: AI Signal Generation")

    from backend.ai.signal_generator import AISignalGenerator

    generator = AISignalGenerator(
        model="gemini-3-flash-preview",
        temperature=0.3,
        confidence_threshold=0.5
    )

    print(f"\n  {BOLD}AI is analyzing market conditions...{RESET}")
    info("Sending ticker + 50 K-lines to LLM...")

    try:
        signal = await generator.generate_signal(
            symbol=symbol,
            ticker=ticker,
            klines=klines,
            context={"vibe_rules": "No specific preferences"}
        )

        dir_map = {
            "long": (GREEN, "📈 LONG"),
            "short": (RED, "📉 SHORT"),
            "close": (YELLOW, "⏹ CLOSE"),
            "neutral": (DIM, "⏸ NEUTRAL"),
        }
        dir_val = signal.direction.value if hasattr(signal.direction, 'value') else str(signal.direction)
        color, label = dir_map.get(dir_val, (RESET, dir_val))

        print(f"\n  {BOLD}{'─'*45}{RESET}")
        print(f"  {BOLD}  AI Trading Signal{RESET}")
        print(f"  {BOLD}{'─'*45}{RESET}")
        print(f"    Direction:  {color}{label}{RESET}")
        print(f"    Strength:   {'█' * int(signal.strength * 10)}{'░' * (10 - int(signal.strength * 10))} {signal.strength:.0%}")
        print(f"    Confidence: {'█' * int(signal.confidence * 10)}{'░' * (10 - int(signal.confidence * 10))} {signal.confidence:.0%}")
        print(f"    Reason:     {signal.reason}")
        if signal.entry_price:
            print(f"    Entry:      ${signal.entry_price:,.2f}")
        if signal.stop_loss:
            print(f"    Stop Loss:  ${signal.stop_loss:,.2f}")
        if signal.take_profit:
            print(f"    Take Profit:${signal.take_profit:,.2f}")
        print(f"  {BOLD}{'─'*45}{RESET}")

        if signal.evidence:
            print(f"\n  {BOLD}Evidence:{RESET}")
            for ev in signal.evidence:
                info(f"• {ev}")

    except Exception as e:
        error(f"Signal generation failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # ── Step 3: Paper Trade ──
    section("Step 3: Paper Trade Execution")

    from backend.execution.executor import MockExecutor
    from backend.data.models import Order, OrderSide, OrderType, OrderStatus

    executor = MockExecutor(fill_probability=1.0, fill_delay=0.3)

    if dir_val in ("long", "short"):
        side = OrderSide.BUY if dir_val == "long" else OrderSide.SELL
        order = Order(
            symbol=symbol,
            side=side,
            type=OrderType.MARKET,
            price=ticker.last_price,
            size=100 / ticker.last_price,  # $100 notional
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            status=OrderStatus.PENDING,
            reason=signal.reason
        )

        print(f"\n  {BOLD}Placing paper order...{RESET}")
        info(f"Side: {side.value}")
        info(f"Size: {order.size:.6f} BTC (≈ $100)")
        info(f"Price: ${order.price:,.2f}")

        result = await executor.submit_order(order)

        if result.get("success"):
            success(f"Order filled!")
            info(f"Fill Price: ${result.get('avg_price', 0):,.2f}")
            info(f"Fee:        ${result.get('fee', 0):.4f}")
            info(f"Order ID:   {result.get('exchange_order_id', 'N/A')}")

            # Show position summary
            entry = result.get("avg_price", ticker.last_price)
            print(f"\n  {BOLD}Position Summary:{RESET}")
            print(f"    {MAGENTA}{'─'*40}{RESET}")
            print(f"    Symbol:     {symbol}")
            print(f"    Side:       {GREEN if side == OrderSide.BUY else RED}{side.value.upper()}{RESET}")
            print(f"    Entry:      ${entry:,.2f}")
            if signal.stop_loss:
                sl_pct = abs(signal.stop_loss - entry) / entry * 100
                print(f"    Stop Loss:  ${signal.stop_loss:,.2f} ({sl_pct:.1f}%)")
            if signal.take_profit:
                tp_pct = abs(signal.take_profit - entry) / entry * 100
                print(f"    Take Profit:${signal.take_profit:,.2f} ({tp_pct:.1f}%)")
            print(f"    {MAGENTA}{'─'*40}{RESET}")
        else:
            error(f"Order failed: {result}")
    else:
        info(f"Signal is {dir_val} - no trade needed")
        info("The agent is waiting for a clearer signal.")

    header("Demo Complete!")
    print(f"  You've seen the full single-agent trading loop:")
    print(f"    Data → AI Analysis → Signal → Paper Trade")
    print(f"  Unit 5 adds risk management before execution.\n")


if __name__ == "__main__":
    asyncio.run(main())
