"""
情绪分析模块
使用LLM分析市场情绪和社交媒体热度
"""

import asyncio
import json
import random
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from openai import OpenAI

from backend.core.logger import get_logger

logger = get_logger("sentiment")


class SentimentResult(BaseModel):
    """情绪分析结果"""
    symbol: str
    sentiment: str = Field(..., description="bullish/bearish/neutral")
    score: float = Field(default=0, ge=-1, le=1, description="情绪分数 -1到1")
    confidence: float = Field(default=0.5, ge=0, le=1)
    sources_count: int = Field(default=0, description="数据源数量")
    keywords: List[str] = Field(default_factory=list, description="关键词")
    reasoning: str = Field(default="", description="分析理由")
    timestamp: datetime = Field(default_factory=datetime.now)


class SentimentAnalyzer:
    """情绪分析器"""
    
    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        temperature: float = 0.2,
        use_llm: bool = True
    ):
        self.model = model
        self.temperature = temperature
        self.use_llm = use_llm
        
        if use_llm:
            self.client = OpenAI()
        
        # 模拟的情绪关键词（用于关键词匹配模式）
        self._bullish_keywords = [
            "bullish", "moon", "pump", "buy", "long", "breakout",
            "ATH", "rally", "surge", "adoption", "institutional"
        ]
        self._bearish_keywords = [
            "bearish", "dump", "sell", "short", "crash", "FUD",
            "hack", "scam", "regulation", "ban", "liquidation"
        ]
    
    async def analyze(
        self,
        symbol: str,
        texts: Optional[List[str]] = None
    ) -> SentimentResult:
        """分析情绪"""
        
        if not texts:
            # 模拟情绪数据
            return self._generate_mock_sentiment(symbol)
        
        # 根据配置选择分析方法
        if self.use_llm:
            return await self._analyze_with_llm(symbol, texts)
        else:
            return self._analyze_with_keywords(symbol, texts)
    
    async def _analyze_with_llm(
        self,
        symbol: str,
        texts: List[str]
    ) -> SentimentResult:
        """使用LLM分析情绪"""
        
        # 限制文本数量和长度
        sample_texts = texts[:20]  # 最多分析20条
        truncated_texts = [t[:200] for t in sample_texts]  # 每条最多200字符
        
        # 构建提示词
        prompt = self._build_llm_prompt(symbol, truncated_texts)
        
        try:
            # 调用LLM
            response = await asyncio.to_thread(
                self._call_llm,
                prompt
            )
            
            # 解析响应
            result = self._parse_llm_response(symbol, response, len(texts))
            
            logger.info(
                f"LLM sentiment for {symbol}: {result.sentiment} "
                f"(score: {result.score:.2f}, confidence: {result.confidence:.2f})"
            )
            return result
            
        except Exception as e:
            logger.error(f"LLM sentiment analysis error: {e}")
            # 降级到关键词匹配
            return self._analyze_with_keywords(symbol, texts)
    
    def _analyze_with_keywords(
        self,
        symbol: str,
        texts: List[str]
    ) -> SentimentResult:
        """使用关键词匹配分析情绪"""
        
        bullish_count = 0
        bearish_count = 0
        found_keywords = []
        
        for text in texts:
            text_lower = text.lower()
            for keyword in self._bullish_keywords:
                if keyword.lower() in text_lower:
                    bullish_count += 1
                    if keyword not in found_keywords:
                        found_keywords.append(keyword)
            
            for keyword in self._bearish_keywords:
                if keyword.lower() in text_lower:
                    bearish_count += 1
                    if keyword not in found_keywords:
                        found_keywords.append(keyword)
        
        total = bullish_count + bearish_count
        if total == 0:
            score = 0
            sentiment = "neutral"
        else:
            score = (bullish_count - bearish_count) / total
            if score > 0.2:
                sentiment = "bullish"
            elif score < -0.2:
                sentiment = "bearish"
            else:
                sentiment = "neutral"
        
        return SentimentResult(
            symbol=symbol,
            sentiment=sentiment,
            score=score,
            confidence=min(0.9, total / 20),  # 数据越多置信度越高
            sources_count=len(texts),
            keywords=found_keywords[:10],
            reasoning=f"基于关键词匹配: {bullish_count} 个看涨关键词, {bearish_count} 个看跌关键词"
        )
    
    def _build_llm_prompt(self, symbol: str, texts: List[str]) -> str:
        """构建LLM提示词"""
        
        system_prompt = """你是一个专业的加密货币市场情绪分析师。你的任务是分析社交媒体上的讨论，评估市场对特定加密货币的整体情绪。

你必须以JSON格式输出，包含以下字段：
- sentiment: "bullish"(看涨), "bearish"(看跌), 或 "neutral"(中性)
- score: -1到1之间的数值，负数表示看跌，正数表示看涨
- confidence: 0-1之间的数值，表示你对这个判断的置信度
- keywords: 3-5个关键词的列表，代表主要讨论话题
- reasoning: 简短解释你的判断理由（50字以内）

评估标准：
1. 看涨情绪: 积极讨论、价格预期上涨、技术突破、采用增加
2. 看跌情绪: 消极讨论、价格预期下跌、技术问题、监管担忧
3. 中性情绪: 讨论平衡、观望态度、技术性讨论

注意事项：
1. 区分噪音和有价值的信号
2. 考虑讨论的质量而非仅仅数量
3. 识别潜在的操纵或FUD
4. 如果讨论内容模糊或矛盾，降低置信度"""

        texts_formatted = "\n".join([f"{i+1}. {t}" for i, t in enumerate(texts)])
        
        user_prompt = f"""
请分析以下关于 {symbol} 的社交媒体讨论：

{texts_formatted}

请给出你的情绪评估（JSON格式）：
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
            max_tokens=400
        )
        return response.choices[0].message.content
    
    def _parse_llm_response(
        self,
        symbol: str,
        response: str,
        total_texts: int
    ) -> SentimentResult:
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
            
            # 创建情绪结果
            result = SentimentResult(
                symbol=symbol,
                sentiment=data.get("sentiment", "neutral"),
                score=float(data.get("score", 0)),
                confidence=float(data.get("confidence", 0.5)),
                sources_count=total_texts,
                keywords=data.get("keywords", []),
                reasoning=data.get("reasoning", "")
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse LLM sentiment response: {e}")
            return SentimentResult(
                symbol=symbol,
                sentiment="neutral",
                score=0,
                confidence=0,
                sources_count=total_texts,
                reasoning=f"Parse error: {str(e)}"
            )
    
    def _generate_mock_sentiment(self, symbol: str) -> SentimentResult:
        """生成模拟情绪数据"""
        # 随机生成情绪
        score = random.gauss(0, 0.3)
        score = max(-1, min(1, score))
        
        if score > 0.2:
            sentiment = "bullish"
            keywords = random.sample(self._bullish_keywords, min(3, len(self._bullish_keywords)))
        elif score < -0.2:
            sentiment = "bearish"
            keywords = random.sample(self._bearish_keywords, min(3, len(self._bearish_keywords)))
        else:
            sentiment = "neutral"
            keywords = []
        
        return SentimentResult(
            symbol=symbol,
            sentiment=sentiment,
            score=score,
            confidence=random.uniform(0.4, 0.8),
            sources_count=random.randint(10, 100),
            keywords=keywords,
            reasoning="模拟数据"
        )
    
    async def get_market_fear_greed(self) -> Dict:
        """获取市场恐惧贪婪指数（模拟）"""
        index = random.randint(20, 80)
        
        if index < 25:
            classification = "Extreme Fear"
        elif index < 45:
            classification = "Fear"
        elif index < 55:
            classification = "Neutral"
        elif index < 75:
            classification = "Greed"
        else:
            classification = "Extreme Greed"
        
        return {
            "value": index,
            "classification": classification,
            "timestamp": datetime.now().isoformat()
        }
    
    async def analyze_sentiment_trend(
        self,
        symbol: str,
        historical_texts: List[List[str]]
    ) -> Dict:
        """分析情绪趋势（需要历史数据）"""
        if not historical_texts or len(historical_texts) < 2:
            return {
                "trend": "unknown",
                "change": 0,
                "confidence": 0
            }
        
        # 分析每个时间点的情绪
        sentiments = []
        for texts in historical_texts:
            result = await self.analyze(symbol, texts)
            sentiments.append(result.score)
        
        # 计算趋势
        if len(sentiments) >= 2:
            recent_avg = sum(sentiments[-3:]) / min(3, len(sentiments))
            earlier_avg = sum(sentiments[:3]) / min(3, len(sentiments))
            change = recent_avg - earlier_avg
            
            if change > 0.1:
                trend = "improving"
            elif change < -0.1:
                trend = "deteriorating"
            else:
                trend = "stable"
            
            return {
                "trend": trend,
                "change": round(change, 3),
                "confidence": 0.7,
                "recent_score": round(recent_avg, 3),
                "earlier_score": round(earlier_avg, 3)
            }
        
        return {
            "trend": "unknown",
            "change": 0,
            "confidence": 0
        }
