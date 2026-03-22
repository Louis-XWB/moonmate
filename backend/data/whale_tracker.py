"""
Whale Tracker Module

Second core hackathon innovation: tracking Hyperliquid on-chain whale behavior
Leveraging on-chain transparency for AI analysis of whale activities
"""

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class WhalePosition:
    """Whale position"""
    address: str
    symbol: str
    side: str  # long/short
    size: float  # PositionSize(USD)
    entry_price: float  # Average cost
    current_price: float  # Current Price
    pnl: float  # Unrealized P&L
    pnl_percent: float  # Unrealized P&L percentage
    leverage: float  # Leverage multiplier
    liquidation_price: Optional[float]  # Liquidation Price
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "symbol": self.symbol,
            "side": self.side,
            "size": self.size,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "leverage": self.leverage,
            "liquidation_price": self.liquidation_price,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class WhaleActivity:
    """Whale activity"""
    address: str
    action: str  # open_long/open_short/close/increase/decrease
    symbol: str
    size: float
    price: float
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "action": self.action,
            "symbol": self.symbol,
            "size": self.size,
            "price": self.price,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class WhaleAnalysis:
    """Whale behavior analysis"""
    symbol: str
    whale_count: int  # WhaleQuantity
    total_long_size: float  # Total long positions 
    total_short_size: float  # Total short positions 
    net_flow: float  # Net flow (positive=buy, negative=sell)
    total_volume: float  # Total trading volume
    top_whales: List[WhalePosition]  # Top 10 Whales
    recent_activities: List[WhaleActivity]  # Recent Activity
    sentiment: str  # bullish/bearish/neutral
    confidence: float  # Confidence
    summary: str  # AISummary
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "whale_count": self.whale_count,
            "total_long_size": self.total_long_size,
            "total_short_size": self.total_short_size,
            "net_flow": self.net_flow,
            "total_volume": self.total_volume,
            "top_whales": [w.to_dict() for w in self.top_whales],
            "recent_activities": [a.to_dict() for a in self.recent_activities],
            "sentiment": self.sentiment,
            "confidence": self.confidence,
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat()
        }


class WhaleTracker:
    """On-chain whale tracker"""
    
    def __init__(
        self,
        whale_threshold: float = 1000000,  # Whale threshold: $1M USD
        api_base_url: str = "https://api.hyperliquid.xyz"
    ):
        self.whale_threshold = whale_threshold
        self.api_base_url = api_base_url
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Cache
        self.whale_positions_cache: Dict[str, List[WhalePosition]] = {}
        self.cache_ttl = 60  # Cache for 60 seconds
        self.last_update: Dict[str, datetime] = {}
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get HTTP session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Close session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def fetch_all_positions(self, symbol: str) -> List[WhalePosition]:
        """
        Fetch all positions(Mock data)
        
        Note: Production implementation should call the Hyperliquid API
        Using mock data for demonstration
        """
        try:
            # Check cache
            if symbol in self.whale_positions_cache:
                last_update = self.last_update.get(symbol)
                if last_update and (datetime.now() - last_update).seconds < self.cache_ttl:
                    return self.whale_positions_cache[symbol]
            
            # Production implementation should call the Hyperliquid API
            # session = await self._get_session()
            # async with session.post(f"{self.api_base_url}/info", json={
            #     "type": "allMids"
            # }) as resp:
            #     data = await resp.json()
            
            # Mock data
            positions = self._generate_mock_positions(symbol)
            
            # Update cache
            self.whale_positions_cache[symbol] = positions
            self.last_update[symbol] = datetime.now()
            
            return positions
            
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    def _generate_mock_positions(self, symbol: str) -> List[WhalePosition]:
        """Generate mock position data"""
        import random
        
        positions = []
        current_price = 89000 if "BTC" in symbol else 3200  # Mock current price
        
        # Generate 5-10 whales
        for i in range(random.randint(5, 10)):
            side = random.choice(["long", "short"])
            size = random.uniform(1000000, 5000000)  # $1M-$5M
            entry_price = current_price * random.uniform(0.95, 1.05)
            
            if side == "long":
                pnl = (current_price - entry_price) * (size / entry_price)
            else:
                pnl = (entry_price - current_price) * (size / entry_price)
            
            pnl_percent = pnl / size
            leverage = random.uniform(2, 10)
            
            # Calculate liquidation price
            if side == "long":
                liquidation_price = entry_price * (1 - 1/leverage * 0.9)
            else:
                liquidation_price = entry_price * (1 + 1/leverage * 0.9)
            
            positions.append(WhalePosition(
                address=f"0x{''.join(random.choices('0123456789abcdef', k=40))}",
                symbol=symbol,
                side=side,
                size=size,
                entry_price=entry_price,
                current_price=current_price,
                pnl=pnl,
                pnl_percent=pnl_percent,
                leverage=leverage,
                liquidation_price=liquidation_price
            ))
        
        return positions
    
    async def identify_whales(self, positions: List[WhalePosition]) -> List[WhalePosition]:
        """Identify whales (position > threshold)"""
        return [p for p in positions if p.size >= self.whale_threshold]
    
    async def analyze_whale_behavior(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Analyze whale behavior"""
        try:
            # Fetch all positions
            all_positions = await self.fetch_all_positions(symbol)
            
            # Identify whales
            whales = await self.identify_whales(all_positions)
            
            if not whales:
                logger.info(f"No whales found for {symbol}")
                return None
            
            # Statistics
            total_long_size = sum(w.size for w in whales if w.side == "long")
            total_short_size = sum(w.size for w in whales if w.side == "short")
            net_flow = total_long_size - total_short_size
            total_volume = total_long_size + total_short_size
            
            # Sentiment assessment
            if net_flow > total_volume * 0.3:
                sentiment = "bullish"
                confidence = 0.8
            elif net_flow < -total_volume * 0.3:
                sentiment = "bearish"
                confidence = 0.8
            else:
                sentiment = "neutral"
                confidence = 0.6
            
            # Generate summary
            summary = self._generate_summary(
                len(whales),
                total_long_size,
                total_short_size,
                net_flow,
                sentiment
            )
            
            # Sort by position size, take top 10
            top_whales = sorted(whales, key=lambda w: w.size, reverse=True)[:10]
            
            # Simulate recent activities
            recent_activities = self._generate_mock_activities(symbol, whales)
            
            analysis = WhaleAnalysis(
                symbol=symbol,
                whale_count=len(whales),
                total_long_size=total_long_size,
                total_short_size=total_short_size,
                net_flow=net_flow,
                total_volume=total_volume,
                top_whales=top_whales,
                recent_activities=recent_activities,
                sentiment=sentiment,
                confidence=confidence,
                summary=summary
            )
            
            return analysis.to_dict()
            
        except Exception as e:
            logger.error(f"Error analyzing whale behavior: {e}")
            return None
    
    def _generate_summary(
        self,
        whale_count: int,
        total_long: float,
        total_short: float,
        net_flow: float,
        sentiment: str
    ) -> str:
        """Generate AI summary"""
        summary = f"Detected {whale_count} whales, "
        
        if sentiment == "bullish":
            summary += f"Bulls dominate, net inflow ${net_flow/1e6:.1f}M. "
            summary += f"Long positions ${total_long/1e6:.1f}M, Short positions ${total_short/1e6:.1f}M. "
            summary += "Whales are actively accumulating, market sentiment is bullish."
        elif sentiment == "bearish":
            summary += f"Bears dominate, net outflow ${-net_flow/1e6:.1f}M. "
            summary += f"Short positions ${total_short/1e6:.1f}M, Long positions ${total_long/1e6:.1f}M. "
            summary += "Whales are actively reducing positions, market sentiment is bearish."
        else:
            summary += f"Bulls and bears balanced, net flow ${net_flow/1e6:.1f}M. "
            summary += f"Long positions ${total_long/1e6:.1f}M, Short positions ${total_short/1e6:.1f}M. "
            summary += "Whale activity is neutral, market is in wait-and-see mode."
        
        return summary
    
    def _generate_mock_activities(
        self,
        symbol: str,
        whales: List[WhalePosition]
    ) -> List[WhaleActivity]:
        """Generate mock activity data"""
        import random
        
        activities = []
        now = datetime.now()
        
        for i in range(min(5, len(whales))):
            whale = random.choice(whales)
            action = random.choice([
                "open_long", "open_short",
                "increase", "decrease", "close"
            ])
            
            activities.append(WhaleActivity(
                address=whale.address,
                action=action,
                symbol=symbol,
                size=random.uniform(100000, 1000000),
                price=whale.current_price * random.uniform(0.99, 1.01),
                timestamp=now - timedelta(minutes=random.randint(1, 60))
            ))
        
        # Sort by time descending
        activities.sort(key=lambda a: a.timestamp, reverse=True)
        
        return activities
    
    async def get_whale_alerts(self, symbol: str) -> List[Dict[str, Any]]:
        """Get whale alerts"""
        try:
            analysis = await self.analyze_whale_behavior(symbol)
            
            if not analysis:
                return []
            
            alerts = []
            
            # Check if whales are about to be liquidated
            for whale in analysis["top_whales"]:
                if whale["liquidation_price"]:
                    price_diff = abs(whale["current_price"] - whale["liquidation_price"])
                    price_diff_percent = price_diff / whale["current_price"]
                    
                    if price_diff_percent < 0.05:  # Within 5% of liquidation price
                        alerts.append({
                            "type": "liquidation_warning",
                            "severity": "high",
                            "message": f"🚨 Whale{whale['address'][:10]}... is about to be liquidated!",
                            "details": {
                                "address": whale["address"],
                                "side": whale["side"],
                                "size": whale["size"],
                                "current_price": whale["current_price"],
                                "liquidation_price": whale["liquidation_price"]
                            }
                        })
            
            # Check if whales are accumulating/reducing
            if abs(analysis["net_flow"]) > 2000000:  # Net flow > $2M
                if analysis["net_flow"] > 0:
                    alerts.append({
                        "type": "whale_accumulation",
                        "severity": "medium",
                        "message": f"🐋 {analysis['whale_count']} whales are buying heavily!",
                        "details": {
                            "net_flow": analysis["net_flow"],
                            "total_volume": analysis["total_volume"]
                        }
                    })
                else:
                    alerts.append({
                        "type": "whale_distribution",
                        "severity": "medium",
                        "message": f"🐋 {analysis['whale_count']} whales are selling heavily!",
                        "details": {
                            "net_flow": analysis["net_flow"],
                            "total_volume": analysis["total_volume"]
                        }
                    })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error getting whale alerts: {e}")
            return []


# Global instance
_whale_tracker_instance: Optional[WhaleTracker] = None


def get_whale_tracker() -> WhaleTracker:
    """Get global WhaleTracker instance"""
    global _whale_tracker_instance
    if _whale_tracker_instance is None:
        _whale_tracker_instance = WhaleTracker()
    return _whale_tracker_instance
