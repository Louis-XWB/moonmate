#!/usr/bin/env python3
"""
==============================================
  Unit 6 Demo: Multi-Agent Architecture
==============================================

Demonstrates:
  1. Multi-agent system with specialized roles
  2. Each agent analyzes real market data independently
  3. Voting mechanism and consensus building
  4. Final committee decision

Run:
  cd moon_mate
  python3 -m scripts.demo_unit6_multiagent
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
    header("Unit 6 Demo: Multi-Agent Committee Decision")

    print(f"  Five AI agents analyze the market independently,")
    print(f"  then vote to reach a consensus decision:\n")
    print(f"    🧑‍💼 {CYAN}News Analyst{RESET}       → Evaluates news impact")
    print(f"    📊 {CYAN}Technical Analyst{RESET}   → Reads chart patterns")
    print(f"    🔗 {CYAN}On-Chain Analyst{RESET}    → Tracks whale behavior")
    print(f"    🛡️ {CYAN}Risk Manager{RESET}        → Assesses risk/reward")
    print(f"    🎯 {CYAN}Decision Maker{RESET}      → Synthesizes final call")

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key == "sk-xxx":
        error("OPENAI_API_KEY not configured in .env")
        return

    # ── Step 1: Gather real market data ──
    section("Step 1: Gathering Real Market Data")

    provider, source = await get_data_provider()
    symbol = "BTC/USDT"

    try:
        ticker = await provider.get_ticker(symbol)
        klines = await provider.get_klines(symbol, interval="1h", limit=50)
        success(f"BTC Price: ${ticker.last_price:,.2f} ({ticker.change_24h:+.2f}%)")
        success(f"Loaded {len(klines)} hourly candles")
    finally:
        if hasattr(provider, 'close'):
            await provider.close()

    # ── Step 2: Prepare analysis context ──
    section("Step 2: Preparing Context for AI Committee")

    from backend.ai.news_analyzer import NewsAnalyzer
    from backend.data.whale_tracker import get_whale_tracker
    from backend.risk.engine import RiskEngine

    news_analyzer = NewsAnalyzer(model="gemini-3-flash-preview", temperature=0.2)
    whale_tracker = get_whale_tracker()
    risk_engine = RiskEngine(config={
        "max_positions": 3,
        "max_position_size": 1000,
        "max_single_order": 500,
        "max_daily_loss": 100,
        "max_drawdown": 10.0,
        "max_consecutive_losses": 5,
    })
    risk_engine.update_balance(10000)

    # Get whale data
    whale_analysis = await whale_tracker.analyze_whale_behavior("BTC")
    if whale_analysis:
        success(f"Whale data: {whale_analysis['whale_count']} whales tracked")
        info(f"Whale sentiment: {whale_analysis['sentiment']}")

    # Analyze a sample news headline
    sample_news = await news_analyzer.analyze_news(
        title="Bitcoin ETF sees record inflows as institutional adoption accelerates",
        content="Major financial institutions continue to increase their Bitcoin holdings through spot ETFs.",
        symbol="BTC"
    )
    news_impacts = []
    if sample_news:
        success(f"News impact: {sample_news.impact_direction.value} ({sample_news.importance_stars}⭐)")
        news_impacts = [sample_news]

    # ── Step 3: Multi-Agent Deliberation ──
    section("Step 3: AI Committee Deliberation")

    from backend.ai.multi_agent_system import MultiAgentSystem

    system = MultiAgentSystem(
        news_analyzer=news_analyzer,
        whale_tracker=whale_tracker,
        risk_manager=risk_engine
    )

    context = {
        "ticker": ticker,
        "klines": klines,
        "news_impacts": news_impacts,
        "symbol": symbol,
    }

    print(f"\n  {BOLD}Committee is deliberating...{RESET}")
    info("Each agent is analyzing independently via LLM...")
    print()

    try:
        result = await system.deliberate(context)

        # ── Display each agent's opinion ──
        agent_icons = {
            "news_analyst": "🧑‍💼",
            "technical_analyst": "📊",
            "onchain_analyst": "🔗",
            "risk_manager": "🛡️",
            "decision_maker": "🎯",
        }

        print(f"  {BOLD}{'─'*55}{RESET}")
        print(f"  {BOLD}  Agent Opinions{RESET}")
        print(f"  {BOLD}{'─'*55}{RESET}")

        for opinion in result.agent_opinions:
            icon = agent_icons.get(opinion.agent_role.value, "🤖")
            vote = opinion.decision.value

            vote_colors = {
                "strong_long": GREEN,
                "long": GREEN,
                "hold": YELLOW,
                "short": RED,
                "strong_short": RED,
            }
            vc = vote_colors.get(vote, RESET)

            print(f"\n  {icon} {BOLD}{opinion.agent_role.value.replace('_', ' ').title()}{RESET}")
            print(f"     Vote:       {vc}{vote.upper()}{RESET}")
            print(f"     Confidence: {opinion.confidence:.0%}")
            reason_lines = opinion.reasoning.split('. ')
            print(f"     Reasoning:  {reason_lines[0]}")
            for line in reason_lines[1:3]:
                if line.strip():
                    print(f"                 {line}")

        # ── Vote distribution ──
        print(f"\n  {BOLD}{'─'*55}{RESET}")
        print(f"  {BOLD}  Vote Distribution{RESET}")
        print(f"  {BOLD}{'─'*55}{RESET}\n")

        for vote_type, count in result.vote_distribution.items():
            bar = "█" * (count * 5)
            vc = GREEN if "long" in vote_type else RED if "short" in vote_type else YELLOW
            print(f"    {vote_type:>15}: {vc}{bar} {count}{RESET}")

        # ── Final Decision ──
        decision_colors = {
            "strong_long": GREEN,
            "long": GREEN,
            "hold": YELLOW,
            "short": RED,
            "strong_short": RED,
        }
        dc = decision_colors.get(result.final_decision.value, RESET)

        print(f"\n  {BOLD}{'═'*55}{RESET}")
        print(f"  {BOLD}  FINAL COMMITTEE DECISION{RESET}")
        print(f"  {BOLD}{'═'*55}{RESET}")
        print(f"\n    Decision:   {dc}{BOLD}{result.final_decision.value.upper()}{RESET}")
        print(f"    Confidence: {result.confidence:.0%}")
        print(f"\n    Summary:")
        summary_lines = result.debate_summary.split('. ')
        for line in summary_lines[:4]:
            if line.strip():
                print(f"      {line.strip()}.")
        print(f"\n  {BOLD}{'═'*55}{RESET}")

    except Exception as e:
        error(f"Committee deliberation failed: {e}")
        import traceback
        traceback.print_exc()
        return

    header("Demo Complete!")
    print(f"  The AI committee makes better decisions than a single agent")
    print(f"  by combining diverse perspectives and voting mechanisms.")
    print(f"  Unit 7 adds advanced quantitative strategies.\n")


if __name__ == "__main__":
    asyncio.run(main())
