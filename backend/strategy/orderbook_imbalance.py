"""
Order book imbalance strategy module
Analyzes buy/sell pressure from order book data to predict short-term price direction
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
    """Order book analyzer"""

    def __init__(self, depth_levels: int = 10):
        self.depth_levels = depth_levels
        self._imbalance_history: deque = deque(maxlen=100)
        self._trade_flow_history: deque = deque(maxlen=100)

    def calculate_imbalance(self, orderbook: OrderBook) -> Dict[str, float]:
        """
        Calculate order book imbalance

        Imbalance = (Bid Volume - Ask Volume) / (Bid Volume + Ask Volume)
        Range: [-1, 1], positive values indicate stronger buy pressure, negative values indicate stronger sell pressure
        """
        # Take the top N levels
        bids = orderbook.bids[:self.depth_levels]
        asks = orderbook.asks[:self.depth_levels]

        # Calculate total volume
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
        Calculate weighted imbalance (closer to mid price = higher weight)
        """
        bids = orderbook.bids[:self.depth_levels]
        asks = orderbook.asks[:self.depth_levels]

        if not bids or not asks:
            return 0

        mid_price = (bids[0].price + asks[0].price) / 2

        # Calculate weighted bid volume
        weighted_bid = 0
        for i, level in enumerate(bids):
            distance = abs(level.price - mid_price) / mid_price
            weight = 1 / (1 + distance * 100)  # Further from mid price = lower weight
            weighted_bid += level.size * weight

        # Calculate weighted ask volume
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
        Calculate depth pressure within a specified price range
        """
        if not orderbook.bids or not orderbook.asks:
            return {"bid_pressure": 0, "ask_pressure": 0, "net_pressure": 0}

        mid_price = (orderbook.bids[0].price + orderbook.asks[0].price) / 2
        price_range = mid_price * price_range_pct / 100

        # Calculate bid depth within range
        bid_depth = sum(
            level.size * level.price
            for level in orderbook.bids
            if level.price >= mid_price - price_range
        )

        # Calculate ask depth within range
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
        Detect large orders (relative to average order size)
        """
        bids = orderbook.bids[:self.depth_levels]
        asks = orderbook.asks[:self.depth_levels]

        # Calculate average order size
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
        Analyze bid-ask spread
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
        Estimate slippage
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
    """Trade flow analyzer"""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self._trades: deque = deque(maxlen=window_size)

    def add_trade(self, trade: Trade):
        """Add trade record"""
        self._trades.append(trade)

    def calculate_buy_sell_ratio(self) -> Dict[str, float]:
        """Calculate buy/sell ratio"""
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
        """Calculate volume-weighted average price"""
        if not self._trades:
            return 0

        total_value = sum(t.price * t.size for t in self._trades)
        total_volume = sum(t.size for t in self._trades)

        return total_value / total_volume if total_volume > 0 else 0

    def detect_aggressive_trades(
        self,
        threshold_multiplier: float = 2.0
    ) -> List[Trade]:
        """Detect aggressive trades (large aggressive fills)"""
        if not self._trades:
            return []

        avg_size = np.mean([t.size for t in self._trades])
        threshold = avg_size * threshold_multiplier

        return [t for t in self._trades if t.size > threshold]


class OrderBookImbalanceStrategy(BaseStrategy):
    """
    Order book imbalance strategy

    Core logic:
    1. Analyze buy/sell pressure imbalance in the order book
    2. Combine with trade flow direction
    3. Predict short-term price direction
    """

    def __init__(
        self,
        imbalance_threshold: float = 0.3,
        depth_levels: int = 10,
        min_confidence: float = 0.5,
        spread_threshold: float = 0.1,  # Maximum spread percentage
        use_weighted_imbalance: bool = True
    ):
        super().__init__(
            name="orderbook_imbalance",
            version="1.0.0",
            description="Order book imbalance strategy: predicts short-term price direction based on order book analysis"
        )

        self.imbalance_threshold = imbalance_threshold
        self.depth_levels = depth_levels
        self.min_confidence = min_confidence
        self.spread_threshold = spread_threshold
        self.use_weighted_imbalance = use_weighted_imbalance

        self.ob_analyzer = OrderBookAnalyzer(depth_levels)
        self.trade_analyzer = TradeFlowAnalyzer()

        # Historical data
        self._imbalance_history: deque = deque(maxlen=50)

    async def generate_signal(
        self,
        symbol: str,
        orderbook: OrderBook,
        recent_trades: Optional[List[Trade]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Signal:
        """Generate order book imbalance signal"""

        # Analyze spread
        spread_info = self.ob_analyzer.calculate_spread_analysis(orderbook)

        # Do not trade when spread is too wide
        if spread_info["spread_pct"] > self.spread_threshold:
            return Signal(
                symbol=symbol,
                direction=SignalDirection.NEUTRAL,
                strength=0,
                confidence=0,
                source="orderbook_imbalance",
                reason=f"Spread too wide: {spread_info['spread_pct']:.3f}%"
            )

        # Calculate imbalance
        if self.use_weighted_imbalance:
            imbalance = self.ob_analyzer.calculate_weighted_imbalance(orderbook)
        else:
            imbalance_info = self.ob_analyzer.calculate_imbalance(orderbook)
            imbalance = imbalance_info["imbalance"]

        # Record history
        self._imbalance_history.append(imbalance)

        # Calculate depth pressure
        pressure = self.ob_analyzer.calculate_depth_pressure(orderbook)

        # Detect large orders
        large_orders = self.ob_analyzer.detect_large_orders(orderbook)

        # Analyze trade flow
        trade_flow = {"net_flow": 0}
        if recent_trades:
            for trade in recent_trades:
                self.trade_analyzer.add_trade(trade)
            trade_flow = self.trade_analyzer.calculate_buy_sell_ratio()

        # Combined score
        score = 0
        reasons = []

        # Imbalance signal
        if abs(imbalance) > self.imbalance_threshold:
            score += imbalance * 0.4
            reasons.append(f"Imbalance: {imbalance:.3f}")

        # Depth pressure signal
        if abs(pressure["net_pressure"]) > 0.2:
            score += pressure["net_pressure"] * 0.3
            reasons.append(f"Depth pressure: {pressure['net_pressure']:.3f}")

        # Trade flow signal
        if abs(trade_flow["net_flow"]) > 0.2:
            score += trade_flow["net_flow"] * 0.2
            reasons.append(f"Trade flow: {trade_flow['net_flow']:.3f}")

        # Large order signal
        if large_orders["large_bids"] and not large_orders["large_asks"]:
            score += 0.1
            reasons.append(f"Large bids detected: {len(large_orders['large_bids'])}")
        elif large_orders["large_asks"] and not large_orders["large_bids"]:
            score -= 0.1
            reasons.append(f"Large asks detected: {len(large_orders['large_asks'])}")

        # Determine signal direction
        if score > self.imbalance_threshold:
            direction = SignalDirection.LONG
            strength = min(score, 1.0)
        elif score < -self.imbalance_threshold:
            direction = SignalDirection.SHORT
            strength = min(abs(score), 1.0)
        else:
            direction = SignalDirection.NEUTRAL
            strength = 0

        # Calculate confidence
        confidence = min(abs(score) / self.imbalance_threshold, 1.0) if self.imbalance_threshold > 0 else 0

        # Estimate slippage
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
        """Calculate optimal order size (to control slippage)"""

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
