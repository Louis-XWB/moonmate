"""
Data providermodule
Supports multiple data source integration with a unified data access interface
"""

import asyncio
import aiohttp
import random
import math
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Callable
from .models import Ticker, OrderBook, OrderBookLevel, Trade, Kline


class DataProvider(ABC):
    """Data provider base class"""
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        """GetMarket ticker snapshot"""
        pass
    
    @abstractmethod
    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """GetOrderbook"""
        pass
    
    @abstractmethod
    async def get_trades(self, symbol: str, limit: int = 100) -> List[Trade]:
        """Get recent trades"""
        pass
    
    @abstractmethod
    async def get_klines(
        self, 
        symbol: str, 
        interval: str = "1h",
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Kline]:
        """GetCandlestick data"""
        pass
    
    @abstractmethod
    async def subscribe_ticker(self, symbol: str, callback: Callable):
        """Subscribe to market data updates"""
        pass
    
    @abstractmethod
    async def unsubscribe_ticker(self, symbol: str):
        """Unsubscribe from event"""
        pass


class OKXDataProvider(DataProvider):
    """OKX Real Data Provider"""
    
    BASE_URL = "https://www.okx.com/api/v5"
    
    # Symbol mapping: internal format -> OKX format
    SYMBOL_MAP = {
        "BTC/USDT": "BTC-USDT",
        "ETH/USDT": "ETH-USDT",
        "SOL/USDT": "SOL-USDT",
        "BNB/USDT": "BNB-USDT",
    }
    
    # Time period mapping
    INTERVAL_MAP = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1H",
        "4h": "4H",
        "1d": "1D",
    }
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._running: bool = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._ticker_cache: Dict[str, Ticker] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl = 1  # Cache for 1 second
    
    def _get_okx_symbol(self, symbol: str) -> str:
        """Convert to OKX symbol format"""
        return self.SYMBOL_MAP.get(symbol, symbol.replace("/", "-"))
    
    def _get_okx_interval(self, interval: str) -> str:
        """Convert to OKX time period format"""
        return self.INTERVAL_MAP.get(interval, "1H")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def _request(self, endpoint: str, params: dict = None) -> dict:
        """Send API request"""
        session = await self._get_session()
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            async with session.get(url, params=params, timeout=10) as response:
                data = await response.json()
                if data.get("code") != "0":
                    raise Exception(f"OKX API Error: {data.get('msg', 'Unknown error')}")
                return data
        except asyncio.TimeoutError:
            raise Exception("OKX API request timeout")
        except Exception as e:
            raise Exception(f"OKX API request failed: {str(e)}")
    
    async def get_ticker(self, symbol: str) -> Ticker:
        """GetMarket ticker snapshot"""
        # Check cache
        now = datetime.now()
        if symbol in self._ticker_cache:
            cache_age = (now - self._cache_time.get(symbol, now)).total_seconds()
            if cache_age < self._cache_ttl:
                return self._ticker_cache[symbol]
        
        okx_symbol = self._get_okx_symbol(symbol)
        data = await self._request("/market/ticker", {"instId": okx_symbol})
        
        if not data.get("data"):
            raise Exception(f"No ticker data for {symbol}")
        
        ticker_data = data["data"][0]
        
        ticker = Ticker(
            symbol=symbol,
            last_price=float(ticker_data["last"]),
            bid_price=float(ticker_data["bidPx"]),
            ask_price=float(ticker_data["askPx"]),
            bid_size=float(ticker_data["bidSz"]),
            ask_size=float(ticker_data["askSz"]),
            volume_24h=float(ticker_data["vol24h"]),
            change_24h=((float(ticker_data["last"]) - float(ticker_data["open24h"])) / float(ticker_data["open24h"]) * 100) if float(ticker_data["open24h"]) > 0 else 0,
            high_24h=float(ticker_data["high24h"]),
            low_24h=float(ticker_data["low24h"]),
            timestamp=datetime.fromtimestamp(int(ticker_data["ts"]) / 1000)
        )
        
        # Update cache
        self._ticker_cache[symbol] = ticker
        self._cache_time[symbol] = now
        
        return ticker
    
    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """GetOrderbook"""
        okx_symbol = self._get_okx_symbol(symbol)
        data = await self._request("/market/books", {"instId": okx_symbol, "sz": str(depth)})
        
        if not data.get("data"):
            raise Exception(f"No orderbook data for {symbol}")
        
        book_data = data["data"][0]
        
        bids = [
            OrderBookLevel(price=float(level[0]), size=float(level[1]))
            for level in book_data.get("bids", [])
        ]
        
        asks = [
            OrderBookLevel(price=float(level[0]), size=float(level[1]))
            for level in book_data.get("asks", [])
        ]
        
        return OrderBook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=datetime.fromtimestamp(int(book_data["ts"]) / 1000)
        )
    
    async def get_trades(self, symbol: str, limit: int = 100) -> List[Trade]:
        """Get recent trades"""
        okx_symbol = self._get_okx_symbol(symbol)
        data = await self._request("/market/trades", {"instId": okx_symbol, "limit": str(min(limit, 500))})
        
        if not data.get("data"):
            return []
        
        trades = []
        for trade_data in data["data"]:
            trade = Trade(
                symbol=symbol,
                price=float(trade_data["px"]),
                size=float(trade_data["sz"]),
                side=trade_data["side"],
                timestamp=datetime.fromtimestamp(int(trade_data["ts"]) / 1000),
                trade_id=trade_data["tradeId"]
            )
            trades.append(trade)
        
        return trades
    
    async def get_klines(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Kline]:
        """GetCandlestick data"""
        okx_symbol = self._get_okx_symbol(symbol)
        okx_interval = self._get_okx_interval(interval)
        
        params = {
            "instId": okx_symbol,
            "bar": okx_interval,
            "limit": str(min(limit, 300))
        }
        
        if end_time:
            params["after"] = str(int(end_time.timestamp() * 1000))
        if start_time:
            params["before"] = str(int(start_time.timestamp() * 1000))
        
        data = await self._request("/market/candles", params)
        
        if not data.get("data"):
            return []
        
        klines = []
        for kline_data in data["data"]:
            # OKX candlestick format: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
            kline = Kline(
                symbol=symbol,
                interval=interval,
                open_time=datetime.fromtimestamp(int(kline_data[0]) / 1000),
                open=float(kline_data[1]),
                high=float(kline_data[2]),
                low=float(kline_data[3]),
                close=float(kline_data[4]),
                volume=float(kline_data[5]),
                close_time=datetime.fromtimestamp(int(kline_data[0]) / 1000),
                quote_volume=float(kline_data[7]) if len(kline_data) > 7 else 0,
                trades_count=0
            )
            klines.append(kline)
        
        # OKX returns in reverse order, needs reversal
        return list(reversed(klines))
    
    async def subscribe_ticker(self, symbol: str, callback: Callable):
        """Subscribe to market data updates"""
        if symbol not in self._subscribers:
            self._subscribers[symbol] = []
        self._subscribers[symbol].append(callback)
        
        if not self._running:
            self._running = True
            asyncio.create_task(self._ticker_loop())
    
    async def unsubscribe_ticker(self, symbol: str):
        """Unsubscribe from event"""
        if symbol in self._subscribers:
            del self._subscribers[symbol]
    
    async def _ticker_loop(self):
        """Market data push loop"""
        while self._running and self._subscribers:
            for symbol, callbacks in list(self._subscribers.items()):
                try:
                    ticker = await self.get_ticker(symbol)
                    for callback in callbacks:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(ticker)
                        else:
                            callback(ticker)
                except Exception as e:
                    print(f"Ticker loop error for {symbol}: {e}")
            
            await asyncio.sleep(2)  # Update every 2 seconds to avoid excessive frequency
    
    def stop(self):
        """Stop data push"""
        self._running = False
    
    async def close(self):
        """Close session"""
        if self._session and not self._session.closed:
            await self._session.close()


class CoinGeckoDataProvider(DataProvider):
    """CoinGecko Data Provider (fallback)"""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    # Symbol mapping: internal format -> CoinGecko ID
    SYMBOL_MAP = {
        "BTC/USDT": "bitcoin",
        "ETH/USDT": "ethereum",
        "SOL/USDT": "solana",
        "BNB/USDT": "binancecoin",
    }
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._running: bool = False
        self._session: Optional[aiohttp.ClientSession] = None
        self._ticker_cache: Dict[str, Ticker] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl = 10  # CoinGecko has strict rate limits, cache for 10 seconds
    
    def _get_coin_id(self, symbol: str) -> str:
        """Convert to CoinGecko ID"""
        return self.SYMBOL_MAP.get(symbol, symbol.split("/")[0].lower())
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get HTTP session"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def _request(self, endpoint: str, params: dict = None) -> dict:
        """Send API request"""
        session = await self._get_session()
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 429:
                    raise Exception("CoinGecko rate limit exceeded")
                return await response.json()
        except asyncio.TimeoutError:
            raise Exception("CoinGecko API request timeout")
        except Exception as e:
            raise Exception(f"CoinGecko API request failed: {str(e)}")
    
    async def get_ticker(self, symbol: str) -> Ticker:
        """GetMarket ticker snapshot"""
        # Check cache
        now = datetime.now()
        if symbol in self._ticker_cache:
            cache_age = (now - self._cache_time.get(symbol, now)).total_seconds()
            if cache_age < self._cache_ttl:
                return self._ticker_cache[symbol]
        
        coin_id = self._get_coin_id(symbol)
        data = await self._request("/simple/price", {
            "ids": coin_id,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_24hr_vol": "true",
            "include_high_24h": "true",
            "include_low_24h": "true"
        })
        
        if coin_id not in data:
            raise Exception(f"No ticker data for {symbol}")
        
        coin_data = data[coin_id]
        price = coin_data.get("usd", 0)
        
        ticker = Ticker(
            symbol=symbol,
            last_price=price,
            bid_price=price * 0.9999,  # CoinGecko doesn't provide bid/ask, simulated
            ask_price=price * 1.0001,
            bid_size=0,
            ask_size=0,
            volume_24h=coin_data.get("usd_24h_vol", 0),
            change_24h=coin_data.get("usd_24h_change", 0),
            high_24h=coin_data.get("usd_24h_high", price),
            low_24h=coin_data.get("usd_24h_low", price),
            timestamp=now
        )
        
        # Update cache
        self._ticker_cache[symbol] = ticker
        self._cache_time[symbol] = now
        
        return ticker
    
    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """CoinGecko doesn't provide orderbook, return mock data"""
        ticker = await self.get_ticker(symbol)
        price = ticker.last_price
        spread = price * 0.0002
        
        bids = []
        asks = []
        
        for i in range(depth):
            bid_price = price - spread / 2 - i * spread
            ask_price = price + spread / 2 + i * spread
            bids.append(OrderBookLevel(price=bid_price, size=random.uniform(0.1, 5)))
            asks.append(OrderBookLevel(price=ask_price, size=random.uniform(0.1, 5)))
        
        return OrderBook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=datetime.now()
        )
    
    async def get_trades(self, symbol: str, limit: int = 100) -> List[Trade]:
        """CoinGecko doesn't provide trade records, return empty list"""
        return []
    
    async def get_klines(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Kline]:
        """GetCandlestick data"""
        coin_id = self._get_coin_id(symbol)
        
        # Calculate days based on limit
        days = min(max(limit // 24, 2), 90)  # 2-90 days
        
        data = await self._request(f"/coins/{coin_id}/market_chart", {
            "vs_currency": "usd",
            "days": str(days)
        })
        
        if "prices" not in data:
            return []
        
        prices = data["prices"]
        klines = []
        
        for i in range(1, min(len(prices), limit)):
            prev_price = prices[i-1][1]
            curr_price = prices[i][1]
            timestamp = datetime.fromtimestamp(prices[i][0] / 1000)
            
            kline = Kline(
                symbol=symbol,
                interval=interval,
                open_time=timestamp - timedelta(hours=1),
                open=prev_price,
                high=max(prev_price, curr_price) * 1.001,
                low=min(prev_price, curr_price) * 0.999,
                close=curr_price,
                volume=0,
                close_time=timestamp,
                quote_volume=0,
                trades_count=0
            )
            klines.append(kline)
        
        return klines[-limit:]
    
    async def subscribe_ticker(self, symbol: str, callback: Callable):
        """Subscribe to market data updates"""
        if symbol not in self._subscribers:
            self._subscribers[symbol] = []
        self._subscribers[symbol].append(callback)
        
        if not self._running:
            self._running = True
            asyncio.create_task(self._ticker_loop())
    
    async def unsubscribe_ticker(self, symbol: str):
        """Unsubscribe from event"""
        if symbol in self._subscribers:
            del self._subscribers[symbol]
    
    async def _ticker_loop(self):
        """Market data push loop"""
        while self._running and self._subscribers:
            for symbol, callbacks in list(self._subscribers.items()):
                try:
                    ticker = await self.get_ticker(symbol)
                    for callback in callbacks:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(ticker)
                        else:
                            callback(ticker)
                except Exception as e:
                    print(f"Ticker loop error for {symbol}: {e}")
            
            await asyncio.sleep(15)  # CoinGecko has strict rate limits, update every 15 seconds
    
    def stop(self):
        """Stop data push"""
        self._running = False
    
    async def close(self):
        """Close session"""
        if self._session and not self._session.closed:
            await self._session.close()


class MockDataProvider(DataProvider):
    """Mock data provider (for testing and demo, fallback when real API is unavailable)"""
    
    def __init__(self):
        self._base_prices: Dict[str, float] = {
            "BTC/USDT": 88000.0,  # Updated to near-real prices
            "ETH/USDT": 2900.0,
            "SOL/USDT": 125.0,
            "BNB/USDT": 600.0,
        }
        self._price_history: Dict[str, List[float]] = {}
        self._subscribers: Dict[str, List[Callable]] = {}
        self._running: bool = False
        self._volatility: float = 0.001  # 0.1% Volatility
        
        # Initialize price history
        for symbol in self._base_prices:
            self._init_price_history(symbol)
    
    def _init_price_history(self, symbol: str, length: int = 500):
        """Initialize price history"""
        base_price = self._base_prices.get(symbol, 100.0)
        prices = [base_price]
        
        for i in range(length - 1):
            trend = math.sin(i / 50) * 0.0005
            noise = random.gauss(0, self._volatility)
            change = trend + noise
            new_price = prices[-1] * (1 + change)
            prices.append(new_price)
        
        self._price_history[symbol] = prices
    
    def _get_current_price(self, symbol: str) -> float:
        """Get current price (with random volatility)"""
        if symbol not in self._price_history:
            self._init_price_history(symbol)
        
        history = self._price_history[symbol]
        last_price = history[-1]
        
        change = random.gauss(0, self._volatility)
        new_price = last_price * (1 + change)
        
        history.append(new_price)
        if len(history) > 1000:
            history.pop(0)
        
        return new_price
    
    async def get_ticker(self, symbol: str) -> Ticker:
        """GetMarket ticker snapshot"""
        price = self._get_current_price(symbol)
        spread = price * 0.0001
        
        history = self._price_history.get(symbol, [price])
        price_24h_ago = history[0] if len(history) > 288 else history[0]
        change_24h = (price - price_24h_ago) / price_24h_ago * 100
        
        return Ticker(
            symbol=symbol,
            last_price=price,
            bid_price=price - spread / 2,
            ask_price=price + spread / 2,
            bid_size=random.uniform(0.1, 10),
            ask_size=random.uniform(0.1, 10),
            volume_24h=random.uniform(1000, 10000),
            change_24h=change_24h,
            high_24h=max(history[-288:]) if len(history) >= 288 else max(history),
            low_24h=min(history[-288:]) if len(history) >= 288 else min(history),
            timestamp=datetime.now()
        )
    
    async def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """GetOrderbook"""
        price = self._get_current_price(symbol)
        spread = price * 0.0001
        
        bids = []
        asks = []
        
        for i in range(depth):
            bid_price = price - spread / 2 - i * spread
            ask_price = price + spread / 2 + i * spread
            bid_size = random.uniform(0.1, 5) * (1 - i / depth)
            ask_size = random.uniform(0.1, 5) * (1 - i / depth)
            bids.append(OrderBookLevel(price=bid_price, size=bid_size))
            asks.append(OrderBookLevel(price=ask_price, size=ask_size))
        
        return OrderBook(
            symbol=symbol,
            bids=bids,
            asks=asks,
            timestamp=datetime.now()
        )
    
    async def get_trades(self, symbol: str, limit: int = 100) -> List[Trade]:
        """Get recent trades"""
        price = self._get_current_price(symbol)
        trades = []
        
        for i in range(limit):
            trade_price = price * (1 + random.gauss(0, 0.0005))
            trade = Trade(
                symbol=symbol,
                price=trade_price,
                size=random.uniform(0.001, 1),
                side=random.choice(["buy", "sell"]),
                timestamp=datetime.now() - timedelta(seconds=i * 5),
                trade_id=f"trade_{i}"
            )
            trades.append(trade)
        
        return trades
    
    async def get_klines(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Kline]:
        """GetCandlestick data"""
        interval_minutes = {
            "1m": 1, "5m": 5, "15m": 15, "30m": 30,
            "1h": 60, "4h": 240, "1d": 1440
        }.get(interval, 60)
        
        if symbol not in self._price_history:
            self._init_price_history(symbol)
        
        history = self._price_history[symbol]
        base_price = history[-1] if history else self._base_prices.get(symbol, 100)
        
        klines = []
        end = end_time or datetime.now()
        
        for i in range(limit):
            close_time = end - timedelta(minutes=i * interval_minutes)
            open_time = close_time - timedelta(minutes=interval_minutes)
            
            volatility = self._volatility * math.sqrt(interval_minutes)
            open_price = base_price * (1 + random.gauss(0, volatility))
            close_price = base_price * (1 + random.gauss(0, volatility))
            high_price = max(open_price, close_price) * (1 + abs(random.gauss(0, volatility / 2)))
            low_price = min(open_price, close_price) * (1 - abs(random.gauss(0, volatility / 2)))
            
            kline = Kline(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=random.uniform(100, 1000),
                close_time=close_time,
                quote_volume=random.uniform(10000, 100000),
                trades_count=random.randint(100, 1000)
            )
            klines.append(kline)
            base_price = open_price
        
        return list(reversed(klines))
    
    async def subscribe_ticker(self, symbol: str, callback: Callable):
        """Subscribe to market data updates"""
        if symbol not in self._subscribers:
            self._subscribers[symbol] = []
        self._subscribers[symbol].append(callback)
        
        if not self._running:
            self._running = True
            asyncio.create_task(self._ticker_loop())
    
    async def unsubscribe_ticker(self, symbol: str):
        """Unsubscribe from event"""
        if symbol in self._subscribers:
            del self._subscribers[symbol]
    
    async def _ticker_loop(self):
        """Market data push loop"""
        while self._running and self._subscribers:
            for symbol, callbacks in list(self._subscribers.items()):
                try:
                    ticker = await self.get_ticker(symbol)
                    for callback in callbacks:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(ticker)
                        else:
                            callback(ticker)
                except Exception as e:
                    print(f"Ticker loop error: {e}")
            
            await asyncio.sleep(1)
    
    def stop(self):
        """Stop data push"""
        self._running = False
