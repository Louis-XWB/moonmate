"""
反转策略模块
实现极值识别、均值回归、避免接飞刀等功能
"""

import numpy as np
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

from backend.data.models import Kline, Signal, SignalDirection
from backend.core.logger import get_logger
from .base import BaseStrategy

logger = get_logger("reversal_strategy")


class ReversalType(str, Enum):
    """反转类型"""
    OVERSOLD = "oversold"       # 超卖反转
    OVERBOUGHT = "overbought"   # 超买反转
    MEAN_REVERSION = "mean_reversion"  # 均值回归
    SUPPORT_BOUNCE = "support_bounce"  # 支撑位反弹
    RESISTANCE_REJECT = "resistance_reject"  # 阻力位回落


class ReversalStrategy(BaseStrategy):
    """
    反转策略
    
    核心逻辑：
    1. 识别极端价格偏离（RSI、布林带、标准差）
    2. 确认反转信号（K线形态、成交量）
    3. 避免接飞刀（趋势确认、止损保护）
    """
    
    def __init__(
        self,
        rsi_oversold: float = 30,
        rsi_overbought: float = 70,
        bb_std: float = 2.0,
        lookback_period: int = 20,
        confirmation_bars: int = 2,
        min_reversal_strength: float = 0.6,
        avoid_falling_knife: bool = True,
        max_consecutive_losses: int = 3
    ):
        super().__init__(
            name="reversal",
            version="1.0.0",
            description="反转策略：捕捉超买超卖后的价格回归"
        )
        
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.bb_std = bb_std
        self.lookback_period = lookback_period
        self.confirmation_bars = confirmation_bars
        self.min_reversal_strength = min_reversal_strength
        self.avoid_falling_knife = avoid_falling_knife
        self.max_consecutive_losses = max_consecutive_losses
        
        # 状态追踪
        self._consecutive_losses = 0
        self._last_signal_time: Optional[datetime] = None
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """计算 RSI 指标"""
        if len(prices) < period + 1:
            return 50  # 默认中性值
        
        deltas = np.diff(prices[-period-1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calculate_bollinger_bands(
        self,
        prices: List[float],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Dict[str, float]:
        """计算布林带"""
        if len(prices) < period:
            return {"upper": 0, "middle": 0, "lower": 0, "width": 0}
        
        prices_array = np.array(prices[-period:])
        middle = np.mean(prices_array)
        std = np.std(prices_array)
        
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        width = (upper - lower) / middle * 100  # 带宽百分比
        
        return {
            "upper": upper,
            "middle": middle,
            "lower": lower,
            "width": width
        }
    
    def calculate_zscore(self, prices: List[float], period: int = 20) -> float:
        """计算 Z-Score（价格偏离度）"""
        if len(prices) < period:
            return 0
        
        prices_array = np.array(prices[-period:])
        mean = np.mean(prices_array)
        std = np.std(prices_array)
        
        if std == 0:
            return 0
        
        current_price = prices[-1]
        zscore = (current_price - mean) / std
        
        return zscore
    
    def detect_candlestick_pattern(self, klines: List[Kline]) -> Dict[str, Any]:
        """检测K线反转形态"""
        if len(klines) < 3:
            return {"pattern": None, "bullish": False, "bearish": False}
        
        k1, k2, k3 = klines[-3], klines[-2], klines[-1]
        
        patterns = {
            "pattern": None,
            "bullish": False,
            "bearish": False,
            "strength": 0
        }
        
        # 锤子线（Hammer）- 看涨反转
        body_k3 = abs(k3.close - k3.open)
        lower_shadow_k3 = min(k3.open, k3.close) - k3.low
        upper_shadow_k3 = k3.high - max(k3.open, k3.close)
        
        if lower_shadow_k3 > 2 * body_k3 and upper_shadow_k3 < body_k3 * 0.5:
            patterns["pattern"] = "hammer"
            patterns["bullish"] = True
            patterns["strength"] = 0.7
        
        # 倒锤子线（Inverted Hammer）- 看涨反转
        if upper_shadow_k3 > 2 * body_k3 and lower_shadow_k3 < body_k3 * 0.5:
            patterns["pattern"] = "inverted_hammer"
            patterns["bullish"] = True
            patterns["strength"] = 0.6
        
        # 吞没形态（Engulfing）
        body_k2 = abs(k2.close - k2.open)
        
        # 看涨吞没
        if k2.close < k2.open and k3.close > k3.open:  # 前阴后阳
            if k3.open < k2.close and k3.close > k2.open:  # 完全吞没
                patterns["pattern"] = "bullish_engulfing"
                patterns["bullish"] = True
                patterns["strength"] = 0.8
        
        # 看跌吞没
        if k2.close > k2.open and k3.close < k3.open:  # 前阳后阴
            if k3.open > k2.close and k3.close < k2.open:  # 完全吞没
                patterns["pattern"] = "bearish_engulfing"
                patterns["bearish"] = True
                patterns["strength"] = 0.8
        
        # 早晨之星（Morning Star）- 看涨反转
        if len(klines) >= 3:
            body_k1 = abs(k1.close - k1.open)
            if (k1.close < k1.open and  # 第一根阴线
                body_k2 < body_k1 * 0.3 and  # 第二根小实体
                k3.close > k3.open and  # 第三根阳线
                k3.close > (k1.open + k1.close) / 2):  # 收盘超过第一根中点
                patterns["pattern"] = "morning_star"
                patterns["bullish"] = True
                patterns["strength"] = 0.85
        
        # 黄昏之星（Evening Star）- 看跌反转
        if len(klines) >= 3:
            if (k1.close > k1.open and  # 第一根阳线
                body_k2 < body_k1 * 0.3 and  # 第二根小实体
                k3.close < k3.open and  # 第三根阴线
                k3.close < (k1.open + k1.close) / 2):  # 收盘低于第一根中点
                patterns["pattern"] = "evening_star"
                patterns["bearish"] = True
                patterns["strength"] = 0.85
        
        return patterns
    
    def is_falling_knife(self, klines: List[Kline], threshold: float = 5.0) -> bool:
        """
        检测是否是"飞刀"（急跌中）
        避免在急跌过程中抄底
        """
        if len(klines) < 5:
            return False
        
        # 计算最近5根K线的跌幅
        recent_klines = klines[-5:]
        total_change = (recent_klines[-1].close - recent_klines[0].open) / recent_klines[0].open * 100
        
        # 计算连续下跌的K线数量
        consecutive_down = 0
        for k in recent_klines:
            if k.close < k.open:
                consecutive_down += 1
        
        # 如果跌幅超过阈值且连续下跌，认为是飞刀
        if total_change < -threshold and consecutive_down >= 4:
            return True
        
        return False
    
    def calculate_support_resistance(
        self,
        klines: List[Kline],
        lookback: int = 50
    ) -> Dict[str, List[float]]:
        """计算支撑位和阻力位"""
        if len(klines) < lookback:
            lookback = len(klines)
        
        recent_klines = klines[-lookback:]
        highs = [k.high for k in recent_klines]
        lows = [k.low for k in recent_klines]
        
        # 简单方法：使用局部极值
        support_levels = []
        resistance_levels = []
        
        for i in range(2, len(recent_klines) - 2):
            # 局部最低点作为支撑
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and \
               lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                support_levels.append(lows[i])
            
            # 局部最高点作为阻力
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and \
               highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                resistance_levels.append(highs[i])
        
        return {
            "support": sorted(support_levels)[-3:] if support_levels else [],
            "resistance": sorted(resistance_levels)[:3] if resistance_levels else []
        }
    
    async def generate_signal(
        self,
        symbol: str,
        klines: List[Kline],
        context: Optional[Dict[str, Any]] = None
    ) -> Signal:
        """生成反转信号"""
        
        if len(klines) < self.lookback_period:
            return Signal(
                symbol=symbol,
                direction=SignalDirection.NEUTRAL,
                strength=0,
                confidence=0,
                source="reversal",
                reason="Insufficient data"
            )
        
        # 提取价格数据
        closes = [k.close for k in klines]
        current_price = closes[-1]
        
        # 计算指标
        rsi = self.calculate_rsi(closes)
        bb = self.calculate_bollinger_bands(closes, self.lookback_period, self.bb_std)
        zscore = self.calculate_zscore(closes, self.lookback_period)
        pattern = self.detect_candlestick_pattern(klines)
        
        # 检测飞刀
        if self.avoid_falling_knife and self.is_falling_knife(klines):
            logger.warning(f"Falling knife detected for {symbol}, skipping signal")
            return Signal(
                symbol=symbol,
                direction=SignalDirection.NEUTRAL,
                strength=0,
                confidence=0,
                source="reversal",
                reason="Falling knife detected - avoiding entry"
            )
        
        # 信号评分
        bullish_score = 0
        bearish_score = 0
        reasons = []
        
        # RSI 超卖/超买
        if rsi < self.rsi_oversold:
            bullish_score += 0.3
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > self.rsi_overbought:
            bearish_score += 0.3
            reasons.append(f"RSI overbought ({rsi:.1f})")
        
        # 布林带突破
        if current_price < bb["lower"]:
            bullish_score += 0.25
            reasons.append("Price below lower Bollinger Band")
        elif current_price > bb["upper"]:
            bearish_score += 0.25
            reasons.append("Price above upper Bollinger Band")
        
        # Z-Score 极值
        if zscore < -2:
            bullish_score += 0.2
            reasons.append(f"Z-Score extreme low ({zscore:.2f})")
        elif zscore > 2:
            bearish_score += 0.2
            reasons.append(f"Z-Score extreme high ({zscore:.2f})")
        
        # K线形态确认
        if pattern["bullish"]:
            bullish_score += pattern["strength"] * 0.25
            reasons.append(f"Bullish pattern: {pattern['pattern']}")
        elif pattern["bearish"]:
            bearish_score += pattern["strength"] * 0.25
            reasons.append(f"Bearish pattern: {pattern['pattern']}")
        
        # 确定信号方向
        if bullish_score > bearish_score and bullish_score >= self.min_reversal_strength:
            direction = SignalDirection.LONG
            strength = bullish_score
            reversal_type = ReversalType.OVERSOLD
        elif bearish_score > bullish_score and bearish_score >= self.min_reversal_strength:
            direction = SignalDirection.SHORT
            strength = bearish_score
            reversal_type = ReversalType.OVERBOUGHT
        else:
            direction = SignalDirection.NEUTRAL
            strength = 0
            reversal_type = None
        
        # 计算置信度
        confidence = min(max(bullish_score, bearish_score), 1.0)
        
        # 构建信号
        signal = Signal(
            symbol=symbol,
            direction=direction,
            strength=strength,
            confidence=confidence,
            source="reversal",
            reason=" | ".join(reasons) if reasons else "No reversal signal",
            metadata={
                "rsi": rsi,
                "zscore": zscore,
                "bb_position": (current_price - bb["lower"]) / (bb["upper"] - bb["lower"]) if bb["upper"] != bb["lower"] else 0.5,
                "pattern": pattern["pattern"],
                "reversal_type": reversal_type.value if reversal_type else None
            }
        )
        
        if direction != SignalDirection.NEUTRAL:
            logger.info(f"Reversal signal generated: {symbol} {direction} (strength={strength:.2f})")
        
        return signal
    
    def calculate_entry_exit(
        self,
        signal: Signal,
        current_price: float,
        atr: float
    ) -> Dict[str, float]:
        """计算入场价、止损价、止盈价"""
        
        if signal.direction == SignalDirection.LONG:
            entry = current_price
            stop_loss = current_price - 2 * atr  # 2倍ATR止损
            take_profit = current_price + 3 * atr  # 3倍ATR止盈
        elif signal.direction == SignalDirection.SHORT:
            entry = current_price
            stop_loss = current_price + 2 * atr
            take_profit = current_price - 3 * atr
        else:
            entry = stop_loss = take_profit = current_price
        
        return {
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "risk_reward_ratio": abs(take_profit - entry) / abs(entry - stop_loss) if entry != stop_loss else 0
        }
