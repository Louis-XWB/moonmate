"""
信号融合模块
融合多个策略和AI的信号，生成最终交易决策
"""

from typing import Dict, List, Optional
from datetime import datetime

from backend.data.models import Signal, SignalDirection


class SignalFusion:
    """信号融合器"""
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        min_confidence: float = 0.5,
        min_agreement: float = 0.6
    ):
        """
        初始化信号融合器
        
        Args:
            weights: 各信号源的权重
            min_confidence: 最小置信度阈值
            min_agreement: 最小一致性阈值（多数信号同方向的比例）
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
        融合多个信号
        
        Args:
            signals: 信号列表
            
        Returns:
            融合后的信号
        """
        if not signals:
            return self._empty_signal()
        
        # 过滤无效信号
        valid_signals = [s for s in signals if s.is_valid and s.confidence >= self.min_confidence]
        
        if not valid_signals:
            return self._empty_signal()
        
        # 统计各方向的加权得分
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
        
        # 归一化得分
        if total_weight > 0:
            for direction in direction_scores:
                direction_scores[direction] /= total_weight
        
        # 选择最高得分的方向
        best_direction = max(direction_scores, key=direction_scores.get)
        best_score = direction_scores[best_direction]
        
        # 计算一致性（同方向信号的比例）
        total_signals = len(valid_signals)
        agreement = direction_counts[best_direction] / total_signals if total_signals > 0 else 0
        
        # 检查一致性阈值
        if agreement < self.min_agreement and best_direction != SignalDirection.NEUTRAL:
            # 一致性不足，降级为中性
            return Signal(
                symbol=valid_signals[0].symbol,
                direction=SignalDirection.NEUTRAL,
                strength=0,
                confidence=0,
                source="fusion",
                reason=f"信号一致性不足({agreement:.1%})",
                evidence=evidence
            )
        
        # 计算融合后的置信度
        fused_confidence = min(0.95, best_score * agreement)
        
        # 获取入场价和止损止盈（取第一个有效信号的值）
        entry_price = None
        stop_loss = None
        take_profit = None
        
        for signal in valid_signals:
            if signal.direction == best_direction:
                entry_price = signal.entry_price
                stop_loss = signal.stop_loss
                take_profit = signal.take_profit
                break
        
        # 生成原因
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
        """返回空信号"""
        return Signal(
            symbol="",
            direction=SignalDirection.NEUTRAL,
            strength=0,
            confidence=0,
            source="fusion",
            reason="No valid signals"
        )
    
    def update_weights(self, weights: Dict[str, float]):
        """更新权重"""
        self.weights.update(weights)
