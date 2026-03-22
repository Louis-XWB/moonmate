"""
Apify Data Scraper Module
Supports scraping cryptocurrency-related content from X (Twitter) and Reddit for sentiment analysis
Supports manual mode and auto mode (scrapes every 20 minutes)

Uses ApifyClientAsync async client
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import os

# Using official Apify client
from apify_client import ApifyClientAsync


class ScraperMode(str, Enum):
    """Scraper mode"""
    MANUAL = "manual"  # Manual mode: click to scrape immediately
    AUTO = "auto"      # Auto mode: scrapes every 20 minutes


class DataSource(str, Enum):
    """Data source"""
    TWITTER = "twitter"
    REDDIT = "reddit"


@dataclass
class SocialPost:
    """Social media post model (unified format)"""
    id: str
    text: str
    title: str  # Reddit post title, empty for Twitter
    author_name: str
    author_username: str
    created_at: str
    source: str  # "twitter" or "reddit"
    url: str = ""
    score: int = 0  # Likes/upvotes
    comments: int = 0
    subreddit: str = ""  # Reddit subreddit
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScrapeResult:
    """Scrape result"""
    success: bool
    posts: List[SocialPost] = field(default_factory=list)
    error: Optional[str] = None
    scraped_at: str = ""
    run_id: str = ""
    dataset_id: str = ""
    source: str = ""  # "twitter" or "reddit"
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
    """Apify social media data scraper"""
    
    # Actor IDs
    REDDIT_ACTOR = "macrocosmos/reddit-scraper"
    TWITTER_ACTOR = "apidojo/tweet-scraper"
    
    # Default search keywords (cryptocurrency-related)
    DEFAULT_SEARCH_TERMS = [
        "Bitcoin",
        "Ethereum", 
        "crypto",
        "cryptocurrency",
        "BTC"
    ]
    
    # Default Reddit subreddits
    DEFAULT_SUBREDDITS = [
        "Bitcoin",
        "CryptoCurrency",
        "ethereum",
        "CryptoMarkets"
    ]
    
    # Auto mode interval (seconds)
    AUTO_INTERVAL = 20 * 60  # 20 minutes
    
    def __init__(self, api_token: str = None):
        """
        Initialize scraper
        
        Args:
            api_token: Apify API Token, If not provided, reads from environment variable
        """
        self.api_token = api_token or os.environ.get("APIFY_API_TOKEN", "")
        self._client: Optional[ApifyClientAsync] = None
        
        # Status
        self.mode = ScraperMode.MANUAL
        self.data_source = DataSource.REDDIT  # Default to Reddit (more stable)
        self._auto_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._last_scrape_result: Optional[ScrapeResult] = None
        self._last_scrape_time: Optional[datetime] = None
        
        # Callback functions
        self._on_scrape_complete: Optional[Callable[[ScrapeResult], None]] = None
        
        # Search configuration
        self.search_terms = self.DEFAULT_SEARCH_TERMS[:2]
        self.subreddits = self.DEFAULT_SUBREDDITS[:2]
        self.max_items = 10
    
    def _get_client(self) -> ApifyClientAsync:
        """Get Apify client"""
        if self._client is None:
            self._client = ApifyClientAsync(token=self.api_token)
        return self._client
    
    async def scrape_reddit(
        self, 
        subreddits: List[str] = None,
        max_items: int = None
    ) -> ScrapeResult:
        """
        Scrape Reddit posts (using official ApifyClientAsync)
        
        Args:
            subreddits: Subreddit list
            max_items: Maximum scrape count
            
        Returns:
            ScrapeResult: Scrape result
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
            
            # Prepare Actor input
            actor_input = {
                "subreddits": subs,
                "limit": max_count,
                "sort": "new"
            }
            
            print(f"[Reddit Scraper] Calling actor={self.REDDIT_ACTOR} with input={actor_input}")
            
            # Run Actor
            run = await client.actor(self.REDDIT_ACTOR).call(
                run_input=actor_input,
                timeout_secs=120  # 2-minute timeout
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
            
            # Fetch results from dataset
            dataset_client = client.dataset(dataset_id)
            items = []
            
            async for item in dataset_client.iterate_items():
                items.append(item)
            
            print(f"[Reddit Scraper] Fetched {len(items)} raw items from dataset")
            
            # Parse post data
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
            
            # Update status
            self._last_scrape_result = result
            self._last_scrape_time = datetime.now()
            
            # Trigger callbacks
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
        """Parse Reddit post data"""
        try:
            # Skip invalid data
            if not item:
                return None
            
            # Handle isNsfw field name
            if 'isNsfw' in item:
                item['is_nsfw'] = item.pop('isNsfw')
            
            # macrocosmos/reddit-scraper format
            post_id = item.get("id", "")
            title = item.get("title", "")
            body = item.get("body", "")
            username = item.get("username", "Unknown")
            community = item.get("communityName", "") or item.get("community", "")
            url = item.get("url", "")
            score = item.get("score", 0)
            num_comments = item.get("num_comments", 0)
            created_at = item.get("createdAt", "")
            
            # Skip empty posts
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
        Scrape Twitter tweets
        
        Args:
            search_terms: Search keywords
            max_items: Maximum scrape count
            
        Returns:
            ScrapeResult: Scrape result
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
            
            # Fetch results from dataset
            dataset_client = client.dataset(dataset_id)
            items = []
            
            async for item in dataset_client.iterate_items():
                items.append(item)
            
            print(f"[Twitter Scraper] Fetched {len(items)} raw items from dataset")
            
            # Parse tweet data
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
            
            # Update status
            self._last_scrape_result = result
            self._last_scrape_time = datetime.now()
            
            # Trigger callbacks
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
        """Parse Twitter tweet data"""
        try:
            # Skip invalid data
            if not item or item.get("noResults"):
                return None
            
            if "text" in item:
                author = item.get("author", {})
                return SocialPost(
                    id=str(item.get("id", "")),
                    title="",  # Twitter has no title
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
        Scrape based on current data source setting
        
        Returns:
            ScrapeResult: Scrape result
        """
        if self.data_source == DataSource.REDDIT:
            return await self.scrape_reddit()
        else:
            return await self.scrape_twitter()
    
    async def _trigger_callback(self, result: ScrapeResult):
        """Trigger callback"""
        if self._on_scrape_complete:
            try:
                if asyncio.iscoroutinefunction(self._on_scrape_complete):
                    await self._on_scrape_complete(result)
                else:
                    self._on_scrape_complete(result)
            except Exception as e:
                print(f"Scrape callback error: {e}")
    
    def set_mode(self, mode: ScraperMode):
        """Set scraper mode"""
        self.mode = mode
        
        if mode == ScraperMode.AUTO and not self._is_running:
            self.start_auto_scrape()
        elif mode == ScraperMode.MANUAL and self._is_running:
            self.stop_auto_scrape()
    
    def set_data_source(self, source: DataSource):
        """Set data source"""
        self.data_source = source
    
    def start_auto_scrape(self):
        """Start auto scraping"""
        if self._is_running:
            return
        
        self._is_running = True
        self._auto_task = asyncio.create_task(self._auto_scrape_loop())
        print(f"Auto scrape started, interval: {self.AUTO_INTERVAL}s, source: {self.data_source.value}")
    
    def stop_auto_scrape(self):
        """Stop auto scraping"""
        self._is_running = False
        if self._auto_task:
            self._auto_task.cancel()
            self._auto_task = None
        print("Auto scrape stopped")
    
    async def _auto_scrape_loop(self):
        """Auto scrape loop"""
        while self._is_running:
            try:
                print(f"Auto scraping at {datetime.now().isoformat()}")
                await self.scrape()
            except Exception as e:
                print(f"Auto scrape error: {e}")
            
            await asyncio.sleep(self.AUTO_INTERVAL)
    
    def on_scrape_complete(self, callback: Callable[[ScrapeResult], None]):
        """Set scrape completion callback"""
        self._on_scrape_complete = callback
    
    def get_last_result(self) -> Optional[ScrapeResult]:
        """Get last scrape result"""
        return self._last_scrape_result
    
    def get_last_scrape_time(self) -> Optional[datetime]:
        """Get last scrape time"""
        return self._last_scrape_time
    
    def get_status(self) -> Dict[str, Any]:
        """Get scraper status"""
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
        """Close scraper"""
        self.stop_auto_scrape()


# Global scraper instance
_scraper: Optional[ApifyScraper] = None


def get_scraper(api_token: str = None) -> ApifyScraper:
    """Get global scraper instance"""
    global _scraper
    if _scraper is None:
        _scraper = ApifyScraper(api_token)
    return _scraper


def set_scraper_token(api_token: str):
    """Set scraper token"""
    global _scraper
    if _scraper:
        _scraper.api_token = api_token
    else:
        _scraper = ApifyScraper(api_token)
