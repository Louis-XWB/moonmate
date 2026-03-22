"""
Signal fusion module
Fuses signals from multiple strategies and AI to produce final trading decisions
"""

from typing import Dict, List, Optional
from datetime import datetime

from backend.data.models import Signal, SignalDirection


class SignalFusion:
    """Signal fusion engine"""

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        min_confidence: float = 0.5,
        min_agreement: float = 0.6
    ):
        """
        Initialize the signal fusion engine

        Args:
            weights: Weights for each signal source
            min_confidence: Minimum confidence threshold
            min_agreement: Minimum agreement threshold (proportion of signals in the same direction)
        """
        self.weights = weights or {
            "ai": 0.3,
            "momentum": 0.3,
            "reversal": 0.2,
            "orderbook": 0.2
        }
        self.min_confidence = min_confidence
        self.min_agreement = min_agreement

    def fuse(self, signals: List[Signal]) -> Signal:
        """
        Fuse multiple signals

        Args:
            signals: List of signals

        Returns:
            Fused signal
        """
        if not signals:
            return self._empty_signal()

        # Filter invalid signals
        valid_signals = [s for s in signals if s.is_valid and s.confidence >= self.min_confidence]

        if not valid_signals:
            return self._empty_signal()

        # Tally weighted scores for each direction
        direction_scores: Dict[SignalDirection, float] = {
            SignalDirection.LONG: 0,
            SignalDirection.SHORT: 0,
            SignalDirection.CLOSE: 0,
            SignalDirection.NEUTRAL: 0
        }

        direction_counts: Dict[SignalDirection, int] = {
            SignalDirection.LONG: 0,
            SignalDirection.SHORT: 0,
            SignalDirection.CLOSE: 0,
            SignalDirection.NEUTRAL: 0
        }

        total_weight = 0
        evidence = []

        for signal in valid_signals:
            weight = self.weights.get(signal.source, 0.1)
            score = signal.strength * signal.confidence * weight

            direction_scores[signal.direction] += score
            direction_counts[signal.direction] += 1
            total_weight += weight

            evidence.append(f"{signal.source}: {signal.direction.value} ({signal.confidence:.2f})")

        # Normalize scores
        if total_weight > 0:
            for direction in direction_scores:
                direction_scores[direction] /= total_weight

        # Select the direction with the highest score
        best_direction = max(direction_scores, key=direction_scores.get)
        best_score = direction_scores[best_direction]

        # Calculate agreement (proportion of signals in the same direction)
        total_signals = len(valid_signals)
        agreement = direction_counts[best_direction] / total_signals if total_signals > 0 else 0

        # Check agreement threshold
        if agreement < self.min_agreement and best_direction != SignalDirection.NEUTRAL:
            # Insufficient agreement, downgrade to neutral
            return Signal(
                symbol=valid_signals[0].symbol,
                direction=SignalDirection.NEUTRAL,
                strength=0,
                confidence=0,
                source="fusion",
                reason=f"Insufficient signal agreement ({agreement:.1%})",
                evidence=evidence
            )

        # Calculate fused confidence
        fused_confidence = min(0.95, best_score * agreement)

        # Get entry price and stop-loss/take-profit (use values from the first valid signal)
        entry_price = None
        stop_loss = None
        take_profit = None

        for signal in valid_signals:
            if signal.direction == best_direction:
                entry_price = signal.entry_price
                stop_loss = signal.stop_loss
                take_profit = signal.take_profit
                break

        # Generate reasons
        reasons = []
        for signal in valid_signals:
            if signal.direction == best_direction and signal.reason:
                reasons.append(f"[{signal.source}] {signal.reason}")

        return Signal(
            symbol=valid_signals[0].symbol,
            direction=best_direction,
            strength=best_score,
            confidence=fused_confidence,
            source="fusion",
            reason="; ".join(reasons[:3]),
            evidence=evidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata={
                "direction_scores": {k.value: v for k, v in direction_scores.items()},
                "agreement": agreement,
                "signal_count": len(valid_signals)
            }
        )

    def _empty_signal(self) -> Signal:
        """Return empty signal"""
        return Signal(
            symbol="",
            direction=SignalDirection.NEUTRAL,
            strength=0,
            confidence=0,
            source="fusion",
            reason="No valid signals"
        )

    def update_weights(self, weights: Dict[str, float]):
        """Update weights"""
        self.weights.update(weights)
