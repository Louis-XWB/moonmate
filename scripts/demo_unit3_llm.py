#!/usr/bin/env python3
"""
==============================================
  Unit 3 Demo: LLM & Prompt Engineering
==============================================

Demonstrates:
  1. LLM API call with structured JSON output
  2. News impact assessment (star rating + direction)
  3. Market sentiment analysis from social text

Run:
  cd moon_mate
  python3 -m scripts.demo_unit3_llm
"""

import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from scripts._helpers import (
    header, section, success, info, warn, error,
    GREEN, CYAN, YELLOW, RED, MAGENTA, BOLD, DIM, RESET,
)


async def demo_raw_llm_call():
    """Part 1: Direct LLM API call with structured output"""
    section("1. Direct LLM Call → Structured JSON Output")

    from openai import OpenAI
    client = OpenAI()

    prompt = """You are a crypto market analyst. Analyze the current BTC market conditions
    based on these facts:
    - BTC price is around $88,000
    - 24h volume is high
    - RSI is at 62 (neutral-slightly overbought)
    - Moving averages show bullish alignment

    Respond in JSON format:
    {
        "direction": "long|short|neutral",
        "strength": 0.0-1.0,
        "confidence": 0.0-1.0,
        "reason": "brief explanation",
        "evidence": ["point1", "point2", "point3"]
    }"""

    print(f"\n  {BOLD}Sending prompt to LLM...{RESET}")
    info(f"Model: {os.getenv('OPENAI_MODEL', 'gemini-3-flash-preview')}")
    info(f"Endpoint: {os.getenv('OPENAI_BASE_URL', 'default')}")

    try:
        response = client.chat.completions.create(
            model="gemini-3-flash-preview",
            messages=[
                {"role": "system", "content": "You are a JSON API. Respond with valid JSON only. No markdown, no code fences, no explanatory text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=8192,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        success("LLM response received!")
        print(f"\n  {BOLD}Raw JSON Output:{RESET}")

        parsed = json.loads(raw)
        print(f"  {json.dumps(parsed, indent=4)}")

        print(f"\n  {BOLD}Parsed Fields:{RESET}")
        dir_color = GREEN if parsed.get("direction") == "long" else RED if parsed.get("direction") == "short" else YELLOW
        info(f"Direction:  {dir_color}{parsed.get('direction', 'N/A').upper()}{RESET}")
        info(f"Strength:   {parsed.get('strength', 0):.0%}")
        info(f"Confidence: {parsed.get('confidence', 0):.0%}")
        info(f"Reason:     {parsed.get('reason', 'N/A')}")
        for ev in parsed.get("evidence", []):
            info(f"  • {ev}")

    except json.JSONDecodeError:
        error(f"Failed to parse JSON. Raw output:\n{raw}")
    except Exception as e:
        error(f"LLM call failed: {e}")


async def demo_news_impact():
    """Part 2: AI News Impact Assessment"""
    section("2. AI News Impact Assessment")

    from backend.ai.news_analyzer import NewsAnalyzer
    analyzer = NewsAnalyzer(model="gemini-3-flash-preview", temperature=0.2)

    # Real-style news headlines
    test_news = [
        {
            "title": "SEC Approves Spot Ethereum ETF Applications from Major Asset Managers",
            "content": "The SEC has given the green light to spot Ethereum ETF applications from BlackRock, Fidelity, and other major financial institutions, marking a historic moment for crypto adoption.",
        },
        {
            "title": "Bitcoin Mining Difficulty Reaches All-Time High After Halving",
            "content": "Bitcoin's mining difficulty has surged to a new record following the recent halving event, squeezing smaller miners while larger operations continue to scale.",
        },
        {
            "title": "New DeFi Protocol Launches on Solana with $5M TVL in First Week",
            "content": "A new decentralized lending protocol built on Solana has attracted $5 million in total value locked within its first week of launch.",
        },
    ]

    for i, news in enumerate(test_news, 1):
        print(f"\n  {BOLD}News #{i}:{RESET} {news['title']}")
        try:
            impact = await analyzer.analyze_news(
                title=news["title"],
                content=news["content"],
                symbol="BTC"
            )
            if impact:
                stars = "⭐" * impact.importance_stars
                dir_color = GREEN if impact.impact_direction.value == "bullish" else RED if impact.impact_direction.value == "bearish" else YELLOW
                success(f"Stars: {stars} ({impact.importance_stars}/5)")
                info(f"Impact Level:     {impact.impact_level.value.upper()}")
                info(f"Direction:        {dir_color}{impact.impact_direction.value.upper()}{RESET}")
                info(f"Score:            {impact.impact_score:+.2f}")
                info(f"Affected Symbols: {', '.join(impact.affected_symbols)}")
                info(f"Key Points:")
                for point in impact.key_points[:3]:
                    info(f"  • {point}")
        except Exception as e:
            error(f"Analysis failed: {e}")


async def demo_sentiment_analysis():
    """Part 3: Market Sentiment Analysis"""
    section("3. Market Sentiment Analysis from Social Text")

    from backend.ai.sentiment import SentimentAnalyzer
    analyzer = SentimentAnalyzer(model="gemini-3-flash-preview", temperature=0.2, use_llm=True)

    # Simulate social media texts
    social_texts = [
        "BTC looking incredibly strong at $88k, this is just the beginning of the bull run!",
        "Just loaded up more Bitcoin, the ETF inflows are insane",
        "Not sure about this rally, RSI is getting overbought on the daily",
        "Whale wallets accumulating like crazy, we're going to $100k",
        "The fed might cut rates, which could push crypto even higher",
        "Be careful, this looks like a distribution pattern to me",
        "Bitcoin dominance rising, altseason might be delayed",
    ]

    print(f"\n  {BOLD}Analyzing {len(social_texts)} social media posts...{RESET}")
    for i, text in enumerate(social_texts[:3], 1):
        info(f'Post {i}: "{text[:60]}..."')

    try:
        result = await analyzer.analyze("BTC", texts=social_texts)
        if result:
            sent_color = GREEN if result.sentiment == "bullish" else RED if result.sentiment == "bearish" else YELLOW
            success(f"Sentiment: {sent_color}{result.sentiment.upper()}{RESET}")
            info(f"Score:      {result.score:+.2f}  (range: -1.0 to +1.0)")
            info(f"Confidence: {result.confidence:.0%}")
            info(f"Reasoning:  {result.reasoning}")
            info(f"Keywords:   {', '.join(result.keywords)}")
    except Exception as e:
        error(f"Sentiment analysis failed: {e}")


async def main():
    header("Unit 3 Demo: LLM & Prompt Engineering")

    print(f"  This demo shows how we use LLMs for trading intelligence:\n")
    print(f"    1. {CYAN}Structured Output{RESET}  → LLM returns parseable JSON")
    print(f"    2. {CYAN}News Assessment{RESET}    → Rate news impact (1-5 stars)")
    print(f"    3. {CYAN}Sentiment Analysis{RESET} → Gauge market mood from social data")

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key == "sk-xxx":
        error("OPENAI_API_KEY not configured in .env")
        print(f"  Please set a valid API key to run this demo.\n")
        return

    await demo_raw_llm_call()
    await demo_news_impact()
    await demo_sentiment_analysis()

    header("Demo Complete!")
    print(f"  The LLM can analyze news, gauge sentiment, and produce")
    print(f"  structured trading signals. Unit 4 will combine these")
    print(f"  with real market data for actual trading decisions.\n")


if __name__ == "__main__":
    asyncio.run(main())
