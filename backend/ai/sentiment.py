"""
Sentiment Analysis Module
Uses LLM to analyze market sentiment and social media trends
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
    """Sentiment analysis result"""
    symbol: str
    sentiment: str = Field(..., description="bullish/bearish/neutral")
    score: float = Field(default=0, ge=-1, le=1, description="Sentiment score from -1 to 1")
    confidence: float = Field(default=0.5, ge=0, le=1)
    sources_count: int = Field(default=0, description="Number of data sources")
    keywords: List[str] = Field(default_factory=list, description="Keywords")
    reasoning: str = Field(default="", description="Analysis reasoning")
    timestamp: datetime = Field(default_factory=datetime.now)


class SentimentAnalyzer:
    """Sentiment analyzer"""
    
    def __init__(
        self,
        model: str = "gemini-3-flash-preview",
        temperature: float = 0.2,
        use_llm: bool = True
    ):
        self.model = model
        self.temperature = temperature
        self.use_llm = use_llm
        
        if use_llm:
            self.client = OpenAI()
        
        # Mock sentiment keywords (for keyword matching mode)
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
        """Analyze sentiment"""
        
        if not texts:
            # Mock sentiment data
            return self._generate_mock_sentiment(symbol)
        
        # Select analysis method based on configuration
        if self.use_llm:
            return await self._analyze_with_llm(symbol, texts)
        else:
            return self._analyze_with_keywords(symbol, texts)
    
    async def _analyze_with_llm(
        self,
        symbol: str,
        texts: List[str]
    ) -> SentimentResult:
        """Analyze sentiment using LLM"""
        
        # Limit text count and length
        sample_texts = texts[:20]  # Analyze up to 20 items
        truncated_texts = [t[:200] for t in sample_texts]  # Max 200 characters each
        
        # Build prompt
        prompt = self._build_llm_prompt(symbol, truncated_texts)
        
        try:
            # Call LLM
            response = await asyncio.to_thread(
                self._call_llm,
                prompt
            )
            
            # Parse response
            result = self._parse_llm_response(symbol, response, len(texts))
            
            logger.info(
                f"LLM sentiment for {symbol}: {result.sentiment} "
                f"(score: {result.score:.2f}, confidence: {result.confidence:.2f})"
            )
            return result
            
        except Exception as e:
            logger.error(f"LLM sentiment analysis error: {e}")
            # Fall back to keyword matching
            return self._analyze_with_keywords(symbol, texts)
    
    def _analyze_with_keywords(
        self,
        symbol: str,
        texts: List[str]
    ) -> SentimentResult:
        """Analyze sentiment using keyword matching"""
        
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
            confidence=min(0.9, total / 20),  # Higher data volume = higher confidence
            sources_count=len(texts),
            keywords=found_keywords[:10],
            reasoning=f"Based on keyword matching: {bullish_count} bullish keywords, {bearish_count} bearish keywords"
        )
    
    def _build_llm_prompt(self, symbol: str, texts: List[str]) -> str:
        """Build LLM prompt"""
        
        system_prompt = """You are a professional cryptocurrency market sentiment analyst. Your task is to analyze social media discussions and assess the overall market sentiment towards a specific cryptocurrency.

You must output in JSON format with the following fields:
- sentiment: "bullish", "bearish", or "neutral"
- score: a value between -1 and 1, negative means bearish, positive means bullish
- confidence: a value between 0-1 indicating your confidence in the judgment
- keywords: a list of 3-5 keywords representing the main discussion topics
- reasoning: a brief explanation of your reasoning (under 50 words)

Evaluation criteria:
1. Bullish sentiment: positive discussions, price expected to rise, technical breakthroughs, increased adoption
2. Bearish sentiment: negative discussions, price expected to fall, technical issues, regulatory concerns
3. Neutral sentiment: balanced discussions, wait-and-see attitude, technical discussions

Guidelines:
1. Distinguish noise from valuable signals
2. Consider the quality of discussions, not just quantity
3. Identify potential manipulation or FUD
4. If discussions are vague or contradictory, lower confidence"""

        texts_formatted = "\n".join([f"{i+1}. {t}" for i, t in enumerate(texts)])
        
        user_prompt = f"""
Please analyze the following social media discussions about {symbol}:

{texts_formatted}

Please provide your sentiment assessment (JSON format):
"""
        
        return f"{system_prompt}\n\n{user_prompt}"
    
    def _call_llm(self, prompt: str) -> str:
        """Call LLM"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a JSON API. Respond with valid JSON only. No markdown, no code fences, no explanatory text."},
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            max_tokens=8192,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""
    
    def _parse_llm_response(
        self,
        symbol: str,
        response: str,
        total_texts: int
    ) -> SentimentResult:
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
            
            # Create sentiment result
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
        """Generate mock sentiment data"""
        # Randomly generate sentiment
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
            reasoning="Mock data"
        )
    
    async def get_market_fear_greed(self) -> Dict:
        """Get market Fear & Greed index (mock)"""
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
        """Analyze sentiment trend (requires historical data)"""
        if not historical_texts or len(historical_texts) < 2:
            return {
                "trend": "unknown",
                "change": 0,
                "confidence": 0
            }
        
        # Analyze sentiment at each time point
        sentiments = []
        for texts in historical_texts:
            result = await self.analyze(symbol, texts)
            sentiments.append(result.score)
        
        # Calculate trend
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
