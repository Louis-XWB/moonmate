"""
多Agent协作系统 (Multi-Agent Collaboration System)

这是黑客松的核心创新功能：多个专业AI Agent协作决策
不是单一AI，而是一个"AI交易委员会"
"""

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Agent角色"""
    NEWS_ANALYST = "news_analyst"  # 新闻分析Agent
    TECHNICAL_ANALYST = "technical_analyst"  # 技术分析Agent
    ONCHAIN_ANALYST = "onchain_analyst"  # 链上分析Agent
    RISK_MANAGER = "risk_manager"  # 风控Agent
    DECISION_MAKER = "decision_maker"  # 决策Agent


class VoteDecision(Enum):
    """投票决策"""
    STRONG_LONG = "strong_long"  # 强烈做多
    LONG = "long"  # 做多
    HOLD = "hold"  # 观望
    SHORT = "short"  # 做空
    STRONG_SHORT = "strong_short"  # 强烈做空


@dataclass
class AgentOpinion:
    """Agent意见"""
    agent_role: AgentRole
    agent_name: str
    decision: VoteDecision
    confidence: float  # 0-1
    reasoning: str  # 分析理由
    key_points: List[str] = field(default_factory=list)  # 关键要点
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_role": self.agent_role.value,
            "agent_name": self.agent_name,
            "decision": self.decision.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "key_points": self.key_points,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ConsensusResult:
    """共识结果"""
    final_decision: VoteDecision
    confidence: float  # 综合置信度
    vote_distribution: Dict[str, int]  # 投票分布
    agent_opinions: List[AgentOpinion]  # 所有Agent意见
    debate_summary: str  # 辩论总结
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "final_decision": self.final_decision.value,
            "confidence": self.confidence,
            "vote_distribution": self.vote_distribution,
            "agent_opinions": [op.to_dict() for op in self.agent_opinions],
            "debate_summary": self.debate_summary,
            "timestamp": self.timestamp.isoformat()
        }


class BaseAgent:
    """Agent基类"""
    
    def __init__(self, role: AgentRole, name: str, weight: float = 1.0):
        self.role = role
        self.name = name
        self.weight = weight  # 权重，用于加权投票
        
    async def analyze(self, context: Dict[str, Any]) -> AgentOpinion:
        """分析并给出意见"""
        raise NotImplementedError
        
    def _create_opinion(
        self,
        decision: VoteDecision,
        confidence: float,
        reasoning: str,
        key_points: List[str]
    ) -> AgentOpinion:
        """创建意见"""
        return AgentOpinion(
            agent_role=self.role,
            agent_name=self.name,
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            key_points=key_points
        )


class NewsAnalystAgent(BaseAgent):
    """新闻分析Agent"""
    
    def __init__(self, news_analyzer, weight: float = 1.0):
        super().__init__(AgentRole.NEWS_ANALYST, "📰 新闻分析师", weight)
        self.news_analyzer = news_analyzer
        
    async def analyze(self, context: Dict[str, Any]) -> AgentOpinion:
        """分析新闻影响"""
        try:
            news_impacts = context.get("news_impacts", [])
            
            if not news_impacts:
                return self._create_opinion(
                    VoteDecision.HOLD,
                    0.5,
                    "暂无重要新闻",
                    ["没有3星以上的重要新闻"]
                )
            
            # 计算新闻综合影响
            bullish_count = sum(1 for n in news_impacts if n.get("impact_direction") == "bullish")
            bearish_count = sum(1 for n in news_impacts if n.get("impact_direction") == "bearish")
            avg_score = sum(n.get("impact_score", 0) for n in news_impacts) / len(news_impacts)
            
            # 决策逻辑
            if avg_score > 0.4:
                decision = VoteDecision.STRONG_LONG
                confidence = min(0.9, 0.6 + abs(avg_score))
            elif avg_score > 0.2:
                decision = VoteDecision.LONG
                confidence = 0.7
            elif avg_score < -0.4:
                decision = VoteDecision.STRONG_SHORT
                confidence = min(0.9, 0.6 + abs(avg_score))
            elif avg_score < -0.2:
                decision = VoteDecision.SHORT
                confidence = 0.7
            else:
                decision = VoteDecision.HOLD
                confidence = 0.6
            
            # 生成理由和要点
            reasoning = f"分析了{len(news_impacts)}条重要新闻，"
            if bullish_count > bearish_count:
                reasoning += f"利好新闻占主导({bullish_count}条利好 vs {bearish_count}条利空)"
            elif bearish_count > bullish_count:
                reasoning += f"利空新闻占主导({bearish_count}条利空 vs {bullish_count}条利好)"
            else:
                reasoning += "利好利空新闻相当"
            
            key_points = []
            for news in news_impacts[:3]:  # 最多3条
                direction_emoji = "📈" if news.get("impact_direction") == "bullish" else "📉" if news.get("impact_direction") == "bearish" else "➡️"
                key_points.append(f"{direction_emoji} {news.get('title', '')[:50]}...")
            
            return self._create_opinion(decision, confidence, reasoning, key_points)
            
        except Exception as e:
            logger.error(f"NewsAnalystAgent error: {e}")
            return self._create_opinion(
                VoteDecision.HOLD,
                0.5,
                f"新闻分析出错: {str(e)}",
                []
            )


class TechnicalAnalystAgent(BaseAgent):
    """技术分析Agent"""
    
    def __init__(self, weight: float = 1.0):
        super().__init__(AgentRole.TECHNICAL_ANALYST, "📊 技术分析师", weight)
        
    async def analyze(self, context: Dict[str, Any]) -> AgentOpinion:
        """分析技术指标"""
        try:
            ticker = context.get("ticker", {})
            klines = context.get("klines", [])
            
            if not ticker or not klines:
                return self._create_opinion(
                    VoteDecision.HOLD,
                    0.5,
                    "数据不足，无法分析",
                    ["缺少价格或K线数据"]
                )
            
            # 简单的技术分析逻辑
            current_price = float(ticker.get("last", 0))
            
            # 计算移动平均线
            closes = [float(k.get("close", 0)) for k in klines[-20:]]
            ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else current_price
            ma20 = sum(closes) / len(closes) if closes else current_price
            
            # 计算RSI（简化版）
            changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
            gains = [c for c in changes if c > 0]
            losses = [-c for c in changes if c < 0]
            avg_gain = sum(gains) / len(gains) if gains else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            rsi = 100 - (100 / (1 + rs))
            
            # 决策逻辑
            key_points = []
            score = 0
            
            # MA交叉
            if ma5 > ma20:
                score += 1
                key_points.append(f"✅ MA5({ma5:.2f}) > MA20({ma20:.2f})，短期趋势向上")
            else:
                score -= 1
                key_points.append(f"❌ MA5({ma5:.2f}) < MA20({ma20:.2f})，短期趋势向下")
            
            # RSI
            if rsi < 30:
                score += 1
                key_points.append(f"✅ RSI({rsi:.1f})超卖，可能反弹")
            elif rsi > 70:
                score -= 1
                key_points.append(f"❌ RSI({rsi:.1f})超买，可能回调")
            else:
                key_points.append(f"➡️ RSI({rsi:.1f})中性")
            
            # 价格位置
            if current_price > ma20 * 1.05:
                score -= 0.5
                key_points.append(f"⚠️ 价格高于MA20 5%以上，谨慎追高")
            elif current_price < ma20 * 0.95:
                score += 0.5
                key_points.append(f"✅ 价格低于MA20 5%以上，可能低吸机会")
            
            # 决策
            if score >= 1.5:
                decision = VoteDecision.LONG
                confidence = 0.75
                reasoning = "技术指标偏多，建议做多"
            elif score <= -1.5:
                decision = VoteDecision.SHORT
                confidence = 0.75
                reasoning = "技术指标偏空，建议做空"
            else:
                decision = VoteDecision.HOLD
                confidence = 0.6
                reasoning = "技术指标中性，建议观望"
            
            return self._create_opinion(decision, confidence, reasoning, key_points)
            
        except Exception as e:
            logger.error(f"TechnicalAnalystAgent error: {e}")
            return self._create_opinion(
                VoteDecision.HOLD,
                0.5,
                f"技术分析出错: {str(e)}",
                []
            )


class OnChainAnalystAgent(BaseAgent):
    """链上分析Agent"""
    
    def __init__(self, whale_tracker, weight: float = 1.0):
        super().__init__(AgentRole.ONCHAIN_ANALYST, "🔗 链上分析师", weight)
        self.whale_tracker = whale_tracker
        
    async def analyze(self, context: Dict[str, Any]) -> AgentOpinion:
        """分析链上大户行为"""
        try:
            symbol = context.get("symbol", "BTC/USDT")
            
            # 获取大户行为分析
            whale_analysis = await self.whale_tracker.analyze_whale_behavior(symbol)
            
            if not whale_analysis:
                return self._create_opinion(
                    VoteDecision.HOLD,
                    0.5,
                    "暂无链上大户数据",
                    ["Hyperliquid链上数据暂不可用"]
                )
            
            # 分析大户行为
            net_flow = whale_analysis.get("net_flow", 0)
            whale_count = whale_analysis.get("whale_count", 0)
            total_volume = whale_analysis.get("total_volume", 0)
            
            key_points = []
            
            # 决策逻辑
            if net_flow > 1000000:  # 净流入>100万
                decision = VoteDecision.STRONG_LONG
                confidence = 0.85
                reasoning = f"大户正在大量买入，净流入${net_flow/1e6:.1f}M"
                key_points.append(f"🐋 {whale_count}个大户正在建仓")
                key_points.append(f"💰 累计买入${total_volume/1e6:.1f}M")
            elif net_flow > 500000:
                decision = VoteDecision.LONG
                confidence = 0.75
                reasoning = f"大户正在买入，净流入${net_flow/1e6:.1f}M"
                key_points.append(f"🐋 {whale_count}个大户正在建仓")
            elif net_flow < -1000000:
                decision = VoteDecision.STRONG_SHORT
                confidence = 0.85
                reasoning = f"大户正在大量卖出，净流出${-net_flow/1e6:.1f}M"
                key_points.append(f"🐋 {whale_count}个大户正在减仓")
                key_points.append(f"💰 累计卖出${-total_volume/1e6:.1f}M")
            elif net_flow < -500000:
                decision = VoteDecision.SHORT
                confidence = 0.75
                reasoning = f"大户正在卖出，净流出${-net_flow/1e6:.1f}M"
                key_points.append(f"🐋 {whale_count}个大户正在减仓")
            else:
                decision = VoteDecision.HOLD
                confidence = 0.6
                reasoning = "大户行为中性，无明显方向"
                key_points.append(f"➡️ 大户资金流动平稳")
            
            return self._create_opinion(decision, confidence, reasoning, key_points)
            
        except Exception as e:
            logger.error(f"OnChainAnalystAgent error: {e}")
            return self._create_opinion(
                VoteDecision.HOLD,
                0.5,
                f"链上分析出错: {str(e)}",
                []
            )


class RiskManagerAgent(BaseAgent):
    """风控Agent"""
    
    def __init__(self, risk_manager, weight: float = 1.0):
        super().__init__(AgentRole.RISK_MANAGER, "🛡️ 风控专家", weight)
        self.risk_manager = risk_manager
        
    async def analyze(self, context: Dict[str, Any]) -> AgentOpinion:
        """分析风险状况"""
        try:
            # 获取风控状态
            risk_status = self.risk_manager.get_status()
            
            current_drawdown = risk_status.get("current_drawdown", 0)
            consecutive_losses = risk_status.get("consecutive_losses", 0)
            daily_pnl = risk_status.get("daily_pnl", 0)
            
            key_points = []
            warnings = []
            
            # 风险评估
            risk_score = 0
            
            # 回撤检查
            if current_drawdown > 0.08:
                risk_score -= 2
                warnings.append(f"⚠️ 当前回撤{current_drawdown*100:.1f}%，超过警戒线")
            elif current_drawdown > 0.05:
                risk_score -= 1
                warnings.append(f"⚠️ 当前回撤{current_drawdown*100:.1f}%，接近警戒线")
            else:
                key_points.append(f"✅ 当前回撤{current_drawdown*100:.1f}%，风险可控")
            
            # 连续亏损检查
            if consecutive_losses >= 3:
                risk_score -= 2
                warnings.append(f"⚠️ 连续亏损{consecutive_losses}次，建议休息")
            elif consecutive_losses >= 2:
                risk_score -= 1
                warnings.append(f"⚠️ 连续亏损{consecutive_losses}次，谨慎交易")
            else:
                key_points.append(f"✅ 连续亏损{consecutive_losses}次，状态良好")
            
            # 日盈亏检查
            if daily_pnl < -1000:
                risk_score -= 1
                warnings.append(f"⚠️ 今日亏损${-daily_pnl:.0f}，建议控制仓位")
            elif daily_pnl > 1000:
                key_points.append(f"✅ 今日盈利${daily_pnl:.0f}，状态良好")
            
            # 决策
            if risk_score <= -3:
                decision = VoteDecision.HOLD
                confidence = 0.9
                reasoning = "风险过高，强烈建议停止交易"
                key_points = warnings
            elif risk_score <= -1:
                decision = VoteDecision.HOLD
                confidence = 0.75
                reasoning = "存在风险，建议谨慎交易或观望"
                key_points = warnings + key_points
            else:
                decision = VoteDecision.HOLD
                confidence = 0.6
                reasoning = "风险可控，可以正常交易"
            
            return self._create_opinion(decision, confidence, reasoning, key_points)
            
        except Exception as e:
            logger.error(f"RiskManagerAgent error: {e}")
            return self._create_opinion(
                VoteDecision.HOLD,
                0.7,
                f"风控分析出错: {str(e)}，建议谨慎",
                []
            )


class DecisionMakerAgent(BaseAgent):
    """决策Agent"""
    
    def __init__(self, weight: float = 1.0):
        super().__init__(AgentRole.DECISION_MAKER, "🎯 决策者", weight)
        
    def make_consensus(self, opinions: List[AgentOpinion]) -> ConsensusResult:
        """基于所有Agent意见做出共识决策"""
        try:
            if not opinions:
                return ConsensusResult(
                    final_decision=VoteDecision.HOLD,
                    confidence=0.5,
                    vote_distribution={},
                    agent_opinions=[],
                    debate_summary="没有Agent意见"
                )
            
            # 统计投票分布
            vote_distribution = {}
            weighted_scores = {}
            
            # 决策映射到分数
            decision_scores = {
                VoteDecision.STRONG_LONG: 2,
                VoteDecision.LONG: 1,
                VoteDecision.HOLD: 0,
                VoteDecision.SHORT: -1,
                VoteDecision.STRONG_SHORT: -2
            }
            
            for opinion in opinions:
                decision_name = opinion.decision.value
                vote_distribution[decision_name] = vote_distribution.get(decision_name, 0) + 1
                
                # 加权计算
                score = decision_scores[opinion.decision]
                weight = 1.0  # 可以根据Agent角色调整权重
                weighted_scores[opinion.agent_role] = score * weight * opinion.confidence
            
            # 计算综合分数
            total_score = sum(weighted_scores.values())
            avg_confidence = sum(op.confidence for op in opinions) / len(opinions)
            
            # 决定最终决策
            if total_score >= 1.5:
                final_decision = VoteDecision.STRONG_LONG
            elif total_score >= 0.5:
                final_decision = VoteDecision.LONG
            elif total_score <= -1.5:
                final_decision = VoteDecision.STRONG_SHORT
            elif total_score <= -0.5:
                final_decision = VoteDecision.SHORT
            else:
                final_decision = VoteDecision.HOLD
            
            # 生成辩论总结
            debate_summary = self._generate_debate_summary(opinions, final_decision, total_score)
            
            return ConsensusResult(
                final_decision=final_decision,
                confidence=min(0.95, avg_confidence),
                vote_distribution=vote_distribution,
                agent_opinions=opinions,
                debate_summary=debate_summary
            )
            
        except Exception as e:
            logger.error(f"DecisionMakerAgent error: {e}")
            return ConsensusResult(
                final_decision=VoteDecision.HOLD,
                confidence=0.5,
                vote_distribution={},
                agent_opinions=opinions,
                debate_summary=f"决策出错: {str(e)}"
            )
    
    def _generate_debate_summary(
        self,
        opinions: List[AgentOpinion],
        final_decision: VoteDecision,
        total_score: float
    ) -> str:
        """生成辩论总结"""
        long_agents = [op for op in opinions if op.decision in [VoteDecision.LONG, VoteDecision.STRONG_LONG]]
        short_agents = [op for op in opinions if op.decision in [VoteDecision.SHORT, VoteDecision.STRONG_SHORT]]
        hold_agents = [op for op in opinions if op.decision == VoteDecision.HOLD]
        
        summary = f"AI委员会投票结果：{len(long_agents)}票做多，{len(short_agents)}票做空，{len(hold_agents)}票观望。"
        
        if final_decision in [VoteDecision.STRONG_LONG, VoteDecision.LONG]:
            summary += f"综合评分{total_score:.2f}，多方占优，最终决定做多。"
        elif final_decision in [VoteDecision.STRONG_SHORT, VoteDecision.SHORT]:
            summary += f"综合评分{total_score:.2f}，空方占优，最终决定做空。"
        else:
            summary += f"综合评分{total_score:.2f}，多空分歧，最终决定观望。"
        
        return summary


class MultiAgentSystem:
    """多Agent协作系统"""
    
    def __init__(
        self,
        news_analyzer,
        whale_tracker,
        risk_manager
    ):
        self.news_analyst = NewsAnalystAgent(news_analyzer)
        self.technical_analyst = TechnicalAnalystAgent()
        self.onchain_analyst = OnChainAnalystAgent(whale_tracker)
        self.risk_manager_agent = RiskManagerAgent(risk_manager)
        self.decision_maker = DecisionMakerAgent()
        
        self.agents = [
            self.news_analyst,
            self.technical_analyst,
            self.onchain_analyst,
            self.risk_manager_agent
        ]
        
    async def deliberate(self, context: Dict[str, Any]) -> ConsensusResult:
        """AI委员会讨论并做出决策"""
        logger.info("🗳️ AI委员会开始讨论...")
        
        # 并发收集所有Agent意见
        tasks = [agent.analyze(context) for agent in self.agents]
        opinions = await asyncio.gather(*tasks)
        
        # 决策Agent做出最终决策
        consensus = self.decision_maker.make_consensus(opinions)
        
        logger.info(f"🎯 最终决策: {consensus.final_decision.value} (置信度: {consensus.confidence:.2f})")
        
        return consensus
