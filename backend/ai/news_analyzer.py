"""
新闻影响评估模块
使用LLM分析新闻对加密货币价格的影响
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field
from openai import OpenAI

from backend.core.logger import get_logger

logger = get_logger("news_analyzer")


class ImpactLevel(str, Enum):
    """影响等级"""
    CRITICAL = "critical"  # 重大影响
    HIGH = "high"  # 高影响
    MEDIUM = "medium"  # 中等影响
    LOW = "low"  # 低影响
    NONE = "none"  # 无影响


class ImpactDirection(str, Enum):
    """影响方向"""
    BULLISH = "bullish"  # 利好
    BEARISH = "bearish"  # 利空
    NEUTRAL = "neutral"  # 中性


class NewsImpact(BaseModel):
    """新闻影响评估结果"""
    title: str = Field(..., description="新闻标题")
    summary: str = Field(default="", description="新闻摘要")
    impact_level: ImpactLevel = Field(..., description="影响等级")
    impact_direction: ImpactDirection = Field(..., description="影响方向")
    impact_score: float = Field(default=0, ge=-1, le=1, description="影响分数 -1到1")
    importance_stars: int = Field(default=3, ge=1, le=5, description="重要性星级 (1-5星)")
    confidence: float = Field(default=0.5, ge=0, le=1, description="置信度")
    affected_symbols: List[str] = Field(default_factory=list, description="受影响的币种")
    key_points: List[str] = Field(default_factory=list, description="关键要点")
    reasoning: str = Field(default="", description="分析理由")
    timestamp: datetime = Field(default_factory=datetime.now)


class NewsAnalyzer:
    """新闻分析器"""
    
    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        temperature: float = 0.2
    ):
        self.model = model
        self.temperature = temperature
        self.client = OpenAI()
        
        # 新闻缓存
        self._cache: Dict[str, NewsImpact] = {}
    
    async def analyze_news(
        self,
        title: str,
        content: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> NewsImpact:
        """分析单条新闻"""
        
        # 检查缓存
        cache_key = f"{title[:50]}_{symbol or 'all'}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 构建提示词
        prompt = self._build_prompt(title, content, symbol)
        
        try:
            # 调用LLM
            response = await asyncio.to_thread(
                self._call_llm,
                prompt
            )
            
            # 解析响应
            impact = self._parse_response(title, response)
            
            # 缓存结果
            self._cache[cache_key] = impact
            
            logger.info(
                f"Analyzed news: {title[:50]}... -> "
                f"{impact.impact_direction} ({impact.impact_level})"
            )
            return impact
            
        except Exception as e:
            logger.error(f"News analysis error: {e}")
            # 返回中性影响
            return NewsImpact(
                title=title,
                impact_level=ImpactLevel.NONE,
                impact_direction=ImpactDirection.NEUTRAL,
                impact_score=0,
                confidence=0,
                reasoning=f"Analysis failed: {str(e)}"
            )
    
    async def analyze_news_batch(
        self,
        news_list: List[Dict[str, str]],
        symbol: Optional[str] = None
    ) -> List[NewsImpact]:
        """批量分析新闻"""
        tasks = [
            self.analyze_news(
                title=news.get("title", ""),
                content=news.get("content"),
                symbol=symbol
            )
            for news in news_list
        ]
        return await asyncio.gather(*tasks)
    
    def _build_prompt(
        self,
        title: str,
        content: Optional[str],
        symbol: Optional[str]
    ) -> str:
        """构建提示词"""
        
        system_prompt = """你是一个专业的加密货币市场分析师，擅长评估新闻事件对加密货币价格的影响。

你的任务是分析给定的新闻，评估其对加密货币市场的影响。

你必须以JSON格式输出，包含以下字段：
- impact_level: "critical"(重大), "high"(高), "medium"(中等), "low"(低), 或 "none"(无影响)
- impact_direction: "bullish"(利好), "bearish"(利空), 或 "neutral"(中性)
- impact_score: -1到1之间的数值，负数表示利空，正数表示利好
- importance_stars: 1-5之间的整数，表示新闻的重要性星级（1星=不重要, 5星=极其重要）
- confidence: 0-1之间的数值，表示你对这个判断的置信度
- affected_symbols: 受影响的币种列表，如 ["BTC", "ETH"]，如果是全市场影响则返回 ["ALL"]
- key_points: 3-5个关键要点的列表
- reasoning: 简短解释你的判断理由（50字以内）

评估标准：

**影响等级 (impact_level)**:
1. **重大影响 (critical)**: 监管政策、重大黑客事件、主流机构采用、协议重大漏洞
2. **高影响 (high)**: 大型交易所上币、知名投资机构投资、重要技术升级
3. **中等影响 (medium)**: 一般性合作、小型交易所事件、行业报告
4. **低影响 (low)**: 社区讨论、小道消息、技术性更新
5. **无影响 (none)**: 与加密货币无关的新闻

**重要性星级 (importance_stars)**:
- **5星**: 全球重大事件，影响整个加密市场（如美联储政策、主要国家监管政策、重大黑天鹅事件）
- **4星**: 重要事件，影响多个主流币种（如大型机构入场、重要技术破、交易所事件）
- **3星**: 中等重要事件，影响特定领域或币种（如项目升级、合作公告、行业报告）
- **2星**: 较低重要性，短期影响小（如社区讨论、小型交易所上币、技术更新）
- **1星**: 几乎无影响，可忽略（如小道消息、无关新闻、营销宣传）

注意事项：
1. 保持客观，不要夸大影响
2. 考虑新闻的可信度和来源
3. 区分短期影响和长期影响
4. 如果新闻模糊或不确定，降低置信度"""

        news_text = f"标题: {title}"
        if content:
            news_text += f"\n内容: {content[:500]}"  # 限制内容长度
        
        symbol_hint = ""
        if symbol:
            symbol_hint = f"\n\n特别关注对 {symbol} 的影响。"
        
        user_prompt = f"""
请分析以下新闻：

{news_text}
{symbol_hint}

请给出你的影响评估（JSON格式）：
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
            max_tokens=600
        )
        return response.choices[0].message.content
    
    def _parse_response(self, title: str, response: str) -> NewsImpact:
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
            
            # 创建影响评估
            impact = NewsImpact(
                title=title,
                impact_level=ImpactLevel(data.get("impact_level", "none")),
                impact_direction=ImpactDirection(data.get("impact_direction", "neutral")),
                impact_score=float(data.get("impact_score", 0)),
                importance_stars=int(data.get("importance_stars", 3)),
                confidence=float(data.get("confidence", 0.5)),
                affected_symbols=data.get("affected_symbols", []),
                key_points=data.get("key_points", []),
                reasoning=data.get("reasoning", "")
            )
            
            return impact
            
        except Exception as e:
            logger.error(f"Failed to parse news analysis response: {e}")
            return NewsImpact(
                title=title,
                impact_level=ImpactLevel.NONE,
                impact_direction=ImpactDirection.NEUTRAL,
                impact_score=0,
                confidence=0,
                reasoning=f"Parse error: {str(e)}"
            )
    
    def get_market_sentiment_from_news(
        self,
        news_impacts: List[NewsImpact],
        time_decay: float = 0.5
    ) -> Dict:
        """从新闻影响中计算市场情绪"""
        if not news_impacts:
            return {
                "overall_score": 0,
                "overall_direction": "neutral",
                "confidence": 0,
                "bullish_count": 0,
                "bearish_count": 0,
                "neutral_count": 0
            }
        
        # 统计各方向新闻数量
        bullish_count = sum(1 for n in news_impacts if n.impact_direction == ImpactDirection.BULLISH)
        bearish_count = sum(1 for n in news_impacts if n.impact_direction == ImpactDirection.BEARISH)
        neutral_count = sum(1 for n in news_impacts if n.impact_direction == ImpactDirection.NEUTRAL)
        
        # 计算加权平均分数
        total_score = 0
        total_weight = 0
        
        for impact in news_impacts:
            # 根据影响等级设置权重
            weight_map = {
                ImpactLevel.CRITICAL: 5.0,
                ImpactLevel.HIGH: 3.0,
                ImpactLevel.MEDIUM: 1.5,
                ImpactLevel.LOW: 0.5,
                ImpactLevel.NONE: 0.0
            }
            weight = weight_map.get(impact.impact_level, 1.0)
            
            # 考虑置信度
            weight *= impact.confidence
            
            total_score += impact.impact_score * weight
            total_weight += weight
        
        overall_score = total_score / total_weight if total_weight > 0 else 0
        
        # 确定整体方向
        if overall_score > 0.2:
            overall_direction = "bullish"
        elif overall_score < -0.2:
            overall_direction = "bearish"
        else:
            overall_direction = "neutral"
        
        # 计算整体置信度
        avg_confidence = sum(n.confidence for n in news_impacts) / len(news_impacts)
        
        return {
            "overall_score": round(overall_score, 3),
            "overall_direction": overall_direction,
            "confidence": round(avg_confidence, 3),
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "neutral_count": neutral_count,
            "total_news": len(news_impacts)
        }
    
    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()
