"""
盘口失衡策略模块
基于订单簿数据分析买卖压力，预测短期价格走向
"""

import numpy as np
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from collections import deque

from backend.data.models import OrderBook, OrderBookLevel, Signal, SignalDirection, Trade
from backend.core.logger import get_logger
from .base import BaseStrategy

logger = get_logger("orderbook_strategy")


class OrderBookAnalyzer:
    """订单簿分析器"""
    
    def __init__(self, depth_levels: int = 10):
        self.depth_levels = depth_levels
        self._imbalance_history: deque = deque(maxlen=100)
        self._trade_flow_history: deque = deque(maxlen=100)
    
    def calculate_imbalance(self, orderbook: OrderBook) -> Dict[str, float]:
        """
        计算订单簿失衡度
        
        Imbalance = (Bid Volume - Ask Volume) / (Bid Volume + Ask Volume)
        范围: [-1, 1]，正值表示买方压力大，负值表示卖方压力大
        """
        # 取前N档
        bids = orderbook.bids[:self.depth_levels]
        asks = orderbook.asks[:self.depth_levels]
        
        # 计算总量
        bid_volume = sum(level.size for level in bids)
        ask_volume = sum(level.size for level in asks)
        total_volume = bid_volume + ask_volume
        
        if total_volume == 0:
            return {
                "imbalance": 0,
                "bid_volume": 0,
                "ask_volume": 0,
                "ratio": 1
            }
        
        imbalance = (bid_volume - ask_volume) / total_volume
        ratio = bid_volume / ask_volume if ask_volume > 0 else float('inf')
        
        return {
            "imbalance": imbalance,
            "bid_volume": bid_volume,
            "ask_volume": ask_volume,
            "ratio": ratio
        }
    
    def calculate_weighted_imbalance(self, orderbook: OrderBook) -> float:
        """
        计算加权失衡度（距离中间价越近权重越高）
        """
        bids = orderbook.bids[:self.depth_levels]
        asks = orderbook.asks[:self.depth_levels]
        
        if not bids or not asks:
            return 0
        
        mid_price = (bids[0].price + asks[0].price) / 2
        
        # 计算加权买单量
        weighted_bid = 0
        for i, level in enumerate(bids):
            distance = abs(level.price - mid_price) / mid_price
            weight = 1 / (1 + distance * 100)  # 距离越远权重越小
            weighted_bid += level.size * weight
        
        # 计算加权卖单量
        weighted_ask = 0
        for i, level in enumerate(asks):
            distance = abs(level.price - mid_price) / mid_price
            weight = 1 / (1 + distance * 100)
            weighted_ask += level.size * weight
        
        total = weighted_bid + weighted_ask
        if total == 0:
            return 0
        
        return (weighted_bid - weighted_ask) / total
    
    def calculate_depth_pressure(
        self,
        orderbook: OrderBook,
        price_range_pct: float = 1.0
    ) -> Dict[str, float]:
        """
        计算指定价格范围内的深度压力
        """
        if not orderbook.bids or not orderbook.asks:
            return {"bid_pressure": 0, "ask_pressure": 0, "net_pressure": 0}
        
        mid_price = (orderbook.bids[0].price + orderbook.asks[0].price) / 2
        price_range = mid_price * price_range_pct / 100
        
        # 计算范围内的买单深度
        bid_depth = sum(
            level.size * level.price
            for level in orderbook.bids
            if level.price >= mid_price - price_range
        )
        
        # 计算范围内的卖单深度
        ask_depth = sum(
            level.size * level.price
            for level in orderbook.asks
            if level.price <= mid_price + price_range
        )
        
        total_depth = bid_depth + ask_depth
        
        return {
            "bid_pressure": bid_depth / total_depth if total_depth > 0 else 0.5,
            "ask_pressure": ask_depth / total_depth if total_depth > 0 else 0.5,
            "net_pressure": (bid_depth - ask_depth) / total_depth if total_depth > 0 else 0
        }
    
    def detect_large_orders(
        self,
        orderbook: OrderBook,
        threshold_multiplier: float = 3.0
    ) -> Dict[str, List[Dict]]:
        """
        检测大单（相对于平均挂单量）
        """
        bids = orderbook.bids[:self.depth_levels]
        asks = orderbook.asks[:self.depth_levels]
        
        # 计算平均挂单量
        all_sizes = [level.size for level in bids + asks]
        avg_size = np.mean(all_sizes) if all_sizes else 0
        threshold = avg_size * threshold_multiplier
        
        large_bids = [
            {"price": level.price, "size": level.size, "ratio": level.size / avg_size}
            for level in bids
            if level.size > threshold
        ]
        
        large_asks = [
            {"price": level.price, "size": level.size, "ratio": level.size / avg_size}
            for level in asks
            if level.size > threshold
        ]
        
        return {
            "large_bids": large_bids,
            "large_asks": large_asks,
            "avg_size": avg_size,
            "threshold": threshold
        }
    
    def calculate_spread_analysis(self, orderbook: OrderBook) -> Dict[str, float]:
        """
        分析买卖价差
        """
        if not orderbook.bids or not orderbook.asks:
            return {"spread": 0, "spread_pct": 0, "mid_price": 0}
        
        best_bid = orderbook.bids[0].price
        best_ask = orderbook.asks[0].price
        mid_price = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
        spread_pct = spread / mid_price * 100
        
        return {
            "spread": spread,
            "spread_pct": spread_pct,
            "mid_price": mid_price,
            "best_bid": best_bid,
            "best_ask": best_ask
        }
    
    def estimate_slippage(
        self,
        orderbook: OrderBook,
        order_size: float,
        side: str  # "buy" or "sell"
    ) -> Dict[str, float]:
        """
        估算滑点
        """
        if side == "buy":
            levels = orderbook.asks
        else:
            levels = orderbook.bids
        
        if not levels:
            return {"slippage": 0, "avg_price": 0, "total_cost": 0}
        
        remaining = order_size
        total_cost = 0
        filled_size = 0
        
        for level in levels:
            if remaining <= 0:
                break
            
            fill_size = min(remaining, level.size)
            total_cost += fill_size * level.price
            filled_size += fill_size
            remaining -= fill_size
        
        if filled_size == 0:
            return {"slippage": 0, "avg_price": 0, "total_cost": 0}
        
        avg_price = total_cost / filled_size
        best_price = levels[0].price
        slippage = abs(avg_price - best_price) / best_price * 100
        
        return {
            "slippage": slippage,
            "avg_price": avg_price,
            "total_cost": total_cost,
            "filled_size": filled_size,
            "unfilled_size": remaining if remaining > 0 else 0
        }


class TradeFlowAnalyzer:
    """成交流分析器"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self._trades: deque = deque(maxlen=window_size)
    
    def add_trade(self, trade: Trade):
        """添加成交记录"""
        self._trades.append(trade)
    
    def calculate_buy_sell_ratio(self) -> Dict[str, float]:
        """计算买卖比例"""
        if not self._trades:
            return {"buy_volume": 0, "sell_volume": 0, "ratio": 1, "net_flow": 0}
        
        buy_volume = sum(t.size for t in self._trades if t.side == "buy")
        sell_volume = sum(t.size for t in self._trades if t.side == "sell")
        total = buy_volume + sell_volume
        
        return {
            "buy_volume": buy_volume,
            "sell_volume": sell_volume,
            "ratio": buy_volume / sell_volume if sell_volume > 0 else float('inf'),
            "net_flow": (buy_volume - sell_volume) / total if total > 0 else 0
        }
    
    def calculate_vwap(self) -> float:
        """计算成交量加权平均价"""
        if not self._trades:
            return 0
        
        total_value = sum(t.price * t.size for t in self._trades)
        total_volume = sum(t.size for t in self._trades)
        
        return total_value / total_volume if total_volume > 0 else 0
    
    def detect_aggressive_trades(
        self,
        threshold_multiplier: float = 2.0
    ) -> List[Trade]:
        """检测激进成交（大单主动成交）"""
        if not self._trades:
            return []
        
        avg_size = np.mean([t.size for t in self._trades])
        threshold = avg_size * threshold_multiplier
        
        return [t for t in self._trades if t.size > threshold]


class OrderBookImbalanceStrategy(BaseStrategy):
    """
    盘口失衡策略
    
    核心逻辑：
    1. 分析订单簿买卖压力失衡
    2. 结合成交流方向
    3. 预测短期价格走向
    """
    
    def __init__(
        self,
        imbalance_threshold: float = 0.3,
        depth_levels: int = 10,
        min_confidence: float = 0.5,
        spread_threshold: float = 0.1,  # 最大价差百分比
        use_weighted_imbalance: bool = True
    ):
        super().__init__(
            name="orderbook_imbalance",
            version="1.0.0",
            description="盘口失衡策略：基于订单簿分析预测短期价格走向"
        )
        
        self.imbalance_threshold = imbalance_threshold
        self.depth_levels = depth_levels
        self.min_confidence = min_confidence
        self.spread_threshold = spread_threshold
        self.use_weighted_imbalance = use_weighted_imbalance
        
        self.ob_analyzer = OrderBookAnalyzer(depth_levels)
        self.trade_analyzer = TradeFlowAnalyzer()
        
        # 历史数据
        self._imbalance_history: deque = deque(maxlen=50)
    
    async def generate_signal(
        self,
        symbol: str,
        orderbook: OrderBook,
        recent_trades: Optional[List[Trade]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Signal:
        """生成盘口失衡信号"""
        
        # 分析价差
        spread_info = self.ob_analyzer.calculate_spread_analysis(orderbook)
        
        # 价差过大时不交易
        if spread_info["spread_pct"] > self.spread_threshold:
            return Signal(
                symbol=symbol,
                direction=SignalDirection.NEUTRAL,
                strength=0,
                confidence=0,
                source="orderbook_imbalance",
                reason=f"Spread too wide: {spread_info['spread_pct']:.3f}%"
            )
        
        # 计算失衡度
        if self.use_weighted_imbalance:
            imbalance = self.ob_analyzer.calculate_weighted_imbalance(orderbook)
        else:
            imbalance_info = self.ob_analyzer.calculate_imbalance(orderbook)
            imbalance = imbalance_info["imbalance"]
        
        # 记录历史
        self._imbalance_history.append(imbalance)
        
        # 计算深度压力
        pressure = self.ob_analyzer.calculate_depth_pressure(orderbook)
        
        # 检测大单
        large_orders = self.ob_analyzer.detect_large_orders(orderbook)
        
        # 分析成交流
        trade_flow = {"net_flow": 0}
        if recent_trades:
            for trade in recent_trades:
                self.trade_analyzer.add_trade(trade)
            trade_flow = self.trade_analyzer.calculate_buy_sell_ratio()
        
        # 综合评分
        score = 0
        reasons = []
        
        # 失衡度信号
        if abs(imbalance) > self.imbalance_threshold:
            score += imbalance * 0.4
            reasons.append(f"Imbalance: {imbalance:.3f}")
        
        # 深度压力信号
        if abs(pressure["net_pressure"]) > 0.2:
            score += pressure["net_pressure"] * 0.3
            reasons.append(f"Depth pressure: {pressure['net_pressure']:.3f}")
        
        # 成交流信号
        if abs(trade_flow["net_flow"]) > 0.2:
            score += trade_flow["net_flow"] * 0.2
            reasons.append(f"Trade flow: {trade_flow['net_flow']:.3f}")
        
        # 大单信号
        if large_orders["large_bids"] and not large_orders["large_asks"]:
            score += 0.1
            reasons.append(f"Large bids detected: {len(large_orders['large_bids'])}")
        elif large_orders["large_asks"] and not large_orders["large_bids"]:
            score -= 0.1
            reasons.append(f"Large asks detected: {len(large_orders['large_asks'])}")
        
        # 确定信号方向
        if score > self.imbalance_threshold:
            direction = SignalDirection.LONG
            strength = min(score, 1.0)
        elif score < -self.imbalance_threshold:
            direction = SignalDirection.SHORT
            strength = min(abs(score), 1.0)
        else:
            direction = SignalDirection.NEUTRAL
            strength = 0
        
        # 计算置信度
        confidence = min(abs(score) / self.imbalance_threshold, 1.0) if self.imbalance_threshold > 0 else 0
        
        # 估算滑点
        slippage_buy = self.ob_analyzer.estimate_slippage(orderbook, 1.0, "buy")
        slippage_sell = self.ob_analyzer.estimate_slippage(orderbook, 1.0, "sell")
        
        signal = Signal(
            symbol=symbol,
            direction=direction,
            strength=strength,
            confidence=confidence,
            source="orderbook_imbalance",
            reason=" | ".join(reasons) if reasons else "No significant imbalance",
            metadata={
                "imbalance": imbalance,
                "bid_pressure": pressure["bid_pressure"],
                "ask_pressure": pressure["ask_pressure"],
                "spread_pct": spread_info["spread_pct"],
                "mid_price": spread_info["mid_price"],
                "slippage_buy": slippage_buy["slippage"],
                "slippage_sell": slippage_sell["slippage"],
                "large_bids_count": len(large_orders["large_bids"]),
                "large_asks_count": len(large_orders["large_asks"])
            }
        )
        
        if direction != SignalDirection.NEUTRAL:
            logger.info(f"OrderBook signal: {symbol} {direction} (imbalance={imbalance:.3f})")
        
        return signal
    
    def get_optimal_order_size(
        self,
        orderbook: OrderBook,
        max_slippage: float = 0.1,
        side: str = "buy"
    ) -> float:
        """计算最优下单量（控制滑点）"""
        
        levels = orderbook.asks if side == "buy" else orderbook.bids
        if not levels:
            return 0
        
        best_price = levels[0].price
        max_price = best_price * (1 + max_slippage / 100) if side == "buy" else best_price * (1 - max_slippage / 100)
        
        optimal_size = 0
        for level in levels:
            if side == "buy" and level.price > max_price:
                break
            if side == "sell" and level.price < max_price:
                break
            optimal_size += level.size
        
        return optimal_size
