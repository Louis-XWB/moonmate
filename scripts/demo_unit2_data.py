#!/usr/bin/env python3
"""
==============================================
  Unit 2 Demo: Data Engineering Pipeline
==============================================

Demonstrates:
  1. Real-time market data from OKX (ticker, OHLC, order book)
  2. On-chain whale tracking from Hyperliquid
  3. Social media scraping via Apify (Reddit)

Run:
  cd moon_mate
  python3 -m scripts.demo_unit2_data
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from scripts._helpers import (
    header, section, success, info, warn, error,
    GREEN, CYAN, YELLOW, RED, MAGENTA, BOLD, DIM, RESET,
    get_data_provider,
)


async def demo_market_data():
    """Part 1: Fetch real-time market data from OKX"""
    section("1. Real-Time Market Data")

    provider, source = await get_data_provider()

    try:
        # ── Ticker ──
        print(f"\n  {BOLD}Fetching BTC/USDT ticker...{RESET}")
        ticker = await provider.get_ticker("BTC/USDT")
        success(f"Last Price:  ${ticker.last_price:,.2f}")
        info(f"Bid/Ask:     ${ticker.bid_price:,.2f} / ${ticker.ask_price:,.2f}")
        info(f"Spread:      {ticker.spread:.4f}%")
        info(f"24h Volume:  {ticker.volume_24h:,.0f}")
        info(f"24h Change:  {ticker.change_24h:+.2f}%")
        info(f"24h Range:   ${ticker.low_24h:,.2f} - ${ticker.high_24h:,.2f}")

        # ── ETH too ──
        print(f"\n  {BOLD}Fetching ETH/USDT ticker...{RESET}")
        eth_ticker = await provider.get_ticker("ETH/USDT")
        success(f"Last Price:  ${eth_ticker.last_price:,.2f}")
        info(f"24h Change:  {eth_ticker.change_24h:+.2f}%")

        # ── OHLC K-lines ──
        print(f"\n  {BOLD}Fetching BTC 1h K-lines (last 10 bars)...{RESET}")
        klines = await provider.get_klines("BTC/USDT", interval="1h", limit=10)
        success(f"Retrieved {len(klines)} candlesticks")
        for k in klines[-3:]:
            candle = "🟢" if k.is_bullish else "🔴"
            info(f"{candle} {k.open_time.strftime('%H:%M')} "
                 f"O={k.open:,.0f} H={k.high:,.0f} L={k.low:,.0f} C={k.close:,.0f} "
                 f"Vol={k.volume:,.0f}")

        # ── Order Book ──
        print(f"\n  {BOLD}Fetching BTC order book (top 5 levels)...{RESET}")
        orderbook = await provider.get_orderbook("BTC/USDT", depth=5)
        success(f"Order book received")
        print(f"\n    {'Ask Price':>12}  {'Size':>12}")
        print(f"    {'─'*12}  {'─'*12}")
        for ask in reversed(orderbook.asks[:5]):
            print(f"    {RED}${ask.price:>10,.2f}  {ask.size:>10.4f}{RESET}")
        print(f"    {BOLD}{'─'*27}{RESET}")
        for bid in orderbook.bids[:5]:
            print(f"    {GREEN}${bid.price:>10,.2f}  {bid.size:>10.4f}{RESET}")

    finally:
        if hasattr(provider, 'close'):
            await provider.close()


async def demo_whale_tracking():
    """Part 2: On-chain whale tracking"""
    section("2. Hyperliquid Whale Tracking")

    from backend.data.whale_tracker import WhaleTracker
    tracker = WhaleTracker(whale_threshold=1_000_000)

    try:
        print(f"\n  {BOLD}Analyzing BTC whale behavior...{RESET}")
        analysis = await tracker.analyze_whale_behavior("BTC")

        if analysis:
            success(f"Found {analysis['whale_count']} whales")
            info(f"Total Long:    ${analysis['total_long_size']:,.0f}")
            info(f"Total Short:   ${analysis['total_short_size']:,.0f}")
            info(f"Net Flow:      ${analysis['net_flow']:+,.0f}")
            info(f"Sentiment:     {analysis['sentiment'].upper()}")
            info(f"Confidence:    {analysis['confidence']:.0%}")

            print(f"\n  {BOLD}Top 3 Whale Positions:{RESET}")
            for i, whale in enumerate(analysis['top_whales'][:3], 1):
                side_color = GREEN if whale['side'] == 'long' else RED
                print(f"    {i}. {side_color}{whale['side'].upper():>5}{RESET}"
                      f"  ${whale['size']:>12,.0f}"
                      f"  Entry=${whale['entry_price']:>10,.0f}"
                      f"  PnL={whale['pnl_percent']:+.2%}")

            print(f"\n  {BOLD}Recent Activity:{RESET}")
            for act in analysis['recent_activities'][:3]:
                print(f"    {act['action']:>12}: ${act['size']:,.0f} @ ${act['price']:,.0f}")

        # Alerts
        alerts = await tracker.get_whale_alerts("BTC")
        if alerts:
            print(f"\n  {BOLD}{RED}Whale Alerts:{RESET}")
            for alert in alerts:
                print(f"    {alert['message']}")
    finally:
        await tracker.close()


async def demo_social_scraping():
    """Part 3: Social media scraping via Apify"""
    section("3. Social Media Scraping (Apify → Reddit)")

    token = os.getenv("APIFY_API_TOKEN", "")
    if not token:
        error("APIFY_API_TOKEN not set in .env - skipping social media demo")
        return

    try:
        from backend.data.apify_scraper import ApifyScraper
    except ImportError:
        error("apify-client not installed. Run: pip install apify-client")
        return
    scraper = ApifyScraper(api_token=token)

    print(f"\n  {BOLD}Scraping r/Bitcoin and r/CryptoCurrency...{RESET}")
    info("This may take 30-60 seconds (Apify actor run)...")

    result = await scraper.scrape_reddit(
        subreddits=["Bitcoin", "CryptoCurrency"],
        max_items=5
    )

    if result.success and result.posts:
        success(f"Scraped {len(result.posts)} posts")
        for i, post in enumerate(result.posts[:5], 1):
            print(f"\n    {BOLD}#{i}{RESET} [{post.source}] {post.author_name or 'anonymous'}")
            # Truncate text to 120 chars
            text = post.text[:120].replace('\n', ' ')
            if len(post.text) > 120:
                text += "..."
            print(f"    {DIM}{text}{RESET}")
            print(f"    Score: {post.score}  |  Comments: {post.comments}")
    else:
        error(f"Scrape failed: {result.error or 'No posts returned'}")


async def main():
    header("Unit 2 Demo: Data Engineering Pipeline")

    print(f"  This demo shows the three pillars of data engineering")
    print(f"  for an AI trading agent:\n")
    print(f"    1. {CYAN}Market Data{RESET}   → Real-time prices from OKX")
    print(f"    2. {CYAN}On-chain Data{RESET} → Whale tracking on Hyperliquid")
    print(f"    3. {CYAN}Social Data{RESET}   → Reddit scraping via Apify")

    await demo_market_data()
    await demo_whale_tracking()
    await demo_social_scraping()

    header("Demo Complete!")
    print(f"  All data sources are working. These feed into the AI")
    print(f"  analysis pipeline you'll see in Unit 3.\n")


if __name__ == "__main__":
    asyncio.run(main())
