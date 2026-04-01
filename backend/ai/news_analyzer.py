"""
News Impact Assessment Module
Uses LLM to analyze the impact of news on cryptocurrency prices
"""

import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field
import httpx

from backend.core.logger import get_logger

logger = get_logger("news_analyzer")


class ImpactLevel(str, Enum):
    """Impact level"""
    CRITICAL = "critical"  # Critical impact
    HIGH = "high"  # High impact
    MEDIUM = "medium"  # Medium impact
    LOW = "low"  # Low impact
    NONE = "none"  # No impact


class ImpactDirection(str, Enum):
    """Impact direction"""
    BULLISH = "bullish"  # Bullish
    BEARISH = "bearish"  # Bearish
    NEUTRAL = "neutral"  # neutral


class NewsImpact(BaseModel):
    """News impact assessment result"""
    title: str = Field(..., description="News title")
    summary: str = Field(default="", description="News summary")
    impact_level: ImpactLevel = Field(..., description="Impact level")
    impact_direction: ImpactDirection = Field(..., description="Impact direction")
    impact_score: float = Field(default=0, ge=-1, le=1, description="Impact score from -1 to 1")
    importance_stars: int = Field(default=3, ge=1, le=5, description="Importance rating (1-5 stars)")
    confidence: float = Field(default=0.5, ge=0, le=1, description="Confidence")
    affected_symbols: List[str] = Field(default_factory=list, description="Affected tokens")
    key_points: List[str] = Field(default_factory=list, description="Key takeaways")
    reasoning: str = Field(default="", description="Analysis reasoning")
    timestamp: datetime = Field(default_factory=datetime.now)


class NewsAnalyzer:
    """News analyzer"""
    
    def __init__(
        self,
        model: str = "gemini-3-flash-preview",
        temperature: float = 0.2
    ):
        self.model = model
        self.temperature = temperature
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        
        # News cache
        self._cache: Dict[str, NewsImpact] = {}
    
    async def analyze_news(
        self,
        title: str,
        content: Optional[str] = None,
        symbol: Optional[str] = None
    ) -> NewsImpact:
        """Analyze a single news item"""
        
        # Check cache
        cache_key = f"{title[:50]}_{symbol or 'all'}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Build prompt
        prompt = self._build_prompt(title, content, symbol)
        
        try:
            # Call LLM
            response = await asyncio.to_thread(
                self._call_llm,
                prompt
            )
            
            # Parse response
            impact = self._parse_response(title, response)
            
            # Cache result
            self._cache[cache_key] = impact
            
            logger.info(
                f"Analyzed news: {title[:50]}... -> "
                f"{impact.impact_direction} ({impact.impact_level})"
            )
            return impact
            
        except Exception as e:
            logger.error(f"News analysis error: {e}")
            # Return neutral impact
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
        """Analyze news in batch"""
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
        """Build prompt"""
        
        system_prompt = """You are a professional cryptocurrency market analyst skilled at assessing the impact of news events on cryptocurrency prices.

Your task is to analyze the given news and assess its impact on the cryptocurrency market.

You must output in JSON format with the following fields:
- impact_level: "critical", "high", "medium", "low", or "none"
- impact_direction: "bullish", "bearish", or "neutral"
- impact_score: a value between -1 and 1, negative means bearish, positive means bullish
- importance_stars: an integer between 1-5 indicating the news importance level (1=unimportant, 5=extremely important)
- confidence: a value between 0-1 indicating your confidence in the judgment
- affected_symbols: list of affected tokens, e.g. ["BTC", "ETH"], use ["ALL"] for market-wide impact
- key_points: a list of 3-5 key takeaways
- reasoning: a brief explanation of your reasoning (under 50 words)

Evaluation criteria:

**Impact Level**:
1. **Critical**: regulatory policies, major hacks, mainstream institutional adoption, major protocol vulnerabilities
2. **High**: major exchange listings, notable institutional investments, important technical upgrades
3. **Medium**: general partnerships, minor exchange events, industry reports
4. **Low**: community discussions, rumors, technical updates
5. **None**: news unrelated to cryptocurrency

**Importance Stars**:
- **5 stars**: major global events affecting the entire crypto market (e.g. Fed policy, major country regulations, black swan events)
- **4 stars**: important events affecting multiple major tokens (e.g. large institutional entry, major technical breakthroughs, exchange events)
- **3 stars**: moderately important events affecting specific sectors or tokens (e.g. project upgrades, partnership announcements, industry reports)
- **2 stars**: lower importance, minimal short-term impact (e.g. community discussions, minor exchange listings, technical updates)
- **1 star**: almost no impact, negligible (e.g. rumors, unrelated news, marketing promotions)

Guidelines:
1. Stay objective, do not exaggerate impact
2. Consider the credibility and source of the news
3. Distinguish between short-term and long-term impact
4. If the news is vague or uncertain, lower confidence"""

        news_text = f"Title: {title}"
        if content:
            news_text += f"\nContent: {content[:500]}"  # Limit content length
        
        symbol_hint = ""
        if symbol:
            symbol_hint = f"\n\nPay special attention to the impact on {symbol}."
        
        user_prompt = f"""
Please analyze the following news:

{news_text}
{symbol_hint}

Please provide your impact assessment (JSON format):
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
    
    def _parse_response(self, title: str, response: str) -> NewsImpact:
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
            
            # Create impact assessment
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
        """Calculate market sentiment from news impacts"""
        if not news_impacts:
            return {
                "overall_score": 0,
                "overall_direction": "neutral",
                "confidence": 0,
                "bullish_count": 0,
                "bearish_count": 0,
                "neutral_count": 0
            }
        
        # Count news by direction
        bullish_count = sum(1 for n in news_impacts if n.impact_direction == ImpactDirection.BULLISH)
        bearish_count = sum(1 for n in news_impacts if n.impact_direction == ImpactDirection.BEARISH)
        neutral_count = sum(1 for n in news_impacts if n.impact_direction == ImpactDirection.NEUTRAL)
        
        # Calculate weighted average score
        total_score = 0
        total_weight = 0
        
        for impact in news_impacts:
            # Set weight based on impact level
            weight_map = {
                ImpactLevel.CRITICAL: 5.0,
                ImpactLevel.HIGH: 3.0,
                ImpactLevel.MEDIUM: 1.5,
                ImpactLevel.LOW: 0.5,
                ImpactLevel.NONE: 0.0
            }
            weight = weight_map.get(impact.impact_level, 1.0)
            
            # Factor in confidence
            weight *= impact.confidence
            
            total_score += impact.impact_score * weight
            total_weight += weight
        
        overall_score = total_score / total_weight if total_weight > 0 else 0
        
        # Determine overall direction
        if overall_score > 0.2:
            overall_direction = "bullish"
        elif overall_score < -0.2:
            overall_direction = "bearish"
        else:
            overall_direction = "neutral"
        
        # Calculate overall confidence
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
        """Clear cache"""
        self._cache.clear()
