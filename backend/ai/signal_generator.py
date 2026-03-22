"""
AI Signal Generator
Uses LLM to analyze market data and news to generate trading signals
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from openai import OpenAI

from backend.data.models import Signal, SignalDirection, Ticker, Kline
from backend.core.logger import get_logger

logger = get_logger("ai_signal")


class AISignalGenerator:
    """AI signal generator"""
    
    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        temperature: float = 0.3,
        confidence_threshold: float = 0.6
    ):
        self.model = model
        self.temperature = temperature
        self.confidence_threshold = confidence_threshold
        self.client = OpenAI()
        
        # Signal cache
        self._signal_cache: Dict[str, Signal] = {}
        self._cache_ttl: int = 300  # 5-minute cache
    
    async def generate_signal(
        self,
        symbol: str,
        ticker: Ticker,
        klines: List[Kline],
        news: Optional[List[str]] = None,
        news_impacts: Optional[List[Dict]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Signal:
        """Generate trading signal"""
        
        # Check cache
        cache_key = f"{symbol}_{datetime.now().strftime('%Y%m%d%H%M')}"
        if cache_key in self._signal_cache:
            cached = self._signal_cache[cache_key]
            if cached.is_valid:
                return cached
        
        # Prepare market data summary
        market_summary = self._prepare_market_summary(ticker, klines)
        
        # Prepare news summary
        news_summary = ""
        if news_impacts:
            # Use AI-analyzed news impact
            news_summary = self._prepare_news_impact_summary(news_impacts)
        elif news:
            # Fallback: use raw news titles
            news_summary = "\n".join([f"- {n}" for n in news[:5]])
        
        # Build prompt
        prompt = self._build_prompt(symbol, market_summary, news_summary, context)
        
        try:
            # Call LLM
            response = await asyncio.to_thread(
                self._call_llm,
                prompt
            )
            
            # Parse response
            signal = self._parse_response(symbol, response, ticker)
            
            # Cache the signal
            self._signal_cache[cache_key] = signal
            
            logger.info(f"Generated signal for {symbol}: {signal.direction} (confidence: {signal.confidence:.2f})")
            return signal
            
        except Exception as e:
            logger.error(f"AI signal generation error: {e}")
            # Return neutral signal
            return Signal(
                symbol=symbol,
                direction=SignalDirection.NEUTRAL,
                strength=0,
                confidence=0,
                source="ai",
                reason=f"AI analysis failed: {str(e)}"
            )
    
    def _prepare_market_summary(self, ticker: Ticker, klines: List[Kline]) -> str:
        """Prepare market data summary"""
        # Calculate technical indicators
        closes = [k.close for k in klines[-20:]]
        
        # Simple moving average
        sma_5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else closes[-1]
        sma_20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
        
        # Price change
        price_change_1h = (closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes) >= 2 else 0
        price_change_24h = ticker.change_24h
        
        # Volatility
        if len(closes) >= 20:
            returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
            volatility = (sum(r**2 for r in returns) / len(returns)) ** 0.5 * 100
        else:
            volatility = 0
        
        summary = f"""
Current Price: ${ticker.last_price:,.2f}
24h Change: {price_change_24h:+.2f}%
1h Change: {price_change_1h:+.2f}%
24h Volume: {ticker.volume_24h:,.0f}
24h High: ${ticker.high_24h:,.2f}
24h Low: ${ticker.low_24h:,.2f}
Bid-Ask Spread: {ticker.spread:.4f}%
SMA5: ${sma_5:,.2f}
SMA20: ${sma_20:,.2f}
Volatility: {volatility:.2f}%
Trend: {'Uptrend' if sma_5 > sma_20 else 'Downtrend' if sma_5 < sma_20 else 'Sideways'}
"""
        return summary.strip()
    
    def _prepare_news_impact_summary(self, news_impacts: List[Dict]) -> str:
        """Prepare news impact summary"""
        if not news_impacts:
            return ""
        
        # Sort by star rating, keep only news with 3+ stars
        important_news = sorted(
            [n for n in news_impacts if n.get('importance_stars', 0) >= 3],
            key=lambda x: x.get('importance_stars', 0),
            reverse=True
        )[:5]  # Maximum 5 entries
        
        if not important_news:
            return ""
        
        lines = []
        for news in important_news:
            stars = '⭐' * news.get('importance_stars', 3)
            direction_emoji = {
                'bullish': '📈',
                'bearish': '📉',
                'neutral': '➡️'
            }.get(news.get('impact_direction', 'neutral'), '➡️')
            
            title = news.get('title', '')
            impact_level = news.get('impact_level', 'medium')
            impact_direction = news.get('impact_direction', 'neutral')
            reasoning = news.get('reasoning', '')
            
            line = f"- {stars} {direction_emoji} [{impact_level.upper()}] {title}"
            if reasoning:
                line += f" | {reasoning}"
            
            lines.append(line)
        
        return "\n".join(lines)
    
    def _build_prompt(
        self,
        symbol: str,
        market_summary: str,
        news_summary: str,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt"""
        
        # Get Vibe strategy
        vibe_prompt = ""
        try:
            from backend.strategy.vibe_strategy import get_vibe_manager
            vibe_manager = get_vibe_manager()
            vibe_prompt = vibe_manager.get_rules_as_prompt()
        except Exception as e:
            logger.warning(f"Failed to load vibe rules: {e}")
        
        system_prompt = """You are a professional cryptocurrency trading analyst. Based on the provided market data and news, analyze the current market conditions and provide trading recommendations.

You must output in JSON format with the following fields:
- direction: "long", "short", "close", or "neutral"
- strength: a value between 0-1 indicating signal strength
- confidence: a value between 0-1 indicating your confidence in the judgment
- reason: a brief explanation of your reasoning
- evidence: a list of evidence supporting your judgment

Guidelines:
1. Stay objective, do not be overconfident
2. If data is insufficient or the market is unclear, choose "neutral"
3. Consider risk, do not give strong signals during high volatility
4. Evidence must come from the provided data, do not fabricate
5. **Important: strictly follow the user's strategy preferences (Vibe) as the highest priority constraint**"""

        user_prompt = f"""
Please analyze the following {symbol} market data:

[Market Data]
{market_summary}

[Related News]
{news_summary if news_summary else "No related news available"}

[Additional Context]
{json.dumps(context, ensure_ascii=False) if context else "None"}

{vibe_prompt if vibe_prompt else ""}

Please provide your trading recommendation (JSON format):
"""
        
        return f"{system_prompt}\n\n{user_prompt}"
    
    def _call_llm(self, prompt: str) -> str:
        """Call LLM"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=self.temperature,
            max_tokens=500
        )
        return response.choices[0].message.content
    
    def _parse_response(self, symbol: str, response: str, ticker: Ticker) -> Signal:
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
            
            # Parse direction
            direction_map = {
                "long": SignalDirection.LONG,
                "short": SignalDirection.SHORT,
                "close": SignalDirection.CLOSE,
                "neutral": SignalDirection.NEUTRAL
            }
            direction = direction_map.get(data.get("direction", "neutral"), SignalDirection.NEUTRAL)
            
            # Create signal
            signal = Signal(
                symbol=symbol,
                direction=direction,
                strength=float(data.get("strength", 0.5)),
                confidence=float(data.get("confidence", 0.5)),
                source="ai",
                reason=data.get("reason", ""),
                evidence=data.get("evidence", []),
                entry_price=ticker.last_price,
                ttl=300
            )
            
            # Set stop-loss/take-profit (based on current price)
            if direction == SignalDirection.LONG:
                signal.stop_loss = ticker.last_price * 0.98  # 2% stop-loss
                signal.take_profit = ticker.last_price * 1.05  # 5% take-profit
            elif direction == SignalDirection.SHORT:
                signal.stop_loss = ticker.last_price * 1.02
                signal.take_profit = ticker.last_price * 0.95
            
            return signal
            
        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")
            return Signal(
                symbol=symbol,
                direction=SignalDirection.NEUTRAL,
                strength=0,
                confidence=0,
                source="ai",
                reason=f"Parse error: {str(e)}"
            )
    
    def clear_cache(self):
        """Clear cache"""
        self._signal_cache.clear()
