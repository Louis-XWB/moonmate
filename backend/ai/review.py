"""
AI交易复盘模块
使用LLM分析历史交易，总结经验教训
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field
from openai import OpenAI

from backend.data.models import Order, Position
from backend.core.logger import get_logger

logger = get_logger("ai_review")


class ReviewType(str, Enum):
    """复盘类型"""
    SINGLE_TRADE = "single_trade"  # 单笔交易
    DAILY = "daily"  # 日度复盘
    WEEKLY = "weekly"  # 周度复盘
    STRATEGY = "strategy"  # 策略复盘


class TradeReview(BaseModel):
    """交易复盘结果"""
    review_type: ReviewType
    period: str = Field(..., description="复盘周期，如 '2024-01-28' 或 '2024-W04'")
    
    # 交易统计
    total_trades: int = Field(default=0)
    winning_trades: int = Field(default=0)
    losing_trades: int = Field(default=0)
    win_rate: float = Field(default=0, ge=0, le=1)
    
    # 盈亏统计
    total_pnl: float = Field(default=0)
    total_pnl_pct: float = Field(default=0)
    avg_win: float = Field(default=0)
    avg_loss: float = Field(default=0)
    profit_factor: float = Field(default=0)
    
    # AI分析
    performance_rating: str = Field(default="", description="表现评级: excellent/good/average/poor")
    strengths: List[str] = Field(default_factory=list, description="优势")
    weaknesses: List[str] = Field(default_factory=list, description="劣势")
    lessons_learned: List[str] = Field(default_factory=list, description="经验教训")
    suggestions: List[str] = Field(default_factory=list, description="改进建议")
    summary: str = Field(default="", description="总结")
    
    timestamp: datetime = Field(default_factory=datetime.now)


class AIReviewer:
    """AI复盘分析器"""
    
    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        temperature: float = 0.3
    ):
        self.model = model
        self.temperature = temperature
        self.client = OpenAI()
    
    async def review_single_trade(
        self,
        order: Order,
        market_context: Optional[Dict] = None
    ) -> TradeReview:
        """复盘单笔交易"""
        
        # 计算交易统计
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
        
        # 构建提示词
        prompt = self._build_single_trade_prompt(order, stats, market_context)
        
        try:
            # 调用LLM
            response = await asyncio.to_thread(
                self._call_llm,
                prompt
            )
            
            # 解析响应
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
        """复盘一段时间的交易"""
        
        if not orders:
            return self._create_fallback_review(review_type, {})
        
        # 计算统计数据
        stats = self._calculate_stats(orders)
        
        # 确定周期
        if review_type == ReviewType.DAILY:
            period = orders[0].created_at.strftime("%Y-%m-%d")
        elif review_type == ReviewType.WEEKLY:
            period = orders[0].created_at.strftime("%Y-W%W")
        else:
            period = f"{orders[0].created_at.strftime('%Y-%m-%d')} to {orders[-1].created_at.strftime('%Y-%m-%d')}"
        
        # 构建提示词
        prompt = self._build_period_prompt(orders, stats, review_type, market_context)
        
        try:
            # 调用LLM
            response = await asyncio.to_thread(
                self._call_llm,
                prompt
            )
            
            # 解析响应
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
        """计算交易统计"""
        total_trades = len(orders)
        winning_trades = sum(1 for o in orders if (o.realized_pnl or 0) > 0)
        losing_trades = sum(1 for o in orders if (o.realized_pnl or 0) < 0)
        
        total_pnl = sum(o.realized_pnl or 0 for o in orders)
        
        wins = [o.realized_pnl for o in orders if (o.realized_pnl or 0) > 0]
        losses = [abs(o.realized_pnl) for o in orders if (o.realized_pnl or 0) < 0]
        
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        
        profit_factor = sum(wins) / sum(losses) if losses and sum(losses) > 0 else 0
        
        # 计算总盈亏百分比
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
        """构建单笔交易复盘提示词"""
        
        system_prompt = """你是一个专业的交易教练，擅长分析交易决策并提供建设性反馈。

你的任务是复盘一笔交易，分析其成功或失败的原因，并给出改进建议。

你必须以JSON格式输出，包含以下字段：
- performance_rating: "excellent"(优秀), "good"(良好), "average"(一般), 或 "poor"(差)
- strengths: 2-3个优势的列表
- weaknesses: 2-3个劣势的列表
- lessons_learned: 2-3个经验教训的列表
- suggestions: 2-3个改进建议的列表
- summary: 一句话总结（30字以内）

评估标准：
1. 进场时机是否合理
2. 止损止盈设置是否恰当
3. 仓位管理是否合理
4. 是否遵守交易纪律
5. 是否考虑了市场环境

注意事项：
1. 保持客观，既要肯定优点也要指出不足
2. 建议要具体可执行
3. 即使是盈利的交易也可能有改进空间
4. 即使是亏损的交易也可能有可取之处"""

        trade_info = f"""
交易信息：
- 币种: {order.symbol}
- 方向: {order.side} ({order.direction})
- 数量: {order.quantity}
- 进场价: ${order.avg_fill_price:.2f}
- 止损价: ${order.stop_loss:.2f if order.stop_loss else 'N/A'}
- 止盈价: ${order.take_profit:.2f if order.take_profit else 'N/A'}
- 盈亏: ${stats['total_pnl']:.2f} ({stats['total_pnl_pct']:+.2f}%)
- 状态: {order.status}
"""

        context_info = ""
        if market_context:
            context_info = f"\n市场环境:\n{json.dumps(market_context, ensure_ascii=False, indent=2)}"
        
        user_prompt = f"""
请复盘以下交易：

{trade_info}
{context_info}

请给出你的复盘分析（JSON格式）：
"""
        
        return f"{system_prompt}\n\n{user_prompt}"
    
    def _build_period_prompt(
        self,
        orders: List[Order],
        stats: Dict,
        review_type: ReviewType,
        market_context: Optional[Dict]
    ) -> str:
        """构建周期复盘提示词"""
        
        system_prompt = """你是一个专业的交易教练，擅长分析交易表现并提供战略性建议。

你的任务是复盘一段时间的交易表现，分析整体策略的有效性，并给出改进方向。

你必须以JSON格式输出，包含以下字段：
- performance_rating: "excellent"(优秀), "good"(良好), "average"(一般), 或 "poor"(差)
- strengths: 3-5个优势的列表
- weaknesses: 3-5个劣势的列表
- lessons_learned: 3-5个经验教训的列表
- suggestions: 3-5个改进建议的列表
- summary: 一句话总结（50字以内）

评估标准：
1. 胜率和盈亏比是否健康
2. 交易频率是否合理
3. 风险控制是否到位
4. 策略执行是否一致
5. 是否适应市场变化

注意事项：
1. 关注整体表现而非个别交易
2. 识别系统性问题
3. 建议要有战略高度
4. 考虑心理因素和纪律性"""

        stats_info = f"""
交易统计：
- 总交易数: {stats['total_trades']}
- 盈利交易: {stats['winning_trades']}
- 亏损交易: {stats['losing_trades']}
- 胜率: {stats['win_rate']:.1%}
- 总盈亏: ${stats['total_pnl']:.2f} ({stats['total_pnl_pct']:+.2f}%)
- 平均盈利: ${stats['avg_win']:.2f}
- 平均亏损: ${stats['avg_loss']:.2f}
- 盈亏比: {stats['profit_factor']:.2f}
"""

        # 列出部分交易详情
        trades_sample = []
        for i, order in enumerate(orders[:5]):  # 最多显示5笔
            pnl = order.realized_pnl or 0
            trades_sample.append(
                f"{i+1}. {order.symbol} {order.side} "
                f"${order.avg_fill_price:.2f} → "
                f"{'盈利' if pnl > 0 else '亏损'} ${abs(pnl):.2f}"
            )
        
        trades_info = "\n".join(trades_sample)
        if len(orders) > 5:
            trades_info += f"\n... 还有 {len(orders) - 5} 笔交易"
        
        context_info = ""
        if market_context:
            context_info = f"\n市场环境:\n{json.dumps(market_context, ensure_ascii=False, indent=2)}"
        
        user_prompt = f"""
请复盘以下 {review_type.value} 的交易表现：

{stats_info}

部分交易详情：
{trades_info}
{context_info}

请给出你的复盘分析（JSON格式）：
"""
        
        return f"{system_prompt}\n\n{user_prompt}"
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=800
        )
        return response.choices[0].message.content
    
    def _parse_response(
        self,
        review_type: ReviewType,
        period: str,
        stats: Dict,
        response: str
    ) -> TradeReview:
        """解析LLM响应"""
        try:
            # 提取JSON部分
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")
            
            # 创建复盘结果
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
        """创建降级复盘结果"""
        return TradeReview(
            review_type=review_type,
            period=period or datetime.now().strftime("%Y-%m-%d"),
            **stats,
            performance_rating="unknown",
            summary="AI分析暂时不可用"
        )
