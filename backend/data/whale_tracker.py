"""
链上大户追踪模块 (Whale Tracker)

这是黑客松的第二个核心创新功能：追踪Hyperliquid链上大户行为
利用链上透明性，AI分析"鲸鱼"在做什么
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
    """大户持仓"""
    address: str
    symbol: str
    side: str  # long/short
    size: float  # 持仓大小（USD）
    entry_price: float  # 平均成本
    current_price: float  # 当前价格
    pnl: float  # 浮动盈亏
    pnl_percent: float  # 浮动盈亏百分比
    leverage: float  # 杠杆倍数
    liquidation_price: Optional[float]  # 清算价
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
    """大户活动"""
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
    """大户行为分析"""
    symbol: str
    whale_count: int  # 大户数量
    total_long_size: float  # 总做多仓位
    total_short_size: float  # 总做空仓位
    net_flow: float  # 净流入（正数=买入，负数=卖出）
    total_volume: float  # 总交易量
    top_whales: List[WhalePosition]  # 前10大户
    recent_activities: List[WhaleActivity]  # 最近活动
    sentiment: str  # bullish/bearish/neutral
    confidence: float  # 置信度
    summary: str  # AI总结
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
    """链上大户追踪器"""
    
    def __init__(
        self,
        whale_threshold: float = 1000000,  # 大户阈值：100万美元
        api_base_url: str = "https://api.hyperliquid.xyz"
    ):
        self.whale_threshold = whale_threshold
        self.api_base_url = api_base_url
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 缓存
        self.whale_positions_cache: Dict[str, List[WhalePosition]] = {}
        self.cache_ttl = 60  # 缓存60秒
        self.last_update: Dict[str, datetime] = {}
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """关闭会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def fetch_all_positions(self, symbol: str) -> List[WhalePosition]:
        """
        获取所有持仓（模拟数据）
        
        注意：实际实现需要调用Hyperliquid API
        这里使用模拟数据进行演示
        """
        try:
            # 检查缓存
            if symbol in self.whale_positions_cache:
                last_update = self.last_update.get(symbol)
                if last_update and (datetime.now() - last_update).seconds < self.cache_ttl:
                    return self.whale_positions_cache[symbol]
            
            # 实际实现应该调用Hyperliquid API
            # session = await self._get_session()
            # async with session.post(f"{self.api_base_url}/info", json={
            #     "type": "allMids"
            # }) as resp:
            #     data = await resp.json()
            
            # 模拟数据
            positions = self._generate_mock_positions(symbol)
            
            # 更新缓存
            self.whale_positions_cache[symbol] = positions
            self.last_update[symbol] = datetime.now()
            
            return positions
            
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    def _generate_mock_positions(self, symbol: str) -> List[WhalePosition]:
        """生成模拟持仓数据"""
        import random
        
        positions = []
        current_price = 89000 if "BTC" in symbol else 3200  # 模拟当前价格
        
        # 生成5-10个大户
        for i in range(random.randint(5, 10)):
            side = random.choice(["long", "short"])
            size = random.uniform(1000000, 5000000)  # 100万-500万
            entry_price = current_price * random.uniform(0.95, 1.05)
            
            if side == "long":
                pnl = (current_price - entry_price) * (size / entry_price)
            else:
                pnl = (entry_price - current_price) * (size / entry_price)
            
            pnl_percent = pnl / size
            leverage = random.uniform(2, 10)
            
            # 计算清算价
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
        """识别大户（持仓>阈值）"""
        return [p for p in positions if p.size >= self.whale_threshold]
    
    async def analyze_whale_behavior(self, symbol: str) -> Optional[Dict[str, Any]]:
        """分析大户行为"""
        try:
            # 获取所有持仓
            all_positions = await self.fetch_all_positions(symbol)
            
            # 识别大户
            whales = await self.identify_whales(all_positions)
            
            if not whales:
                logger.info(f"No whales found for {symbol}")
                return None
            
            # 统计
            total_long_size = sum(w.size for w in whales if w.side == "long")
            total_short_size = sum(w.size for w in whales if w.side == "short")
            net_flow = total_long_size - total_short_size
            total_volume = total_long_size + total_short_size
            
            # 情绪判断
            if net_flow > total_volume * 0.3:
                sentiment = "bullish"
                confidence = 0.8
            elif net_flow < -total_volume * 0.3:
                sentiment = "bearish"
                confidence = 0.8
            else:
                sentiment = "neutral"
                confidence = 0.6
            
            # 生成总结
            summary = self._generate_summary(
                len(whales),
                total_long_size,
                total_short_size,
                net_flow,
                sentiment
            )
            
            # 按持仓大小排序，取前10
            top_whales = sorted(whales, key=lambda w: w.size, reverse=True)[:10]
            
            # 模拟最近活动
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
        """生成AI总结"""
        summary = f"检测到{whale_count}个大户，"
        
        if sentiment == "bullish":
            summary += f"多方占优，净流入${net_flow/1e6:.1f}M。"
            summary += f"做多仓位${total_long/1e6:.1f}M，做空仓位${total_short/1e6:.1f}M。"
            summary += "大户正在积极建仓，市场情绪偏多。"
        elif sentiment == "bearish":
            summary += f"空方占优，净流出${-net_flow/1e6:.1f}M。"
            summary += f"做空仓位${total_short/1e6:.1f}M，做多仓位${total_long/1e6:.1f}M。"
            summary += "大户正在积极减仓，市场情绪偏空。"
        else:
            summary += f"多空平衡，净流动${net_flow/1e6:.1f}M。"
            summary += f"做多仓位${total_long/1e6:.1f}M，做空仓位${total_short/1e6:.1f}M。"
            summary += "大户行为中性，市场观望情绪浓厚。"
        
        return summary
    
    def _generate_mock_activities(
        self,
        symbol: str,
        whales: List[WhalePosition]
    ) -> List[WhaleActivity]:
        """生成模拟活动数据"""
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
        
        # 按时间倒序
        activities.sort(key=lambda a: a.timestamp, reverse=True)
        
        return activities
    
    async def get_whale_alerts(self, symbol: str) -> List[Dict[str, Any]]:
        """获取大户警报"""
        try:
            analysis = await self.analyze_whale_behavior(symbol)
            
            if not analysis:
                return []
            
            alerts = []
            
            # 检查大户是否即将被清算
            for whale in analysis["top_whales"]:
                if whale["liquidation_price"]:
                    price_diff = abs(whale["current_price"] - whale["liquidation_price"])
                    price_diff_percent = price_diff / whale["current_price"]
                    
                    if price_diff_percent < 0.05:  # 距离清算价<5%
                        alerts.append({
                            "type": "liquidation_warning",
                            "severity": "high",
                            "message": f"🚨 大户{whale['address'][:10]}...即将被清算！",
                            "details": {
                                "address": whale["address"],
                                "side": whale["side"],
                                "size": whale["size"],
                                "current_price": whale["current_price"],
                                "liquidation_price": whale["liquidation_price"]
                            }
                        })
            
            # 检查大户是否在大量建仓/减仓
            if abs(analysis["net_flow"]) > 2000000:  # 净流动>200万
                if analysis["net_flow"] > 0:
                    alerts.append({
                        "type": "whale_accumulation",
                        "severity": "medium",
                        "message": f"🐋 {analysis['whale_count']}个大户正在大量买入！",
                        "details": {
                            "net_flow": analysis["net_flow"],
                            "total_volume": analysis["total_volume"]
                        }
                    })
                else:
                    alerts.append({
                        "type": "whale_distribution",
                        "severity": "medium",
                        "message": f"🐋 {analysis['whale_count']}个大户正在大量卖出！",
                        "details": {
                            "net_flow": analysis["net_flow"],
                            "total_volume": analysis["total_volume"]
                        }
                    })
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error getting whale alerts: {e}")
            return []


# 全局实例
_whale_tracker_instance: Optional[WhaleTracker] = None


def get_whale_tracker() -> WhaleTracker:
    """获取全局WhaleTracker实例"""
    global _whale_tracker_instance
    if _whale_tracker_instance is None:
        _whale_tracker_instance = WhaleTracker()
    return _whale_tracker_instance
