"""
FastAPI main application
Provides REST API and WebSocket endpoints
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv('/home/ubuntu/auto-trading-agent/.env')

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import core modules
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


# ==================== Global State ====================

class TradingAgent:
    """Trading Agent main class"""
    
    def __init__(self):
        self.config = get_config()
        self.event_bus = get_event_bus()
        
        # Initialize components
        # Use OKX real data, fallback to mock data if failed
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
        
        # Apify scraper (for X/Twitter data scraping)
        self.apify_scraper = get_scraper()
        self.apify_scraper.on_scrape_complete(self._on_scrape_complete)
        
        # Status
        self.is_running = False
        self.current_symbol = "BTC/USDT"
        self.last_ticker: Optional[Ticker] = None
        self.last_signal: Optional[Signal] = None
        
        # WebSocket connection management
        self.ws_connections: List[WebSocket] = []
    
    async def start(self):
        """StartAgent"""
        if self.is_running:
            return
        
        self.is_running = True
        logger.info("Trading Agent started")
        
        # Start data subscription
        await self.data_provider.subscribe_ticker(
            self.current_symbol,
            self._on_ticker_update
        )
        
        # Start event loop
        asyncio.create_task(self._main_loop())
    
    async def stop(self):
        """StopAgent"""
        self.is_running = False
        await self.data_provider.unsubscribe_ticker(self.current_symbol)
        self.data_provider.stop()
        logger.info("Trading Agent stopped")
    
    async def _on_ticker_update(self, ticker: Ticker):
        """Handle market data updates"""
        self.last_ticker = ticker
        
        # UpdatePositionP&L
        self.order_manager.update_position_price(ticker.symbol, ticker.last_price)
        
        # Broadcast to WebSocket
        await self._broadcast({
            "type": "ticker",
            "data": ticker.model_dump()
        })
    
    async def _main_loop(self):
        """Main loop"""
        while self.is_running:
            try:
                await asyncio.sleep(5)  # Execute every 5 seconds
                
                if not self.last_ticker:
                    continue
                
                # GetCandlestick data
                klines = await self.data_provider.get_klines(
                    self.current_symbol,
                    interval="1h",
                    limit=100
                )
                
                # Generate strategy signals
                momentum_signal = await self.momentum_strategy.run(
                    self.current_symbol,
                    self.last_ticker,
                    klines
                )
                
                # Signal fusion
                signals = [momentum_signal]
                fused_signal = self.signal_fusion.fuse(signals)
                self.last_signal = fused_signal
                
                # Broadcast signals
                await self._broadcast({
                    "type": "signal",
                    "data": fused_signal.model_dump()
                })
                
                # Risk controlCheck
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
                        # CreateOrder
                        order = self.order_manager.create_order_from_signal(
                            fused_signal,
                            size=100  # Fixed order amount
                        )
                        
                        if order:
                            # ExecuteOrder
                            result = await self.executor.submit_order(order)
                            
                            # UpdateOrder status
                            self.order_manager.update_order_status(
                                order.id,
                                result["status"],
                                filled_size=result.get("filled_size", 0),
                                avg_price=result.get("avg_price", 0),
                                fee=result.get("fee", 0),
                                error_msg=result.get("error", "")
                            )
                            
                            # Broadcast order updates
                            await self._broadcast({
                                "type": "order",
                                "data": order.model_dump()
                            })
                    else:
                        logger.warning(f"Risk check failed: {risk_result.reason}")
                
            except Exception as e:
                logger.error(f"Main loop error: {e}")
    
    async def _on_scrape_complete(self, result):
        """Handle Apify scrape completion"""
        logger.info(f"Apify scrape completed: {result.total_count} posts from {result.source}")
        
        # Broadcast to WebSocket
        await self._broadcast({
            "type": "scrape_result",
            "data": result.to_dict()
        })
        
        # If posts available, perform sentiment analysis
        if result.posts:
            texts = [p.text for p in result.posts]
            sentiment = await self.sentiment_analyzer.analyze_batch(texts)
            logger.info(f"Sentiment analysis: {sentiment}")
    
    async def _broadcast(self, message: dict):
        """Broadcast message to all WebSocket connections"""
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


# Global agent instance
agent: Optional[TradingAgent] = None


# ==================== Request/ResponseModel ====================

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


# ==================== Application Lifecycle ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application LifecycleManagement"""
    global agent
    agent = TradingAgent()
    logger.info("Application started")
    yield
    if agent and agent.is_running:
        await agent.stop()
    logger.info("Application stopped")


def create_app() -> FastAPI:
    """Create FastAPI application"""
    app = FastAPI(
        title="Auto Trading Agent API",
        description="Web3 AI Automated Trading System API",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # CORSconfiguration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app


app = create_app()


# ==================== REST API Route ====================

@app.get("/")
async def root():
    """RootRoute"""
    return {
        "name": "Auto Trading Agent",
        "version": "1.0.0",
        "status": "running" if agent and agent.is_running else "stopped"
    }


@app.get("/api/status")
async def get_status():
    """Get system status"""
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
    """StartAgent"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    agent.current_symbol = request.symbol
    await agent.start()
    
    return {"status": "started", "symbol": request.symbol}


@app.post("/api/stop")
async def stop_agent():
    """StopAgent"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    await agent.stop()
    
    return {"status": "stopped"}


@app.get("/api/ticker/{symbol}")
async def get_ticker(symbol: str):
    """Get market data"""
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
    """GetCandlestick data"""
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
    """GetTrading signal"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    symbol = symbol.replace("-", "/")
    
    # Get data
    ticker = await agent.data_provider.get_ticker(symbol)
    klines = await agent.data_provider.get_klines(symbol, interval="1h", limit=100)
    
    # Generate signals
    signal = await agent.momentum_strategy.run(symbol, ticker, klines)
    
    return SignalResponse(signal=signal, ticker=ticker).model_dump()


@app.get("/api/positions")
async def get_positions():
    """GetPosition"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    return [p.model_dump() for p in agent.order_manager.get_all_positions()]


@app.get("/api/orders")
async def get_orders():
    """GetOrder"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    return [o.model_dump() for o in agent.order_manager.orders.values()]


@app.get("/api/risk")
async def get_risk_status():
    """GetRisk controlStatus"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    return {
        "state": agent.risk_engine.get_state().model_dump(),
        "rules": agent.risk_engine.get_rules_status()
    }


@app.post("/api/risk/reset")
async def reset_risk():
    """Reset Risk ControlsStatus"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    agent.risk_engine.reset_circuit_breaker()
    agent.risk_engine.reset_daily()
    
    return {"status": "reset"}


@app.get("/api/sentiment/{symbol}")
async def get_sentiment(symbol: str):
    """GetSentimentAnalysis"""
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
    """RunningBacktest"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    # Get historical data
    klines = await agent.data_provider.get_klines(
        request.symbol,
        interval="1h",
        limit=request.bars
    )
    
    # CreateStrategy
    if request.strategy == "momentum":
        strategy = MomentumStrategy()
    else:
        strategy = MomentumStrategy()
    
    # CreateBacktest engine
    backtest = BacktestEngine(
        initial_balance=request.initial_balance,
        fee_rate=0.001,
        slippage=0.0005
    )
    
    # RunningBacktest
    result = await backtest.run(
        request.symbol,
        strategy,
        klines,
        order_size=request.order_size
    )
    
    return result.model_dump()


@app.get("/api/config")
async def get_config_api():
    """Getconfiguration"""
    config = get_config()
    return config.model_dump()


@app.put("/api/config")
async def update_config(request: ConfigUpdateRequest):
    """Update configuration"""
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


# ==================== Apify Scrape API ====================

class ScraperModeRequest(BaseModel):
    mode: str = "manual"  # "manual" or "auto"


class ScraperConfigRequest(BaseModel):
    search_terms: Optional[List[str]] = None
    subreddits: Optional[List[str]] = None
    max_items: Optional[int] = None
    api_token: Optional[str] = None
    data_source: Optional[str] = None  # "twitter" or "reddit"


@app.get("/api/scraper/status")
async def get_scraper_status():
    """Get scraper status"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    return agent.apify_scraper.get_status()


@app.post("/api/scraper/scrape")
async def trigger_scrape():
    """Manually trigger a scrape"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    result = await agent.apify_scraper.scrape()
    return result.to_dict()


@app.post("/api/scraper/scrape/reddit")
async def trigger_reddit_scrape():
    """ManualTrigger Reddit Scrape"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    result = await agent.apify_scraper.scrape_reddit()
    return result.to_dict()


@app.post("/api/scraper/scrape/twitter")
async def trigger_twitter_scrape():
    """ManualTrigger Twitter Scrape"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    result = await agent.apify_scraper.scrape_twitter()
    return result.to_dict()


@app.post("/api/scraper/mode")
async def set_scraper_mode(request: ScraperModeRequest):
    """Set scraper mode(Manual/Auto)"""
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
    """Update scraper configuration"""
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
    """Get last scrape result"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    result = agent.apify_scraper.get_last_result()
    if result:
        return result.to_dict()
    return {"message": "No scrape result yet"}


# ==================== WebSocket =======================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection"""
    await websocket.accept()
    
    if agent:
        agent.ws_connections.append(websocket)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Process client messages
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


# ==================== Entry Point ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# ==================== NewsScrape API ====================

@app.get("/api/news/latest")
async def get_latest_news(
    symbol: Optional[str] = Query(None, description="Trading symbol, e.g. BTC"),
    limit: int = Query(10, ge=1, le=50, description="ReturnNewsQuantity")
):
    """Get latest financial news"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    try:
        from backend.data.news_scraper import NewsScraper
        from backend.ai.news_analyzer import NewsAnalyzer
        
        # CreateNews scraper
        scraper = NewsScraper()
        
        # ScrapeNews
        articles = await scraper.scrape_all(symbol=symbol)
        
        # Close client
        await scraper.close()
        
        # LimitReturnQuantity
        articles = articles[:limit]
        
        # Convert to dictionary
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
    symbol: Optional[str] = Query(None, description="Trading symbol, e.g. BTC"),
    min_stars: int = Query(3, ge=1, le=5, description="Minimum star rating filter"),
    limit: int = Query(10, ge=1, le=50, description="ReturnNewsQuantity")
):
    """Get AI-analyzed financial news"""
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    
    try:
        from backend.data.news_scraper import NewsScraper
        from backend.ai.news_analyzer import NewsAnalyzer
        
        # Create news scraper and analyzer
        scraper = NewsScraper()
        analyzer = NewsAnalyzer()
        
        # ScrapeNews
        articles = await scraper.scrape_all(symbol=symbol)
        
        # Close scraperClient
        await scraper.close()
        
        # AIAnalysisNews
        analyzed_news = []
        for article in articles[:limit * 2]:  # Scrape extra, may not be enough after filtering
            try:
                impact = await analyzer.analyze_news(
                    title=article.title,
                    content=article.summary,
                    symbol=symbol
                )
                
                # Filter low-star news
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
                
                # Stop when quantity limit reached
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
    title: str = Query(..., description="News title"),
    content: Optional[str] = Query(None, description="News content"),
    symbol: Optional[str] = Query(None, description="Trading symbol")
):
    """Analyze a single news item"""
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



# ==================== Multi-Agent collaboration system API ====================

@app.get("/api/multi-agent/deliberate")
async def multi_agent_deliberate(
    symbol: str = Query("BTC/USDT", description="Trading pair")
):
    """
    AI committee deliberates and makes decision
    
    This is the core hackathon innovation!
    """
    try:
        # Prepare context
        ticker = await agent.data_provider.get_ticker(symbol)
        klines = await agent.data_provider.get_klines(symbol, "1h", limit=100)
        
        # Get news impact
        from backend.data.news_scraper import NewsScraper
        news_scraper = NewsScraper()
        news_list = await news_scraper.scrape_all()
        
        # AnalysisNews
        from backend.ai.news_analyzer import NewsAnalyzer
        news_analyzer = NewsAnalyzer()
        analyzed_news = []
        for news in news_list[:5]:  # Only analyze the top 5
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
        
        # AI committee discussion
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
    """GetMulti-Agent systemStatus"""
    try:
        return {
            "success": True,
            "data": {
                "agents": [
                    {
                        "role": "news_analyst",
                        "name": "📰 News Analyst",
                        "status": "active",
                        "weight": 1.0
                    },
                    {
                        "role": "technical_analyst",
                        "name": "📊 Technical Analyst",
                        "status": "active",
                        "weight": 1.0
                    },
                    {
                        "role": "onchain_analyst",
                        "name": "🔗 On-chain Analyst",
                        "status": "active",
                        "weight": 1.0
                    },
                    {
                        "role": "risk_manager",
                        "name": "🛡️ Risk Control Expert",
                        "status": "active",
                        "weight": 1.0
                    },
                    {
                        "role": "decision_maker",
                        "name": "🎯 Decision Maker",
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


# ==================== Whale Tracker API ====================

@app.get("/api/whale/analysis")
async def whale_analysis(
    symbol: str = Query("BTC/USDT", description="Trading pair")
):
    """
    Get on-chain whale behavior analysis
    
    This is the second core hackathon innovation!
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
    symbol: str = Query("BTC/USDT", description="Trading pair")
):
    """Get whale alerts"""
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
    symbol: str = Query("BTC/USDT", description="Trading pair"),
    limit: int = Query(10, description="ReturnQuantity")
):
    """Get top N whale positions"""
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


# ==================== Integrated Decision API ====================

@app.get("/api/integrated-decision")
async def integrated_decision(
    symbol: str = Query("BTC/USDT", description="Trading pair")
):
    """
    Integrated Decision: Multi-Agent + Whale Tracker + AI Analysis
    
    This demonstrates the complete decision flow!
    """
    try:
        # 1. Get market data
        ticker = await agent.data_provider.get_ticker(symbol)
        klines = await agent.data_provider.get_klines(symbol, "1h", limit=100)
        
        # 2. Get news
        from backend.data.news_scraper import NewsScraper
        news_scraper = NewsScraper()
        news_list = await news_scraper.scrape_all()
        
        # 3. Analyze news
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
        
        # 4. Whale Tracker
        from backend.data.whale_tracker import get_whale_tracker
        whale_tracker = get_whale_tracker()
        whale_analysis = await whale_tracker.analyze_whale_behavior(symbol)
        whale_alerts = await whale_tracker.get_whale_alerts(symbol)
        
        # 5. Multi-agent discussion
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
        
        # 6. Return complete decision
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


# ==================== VibeStrategyManagement API ====================

from backend.strategy.vibe_strategy import get_vibe_manager, VibeRule

class VibeRuleRequest(BaseModel):
    """VibeRuleRequestModel"""
    content: str = Field(..., description="Rule content")

class VibeRuleUpdateRequest(BaseModel):
    """Vibe rule update request model"""
    content: Optional[str] = Field(None, description="Rule content")
    enabled: Optional[bool] = Field(None, description="Whether to enable")

@app.get("/api/vibe/rules")
async def get_vibe_rules(enabled_only: bool = Query(False, description="Whether to return only enabled rules")):
    """Get all vibe rules"""
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
    """Add a new vibe rule"""
    try:
        vibe_manager = get_vibe_manager()
        rule = vibe_manager.add_rule(request.content)
        return {
            "success": True,
            "rule": rule.to_dict(),
            "message": "RuleAddSuccess"
        }
    except Exception as e:
        logger.error(f"Add vibe rule error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/vibe/rules/{rule_id}")
async def update_vibe_rule(rule_id: str, request: VibeRuleUpdateRequest):
    """Update vibe rule"""
    try:
        vibe_manager = get_vibe_manager()
        rule = vibe_manager.update_rule(
            rule_id=rule_id,
            content=request.content,
            enabled=request.enabled
        )
        
        if rule is None:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        return {
            "success": True,
            "rule": rule.to_dict(),
            "message": "Rule updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update vibe rule error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/vibe/rules/{rule_id}")
async def delete_vibe_rule(rule_id: str):
    """DeleteVibeRule"""
    try:
        vibe_manager = get_vibe_manager()
        success = vibe_manager.delete_rule(rule_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Rule not found")
        
        return {
            "success": True,
            "message": "RuleDeleteSuccess"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete vibe rule error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vibe/prompt")
async def get_vibe_prompt():
    """Get vibe rules in prompt format (for AI)"""
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
    """Decision flow update request"""
    master_switch: Optional[bool] = None
    nodes: Optional[Dict[str, dict]] = None

@app.get("/api/decision-flow/config")
async def get_decision_flow_config():
    """Get decision flow configuration"""
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
    """Update decision flow configuration"""
    try:
        manager = get_decision_flow_manager()
        config = manager.update_config(
            master_switch=request.master_switch,
            nodes=request.nodes
        )
        return {
            "success": True,
            "config": config,
            "message": "Configuration updated"
        }
    except Exception as e:
        logger.error(f"Update decision flow config error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/decision-flow/toggle/{node_id}")
async def toggle_decision_flow_node(node_id: str):
    """ToggleNodeEnabledStatus"""
    try:
        manager = get_decision_flow_manager()
        result = manager.toggle_node(node_id)
        return result
    except Exception as e:
        logger.error(f"Toggle node error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/decision-flow/reset")
async def reset_decision_flow_config():
    """Reset to default configuration"""
    try:
        manager = get_decision_flow_manager()
        config = manager.reset_to_default()
        return {
            "success": True,
            "config": config,
            "message": "Reset to default configuration"
        }
    except Exception as e:
        logger.error(f"Reset decision flow config error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/decision-flow/enabled-nodes")
async def get_enabled_nodes():
    """Get all enabled nodes"""
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
    """Toggle sub-node enabled status"""
    try:
        manager = get_decision_flow_manager()
        result = manager.toggle_sub_node(node_id, sub_node_id)
        return result
    except Exception as e:
        logger.error(f"Toggle sub node error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/decision-flow/sync-vibe-rules")
async def sync_vibe_rules_to_decision_flow():
    """Sync vibe rules to decision flow"""
    try:
        from backend.strategy.vibe_strategy import get_vibe_manager
        vibe_manager = get_vibe_manager()
        rules = vibe_manager.get_all_rules()
        
        # Convert vibe rule objects to dictionaries
        rules_dict = [rule.to_dict() for rule in rules]
        
        decision_manager = get_decision_flow_manager()
        decision_manager.load_vibe_rules(rules_dict)
        
        return {
            "success": True,
            "message": f"Synced {len(rules)} vibe rules",
            "rules_count": len(rules)
        }
    except Exception as e:
        logger.error(f"Sync vibe rules error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
