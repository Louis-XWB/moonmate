"""Shared helpers for demo scripts."""
import os
import sys

# Color helpers
GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

def header(title):
    print(f"\n{BOLD}{CYAN}{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}{RESET}\n")

def section(title):
    print(f"\n{BOLD}{YELLOW}── {title} ──{RESET}")

def success(msg):
    print(f"  {GREEN}✓{RESET} {msg}")

def info(msg):
    print(f"  {DIM}→{RESET} {msg}")

def warn(msg):
    print(f"  {YELLOW}⚠{RESET} {msg}")

def error(msg):
    print(f"  {RED}✗{RESET} {msg}")


async def get_data_provider():
    """Try OKX first, fallback to MockDataProvider if unreachable."""
    from backend.data.provider import OKXDataProvider, MockDataProvider

    provider = OKXDataProvider()
    try:
        await provider.get_ticker("BTC/USDT")
        success("Connected to OKX (real market data)")
        return provider, "OKX"
    except Exception:
        await provider.close()
        warn("OKX unreachable (VPN needed in China) → using MockDataProvider")
        return MockDataProvider(), "Mock"
