#!/usr/bin/env python3
"""
==============================================
  Unit 7 Demo: Advanced Strategies & Backtest
==============================================

Demonstrates:
  1. Fetch real historical data from OKX
  2. Momentum strategy backtest
  3. Reversal strategy backtest
  4. Results comparison (Sharpe, win rate, drawdown)

Run:
  cd moon_mate
  python3 -m scripts.demo_unit7_backtest
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


def print_backtest_result(name, result):
    """Pretty print backtest results"""
    ret_color = GREEN if result.total_return > 0 else RED

    print(f"\n  {BOLD}{'─'*50}{RESET}")
    print(f"  {BOLD}  {name} - Backtest Results{RESET}")
    print(f"  {BOLD}{'─'*50}{RESET}")

    # Performance
    print(f"\n  {BOLD}Performance:{RESET}")
    print(f"    Total Return:      {ret_color}${result.total_return:+,.2f} ({result.total_return_pct:+.2f}%){RESET}")
    print(f"    Annualized Return: {ret_color}{result.annualized_return:.2f}%{RESET}")
    print(f"    Max Drawdown:      {RED}{result.max_drawdown_pct:.2f}%{RESET} (${result.max_drawdown:,.2f})")

    # Risk Metrics
    print(f"\n  {BOLD}Risk Metrics:{RESET}")
    sr_color = GREEN if result.sharpe_ratio > 1 else YELLOW if result.sharpe_ratio > 0 else RED
    print(f"    Sharpe Ratio:      {sr_color}{result.sharpe_ratio:.2f}{RESET}")
    print(f"    Sortino Ratio:     {result.sortino_ratio:.2f}")
    print(f"    Calmar Ratio:      {result.calmar_ratio:.2f}")

    # Trade Stats
    print(f"\n  {BOLD}Trade Statistics:{RESET}")
    print(f"    Total Trades:      {result.total_trades}")
    wr_color = GREEN if result.win_rate > 0.5 else RED
    print(f"    Win Rate:          {wr_color}{result.win_rate:.1%}{RESET}")
    print(f"    Winning Trades:    {GREEN}{result.winning_trades}{RESET}")
    print(f"    Losing Trades:     {RED}{result.total_trades - result.winning_trades}{RESET}")
    print(f"    Avg Win:           {GREEN}${result.avg_win:,.2f}{RESET}")
    print(f"    Avg Loss:          {RED}${result.avg_loss:,.2f}{RESET}")
    pf_color = GREEN if result.profit_factor > 1 else RED
    print(f"    Profit Factor:     {pf_color}{result.profit_factor:.2f}{RESET}")

    # Equity curve mini visualization
    if result.equity_curve and len(result.equity_curve) > 10:
        curve = result.equity_curve
        step = max(1, len(curve) // 20)
        sampled = curve[::step]
        min_val = min(sampled)
        max_val = max(sampled)
        range_val = max_val - min_val if max_val != min_val else 1

        print(f"\n  {BOLD}Equity Curve:{RESET}")
        print(f"    ${max_val:>10,.0f} ┤")
        for val in sampled:
            bar_len = int((val - min_val) / range_val * 30)
            color = GREEN if val >= curve[0] else RED
            print(f"               │{color}{'█' * bar_len}{RESET}")
        print(f"    ${min_val:>10,.0f} ┤")


async def main():
    header("Unit 7 Demo: Advanced Strategies & Backtesting")

    print(f"  Backtest two strategies on real OKX historical data:\n")
    print(f"    1. {CYAN}Momentum Strategy{RESET}  → Trend-following with RSI + SMA")
    print(f"    2. {CYAN}Reversal Strategy{RESET}  → Mean reversion at extremes")

    # ── Step 1: Fetch real historical data ──
    section("Step 1: Fetch Real Historical Data from OKX")

    provider, source = await get_data_provider()
    symbol = "BTC/USDT"

    try:
        print(f"\n  {BOLD}Fetching BTC/USDT 1h candles...{RESET}")
        klines = await provider.get_klines(symbol, interval="1h", limit=500)
        success(f"Loaded {len(klines)} candles")

        if klines:
            first = klines[0]
            last = klines[-1]
            info(f"Period: {first.open_time.strftime('%Y-%m-%d %H:%M')} → {last.open_time.strftime('%Y-%m-%d %H:%M')}")
            info(f"Price Range: ${min(k.low for k in klines):,.0f} - ${max(k.high for k in klines):,.0f}")

            # Price summary
            open_price = klines[0].open
            close_price = klines[-1].close
            period_return = (close_price - open_price) / open_price * 100
            ret_color = GREEN if period_return > 0 else RED
            info(f"Buy & Hold:  {ret_color}{period_return:+.2f}%{RESET} (${open_price:,.0f} → ${close_price:,.0f})")
    finally:
        if hasattr(provider, 'close'):
            await provider.close()

    if len(klines) < 50:
        error("Not enough data for backtesting (need at least 50 bars)")
        return

    # ── Step 2: Momentum Strategy Backtest ──
    section("Step 2: Momentum Strategy Backtest")

    from backend.strategy.momentum import MomentumStrategy
    from backend.backtest.engine import BacktestEngine

    momentum = MomentumStrategy(params={
        "rsi_period": 14,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
        "sma_fast": 5,
        "sma_slow": 20,
        "volume_threshold": 1.5,
    })

    engine1 = BacktestEngine(
        initial_balance=10000,
        fee_rate=0.001,
        slippage=0.0005
    )

    print(f"\n  {BOLD}Running momentum backtest...{RESET}")
    info("Strategy: RSI + SMA crossover + Volume confirmation")
    info(f"Initial balance: $10,000 | Order size: $200")

    momentum_result = await engine1.run(
        symbol=symbol,
        strategy=momentum,
        klines=klines,
        order_size=200
    )

    print_backtest_result("Momentum Strategy", momentum_result)

    # ── Step 3: Reversal Strategy Backtest ──
    section("Step 3: Reversal Strategy Backtest")

    from backend.strategy.reversal import ReversalStrategy

    reversal = ReversalStrategy(
        rsi_oversold=25,
        rsi_overbought=75,
        bb_std=2.0,
        lookback_period=20,
    )

    engine2 = BacktestEngine(
        initial_balance=10000,
        fee_rate=0.001,
        slippage=0.0005
    )

    print(f"\n  {BOLD}Running reversal backtest...{RESET}")
    info("Strategy: RSI extremes + Bollinger Bands + Z-Score")
    info(f"Initial balance: $10,000 | Order size: $200")

    reversal_result = await engine2.run(
        symbol=symbol,
        strategy=reversal,
        klines=klines,
        order_size=200
    )

    print_backtest_result("Reversal Strategy", reversal_result)

    # ── Step 4: Strategy Comparison ──
    section("Step 4: Strategy Comparison")

    print(f"\n  {BOLD}{'Metric':<25} {'Momentum':>12} {'Reversal':>12}{RESET}")
    print(f"  {'─'*50}")

    def compare_row(label, v1, v2, fmt=".2f", pct=False, higher_better=True):
        s = "%" if pct else ""
        v1_str = f"{v1:{fmt}}{s}"
        v2_str = f"{v2:{fmt}}{s}"
        if higher_better:
            c1 = GREEN if v1 > v2 else RED if v1 < v2 else RESET
            c2 = GREEN if v2 > v1 else RED if v2 < v1 else RESET
        else:
            c1 = GREEN if v1 < v2 else RED if v1 > v2 else RESET
            c2 = GREEN if v2 < v1 else RED if v2 > v1 else RESET
        print(f"  {label:<25} {c1}{v1_str:>12}{RESET} {c2}{v2_str:>12}{RESET}")

    compare_row("Total Return ($)", momentum_result.total_return, reversal_result.total_return, "+,.2f")
    compare_row("Return (%)", momentum_result.total_return_pct, reversal_result.total_return_pct, "+.2f", pct=True)
    compare_row("Sharpe Ratio", momentum_result.sharpe_ratio, reversal_result.sharpe_ratio)
    compare_row("Win Rate", momentum_result.win_rate * 100, reversal_result.win_rate * 100, ".1f", pct=True)
    compare_row("Profit Factor", momentum_result.profit_factor, reversal_result.profit_factor)
    compare_row("Max Drawdown (%)", momentum_result.max_drawdown_pct, reversal_result.max_drawdown_pct, ".2f", pct=True, higher_better=False)
    compare_row("Total Trades", momentum_result.total_trades, reversal_result.total_trades, "d")

    # Winner
    m_score = (1 if momentum_result.sharpe_ratio > reversal_result.sharpe_ratio else 0) + \
              (1 if momentum_result.total_return > reversal_result.total_return else 0) + \
              (1 if momentum_result.win_rate > reversal_result.win_rate else 0)

    winner = "Momentum" if m_score >= 2 else "Reversal"
    print(f"\n  {BOLD}🏆 Winner: {GREEN}{winner} Strategy{RESET}")

    header("Demo Complete!")
    print(f"  Real historical data backtesting reveals strategy strengths")
    print(f"  and weaknesses. In production (Unit 8), we combine both")
    print(f"  strategies with the AI multi-agent system.\n")


if __name__ == "__main__":
    asyncio.run(main())
