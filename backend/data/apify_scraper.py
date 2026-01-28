"""
Apify 数据抓取模块
支持从 X (Twitter) 和 Reddit 抓取加密货币相关内容进行情绪分析
支持手动模式和自动模式（每20分钟抓取一次）

使用 ApifyClientAsync 异步客户端
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import os

# 使用官方 Apify 客户端
from apify_client import ApifyClientAsync


class ScraperMode(str, Enum):
    """抓取模式"""
    MANUAL = "manual"  # 手动模式：点击立即抓取
    AUTO = "auto"      # 自动模式：每20分钟抓取一次


class DataSource(str, Enum):
    """数据源"""
    TWITTER = "twitter"
    REDDIT = "reddit"


@dataclass
class SocialPost:
    """社交媒体帖子数据模型（统一格式）"""
    id: str
    text: str
    title: str  # Reddit 帖子标题，Twitter 为空
    author_name: str
    author_username: str
    created_at: str
    source: str  # "twitter" 或 "reddit"
    url: str = ""
    score: int = 0  # 点赞数/upvotes
    comments: int = 0
    subreddit: str = ""  # Reddit 子版块
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScrapeResult:
    """抓取结果"""
    success: bool
    posts: List[SocialPost] = field(default_factory=list)
    error: Optional[str] = None
    scraped_at: str = ""
    run_id: str = ""
    dataset_id: str = ""
    source: str = ""  # "twitter" 或 "reddit"
    search_terms: List[str] = field(default_factory=list)
    total_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "posts": [p.to_dict() for p in self.posts],
            "error": self.error,
            "scraped_at": self.scraped_at,
            "run_id": self.run_id,
            "dataset_id": self.dataset_id,
            "source": self.source,
            "search_terms": self.search_terms,
            "total_count": self.total_count
        }


class ApifyScraper:
    """Apify 社交媒体数据抓取器"""
    
    # Actor IDs
    REDDIT_ACTOR = "macrocosmos/reddit-scraper"
    TWITTER_ACTOR = "apidojo/tweet-scraper"
    
    # 默认搜索关键词（加密货币相关）
    DEFAULT_SEARCH_TERMS = [
        "Bitcoin",
        "Ethereum", 
        "crypto",
        "cryptocurrency",
        "BTC"
    ]
    
    # 默认 Reddit 子版块
    DEFAULT_SUBREDDITS = [
        "Bitcoin",
        "CryptoCurrency",
        "ethereum",
        "CryptoMarkets"
    ]
    
    # 自动模式间隔（秒）
    AUTO_INTERVAL = 20 * 60  # 20分钟
    
    def __init__(self, api_token: str = None):
        """
        初始化抓取器
        
        Args:
            api_token: Apify API Token，如果不提供则从环境变量读取
        """
        self.api_token = api_token or os.environ.get("APIFY_API_TOKEN", "")
        self._client: Optional[ApifyClientAsync] = None
        
        # 状态
        self.mode = ScraperMode.MANUAL
        self.data_source = DataSource.REDDIT  # 默认使用 Reddit（更稳定）
        self._auto_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._last_scrape_result: Optional[ScrapeResult] = None
        self._last_scrape_time: Optional[datetime] = None
        
        # 回调函数
        self._on_scrape_complete: Optional[Callable[[ScrapeResult], None]] = None
        
        # 搜索配置
        self.search_terms = self.DEFAULT_SEARCH_TERMS[:2]
        self.subreddits = self.DEFAULT_SUBREDDITS[:2]
        self.max_items = 10
    
    def _get_client(self) -> ApifyClientAsync:
        """获取 Apify 客户端"""
        if self._client is None:
            self._client = ApifyClientAsync(token=self.api_token)
        return self._client
    
    async def scrape_reddit(
        self, 
        subreddits: List[str] = None,
        max_items: int = None
    ) -> ScrapeResult:
        """
        抓取 Reddit 帖子（使用官方 ApifyClientAsync）
        
        Args:
            subreddits: 子版块列表
            max_items: 最大抓取数量
            
        Returns:
            ScrapeResult: 抓取结果
        """
        if not self.api_token:
            return ScrapeResult(
                success=False,
                error="Apify API Token not configured",
                scraped_at=datetime.now().isoformat(),
                source="reddit"
            )
        
        subs = subreddits or self.subreddits
        max_count = max_items or self.max_items
        
        try:
            client = self._get_client()
            
            # 准备 Actor 输入（参考你成功的脚本）
            actor_input = {
                "subreddits": subs,
                "limit": max_count,
                "sort": "new"
            }
            
            print(f"[Reddit Scraper] Calling actor={self.REDDIT_ACTOR} with input={actor_input}")
            
            # 运行 Actor
            run = await client.actor(self.REDDIT_ACTOR).call(
                run_input=actor_input,
                timeout_secs=120  # 2分钟超时
            )
            
            run_id = run.get("id", "")
            dataset_id = run.get("defaultDatasetId", "")
            status = run.get("status", "")
            
            print(f"[Reddit Scraper] Actor run completed: status={status}, datasetId={dataset_id}")
            
            if status not in ["SUCCEEDED", "READY"]:
                return ScrapeResult(
                    success=False,
                    error=f"Actor run failed with status: {status}",
                    scraped_at=datetime.now().isoformat(),
                    run_id=run_id,
                    source="reddit"
                )
            
            # 从数据集获取结果
            dataset_client = client.dataset(dataset_id)
            items = []
            
            async for item in dataset_client.iterate_items():
                items.append(item)
            
            print(f"[Reddit Scraper] Fetched {len(items)} raw items from dataset")
            
            # 解析帖子数据
            posts = []
            for item in items:
                post = self._parse_reddit_post(item)
                if post:
                    posts.append(post)
            
            result = ScrapeResult(
                success=True,
                posts=posts,
                scraped_at=datetime.now().isoformat(),
                run_id=run_id,
                dataset_id=dataset_id,
                source="reddit",
                search_terms=subs,
                total_count=len(posts)
            )
            
            # 更新状态
            self._last_scrape_result = result
            self._last_scrape_time = datetime.now()
            
            # 触发回调
            await self._trigger_callback(result)
            
            return result
            
        except Exception as e:
            import traceback
            print(f"[Reddit Scraper] Error: {e}")
            print(f"[Reddit Scraper] Traceback: {traceback.format_exc()}")
            return ScrapeResult(
                success=False,
                error=str(e),
                scraped_at=datetime.now().isoformat(),
                source="reddit"
            )
    
    def _parse_reddit_post(self, item: Dict[str, Any]) -> Optional[SocialPost]:
        """解析 Reddit 帖子数据"""
        try:
            # 跳过无效数据
            if not item:
                return None
            
            # 处理 isNsfw 字段名
            if 'isNsfw' in item:
                item['is_nsfw'] = item.pop('isNsfw')
            
            # macrocosmos/reddit-scraper 格式
            post_id = item.get("id", "")
            title = item.get("title", "")
            body = item.get("body", "")
            username = item.get("username", "Unknown")
            community = item.get("communityName", "") or item.get("community", "")
            url = item.get("url", "")
            score = item.get("score", 0)
            num_comments = item.get("num_comments", 0)
            created_at = item.get("createdAt", "")
            
            # 跳过空帖子
            if not title and not body:
                return None
            
            return SocialPost(
                id=str(post_id),
                title=title,
                text=body or title,
                author_name=username,
                author_username=username,
                created_at=created_at,
                source="reddit",
                url=url,
                score=score,
                comments=num_comments,
                subreddit=community.replace("r/", "") if community else ""
            )
            
        except Exception as e:
            print(f"Error parsing Reddit post: {e}")
            return None
    
    async def scrape_twitter(
        self, 
        search_terms: List[str] = None,
        max_items: int = None
    ) -> ScrapeResult:
        """
        抓取 Twitter 推文
        
        Args:
            search_terms: 搜索关键词
            max_items: 最大抓取数量
            
        Returns:
            ScrapeResult: 抓取结果
        """
        if not self.api_token:
            return ScrapeResult(
                success=False,
                error="Apify API Token not configured",
                scraped_at=datetime.now().isoformat(),
                source="twitter"
            )
        
        terms = search_terms or self.search_terms
        max_count = max_items or self.max_items
        
        try:
            client = self._get_client()
            
            actor_input = {
                "searchTerms": terms,
                "maxTweets": max_count,
                "sort": "Latest"
            }
            
            print(f"[Twitter Scraper] Calling actor={self.TWITTER_ACTOR} with input={actor_input}")
            
            run = await client.actor(self.TWITTER_ACTOR).call(
                run_input=actor_input,
                timeout_secs=120
            )
            
            run_id = run.get("id", "")
            dataset_id = run.get("defaultDatasetId", "")
            status = run.get("status", "")
            
            print(f"[Twitter Scraper] Actor run completed: status={status}, datasetId={dataset_id}")
            
            if status not in ["SUCCEEDED", "READY"]:
                return ScrapeResult(
                    success=False,
                    error=f"Actor run failed with status: {status}",
                    scraped_at=datetime.now().isoformat(),
                    run_id=run_id,
                    source="twitter"
                )
            
            # 从数据集获取结果
            dataset_client = client.dataset(dataset_id)
            items = []
            
            async for item in dataset_client.iterate_items():
                items.append(item)
            
            print(f"[Twitter Scraper] Fetched {len(items)} raw items from dataset")
            
            # 解析推文数据
            posts = []
            for item in items:
                post = self._parse_twitter_post(item)
                if post:
                    posts.append(post)
            
            result = ScrapeResult(
                success=True,
                posts=posts,
                scraped_at=datetime.now().isoformat(),
                run_id=run_id,
                dataset_id=dataset_id,
                source="twitter",
                search_terms=terms,
                total_count=len(posts)
            )
            
            # 更新状态
            self._last_scrape_result = result
            self._last_scrape_time = datetime.now()
            
            # 触发回调
            await self._trigger_callback(result)
            
            return result
            
        except Exception as e:
            import traceback
            print(f"[Twitter Scraper] Error: {e}")
            print(f"[Twitter Scraper] Traceback: {traceback.format_exc()}")
            return ScrapeResult(
                success=False,
                error=str(e),
                scraped_at=datetime.now().isoformat(),
                source="twitter"
            )
    
    def _parse_twitter_post(self, item: Dict[str, Any]) -> Optional[SocialPost]:
        """解析 Twitter 推文数据"""
        try:
            # 跳过无效数据
            if not item or item.get("noResults"):
                return None
            
            if "text" in item:
                author = item.get("author", {})
                return SocialPost(
                    id=str(item.get("id", "")),
                    title="",  # Twitter 没有标题
                    text=item.get("text", ""),
                    author_name=author.get("name", "Unknown"),
                    author_username=author.get("userName", "unknown"),
                    created_at=item.get("createdAt", ""),
                    source="twitter",
                    url=item.get("url", ""),
                    score=item.get("likeCount", 0),
                    comments=item.get("replyCount", 0)
                )
            
            return None
            
        except Exception as e:
            print(f"Error parsing Twitter post: {e}")
            return None
    
    async def scrape(self) -> ScrapeResult:
        """
        根据当前数据源设置进行抓取
        
        Returns:
            ScrapeResult: 抓取结果
        """
        if self.data_source == DataSource.REDDIT:
            return await self.scrape_reddit()
        else:
            return await self.scrape_twitter()
    
    async def _trigger_callback(self, result: ScrapeResult):
        """触发回调"""
        if self._on_scrape_complete:
            try:
                if asyncio.iscoroutinefunction(self._on_scrape_complete):
                    await self._on_scrape_complete(result)
                else:
                    self._on_scrape_complete(result)
            except Exception as e:
                print(f"Scrape callback error: {e}")
    
    def set_mode(self, mode: ScraperMode):
        """设置抓取模式"""
        self.mode = mode
        
        if mode == ScraperMode.AUTO and not self._is_running:
            self.start_auto_scrape()
        elif mode == ScraperMode.MANUAL and self._is_running:
            self.stop_auto_scrape()
    
    def set_data_source(self, source: DataSource):
        """设置数据源"""
        self.data_source = source
    
    def start_auto_scrape(self):
        """启动自动抓取"""
        if self._is_running:
            return
        
        self._is_running = True
        self._auto_task = asyncio.create_task(self._auto_scrape_loop())
        print(f"Auto scrape started, interval: {self.AUTO_INTERVAL}s, source: {self.data_source.value}")
    
    def stop_auto_scrape(self):
        """停止自动抓取"""
        self._is_running = False
        if self._auto_task:
            self._auto_task.cancel()
            self._auto_task = None
        print("Auto scrape stopped")
    
    async def _auto_scrape_loop(self):
        """自动抓取循环"""
        while self._is_running:
            try:
                print(f"Auto scraping at {datetime.now().isoformat()}")
                await self.scrape()
            except Exception as e:
                print(f"Auto scrape error: {e}")
            
            await asyncio.sleep(self.AUTO_INTERVAL)
    
    def on_scrape_complete(self, callback: Callable[[ScrapeResult], None]):
        """设置抓取完成回调"""
        self._on_scrape_complete = callback
    
    def get_last_result(self) -> Optional[ScrapeResult]:
        """获取最近一次抓取结果"""
        return self._last_scrape_result
    
    def get_last_scrape_time(self) -> Optional[datetime]:
        """获取最近一次抓取时间"""
        return self._last_scrape_time
    
    def get_status(self) -> Dict[str, Any]:
        """获取抓取器状态"""
        return {
            "mode": self.mode.value,
            "data_source": self.data_source.value,
            "is_running": self._is_running,
            "last_scrape_time": self._last_scrape_time.isoformat() if self._last_scrape_time else None,
            "next_scrape_time": (self._last_scrape_time + timedelta(seconds=self.AUTO_INTERVAL)).isoformat() 
                if self._is_running and self._last_scrape_time else None,
            "search_terms": self.search_terms,
            "subreddits": self.subreddits,
            "max_items": self.max_items,
            "auto_interval_minutes": self.AUTO_INTERVAL // 60,
            "last_result": self._last_scrape_result.to_dict() if self._last_scrape_result else None
        }
    
    async def close(self):
        """关闭抓取器"""
        self.stop_auto_scrape()


# 全局抓取器实例
_scraper: Optional[ApifyScraper] = None


def get_scraper(api_token: str = None) -> ApifyScraper:
    """获取全局抓取器实例"""
    global _scraper
    if _scraper is None:
        _scraper = ApifyScraper(api_token)
    return _scraper


def set_scraper_token(api_token: str):
    """设置抓取器 Token"""
    global _scraper
    if _scraper:
        _scraper.api_token = api_token
    else:
        _scraper = ApifyScraper(api_token)
