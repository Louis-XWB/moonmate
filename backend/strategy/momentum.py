"""
动量策略
基于价格动量和技术指标生成交易信号
"""

from typing import Dict, List, Optional, Any
import numpy as np

from backend.data.models import Signal, SignalDirection, Ticker, Kline, Position
from .base import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """动量策略"""
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "sma_fast": 5,
            "sma_slow": 20,
            "volume_threshold": 1.5,  # 成交量放大倍数
            "min_strength": 0.3,
        }
        if params:
            default_params.update(params)
        super().__init__("momentum", default_params)
    
    async def generate_signal(
        self,
        symbol: str,
        ticker: Ticker,
        klines: List[Kline],
        position: Optional[Position] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Signal:
        """生成动量信号"""
        
        if len(klines) < self.params["sma_slow"]:
            return self._neutral_signal(symbol, "Insufficient data")
        
        # 提取收盘价和成交量
        closes = np.array([k.close for k in klines])
        volumes = np.array([k.volume for k in klines])
        
        # 计算技术指标
        rsi = self._calculate_rsi(closes, self.params["rsi_period"])
        sma_fast = self._calculate_sma(closes, self.params["sma_fast"])
        sma_slow = self._calculate_sma(closes, self.params["sma_slow"])
        volume_ratio = volumes[-1] / np.mean(volumes[-20:]) if len(volumes) >= 20 else 1
        
        # 信号逻辑
        signals = []
        evidence = []
        
        # RSI信号
        if rsi < self.params["rsi_oversold"]:
            signals.append(("long", 0.3, f"RSI超卖({rsi:.1f})"))
        elif rsi > self.params["rsi_overbought"]:
            signals.append(("short", 0.3, f"RSI超买({rsi:.1f})"))
        
        # 均线交叉信号
        if sma_fast > sma_slow:
            signals.append(("long", 0.4, f"均线金叉(SMA{self.params['sma_fast']}>{self.params['sma_slow']})"))
        elif sma_fast < sma_slow:
            signals.append(("short", 0.4, f"均线死叉(SMA{self.params['sma_fast']}<{self.params['sma_slow']})"))
        
        # 成交量确认
        if volume_ratio > self.params["volume_threshold"]:
            signals.append(("confirm", 0.2, f"成交量放大({volume_ratio:.1f}x)"))
            evidence.append(f"成交量放大{volume_ratio:.1f}倍")
        
        # 价格动量
        momentum = (closes[-1] - closes[-5]) / closes[-5] * 100 if len(closes) >= 5 else 0
        if momentum > 2:
            signals.append(("long", 0.2, f"价格动量强({momentum:.1f}%)"))
        elif momentum < -2:
            signals.append(("short", 0.2, f"价格动量弱({momentum:.1f}%)"))
        
        # 综合信号
        long_score = sum(s[1] for s in signals if s[0] == "long")
        short_score = sum(s[1] for s in signals if s[0] == "short")
        confirm_score = sum(s[1] for s in signals if s[0] == "confirm")
        
        # 确定方向
        if long_score > short_score and long_score >= self.params["min_strength"]:
            direction = SignalDirection.LONG
            strength = min(1.0, long_score + confirm_score * 0.5)
            reasons = [s[2] for s in signals if s[0] in ["long", "confirm"]]
        elif short_score > long_score and short_score >= self.params["min_strength"]:
            direction = SignalDirection.SHORT
            strength = min(1.0, short_score + confirm_score * 0.5)
            reasons = [s[2] for s in signals if s[0] in ["short", "confirm"]]
        else:
            direction = SignalDirection.NEUTRAL
            strength = 0
            reasons = ["信号不明确"]
        
        # 计算置信度
        confidence = min(0.9, strength * 0.8 + 0.1)
        
        # 创建信号
        signal = Signal(
            symbol=symbol,
            direction=direction,
            strength=strength,
            confidence=confidence,
            source=self.name,
            strategy_id=self.name,
            reason="; ".join(reasons),
            evidence=evidence + [f"RSI={rsi:.1f}", f"动量={momentum:.1f}%"],
            entry_price=ticker.last_price,
            metadata={
                "rsi": rsi,
                "sma_fast": sma_fast,
                "sma_slow": sma_slow,
                "volume_ratio": volume_ratio,
                "momentum": momentum
            }
        )
        
        # 设置止损止盈
        if direction == SignalDirection.LONG:
            signal.stop_loss = ticker.last_price * 0.98
            signal.take_profit = ticker.last_price * 1.05
        elif direction == SignalDirection.SHORT:
            signal.stop_loss = ticker.last_price * 1.02
            signal.take_profit = ticker.last_price * 0.95
        
        return signal
    
    def _neutral_signal(self, symbol: str, reason: str) -> Signal:
        """返回中性信号"""
        return Signal(
            symbol=symbol,
            direction=SignalDirection.NEUTRAL,
            strength=0,
            confidence=0,
            source=self.name,
            reason=reason
        )
    
    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """计算RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return float(rsi)
    
    def _calculate_sma(self, prices: np.ndarray, period: int) -> float:
        """计算简单移动平均"""
        if len(prices) < period:
            return float(prices[-1])
        return float(np.mean(prices[-period:]))
