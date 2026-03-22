"""
Momentum strategy
Generates trading signals based on price momentum and technical indicators
"""

from typing import Dict, List, Optional, Any
import numpy as np

from backend.data.models import Signal, SignalDirection, Ticker, Kline, Position
from .base import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """Momentum strategy"""

    def __init__(self, params: Optional[Dict[str, Any]] = None):
        default_params = {
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "sma_fast": 5,
            "sma_slow": 20,
            "volume_threshold": 1.5,  # Volume surge multiplier
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
        """Generate momentum signal"""

        if len(klines) < self.params["sma_slow"]:
            return self._neutral_signal(symbol, "Insufficient data")

        # Extract closing prices and volumes
        closes = np.array([k.close for k in klines])
        volumes = np.array([k.volume for k in klines])

        # Calculate technical indicators
        rsi = self._calculate_rsi(closes, self.params["rsi_period"])
        sma_fast = self._calculate_sma(closes, self.params["sma_fast"])
        sma_slow = self._calculate_sma(closes, self.params["sma_slow"])
        volume_ratio = volumes[-1] / np.mean(volumes[-20:]) if len(volumes) >= 20 else 1

        # Signal logic
        signals = []
        evidence = []

        # RSI signal
        if rsi < self.params["rsi_oversold"]:
            signals.append(("long", 0.3, f"RSI oversold ({rsi:.1f})"))
        elif rsi > self.params["rsi_overbought"]:
            signals.append(("short", 0.3, f"RSI overbought ({rsi:.1f})"))

        # Moving average crossover signal
        if sma_fast > sma_slow:
            signals.append(("long", 0.4, f"MA golden cross (SMA{self.params['sma_fast']}>{self.params['sma_slow']})"))
        elif sma_fast < sma_slow:
            signals.append(("short", 0.4, f"MA death cross (SMA{self.params['sma_fast']}<{self.params['sma_slow']})"))

        # Volume confirmation
        if volume_ratio > self.params["volume_threshold"]:
            signals.append(("confirm", 0.2, f"Volume surge ({volume_ratio:.1f}x)"))
            evidence.append(f"Volume surged {volume_ratio:.1f}x")

        # Price momentum
        momentum = (closes[-1] - closes[-5]) / closes[-5] * 100 if len(closes) >= 5 else 0
        if momentum > 2:
            signals.append(("long", 0.2, f"Strong price momentum ({momentum:.1f}%)"))
        elif momentum < -2:
            signals.append(("short", 0.2, f"Weak price momentum ({momentum:.1f}%)"))

        # Composite signal
        long_score = sum(s[1] for s in signals if s[0] == "long")
        short_score = sum(s[1] for s in signals if s[0] == "short")
        confirm_score = sum(s[1] for s in signals if s[0] == "confirm")

        # Determine direction
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
            reasons = ["Signal unclear"]

        # Calculate confidence
        confidence = min(0.9, strength * 0.8 + 0.1)

        # Create signal
        signal = Signal(
            symbol=symbol,
            direction=direction,
            strength=strength,
            confidence=confidence,
            source=self.name,
            strategy_id=self.name,
            reason="; ".join(reasons),
            evidence=evidence + [f"RSI={rsi:.1f}", f"momentum={momentum:.1f}%"],
            entry_price=ticker.last_price,
            metadata={
                "rsi": rsi,
                "sma_fast": sma_fast,
                "sma_slow": sma_slow,
                "volume_ratio": volume_ratio,
                "momentum": momentum
            }
        )

        # Set stop-loss and take-profit
        if direction == SignalDirection.LONG:
            signal.stop_loss = ticker.last_price * 0.98
            signal.take_profit = ticker.last_price * 1.05
        elif direction == SignalDirection.SHORT:
            signal.stop_loss = ticker.last_price * 1.02
            signal.take_profit = ticker.last_price * 0.95

        return signal

    def _neutral_signal(self, symbol: str, reason: str) -> Signal:
        """Return neutral signal"""
        return Signal(
            symbol=symbol,
            direction=SignalDirection.NEUTRAL,
            strength=0,
            confidence=0,
            source=self.name,
            reason=reason
        )

    def _calculate_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """Calculate RSI"""
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
        """Calculate simple moving average"""
        if len(prices) < period:
            return float(prices[-1])
        return float(np.mean(prices[-period:]))
