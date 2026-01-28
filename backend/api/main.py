"""
FastAPI 主应用
提供REST API和WebSocket接口
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# 加载.env文件
load_dotenv('/home/ubuntu/auto-trading-agent/.env')

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# 导入核心模块
import sys
sys.path.insert(0, '/home/ubuntu/auto-trading-agent')

from backend.core.config import Config, get_config, set_config
from backend.core.events import EventBus, Event, EventType, get_event_bus
from backend.core.logger import get_logger
from backend.data.models import Signal, SignalDirection, Order, OrderStatus, Position, Ticker
from backend.data.provider import OKXDataProvider, MockDataProvider
from backend.ai.signal_generator import AISignalGenerator
from backend.ai.sentiment import SentimentAnalyzer
from backend.strategy.momentum import MomentumStrategy
from backend.strategy.signal_fusion import SignalFusion
from backend.risk.engine import RiskEngine
from backend.execution.order_manager import OrderManager
from backend.execution.executor import MockExecutor
from backend.backtest.engine import BacktestEngine, BacktestResult
from backend.data.apify_scraper import ApifyScraper, ScraperMode, DataSource, get_scraper, set_scraper_token

logger = get_logger("api")


# ==================== 全局状态 ====================

class TradingAgent:
    """交易Agent主类"""
    
    def __init__(self):
        self.config = get_config()
        self.event_bus = get_event_bus()
        
        # 初始化组件
        # 使用OKX真实数据，如果失败则降级到模拟数据
        try:
            self.data_provider = OKXDataProvider()
            self._use_real_data = True
            logger.info("Using OKX real data provider")
        except Exception as e:
            logger.warning(f"Failed to init OKX provider, falling back to mock: {e}")
            self.data_provider = MockDataProvider()
            self._use_real_data = False
        self.ai_generator = AISignalGenerator()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.momentum_strategy = MomentumStrategy()
        self.signal_fusion = SignalFusion()
        self.risk_engine = RiskEngine()
        self.order_manager = OrderManager()
        self.executor = MockExecutor()
        self.backtest_engine = BacktestEngine()
        
        # Apify 抓取器（用于 X/Twitter 数据抓取）
        self.apify_scraper = get_scraper()
        self.apify_scraper.on_scrape_complete(self._on_scrape_complete)
        
        # 状态
        self.is_running = False
        self.current_symbol = "BTC/USDT"
        self.last_ticker: Optional[Ticker] = None
        self.last_signal: Optional[Signal] = None
        
        # WebSocket连接管理
        self.ws_connections: List[WebSocket] = []
    
    async def start(self):
        """启动Agent"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("Trading Agent started")
        
        # 启动数据订阅
        await self.data_provider.subscribe_ticker(
            self.current_symbol,
            self._on_ticker_update
        )
        
        # 启动事件循环
        asyncio.create_task(self._main_loop())
    
    async def stop(self):
        """停止Agent"""
        self.is_running = False
        await self.data_provider.unsubscribe_ticker(self.current_symbol)
        self.data_provider.stop()
        logger.info("Trading Agent stopped")
    
    async def _on_ticker_update(self, ticker: Ticker):
        """处理行情更新"""
        self.last_ticker = ticker
        
        # 更新持仓盈亏
        self.order_manager.update_position_price(ticker.symbol, ticker.last_price)
        
        # 广播到WebSocket
        await self._broadcast({
            "type": "ticker",
            "data": ticker.model_dump()
        })
    
    async def _main_loop(self):
        """主循环"""
        while self.is_running:
            try:
                await asyncio.sleep(5)  # 每5秒执行一次
                
                if not self.last_ticker:
                    continue
                
                # 获取K线数据
                klines = await self.data_provider.get_klines(
                    self.current_symbol,
                    interval="1h",
                    limit=100
                )
                
                # 生成策略信号
                momentum_signal = await self.momentum_strategy.run(
                    self.current_symbol,
                    self.last_ticker,
                    klines
                )
                
                # 信号融合
                signals = [momentum_signal]
                fused_signal = self.signal_fusion.fuse(signals)
                self.last_signal = fused_signal
                
                # 广播信号
                await self._broadcast({
                    "type": "signal",
                    "data": fused_signal.model_dump()
                })
                
                # 风控检查
                if fused_signal.is_actionable:
                    positions = self.order_manager.get_all_positions()
                    orders = self.order_manager.get_active_orders()
                    
                    risk_result = self.risk_engine.check(
                        fused_signal,
                        positions,
                        orders,
                        {"ticker": self.last_ticker}
                    )
                    
                    if risk_result.passed:
                        # 创建订单
                        order = self.order_manager.create_order_from_signal(
                            fused_signal,
                            size=100  # 固定下单金额
                        )
                        
                        if order:
                            # 执行订单
                            result = await self.executor.submit_order(order)
                            
                            # 更新订单状态
                            self.order_manager.update_order_status(
                                order.id,
                                result["status"],
                                filled_size=result.get("filled_size", 0),
                                avg_price=result.get("avg_price", 0),
                                fee=result.get("fee", 0),
                                error_msg=result.get("error", "")
                            )
                            
                            # 广播订单更新
                            await self._broadcast({
                                "type": "order",
                                "data": order.model_dump()
                            })
                    else:
                        logger.warning(f"Risk check failed: {risk_result.reason}")
                
            except Exception as e:
                logger.error(f"Main loop error: {e}")
    
    async def _on_scrape_complete(self, result):
        """处理 Apify 抓取完成"""
        logger.info(f"Apify scrape completed: {result.total_count} posts from {result.source}")
        
        # 广播到 WebSocket
        await self._broadcast({
            "type": "scrape_result",
            "data": result.to_dict()
        })
        
        # 如果有帖子，进行情绪分析
        if result.posts:
            texts = [p.text for p in result.posts]
            sentiment = await self.sentiment_analyzer.analyze_batch(texts)
            logger.info(f"Sentiment analysis: {sentiment}")
    
    async def _broadcast(self, message: dict):
        """广播消息到所有WebSocket连接"""
        if not self.ws_connections:
            return
        
        message_str = json.dumps(message, default=str)
        disconnected = []
        
        for ws in self.ws_connections:
            try:
                await ws.send_text(message_str)
            except:
                disconnected.append(ws)
        
        for ws in disconnected:
            self.ws_connections.remove(ws)


# 全局Agent实例
agent: Optional[TradingAgent] = None


# ==================== 请求/响应模型 ====================

class StartRequest(BaseModel):
    symbol: str = "BTC/USDT"


class SignalResponse(BaseModel):
    signal: Optional[Signal] = None
    ticker: Optional[Ticker] = None


class BacktestRequest(BaseModel):
    symbol: str = "BTC/USDT"
    strategy: str = "momentum"
    initial_balance: float = 10000
    order_size: float = 100
    bars: int = 500


class ConfigUpdateRequest(BaseModel):
    trading: Optional[Dict[str, Any]] = None
    risk: Optional[Dict[str, Any]] = None
    ai: Optional[Dict[str, Any]] = None


# ==================== 应用生命周期 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global agent
    agent = TradingAgent()
    logger.info("Application started")
    yield
    if agent and agent.is_running:
        await agent.stop()
    logger.info("Application stopped")


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    app = FastAPI(
        title="Auto Trading Agent API",
        description="Web3 AI自动交易系统API",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # CORS配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app


app = create_app()


# ==================== REST API 路由 ====================

@app.get("/")
async def root():
    """根路由"""
    return {
        "name": "Auto Trading Agent",
        "version": "1.0.0",
        "status": "running" if agent and agent.is_running else "stopped"
    }


@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    return {
        "is_running": agent.is_running,
        "current_symbol": agent.current_symbol,
        "last_ticker": agent.last_ticker.model_dump() if agent.last_ticker else None,
        "last_signal": agent.last_signal.model_dump() if agent.last_signal else None,
        "positions": [p.model_dump() for p in agent.order_manager.get_all_positions()],
        "active_orders": [o.model_dump() for o in agent.order_manager.get_active_orders()],
        "statistics": agent.order_manager.get_statistics(),
        "risk_state": agent.risk_engine.get_state().model_dump()
    }


@app.post("/api/start")
async def start_agent(request: StartRequest):
    """启动Agent"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    agent.current_symbol = request.symbol
    await agent.start()
    
    return {"status": "started", "symbol": request.symbol}


@app.post("/api/stop")
async def stop_agent():
    """停止Agent"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    await agent.stop()
    
    return {"status": "stopped"}


@app.get("/api/ticker/{symbol}")
async def get_ticker(symbol: str):
    """获取行情"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    ticker = await agent.data_provider.get_ticker(symbol.replace("-", "/"))
    return ticker.model_dump()


@app.get("/api/klines/{symbol}")
async def get_klines(
    symbol: str,
    interval: str = "1h",
    limit: int = 100
):
    """获取K线数据"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    klines = await agent.data_provider.get_klines(
        symbol.replace("-", "/"),
        interval=interval,
        limit=limit
    )
    return [k.model_dump() for k in klines]


@app.get("/api/signal/{symbol}")
async def get_signal(symbol: str):
    """获取交易信号"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    symbol = symbol.replace("-", "/")
    
    # 获取数据
    ticker = await agent.data_provider.get_ticker(symbol)
    klines = await agent.data_provider.get_klines(symbol, interval="1h", limit=100)
    
    # 生成信号
    signal = await agent.momentum_strategy.run(symbol, ticker, klines)
    
    return SignalResponse(signal=signal, ticker=ticker).model_dump()


@app.get("/api/positions")
async def get_positions():
    """获取持仓"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    return [p.model_dump() for p in agent.order_manager.get_all_positions()]


@app.get("/api/orders")
async def get_orders():
    """获取订单"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    return [o.model_dump() for o in agent.order_manager.orders.values()]


@app.get("/api/risk")
async def get_risk_status():
    """获取风控状态"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    return {
        "state": agent.risk_engine.get_state().model_dump(),
        "rules": agent.risk_engine.get_rules_status()
    }


@app.post("/api/risk/reset")
async def reset_risk():
    """重置风控状态"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    agent.risk_engine.reset_circuit_breaker()
    agent.risk_engine.reset_daily()
    
    return {"status": "reset"}


@app.get("/api/sentiment/{symbol}")
async def get_sentiment(symbol: str):
    """获取情绪分析"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    result = await agent.sentiment_analyzer.analyze(symbol.replace("-", "/"))
    fear_greed = await agent.sentiment_analyzer.get_market_fear_greed()
    
    return {
        "sentiment": result.model_dump(),
        "fear_greed_index": fear_greed
    }


@app.post("/api/backtest")
async def run_backtest(request: BacktestRequest):
    """运行回测"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    # 获取历史数据
    klines = await agent.data_provider.get_klines(
        request.symbol,
        interval="1h",
        limit=request.bars
    )
    
    # 创建策略
    if request.strategy == "momentum":
        strategy = MomentumStrategy()
    else:
        strategy = MomentumStrategy()
    
    # 创建回测引擎
    backtest = BacktestEngine(
        initial_balance=request.initial_balance,
        fee_rate=0.001,
        slippage=0.0005
    )
    
    # 运行回测
    result = await backtest.run(
        request.symbol,
        strategy,
        klines,
        order_size=request.order_size
    )
    
    return result.model_dump()


@app.get("/api/config")
async def get_config_api():
    """获取配置"""
    config = get_config()
    return config.model_dump()


@app.put("/api/config")
async def update_config(request: ConfigUpdateRequest):
    """更新配置"""
    config = get_config()
    
    if request.trading:
        for key, value in request.trading.items():
            if hasattr(config.trading, key):
                setattr(config.trading, key, value)
    
    if request.risk:
        for key, value in request.risk.items():
            if hasattr(config.risk, key):
                setattr(config.risk, key, value)
    
    if request.ai:
        for key, value in request.ai.items():
            if hasattr(config.ai, key):
                setattr(config.ai, key, value)
    
    set_config(config)
    
    return {"status": "updated", "config": config.model_dump()}


# ==================== Apify 抓取 API ====================

class ScraperModeRequest(BaseModel):
    mode: str = "manual"  # "manual" 或 "auto"


class ScraperConfigRequest(BaseModel):
    search_terms: Optional[List[str]] = None
    subreddits: Optional[List[str]] = None
    max_items: Optional[int] = None
    api_token: Optional[str] = None
    data_source: Optional[str] = None  # "twitter" 或 "reddit"


@app.get("/api/scraper/status")
async def get_scraper_status():
    """获取抓取器状态"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    return agent.apify_scraper.get_status()


@app.post("/api/scraper/scrape")
async def trigger_scrape():
    """手动触发一次抓取"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    result = await agent.apify_scraper.scrape()
    return result.to_dict()


@app.post("/api/scraper/scrape/reddit")
async def trigger_reddit_scrape():
    """手动触发 Reddit 抓取"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    result = await agent.apify_scraper.scrape_reddit()
    return result.to_dict()


@app.post("/api/scraper/scrape/twitter")
async def trigger_twitter_scrape():
    """手动触发 Twitter 抓取"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    result = await agent.apify_scraper.scrape_twitter()
    return result.to_dict()


@app.post("/api/scraper/mode")
async def set_scraper_mode(request: ScraperModeRequest):
    """设置抓取模式（手动/自动）"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    mode = ScraperMode.AUTO if request.mode == "auto" else ScraperMode.MANUAL
    agent.apify_scraper.set_mode(mode)
    
    return {
        "mode": mode.value,
        "message": f"Scraper mode set to {mode.value}"
    }


@app.post("/api/scraper/config")
async def update_scraper_config(request: ScraperConfigRequest):
    """更新抓取器配置"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    if request.search_terms:
        agent.apify_scraper.search_terms = request.search_terms
    
    if request.subreddits:
        agent.apify_scraper.subreddits = request.subreddits
    
    if request.max_items:
        agent.apify_scraper.max_items = request.max_items
    
    if request.api_token:
        agent.apify_scraper.api_token = request.api_token
    
    if request.data_source:
        source = DataSource.REDDIT if request.data_source == "reddit" else DataSource.TWITTER
        agent.apify_scraper.set_data_source(source)
    
    return {
        "message": "Scraper config updated",
        "config": {
            "search_terms": agent.apify_scraper.search_terms,
            "subreddits": agent.apify_scraper.subreddits,
            "max_items": agent.apify_scraper.max_items,
            "data_source": agent.apify_scraper.data_source.value
        }
    }


@app.get("/api/scraper/last-result")
async def get_last_scrape_result():
    """获取最近一次抓取结果"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    result = agent.apify_scraper.get_last_result()
    if result:
        return result.to_dict()
    return {"message": "No scrape result yet"}


# ==================== WebSocket =======================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接"""
    await websocket.accept()
    
    if agent:
        agent.ws_connections.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # 处理客户端消息
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            
            elif message.get("type") == "subscribe":
                symbol = message.get("symbol", "BTC/USDT")
                if agent:
                    agent.current_symbol = symbol
                    await websocket.send_text(json.dumps({
                        "type": "subscribed",
                        "symbol": symbol
                    }))
    
    except WebSocketDisconnect:
        if agent and websocket in agent.ws_connections:
            agent.ws_connections.remove(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if agent and websocket in agent.ws_connections:
            agent.ws_connections.remove(websocket)


# ==================== 启动入口 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# ==================== 新闻抓取 API ====================

@app.get("/api/news/latest")
async def get_latest_news(
    symbol: Optional[str] = Query(None, description="币种符号，如BTC"),
    limit: int = Query(10, ge=1, le=50, description="返回新闻数量")
):
    """获取最新财经新闻"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    try:
        from backend.data.news_scraper import NewsScraper
        from backend.ai.news_analyzer import NewsAnalyzer
        
        # 创建新闻抓取器
        scraper = NewsScraper()
        
        # 抓取新闻
        articles = await scraper.scrape_all(symbol=symbol)
        
        # 关闭客户端
        await scraper.close()
        
        # 限制返回数量
        articles = articles[:limit]
        
        # 转换为字典
        news_list = [
            {
                "title": article.title,
                "url": article.url,
                "source": article.source,
                "published_at": article.published_at.isoformat(),
                "summary": article.summary,
                "tags": article.tags
            }
            for article in articles
        ]
        
        return {
            "count": len(news_list),
            "news": news_list
        }
    
    except Exception as e:
        logger.error(f"News scraping error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/news/analyzed")
async def get_analyzed_news(
    symbol: Optional[str] = Query(None, description="币种符号，如BTC"),
    min_stars: int = Query(3, ge=1, le=5, description="最低星级过滤"),
    limit: int = Query(10, ge=1, le=50, description="返回新闻数量")
):
    """获取AI分析后的财经新闻"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    try:
        from backend.data.news_scraper import NewsScraper
        from backend.ai.news_analyzer import NewsAnalyzer
        
        # 创建新闻抓取器和分析器
        scraper = NewsScraper()
        analyzer = NewsAnalyzer()
        
        # 抓取新闻
        articles = await scraper.scrape_all(symbol=symbol)
        
        # 关闭抓取器客户端
        await scraper.close()
        
        # AI分析新闻
        analyzed_news = []
        for article in articles[:limit * 2]:  # 多抓取一些，过滤后可能不够
            try:
                impact = await analyzer.analyze_news(
                    title=article.title,
                    content=article.summary,
                    symbol=symbol
                )
                
                # 过滤低星级新闻
                if impact.importance_stars >= min_stars:
                    analyzed_news.append({
                        "title": article.title,
                        "url": article.url,
                        "source": article.source,
                        "published_at": article.published_at.isoformat(),
                        "summary": article.summary,
                        "importance_stars": impact.importance_stars,
                        "impact_level": impact.impact_level,
                        "impact_direction": impact.impact_direction,
                        "impact_score": impact.impact_score,
                        "confidence": impact.confidence,
                        "affected_symbols": impact.affected_symbols,
                        "key_points": impact.key_points,
                        "reasoning": impact.reasoning
                    })
                
                # 达到数量限制就停止
                if len(analyzed_news) >= limit:
                    break
            
            except Exception as e:
                logger.warning(f"Failed to analyze news: {e}")
                continue
        
        return {
            "count": len(analyzed_news),
            "news": analyzed_news
        }
    
    except Exception as e:
        logger.error(f"News analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/news/analyze")
async def analyze_single_news(
    title: str = Query(..., description="新闻标题"),
    content: Optional[str] = Query(None, description="新闻内容"),
    symbol: Optional[str] = Query(None, description="币种符号")
):
    """分析单条新闻"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    try:
        from backend.ai.news_analyzer import NewsAnalyzer
        
        analyzer = NewsAnalyzer()
        impact = await analyzer.analyze_news(
            title=title,
            content=content,
            symbol=symbol
        )
        
        return {
            "title": title,
            "importance_stars": impact.importance_stars,
            "impact_level": impact.impact_level,
            "impact_direction": impact.impact_direction,
            "impact_score": impact.impact_score,
            "confidence": impact.confidence,
            "affected_symbols": impact.affected_symbols,
            "key_points": impact.key_points,
            "reasoning": impact.reasoning
        }
    
    except Exception as e:
        logger.error(f"News analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ==================== 多Agent协作系统 API ====================

@app.get("/api/multi-agent/deliberate")
async def multi_agent_deliberate(
    symbol: str = Query("BTC/USDT", description="交易对")
):
    """
    AI委员会讨论并做出决策
    
    这是黑客松的核心创新功能！
    """
    try:
        # 准备上下文
        ticker = await agent.data_provider.get_ticker(symbol)
        klines = await agent.data_provider.get_klines(symbol, "1h", limit=100)
        
        # 获取新闻影响
        from backend.data.news_scraper import NewsScraper
        news_scraper = NewsScraper()
        news_list = await news_scraper.scrape_all()
        
        # 分析新闻
        from backend.ai.news_analyzer import NewsAnalyzer
        news_analyzer = NewsAnalyzer()
        analyzed_news = []
        for news in news_list[:5]:  # 只分析前5条
            impact = await news_analyzer.analyze_news(
                news.title,
                news.content,
                symbol
            )
            if impact and impact.importance_stars >= 3:
                analyzed_news.append(impact.dict())
        
        context = {
            "symbol": symbol,
            "ticker": ticker,
            "klines": klines,
            "news_impacts": analyzed_news
        }
        
        # AI委员会讨论
        from backend.ai.multi_agent_system import MultiAgentSystem
        from backend.data.whale_tracker import get_whale_tracker
        
        multi_agent = MultiAgentSystem(
            news_analyzer=news_analyzer,
            whale_tracker=get_whale_tracker(),
            risk_manager=agent.risk_engine
        )
        
        consensus = await multi_agent.deliberate(context)
        
        return {
            "success": True,
            "data": consensus.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Multi-agent deliberate error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/multi-agent/status")
async def multi_agent_status():
    """获取多Agent系统状态"""
    try:
        return {
            "success": True,
            "data": {
                "agents": [
                    {
                        "role": "news_analyst",
                        "name": "📰 新闻分析师",
                        "status": "active",
                        "weight": 1.0
                    },
                    {
                        "role": "technical_analyst",
                        "name": "📊 技术分析师",
                        "status": "active",
                        "weight": 1.0
                    },
                    {
                        "role": "onchain_analyst",
                        "name": "🔗 链上分析师",
                        "status": "active",
                        "weight": 1.0
                    },
                    {
                        "role": "risk_manager",
                        "name": "🛡️ 风控专家",
                        "status": "active",
                        "weight": 1.0
                    },
                    {
                        "role": "decision_maker",
                        "name": "🎯 决策者",
                        "status": "active",
                        "weight": 1.0
                    }
                ],
                "last_deliberation": None,
                "total_deliberations": 0
            }
        }
    except Exception as e:
        logger.error(f"Multi-agent status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 鲸鱼追踪 API ====================

@app.get("/api/whale/analysis")
async def whale_analysis(
    symbol: str = Query("BTC/USDT", description="交易对")
):
    """
    获取链上大户行为分析
    
    这是黑客松的第二个核心创新功能！
    """
    try:
        from backend.data.whale_tracker import get_whale_tracker
        
        whale_tracker = get_whale_tracker()
        analysis = await whale_tracker.analyze_whale_behavior(symbol)
        
        if not analysis:
            return {
                "success": False,
                "message": "No whale data available"
            }
        
        return {
            "success": True,
            "data": analysis
        }
        
    except Exception as e:
        logger.error(f"Whale analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/whale/alerts")
async def whale_alerts(
    symbol: str = Query("BTC/USDT", description="交易对")
):
    """获取大户警报"""
    try:
        from backend.data.whale_tracker import get_whale_tracker
        
        whale_tracker = get_whale_tracker()
        alerts = await whale_tracker.get_whale_alerts(symbol)
        
        return {
            "success": True,
            "data": alerts
        }
        
    except Exception as e:
        logger.error(f"Whale alerts error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/whale/top-positions")
async def whale_top_positions(
    symbol: str = Query("BTC/USDT", description="交易对"),
    limit: int = Query(10, description="返回数量")
):
    """获取前N大户持仓"""
    try:
        from backend.data.whale_tracker import get_whale_tracker
        
        whale_tracker = get_whale_tracker()
        analysis = await whale_tracker.analyze_whale_behavior(symbol)
        
        if not analysis:
            return {
                "success": False,
                "message": "No whale data available"
            }
        
        top_whales = analysis["top_whales"][:limit]
        
        return {
            "success": True,
            "data": top_whales
        }
        
    except Exception as e:
        logger.error(f"Whale top positions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 集成决策 API ====================

@app.get("/api/integrated-decision")
async def integrated_decision(
    symbol: str = Query("BTC/USDT", description="交易对")
):
    """
    集成决策：多Agent + 鲸鱼追踪 + AI分析
    
    这是完整的决策流程展示！
    """
    try:
        # 1. 获取市场数据
        ticker = await agent.data_provider.get_ticker(symbol)
        klines = await agent.data_provider.get_klines(symbol, "1h", limit=100)
        
        # 2. 获取新闻
        from backend.data.news_scraper import NewsScraper
        news_scraper = NewsScraper()
        news_list = await news_scraper.scrape_all()
        
        # 3. 分析新闻
        from backend.ai.news_analyzer import NewsAnalyzer
        news_analyzer = NewsAnalyzer()
        analyzed_news = []
        for news in news_list[:5]:
            impact = await news_analyzer.analyze_news(
                news.title,
                news.content,
                symbol
            )
            if impact and impact.importance_stars >= 3:
                analyzed_news.append(impact.dict())
        
        # 4. 鲸鱼追踪
        from backend.data.whale_tracker import get_whale_tracker
        whale_tracker = get_whale_tracker()
        whale_analysis = await whale_tracker.analyze_whale_behavior(symbol)
        whale_alerts = await whale_tracker.get_whale_alerts(symbol)
        
        # 5. 多Agent讨论
        from backend.ai.multi_agent_system import MultiAgentSystem
        multi_agent = MultiAgentSystem(
            news_analyzer=news_analyzer,
            whale_tracker=whale_tracker,
            risk_manager=agent.risk_engine
        )
        
        context = {
            "symbol": symbol,
            "ticker": ticker,
            "klines": klines,
            "news_impacts": analyzed_news
        }
        
        consensus = await multi_agent.deliberate(context)
        
        # 6. 返回完整决策
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "timestamp": datetime.now().isoformat(),
                "market_data": {
                    "price": ticker.get("last"),
                    "change_24h": ticker.get("percentage")
                },
                "news_analysis": {
                    "count": len(analyzed_news),
                    "top_news": analyzed_news[:3]
                },
                "whale_analysis": whale_analysis,
                "whale_alerts": whale_alerts,
                "multi_agent_consensus": consensus.to_dict(),
                "final_recommendation": {
                    "decision": consensus.final_decision.value,
                    "confidence": consensus.confidence,
                    "reasoning": consensus.debate_summary
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Integrated decision error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Vibe策略管理 API ====================

from backend.strategy.vibe_strategy import get_vibe_manager, VibeRule

class VibeRuleRequest(BaseModel):
    """Vibe规则请求模型"""
    content: str = Field(..., description="规则内容")

class VibeRuleUpdateRequest(BaseModel):
    """Vibe规则更新请求模型"""
    content: Optional[str] = Field(None, description="规则内容")
    enabled: Optional[bool] = Field(None, description="是否启用")

@app.get("/api/vibe/rules")
async def get_vibe_rules(enabled_only: bool = Query(False, description="是否只返回启用的规则")):
    """获取所有Vibe规则"""
    try:
        vibe_manager = get_vibe_manager()
        rules = vibe_manager.get_all_rules(enabled_only=enabled_only)
        return {
            "success": True,
            "rules": [rule.to_dict() for rule in rules],
            "total": len(rules)
        }
    except Exception as e:
        logger.error(f"Get vibe rules error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vibe/rules")
async def add_vibe_rule(request: VibeRuleRequest):
    """添加新的Vibe规则"""
    try:
        vibe_manager = get_vibe_manager()
        rule = vibe_manager.add_rule(request.content)
        return {
            "success": True,
            "rule": rule.to_dict(),
            "message": "规则添加成功"
        }
    except Exception as e:
        logger.error(f"Add vibe rule error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/vibe/rules/{rule_id}")
async def update_vibe_rule(rule_id: str, request: VibeRuleUpdateRequest):
    """更新Vibe规则"""
    try:
        vibe_manager = get_vibe_manager()
        rule = vibe_manager.update_rule(
            rule_id=rule_id,
            content=request.content,
            enabled=request.enabled
        )
        
        if rule is None:
            raise HTTPException(status_code=404, detail="规则不存在")
        
        return {
            "success": True,
            "rule": rule.to_dict(),
            "message": "规则更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update vibe rule error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/vibe/rules/{rule_id}")
async def delete_vibe_rule(rule_id: str):
    """删除Vibe规则"""
    try:
        vibe_manager = get_vibe_manager()
        success = vibe_manager.delete_rule(rule_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="规则不存在")
        
        return {
            "success": True,
            "message": "规则删除成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete vibe rule error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vibe/prompt")
async def get_vibe_prompt():
    """获取Vibe规则的Prompt格式（用于AI）"""
    try:
        vibe_manager = get_vibe_manager()
        prompt = vibe_manager.get_rules_as_prompt()
        return {
            "success": True,
            "prompt": prompt,
            "rules_count": len(vibe_manager.get_all_rules(enabled_only=True))
        }
    except Exception as e:
        logger.error(f"Get vibe prompt error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Decision Flow Matrix API ====================

from backend.strategy.decision_flow import get_decision_flow_manager

class DecisionFlowUpdateRequest(BaseModel):
    """决策流更新请求"""
    master_switch: Optional[bool] = None
    nodes: Optional[Dict[str, dict]] = None

@app.get("/api/decision-flow/config")
async def get_decision_flow_config():
    """获取决策流配置"""
    try:
        manager = get_decision_flow_manager()
        config = manager.get_config()
        return {
            "success": True,
            "config": config
        }
    except Exception as e:
        logger.error(f"Get decision flow config error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/decision-flow/config")
async def update_decision_flow_config(request: DecisionFlowUpdateRequest):
    """更新决策流配置"""
    try:
        manager = get_decision_flow_manager()
        config = manager.update_config(
            master_switch=request.master_switch,
            nodes=request.nodes
        )
        return {
            "success": True,
            "config": config,
            "message": "配置已更新"
        }
    except Exception as e:
        logger.error(f"Update decision flow config error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/decision-flow/toggle/{node_id}")
async def toggle_decision_flow_node(node_id: str):
    """切换节点启用状态"""
    try:
        manager = get_decision_flow_manager()
        result = manager.toggle_node(node_id)
        return result
    except Exception as e:
        logger.error(f"Toggle node error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/decision-flow/reset")
async def reset_decision_flow_config():
    """重置为默认配置"""
    try:
        manager = get_decision_flow_manager()
        config = manager.reset_to_default()
        return {
            "success": True,
            "config": config,
            "message": "已重置为默认配置"
        }
    except Exception as e:
        logger.error(f"Reset decision flow config error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/decision-flow/enabled-nodes")
async def get_enabled_nodes():
    """获取所有启用的节点"""
    try:
        manager = get_decision_flow_manager()
        enabled_nodes = manager.get_enabled_nodes()
        return {
            "success": True,
            "enabled_nodes": enabled_nodes,
            "total": len(enabled_nodes)
        }
    except Exception as e:
        logger.error(f"Get enabled nodes error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/decision-flow/toggle/{node_id}/{sub_node_id}")
async def toggle_decision_flow_sub_node(node_id: str, sub_node_id: str):
    """切换子节点启用状态"""
    try:
        manager = get_decision_flow_manager()
        result = manager.toggle_sub_node(node_id, sub_node_id)
        return result
    except Exception as e:
        logger.error(f"Toggle sub node error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/decision-flow/sync-vibe-rules")
async def sync_vibe_rules_to_decision_flow():
    """同步Vibe规则到决策流"""
    try:
        from backend.strategy.vibe_strategy import get_vibe_manager
        vibe_manager = get_vibe_manager()
        rules = vibe_manager.get_all_rules()
        
        # 转换VibeRule对象为字典
        rules_dict = [rule.to_dict() for rule in rules]
        
        decision_manager = get_decision_flow_manager()
        decision_manager.load_vibe_rules(rules_dict)
        
        return {
            "success": True,
            "message": f"已同步 {len(rules)} 条Vibe规则",
            "rules_count": len(rules)
        }
    except Exception as e:
        logger.error(f"Sync vibe rules error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
