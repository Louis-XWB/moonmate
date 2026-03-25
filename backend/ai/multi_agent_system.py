"""
Multi-Agent Collaboration System

Core hackathon innovation: multiple specialized AI Agents collaborate on decisions
Not a single AI, but an "AI Trading Committee"
"""

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Agent role"""
    NEWS_ANALYST = "news_analyst"  # News Analyst Agent
    TECHNICAL_ANALYST = "technical_analyst"  # Technical Analyst Agent
    ONCHAIN_ANALYST = "onchain_analyst"  # On-chain Analyst Agent
    RISK_MANAGER = "risk_manager"  # Risk Control Agent
    DECISION_MAKER = "decision_maker"  # Decision Maker Agent


class VoteDecision(Enum):
    """Vote decision"""
    STRONG_LONG = "strong_long"  # Strong Long
    LONG = "long"  # Long
    HOLD = "hold"  # Hold
    SHORT = "short"  # Short
    STRONG_SHORT = "strong_short"  # Strong Short


@dataclass
class AgentOpinion:
    """Agent opinion"""
    agent_role: AgentRole
    agent_name: str
    decision: VoteDecision
    confidence: float  # 0-1
    reasoning: str  # Analysis reasoning
    key_points: List[str] = field(default_factory=list)  # Key takeaways
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
    """Consensus result"""
    final_decision: VoteDecision
    confidence: float  # Overall confidence
    vote_distribution: Dict[str, int]  # Vote distribution
    agent_opinions: List[AgentOpinion]  # All agent opinions
    debate_summary: str  # Debate summary
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
    """Agent base class"""
    
    def __init__(self, role: AgentRole, name: str, weight: float = 1.0):
        self.role = role
        self.name = name
        self.weight = weight  # Weight for weighted voting
        
    async def analyze(self, context: Dict[str, Any]) -> AgentOpinion:
        """Analyze and provide opinion"""
        raise NotImplementedError
        
    def _create_opinion(
        self,
        decision: VoteDecision,
        confidence: float,
        reasoning: str,
        key_points: List[str]
    ) -> AgentOpinion:
        """Create opinion"""
        return AgentOpinion(
            agent_role=self.role,
            agent_name=self.name,
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            key_points=key_points
        )


class NewsAnalystAgent(BaseAgent):
    """News Analyst Agent"""
    
    def __init__(self, news_analyzer, weight: float = 1.0):
        super().__init__(AgentRole.NEWS_ANALYST, "📰 News Analyst", weight)
        self.news_analyzer = news_analyzer
        
    async def analyze(self, context: Dict[str, Any]) -> AgentOpinion:
        """Analyze news impact"""
        try:
            news_impacts = context.get("news_impacts", [])
            
            if not news_impacts:
                return self._create_opinion(
                    VoteDecision.HOLD,
                    0.5,
                    "No significant news available",
                    ["No important news with 3+ star rating"]
                )
            
            # Calculate combined news impact
            def _dir(n): return n.impact_direction.value if hasattr(n.impact_direction, 'value') else str(n.impact_direction)
            def _score(n): return float(n.impact_score) if hasattr(n, 'impact_score') else 0
            def _title(n): return str(n.title) if hasattr(n, 'title') else ''
            bullish_count = sum(1 for n in news_impacts if _dir(n) == "bullish")
            bearish_count = sum(1 for n in news_impacts if _dir(n) == "bearish")
            avg_score = sum(_score(n) for n in news_impacts) / len(news_impacts)
            
            # Decision logic
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
            
            # Generate reasoning and key points
            reasoning = f"Analyzed {len(news_impacts)} important news items, "
            if bullish_count > bearish_count:
                reasoning += f"Bullish news dominates({bullish_count} bullish vs {bearish_count} bearish)"
            elif bearish_count > bullish_count:
                reasoning += f"Bearish news dominates({bearish_count} bearish vs {bullish_count} bullish)"
            else:
                reasoning += "Bullish and bearish news are balanced"
            
            key_points = []
            for news in news_impacts[:3]:  # Up to 3 items
                direction_emoji = "📈" if _dir(news) == "bullish" else "📉" if _dir(news) == "bearish" else "➡️"
                key_points.append(f"{direction_emoji} {_title(news)[:50]}...")
            
            return self._create_opinion(decision, confidence, reasoning, key_points)
            
        except Exception as e:
            logger.error(f"NewsAnalystAgent error: {e}")
            return self._create_opinion(
                VoteDecision.HOLD,
                0.5,
                f"News analysis error: {str(e)}",
                []
            )


class TechnicalAnalystAgent(BaseAgent):
    """Technical Analyst Agent"""
    
    def __init__(self, weight: float = 1.0):
        super().__init__(AgentRole.TECHNICAL_ANALYST, "📊 Technical Analyst", weight)
        
    async def analyze(self, context: Dict[str, Any]) -> AgentOpinion:
        """Analyze technical indicators"""
        try:
            ticker = context.get("ticker", {})
            klines = context.get("klines", [])
            
            if not ticker or not klines:
                return self._create_opinion(
                    VoteDecision.HOLD,
                    0.5,
                    "Insufficient data for analysis",
                    ["Missing price or candlestick data"]
                )
            
            # Simple technical analysis logic
            current_price = float(ticker.last_price) if hasattr(ticker, 'last_price') else float(ticker.get("last", 0))

            # Calculate moving averages
            closes = [float(k.close) if hasattr(k, 'close') else float(k.get("close", 0)) for k in klines[-20:]]
            ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else current_price
            ma20 = sum(closes) / len(closes) if closes else current_price
            
            # Calculate RSI (simplified)
            changes = [closes[i] - closes[i-1] for i in range(1, len(closes))]
            gains = [c for c in changes if c > 0]
            losses = [-c for c in changes if c < 0]
            avg_gain = sum(gains) / len(gains) if gains else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            rs = avg_gain / avg_loss if avg_loss > 0 else 100
            rsi = 100 - (100 / (1 + rs))
            
            # Decision logic
            key_points = []
            score = 0
            
            # MA crossover
            if ma5 > ma20:
                score += 1
                key_points.append(f"✅ MA5({ma5:.2f}) > MA20({ma20:.2f}), short-term trend is up")
            else:
                score -= 1
                key_points.append(f"❌ MA5({ma5:.2f}) < MA20({ma20:.2f}), short-term trend is down")
            
            # RSI
            if rsi < 30:
                score += 1
                key_points.append(f"✅ RSI({rsi:.1f})oversold, possible rebound")
            elif rsi > 70:
                score -= 1
                key_points.append(f"❌ RSI({rsi:.1f})overbought, possible pullback")
            else:
                key_points.append(f"➡️ RSI({rsi:.1f})neutral")
            
            # Price position
            if current_price > ma20 * 1.05:
                score -= 0.5
                key_points.append(f"⚠️ Price >5% above MA20, be cautious chasing highs")
            elif current_price < ma20 * 0.95:
                score += 0.5
                key_points.append(f"✅ Price >5% below MA20, possible buying opportunity")
            
            # Decision
            if score >= 1.5:
                decision = VoteDecision.LONG
                confidence = 0.75
                reasoning = "Technical indicators are bullish, recommend long"
            elif score <= -1.5:
                decision = VoteDecision.SHORT
                confidence = 0.75
                reasoning = "Technical indicators are bearish, recommend short"
            else:
                decision = VoteDecision.HOLD
                confidence = 0.6
                reasoning = "Technical indicators are neutral, recommend hold"
            
            return self._create_opinion(decision, confidence, reasoning, key_points)
            
        except Exception as e:
            logger.error(f"TechnicalAnalystAgent error: {e}")
            return self._create_opinion(
                VoteDecision.HOLD,
                0.5,
                f"Technical analysis error: {str(e)}",
                []
            )


class OnChainAnalystAgent(BaseAgent):
    """On-chain Analyst Agent"""
    
    def __init__(self, whale_tracker, weight: float = 1.0):
        super().__init__(AgentRole.ONCHAIN_ANALYST, "🔗 On-chain Analyst", weight)
        self.whale_tracker = whale_tracker
        
    async def analyze(self, context: Dict[str, Any]) -> AgentOpinion:
        """Analyze on-chain whale behavior"""
        try:
            symbol = context.get("symbol", "BTC/USDT")
            
            # Get whale behavior analysis
            whale_analysis = await self.whale_tracker.analyze_whale_behavior(symbol)
            
            if not whale_analysis:
                return self._create_opinion(
                    VoteDecision.HOLD,
                    0.5,
                    "No on-chain whale data available",
                    ["Hyperliquid on-chain data temporarily unavailable"]
                )
            
            # Analyze whale behavior
            net_flow = whale_analysis.get("net_flow", 0)
            whale_count = whale_analysis.get("whale_count", 0)
            total_volume = whale_analysis.get("total_volume", 0)
            
            key_points = []
            
            # Decision logic
            if net_flow > 1000000:  # Net inflow > 1M
                decision = VoteDecision.STRONG_LONG
                confidence = 0.85
                reasoning = f"Whales are buying heavily, net inflow ${net_flow/1e6:.1f}M"
                key_points.append(f"🐋 {whale_count} whales are accumulating")
                key_points.append(f"💰 Total bought ${total_volume/1e6:.1f}M")
            elif net_flow > 500000:
                decision = VoteDecision.LONG
                confidence = 0.75
                reasoning = f"Whales are buying, net inflow ${net_flow/1e6:.1f}M"
                key_points.append(f"🐋 {whale_count} whales are accumulating")
            elif net_flow < -1000000:
                decision = VoteDecision.STRONG_SHORT
                confidence = 0.85
                reasoning = f"Whales are selling heavily, net outflow ${-net_flow/1e6:.1f}M"
                key_points.append(f"🐋 {whale_count} whales are reducing positions")
                key_points.append(f"💰 Total sold ${-total_volume/1e6:.1f}M")
            elif net_flow < -500000:
                decision = VoteDecision.SHORT
                confidence = 0.75
                reasoning = f"Whales are selling, net outflow ${-net_flow/1e6:.1f}M"
                key_points.append(f"🐋 {whale_count} whales are reducing positions")
            else:
                decision = VoteDecision.HOLD
                confidence = 0.6
                reasoning = "Whale activity neutral, no clear direction"
                key_points.append(f"➡️ Whale fund flow is stable")
            
            return self._create_opinion(decision, confidence, reasoning, key_points)
            
        except Exception as e:
            logger.error(f"OnChainAnalystAgent error: {e}")
            return self._create_opinion(
                VoteDecision.HOLD,
                0.5,
                f"On-chain analysis error: {str(e)}",
                []
            )


class RiskManagerAgent(BaseAgent):
    """Risk Control Agent"""
    
    def __init__(self, risk_manager, weight: float = 1.0):
        super().__init__(AgentRole.RISK_MANAGER, "🛡️ Risk Control Expert", weight)
        self.risk_manager = risk_manager
        
    async def analyze(self, context: Dict[str, Any]) -> AgentOpinion:
        """Analyze risk status"""
        try:
            # Get risk control status
            risk_state = self.risk_manager.get_state()

            current_drawdown = getattr(risk_state, 'current_drawdown', 0)
            consecutive_losses = getattr(risk_state, 'consecutive_losses', 0)
            daily_pnl = getattr(risk_state, 'daily_pnl', 0)
            
            key_points = []
            warnings = []
            
            # Risk assessment
            risk_score = 0
            
            # Drawdown check
            if current_drawdown > 0.08:
                risk_score -= 2
                warnings.append(f"⚠️ Current drawdown {current_drawdown*100:.1f}%, exceeds warning threshold")
            elif current_drawdown > 0.05:
                risk_score -= 1
                warnings.append(f"⚠️ Current drawdown {current_drawdown*100:.1f}%, approaching warning threshold")
            else:
                key_points.append(f"✅ Current drawdown {current_drawdown*100:.1f}%, risk manageable")
            
            # Consecutive loss check
            if consecutive_losses >= 3:
                risk_score -= 2
                warnings.append(f"⚠️ Consecutive losses {consecutive_losses} times, recommend rest")
            elif consecutive_losses >= 2:
                risk_score -= 1
                warnings.append(f"⚠️ Consecutive losses {consecutive_losses} times, trade cautiously")
            else:
                key_points.append(f"✅ Consecutive losses {consecutive_losses} times, status good")
            
            # Daily P&L check
            if daily_pnl < -1000:
                risk_score -= 1
                warnings.append(f"⚠️ Today's loss ${-daily_pnl:.0f}, recommend reducing position size")
            elif daily_pnl > 1000:
                key_points.append(f"✅ Today's profit ${daily_pnl:.0f}, status good")
            
            # Decision
            if risk_score <= -3:
                decision = VoteDecision.HOLD
                confidence = 0.9
                reasoning = "Risk too high, strongly recommend stopping trading"
                key_points = warnings
            elif risk_score <= -1:
                decision = VoteDecision.HOLD
                confidence = 0.75
                reasoning = "Risk exists, recommend cautious trading or holding"
                key_points = warnings + key_points
            else:
                decision = VoteDecision.HOLD
                confidence = 0.6
                reasoning = "Risk manageable, normal trading permitted"
            
            return self._create_opinion(decision, confidence, reasoning, key_points)
            
        except Exception as e:
            logger.error(f"RiskManagerAgent error: {e}")
            return self._create_opinion(
                VoteDecision.HOLD,
                0.7,
                f"Risk analysis error: {str(e)}, recommend caution",
                []
            )


class DecisionMakerAgent(BaseAgent):
    """Decision Maker Agent"""
    
    def __init__(self, weight: float = 1.0):
        super().__init__(AgentRole.DECISION_MAKER, "🎯 Decision Maker", weight)
        
    def make_consensus(self, opinions: List[AgentOpinion]) -> ConsensusResult:
        """Make consensus decision based on all Agent opinions"""
        try:
            if not opinions:
                return ConsensusResult(
                    final_decision=VoteDecision.HOLD,
                    confidence=0.5,
                    vote_distribution={},
                    agent_opinions=[],
                    debate_summary="No Agent opinions"
                )
            
            # Count vote distribution
            vote_distribution = {}
            weighted_scores = {}
            
            # Map decisions to scores
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
                
                # Weighted calculation
                score = decision_scores[opinion.decision]
                weight = 1.0  # Weight can be adjusted by Agent role
                weighted_scores[opinion.agent_role] = score * weight * opinion.confidence
            
            # Calculate combined score
            total_score = sum(weighted_scores.values())
            avg_confidence = sum(op.confidence for op in opinions) / len(opinions)
            
            # Determine final decision
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
            
            # Generate debate summary
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
                debate_summary=f"Decision error: {str(e)}"
            )
    
    def _generate_debate_summary(
        self,
        opinions: List[AgentOpinion],
        final_decision: VoteDecision,
        total_score: float
    ) -> str:
        """Generate debate summary"""
        long_agents = [op for op in opinions if op.decision in [VoteDecision.LONG, VoteDecision.STRONG_LONG]]
        short_agents = [op for op in opinions if op.decision in [VoteDecision.SHORT, VoteDecision.STRONG_SHORT]]
        hold_agents = [op for op in opinions if op.decision == VoteDecision.HOLD]
        
        summary = f"AI Committee vote results: {len(long_agents)} votes long, {len(short_agents)} votes short, {len(hold_agents)} votes hold. "
        
        if final_decision in [VoteDecision.STRONG_LONG, VoteDecision.LONG]:
            summary += f"Combined score{total_score:.2f}, bulls dominate, final decision: long."
        elif final_decision in [VoteDecision.STRONG_SHORT, VoteDecision.SHORT]:
            summary += f"Combined score{total_score:.2f}, bears dominate, final decision: short."
        else:
            summary += f"Combined score{total_score:.2f}, bulls and bears divided, final decision: hold."
        
        return summary


class MultiAgentSystem:
    """Multi-Agent collaboration system"""
    
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
        """AI committee deliberates and makes decision"""
        logger.info("AI Committee deliberation started...")
        
        # Collect all Agent opinions concurrently
        tasks = [agent.analyze(context) for agent in self.agents]
        opinions = await asyncio.gather(*tasks)
        
        # Decision maker Agent makes final decision
        consensus = self.decision_maker.make_consensus(opinions)
        
        logger.info(f"Final decision: {consensus.final_decision.value} (confidence: {consensus.confidence:.2f})")
        
        return consensus
