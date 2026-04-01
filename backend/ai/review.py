"""
AI Trade Review Module
Uses LLM to analyze historical trades and summarize lessons learned
"""

import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field
import httpx

from backend.data.models import Order, Position
from backend.core.logger import get_logger

logger = get_logger("ai_review")


class ReviewType(str, Enum):
    """Review type"""
    SINGLE_TRADE = "single_trade"  # Single trade
    DAILY = "daily"  # Daily review
    WEEKLY = "weekly"  # Weekly review
    STRATEGY = "strategy"  # Strategy review


class TradeReview(BaseModel):
    """Trade review result"""
    review_type: ReviewType
    period: str = Field(..., description="Review period, e.g. '2024-01-28' or '2024-W04'")
    
    # Trade statistics
    total_trades: int = Field(default=0)
    winning_trades: int = Field(default=0)
    losing_trades: int = Field(default=0)
    win_rate: float = Field(default=0, ge=0, le=1)
    
    # P&LStatistics
    total_pnl: float = Field(default=0)
    total_pnl_pct: float = Field(default=0)
    avg_win: float = Field(default=0)
    avg_loss: float = Field(default=0)
    profit_factor: float = Field(default=0)
    
    # AIAnalysis
    performance_rating: str = Field(default="", description="Performance rating: excellent/good/average/poor")
    strengths: List[str] = Field(default_factory=list, description="Strengths")
    weaknesses: List[str] = Field(default_factory=list, description="Weaknesses")
    lessons_learned: List[str] = Field(default_factory=list, description="Lessons learned")
    suggestions: List[str] = Field(default_factory=list, description="Improvement suggestions")
    summary: str = Field(default="", description="Summary")
    
    timestamp: datetime = Field(default_factory=datetime.now)


class AIReviewer:
    """AI trade reviewer"""
    
    def __init__(
        self,
        model: str = "gemini-3-flash-preview",
        temperature: float = 0.3
    ):
        self.model = model
        self.temperature = temperature
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    
    async def review_single_trade(
        self,
        order: Order,
        market_context: Optional[Dict] = None
    ) -> TradeReview:
        """Review a single trade"""
        
        # Calculate trade statistics
        pnl = order.realized_pnl or 0
        pnl_pct = (pnl / order.filled_value * 100) if order.filled_value > 0 else 0
        
        stats = {
            "total_trades": 1,
            "winning_trades": 1 if pnl > 0 else 0,
            "losing_trades": 1 if pnl < 0 else 0,
            "win_rate": 1.0 if pnl > 0 else 0.0,
            "total_pnl": pnl,
            "total_pnl_pct": pnl_pct
        }
        
        # Build prompt
        prompt = self._build_single_trade_prompt(order, stats, market_context)
        
        try:
            # Call LLM
            response = await asyncio.to_thread(
                self._call_llm,
                prompt
            )
            
            # Parse response
            review = self._parse_response(
                ReviewType.SINGLE_TRADE,
                order.created_at.strftime("%Y-%m-%d"),
                stats,
                response
            )
            
            logger.info(f"Reviewed trade {order.order_id}: {review.performance_rating}")
            return review
            
        except Exception as e:
            logger.error(f"Trade review error: {e}")
            return self._create_fallback_review(ReviewType.SINGLE_TRADE, stats)
    
    async def review_period(
        self,
        orders: List[Order],
        review_type: ReviewType = ReviewType.DAILY,
        market_context: Optional[Dict] = None
    ) -> TradeReview:
        """Review trades over a period"""
        
        if not orders:
            return self._create_fallback_review(review_type, {})
        
        # CalculateStatistics
        stats = self._calculate_stats(orders)
        
        # Determine period
        if review_type == ReviewType.DAILY:
            period = orders[0].created_at.strftime("%Y-%m-%d")
        elif review_type == ReviewType.WEEKLY:
            period = orders[0].created_at.strftime("%Y-W%W")
        else:
            period = f"{orders[0].created_at.strftime('%Y-%m-%d')} to {orders[-1].created_at.strftime('%Y-%m-%d')}"
        
        # Build prompt
        prompt = self._build_period_prompt(orders, stats, review_type, market_context)
        
        try:
            # Call LLM
            response = await asyncio.to_thread(
                self._call_llm,
                prompt
            )
            
            # Parse response
            review = self._parse_response(review_type, period, stats, response)
            
            logger.info(
                f"Reviewed {review_type} period {period}: "
                f"{review.performance_rating} ({review.win_rate:.1%} win rate)"
            )
            return review
            
        except Exception as e:
            logger.error(f"Period review error: {e}")
            return self._create_fallback_review(review_type, stats, period)
    
    def _calculate_stats(self, orders: List[Order]) -> Dict:
        """Calculate trade statistics"""
        total_trades = len(orders)
        winning_trades = sum(1 for o in orders if (o.realized_pnl or 0) > 0)
        losing_trades = sum(1 for o in orders if (o.realized_pnl or 0) < 0)
        
        total_pnl = sum(o.realized_pnl or 0 for o in orders)
        
        wins = [o.realized_pnl for o in orders if (o.realized_pnl or 0) > 0]
        losses = [abs(o.realized_pnl) for o in orders if (o.realized_pnl or 0) < 0]
        
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        profit_factor = sum(wins) / sum(losses) if losses and sum(losses) > 0 else 0
        
        # Calculate total P&L percentage
        total_value = sum(o.filled_value for o in orders if o.filled_value > 0)
        total_pnl_pct = (total_pnl / total_value * 100) if total_value > 0 else 0
        
        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": winning_trades / total_trades if total_trades > 0 else 0,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor
        }
    
    def _build_single_trade_prompt(
        self,
        order: Order,
        stats: Dict,
        market_context: Optional[Dict]
    ) -> str:
        """Build single trade review prompt"""
        
        system_prompt = """You are a professional trading coach skilled at analyzing trading decisions and providing constructive feedback.

Your task is to review a trade, analyze the reasons for its success or failure, and provide improvement suggestions.

You must output in JSON format with the following fields:
- performance_rating: "excellent", "good", "average", or "poor"
- strengths: a list of 2-3 strengths
- weaknesses: a list of 2-3 weaknesses
- lessons_learned: a list of 2-3 lessons learned
- suggestions: a list of 2-3 improvement suggestions
- summary: a one-sentence summary (under 30 words)

Evaluation criteria:
1. Was the entry timing reasonable
2. Were stop-loss/take-profit levels appropriate
3. Was position sizing reasonable
4. Was trading discipline followed
5. Was the market environment considered

Guidelines:
1. Stay objective, acknowledge strengths while pointing out weaknesses
2. Suggestions should be specific and actionable
3. Even profitable trades may have room for improvement
4. Even losing trades may have commendable aspects"""

        trade_info = f"""
Trade Information:
- Symbol: {order.symbol}
- Direction: {order.side} ({order.direction})
- Quantity: {order.quantity}
- Entry Price: ${order.avg_fill_price:.2f}
- Stop-loss Price: ${order.stop_loss:.2f if order.stop_loss else 'N/A'}
- Take-profit Price: ${order.take_profit:.2f if order.take_profit else 'N/A'}
- P&L: ${stats['total_pnl']:.2f} ({stats['total_pnl_pct']:+.2f}%)
- Status: {order.status}
"""

        context_info = ""
        if market_context:
            context_info = f"\nMarket Context:\n{json.dumps(market_context, ensure_ascii=False, indent=2)}"
        
        user_prompt = f"""
Please review the following trade:

{trade_info}
{context_info}

Please provide your review analysis (JSON format):
"""
        
        return f"{system_prompt}\n\n{user_prompt}"
    
    def _build_period_prompt(
        self,
        orders: List[Order],
        stats: Dict,
        review_type: ReviewType,
        market_context: Optional[Dict]
    ) -> str:
        """Build period review prompt"""
        
        system_prompt = """You are a professional trading coach skilled at analyzing trading performance and providing strategic advice.

Your task is to review trading performance over a period of time, analyze the effectiveness of the overall strategy, and provide improvement directions.

You must output in JSON format with the following fields:
- performance_rating: "excellent", "good", "average", or "poor"
- strengths: a list of 3-5 strengths
- weaknesses: a list of 3-5 weaknesses
- lessons_learned: a list of 3-5 lessons learned
- suggestions: a list of 3-5 improvement suggestions
- summary: a one-sentence summary (under 50 words)

Evaluation criteria:
1. Are win rate and profit/loss ratio healthy
2. Is trading frequency reasonable
3. Is risk control adequate
4. Is strategy execution consistent
5. Is there adaptation to market changes

Guidelines:
1. Focus on overall performance rather than individual trades
2. Identify systematic issues
3. Suggestions should be strategic
4. Consider psychological factors and discipline"""

        stats_info = f"""
Trade Statistics:
- Total trades: {stats['total_trades']}
- Winning trades: {stats['winning_trades']}
- Losing trades: {stats['losing_trades']}
- Win rate: {stats['win_rate']:.1%}
- Total P&L: ${stats['total_pnl']:.2f} ({stats['total_pnl_pct']:+.2f}%)
- Average win: ${stats['avg_win']:.2f}
- Average loss: ${stats['avg_loss']:.2f}
- Profit factor: {stats['profit_factor']:.2f}
"""

        # List partial trade details
        trades_sample = []
        for i, order in enumerate(orders[:5]):  # Show up to 5 trades
            pnl = order.realized_pnl or 0
            trades_sample.append(
                f"{i+1}. {order.symbol} {order.side} "
                f"${order.avg_fill_price:.2f} → "
                f"{'Profit' if pnl > 0 else 'Loss'} ${abs(pnl):.2f}"
            )
        
        trades_info = "\n".join(trades_sample)
        if len(orders) > 5:
            trades_info += f"\n... and {len(orders) - 5} more trades"
        
        context_info = ""
        if market_context:
            context_info = f"\nMarket Context:\n{json.dumps(market_context, ensure_ascii=False, indent=2)}"
        
        user_prompt = f"""
Please review the following {review_type.value} trading performance:

{stats_info}

Partial trade details:
{trades_info}
{context_info}

Please provide your review analysis (JSON format):
"""
        
        return f"{system_prompt}\n\n{user_prompt}"
    
    def _call_llm(self, prompt: str) -> str:
        """Call LLM"""
        full_prompt = "You are a JSON API. Respond with valid JSON only. No markdown, no code fences, no explanatory text.\n\n" + prompt

        payload = {
            "contents": [{
                "parts": [{"text": full_prompt}]
            }],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": 8192,
                "responseMimeType": "application/json"
            }
        }

        try:
            response = httpx.post(
                f"{self.api_url}?key={self.api_key}",
                json=payload,
                timeout=60.0
            )
            response.raise_for_status()
            data = response.json()
            return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "") or ""
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise
    
    def _parse_response(
        self,
        review_type: ReviewType,
        period: str,
        stats: Dict,
        response: str
    ) -> TradeReview:
        """Parse LLM response"""
        try:
            # Extract JSON part
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")
            
            # Create review result
            review = TradeReview(
                review_type=review_type,
                period=period,
                **stats,
                performance_rating=data.get("performance_rating", "average"),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                lessons_learned=data.get("lessons_learned", []),
                suggestions=data.get("suggestions", []),
                summary=data.get("summary", "")
            )
            
            return review
            
        except Exception as e:
            logger.error(f"Failed to parse review response: {e}")
            return self._create_fallback_review(review_type, stats, period)
    
    def _create_fallback_review(
        self,
        review_type: ReviewType,
        stats: Dict,
        period: str = ""
    ) -> TradeReview:
        """Create fallback review result"""
        return TradeReview(
            review_type=review_type,
            period=period or datetime.now().strftime("%Y-%m-%d"),
            **stats,
            performance_rating="unknown",
            summary="AI analysis temporarily unavailable"
        )
