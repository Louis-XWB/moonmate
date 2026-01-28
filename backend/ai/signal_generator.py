"""
AI信号生成器
使用LLM分析市场数据和新闻，生成交易信号
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
    """AI信号生成器"""
    
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
        
        # 信号缓存
        self._signal_cache: Dict[str, Signal] = {}
        self._cache_ttl: int = 300  # 5分钟缓存
    
    async def generate_signal(
        self,
        symbol: str,
        ticker: Ticker,
        klines: List[Kline],
        news: Optional[List[str]] = None,
        news_impacts: Optional[List[Dict]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Signal:
        """生成交易信号"""
        
        # 检查缓存
        cache_key = f"{symbol}_{datetime.now().strftime('%Y%m%d%H%M')}"
        if cache_key in self._signal_cache:
            cached = self._signal_cache[cache_key]
            if cached.is_valid:
                return cached
        
        # 准备市场数据摘要
        market_summary = self._prepare_market_summary(ticker, klines)
        
        # 准备新闻摘要
        news_summary = ""
        if news_impacts:
            # 使用AI分析后的新闻影响
            news_summary = self._prepare_news_impact_summary(news_impacts)
        elif news:
            # 备选：使用原始新闻标题
            news_summary = "\n".join([f"- {n}" for n in news[:5]])
        
        # 构建提示词
        prompt = self._build_prompt(symbol, market_summary, news_summary, context)
        
        try:
            # 调用LLM
            response = await asyncio.to_thread(
                self._call_llm,
                prompt
            )
            
            # 解析响应
            signal = self._parse_response(symbol, response, ticker)
            
            # 缓存信号
            self._signal_cache[cache_key] = signal
            
            logger.info(f"Generated signal for {symbol}: {signal.direction} (confidence: {signal.confidence:.2f})")
            return signal
            
        except Exception as e:
            logger.error(f"AI signal generation error: {e}")
            # 返回中性信号
            return Signal(
                symbol=symbol,
                direction=SignalDirection.NEUTRAL,
                strength=0,
                confidence=0,
                source="ai",
                reason=f"AI analysis failed: {str(e)}"
            )
    
    def _prepare_market_summary(self, ticker: Ticker, klines: List[Kline]) -> str:
        """准备市场数据摘要"""
        # 计算技术指标
        closes = [k.close for k in klines[-20:]]
        
        # 简单移动平均
        sma_5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else closes[-1]
        sma_20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else closes[-1]
        
        # 价格变化
        price_change_1h = (closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes) >= 2 else 0
        price_change_24h = ticker.change_24h
        
        # 波动率
        if len(closes) >= 20:
            returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
            volatility = (sum(r**2 for r in returns) / len(returns)) ** 0.5 * 100
        else:
            volatility = 0
        
        summary = f"""
当前价格: ${ticker.last_price:,.2f}
24小时涨跌: {price_change_24h:+.2f}%
1小时涨跌: {price_change_1h:+.2f}%
24小时成交量: {ticker.volume_24h:,.0f}
24小时最高: ${ticker.high_24h:,.2f}
24小时最低: ${ticker.low_24h:,.2f}
买卖价差: {ticker.spread:.4f}%
SMA5: ${sma_5:,.2f}
SMA20: ${sma_20:,.2f}
波动率: {volatility:.2f}%
趋势: {'上涨' if sma_5 > sma_20 else '下跌' if sma_5 < sma_20 else '横盘'}
"""
        return summary.strip()
    
    def _prepare_news_impact_summary(self, news_impacts: List[Dict]) -> str:
        """准备新闻影响摘要"""
        if not news_impacts:
            return ""
        
        # 按星级排序，只保留31星以上的重要新闻
        important_news = sorted(
            [n for n in news_impacts if n.get('importance_stars', 0) >= 3],
            key=lambda x: x.get('importance_stars', 0),
            reverse=True
        )[:5]  # 最多5条
        
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
        """构建提示词"""
        
        # 获取Vibe策略
        vibe_prompt = ""
        try:
            from backend.strategy.vibe_strategy import get_vibe_manager
            vibe_manager = get_vibe_manager()
            vibe_prompt = vibe_manager.get_rules_as_prompt()
        except Exception as e:
            logger.warning(f"Failed to load vibe rules: {e}")
        
        system_prompt = """你是一个专业的加密货币交易分析师。基于提供的市场数据和新闻，分析当前市场状况并给出交易建议。

你必须以JSON格式输出，包含以下字段：
- direction: "long"(做多), "short"(做空), "close"(平仓), 或 "neutral"(观望)
- strength: 0-1之间的数值，表示信号强度
- confidence: 0-1之间的数值，表示你对这个判断的置信度
- reason: 简短解释你的判断理由
- evidence: 支持你判断的证据列表

注意事项：
1. 保持客观，不要过度自信
2. 如果数据不足或市场不明朗，选择"neutral"
3. 考虑风险，不要在高波动时给出强信号
4. 证据必须来自提供的数据，不要编造
5. **重要：必须严格遵守用户的策略偏好（Vibe），这是最高优先级的约束**"""

        user_prompt = f"""
请分析以下{symbol}的市场数据：

【市场数据】
{market_summary}

【相关新闻】
{news_summary if news_summary else "暂无相关新闻"}

【额外上下文】
{json.dumps(context, ensure_ascii=False) if context else "无"}

{vibe_prompt if vibe_prompt else ""}

请给出你的交易建议（JSON格式）：
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
            max_tokens=500
        )
        return response.choices[0].message.content
    
    def _parse_response(self, symbol: str, response: str, ticker: Ticker) -> Signal:
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
            
            # 解析方向
            direction_map = {
                "long": SignalDirection.LONG,
                "short": SignalDirection.SHORT,
                "close": SignalDirection.CLOSE,
                "neutral": SignalDirection.NEUTRAL
            }
            direction = direction_map.get(data.get("direction", "neutral"), SignalDirection.NEUTRAL)
            
            # 创建信号
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
            
            # 设置止损止盈（基于当前价格）
            if direction == SignalDirection.LONG:
                signal.stop_loss = ticker.last_price * 0.98  # 2%止损
                signal.take_profit = ticker.last_price * 1.05  # 5%止盈
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
        """清除缓存"""
        self._signal_cache.clear()
