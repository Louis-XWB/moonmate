"""
财经新闻抓取模块
支持从多个来源抓取加密货币相关的财经新闻
"""

import asyncio
import httpx
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup

from backend.core.logger import get_logger

logger = get_logger("news_scraper")


class NewsArticle(BaseModel):
    """新闻文章"""
    title: str = Field(..., description="新闻标题")
    url: str = Field(..., description="新闻链接")
    source: str = Field(..., description="新闻来源")
    published_at: datetime = Field(..., description="发布时间")
    summary: Optional[str] = Field(None, description="新闻摘要")
    content: Optional[str] = Field(None, description="新闻正文")
    tags: List[str] = Field(default_factory=list, description="标签")
    
    # AI 分析结果（由 NewsAnalyzer 填充）
    importance_stars: Optional[int] = Field(None, ge=1, le=5, description="重要性星级 (1-5)")
    impact_level: Optional[str] = Field(None, description="影响等级")
    impact_direction: Optional[str] = Field(None, description="影响方向")
    key_points: List[str] = Field(default_factory=list, description="关键要点")


class NewsScraperConfig(BaseModel):
    """新闻抓取配置"""
    sources: List[str] = Field(
        default=["coindesk", "cointelegraph", "cryptonews"],
        description="新闻源列表"
    )
    max_articles_per_source: int = Field(default=10, description="每个源最多抓取文章数")
    time_range_hours: int = Field(default=24, description="抓取时间范围（小时）")
    keywords: List[str] = Field(
        default=["bitcoin", "ethereum", "crypto", "blockchain", "defi"],
        description="关键词过滤"
    )
    timeout: int = Field(default=10, description="请求超时时间（秒）")


class NewsScraper:
    """财经新闻抓取器"""
    
    def __init__(self, config: Optional[NewsScraperConfig] = None):
        self.config = config or NewsScraperConfig()
        self.client = httpx.AsyncClient(
            timeout=self.config.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        )
    
    async def scrape_all(self, symbol: Optional[str] = None) -> List[NewsArticle]:
        """
        从所有配置的源抓取新闻
        
        Args:
            symbol: 可选的币种符号，用于过滤相关新闻
        
        Returns:
            新闻文章列表
        """
        all_articles = []
        
        tasks = []
        for source in self.config.sources:
            if source == "coindesk":
                tasks.append(self._scrape_coindesk(symbol))
            elif source == "cointelegraph":
                tasks.append(self._scrape_cointelegraph(symbol))
            elif source == "cryptonews":
                tasks.append(self._scrape_cryptonews(symbol))
            elif source == "rss":
                tasks.append(self._scrape_rss_feeds(symbol))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"News scraping error: {result}")
            elif isinstance(result, list):
                all_articles.extend(result)
        
        # 按发布时间排序
        all_articles.sort(key=lambda x: x.published_at, reverse=True)
        
        logger.info(f"Scraped {len(all_articles)} articles from {len(self.config.sources)} sources")
        return all_articles
    
    async def _scrape_coindesk(self, symbol: Optional[str] = None) -> List[NewsArticle]:
        """抓取 CoinDesk 新闻"""
        articles = []
        
        try:
            # CoinDesk RSS feed
            url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "xml")
            items = soup.find_all("item")
            
            cutoff_time = datetime.now(datetime.now().astimezone().tzinfo) - timedelta(hours=self.config.time_range_hours)
            
            for item in items[:self.config.max_articles_per_source]:
                try:
                    title = item.find("title").text if item.find("title") else ""
                    
                    # 关键词过滤
                    if not self._matches_keywords(title):
                        continue
                    
                    pub_date = item.find("pubDate")
                    if pub_date:
                        published_at = datetime.strptime(
                            pub_date.text, "%a, %d %b %Y %H:%M:%S %z"
                        )
                    else:
                        published_at = datetime.now(datetime.now().astimezone().tzinfo)
                    
                    if published_at < cutoff_time:
                        continue
                    
                    article = NewsArticle(
                        title=title,
                        url=item.find("link").text if item.find("link") else "",
                        source="CoinDesk",
                        published_at=published_at,
                        summary=item.find("description").text if item.find("description") else None
                    )
                    
                    articles.append(article)
                
                except Exception as e:
                    logger.warning(f"Failed to parse CoinDesk article: {e}")
                    continue
            
            logger.info(f"Scraped {len(articles)} articles from CoinDesk")
        
        except Exception as e:
            logger.error(f"CoinDesk scraping error: {e}")
        
        return articles
    
    async def _scrape_cointelegraph(self, symbol: Optional[str] = None) -> List[NewsArticle]:
        """抓取 CoinTelegraph 新闻"""
        articles = []
        
        try:
            url = "https://cointelegraph.com/rss"
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "xml")
            items = soup.find_all("item")
            
            cutoff_time = datetime.now(datetime.now().astimezone().tzinfo) - timedelta(hours=self.config.time_range_hours)
            
            for item in items[:self.config.max_articles_per_source]:
                try:
                    title = item.find("title").text
                    
                    # 关键词过滤
                    if not self._matches_keywords(title):
                        continue
                    
                    pub_date_str = item.find("pubDate").text
                    published_at = datetime.strptime(
                        pub_date_str, "%a, %d %b %Y %H:%M:%S %z"
                    )
                    
                    if published_at < cutoff_time:
                        continue
                    
                    article = NewsArticle(
                        title=title,
                        url=item.find("link").text,
                        source="CoinTelegraph",
                        published_at=published_at,
                        summary=item.find("description").text if item.find("description") else None
                    )
                    
                    articles.append(article)
                
                except Exception as e:
                    logger.warning(f"Failed to parse CoinTelegraph article: {e}")
                    continue
            
            logger.info(f"Scraped {len(articles)} articles from CoinTelegraph")
        
        except Exception as e:
            logger.error(f"CoinTelegraph scraping error: {e}")
        
        return articles
    
    async def _scrape_cryptonews(self, symbol: Optional[str] = None) -> List[NewsArticle]:
        """抓取 CryptoNews 新闻"""
        articles = []
        
        try:
            url = "https://cryptonews.com/news/"
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            cutoff_time = datetime.now(datetime.now().astimezone().tzinfo) - timedelta(hours=self.config.time_range_hours)
            
            # 查找新闻列表
            news_items = soup.select(".news-item, .article-item")[:self.config.max_articles_per_source]
            
            for item in news_items:
                try:
                    title_elem = item.select_one("h3, h2, .title")
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    # 关键词过滤
                    if not self._matches_keywords(title):
                        continue
                    
                    link_elem = item.select_one("a")
                    url = link_elem.get("href", "") if link_elem else ""
                    if url and not url.startswith("http"):
                        url = f"https://cryptonews.com{url}"
                    
                    # 尝试获取时间
                    time_elem = item.select_one("time, .date, .time")
                    published_at = datetime.now()  # 默认当前时间
                    
                    if time_elem and time_elem.get("datetime"):
                        try:
                            published_at = datetime.fromisoformat(
                                time_elem.get("datetime").replace("Z", "+00:00")
                            )
                        except:
                            pass
                    
                    if published_at < cutoff_time:
                        continue
                    
                    article = NewsArticle(
                        title=title,
                        url=url,
                        source="CryptoNews",
                        published_at=published_at
                    )
                    
                    articles.append(article)
                
                except Exception as e:
                    logger.warning(f"Failed to parse CryptoNews article: {e}")
                    continue
            
            logger.info(f"Scraped {len(articles)} articles from CryptoNews")
        
        except Exception as e:
            logger.error(f"CryptoNews scraping error: {e}")
        
        return articles
    
    async def _scrape_rss_feeds(self, symbol: Optional[str] = None) -> List[NewsArticle]:
        """
        抓取通用 RSS 源
        可以配置多个 RSS feed URL
        """
        articles = []
        
        # 可配置的 RSS 源列表
        rss_feeds = [
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "https://decrypt.co/feed",
            "https://bitcoinmagazine.com/.rss/full/"
        ]
        
        for feed_url in rss_feeds:
            try:
                response = await self.client.get(feed_url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, "xml")
                items = soup.find_all("item")
                
                cutoff_time = datetime.now(datetime.now().astimezone().tzinfo) - timedelta(hours=self.config.time_range_hours)
                
                for item in items[:self.config.max_articles_per_source]:
                    try:
                        title = item.find("title").text
                        
                        if not self._matches_keywords(title):
                            continue
                        
                        pub_date = item.find("pubDate")
                        if pub_date:
                            published_at = datetime.strptime(
                                pub_date.text, "%a, %d %b %Y %H:%M:%S %z"
                            )
                        else:
                            published_at = datetime.now()
                        
                        if published_at < cutoff_time:
                            continue
                        
                        article = NewsArticle(
                            title=title,
                            url=item.find("link").text if item.find("link") else "",
                            source=feed_url.split("//")[1].split("/")[0],
                            published_at=published_at,
                            summary=item.find("description").text if item.find("description") else None
                        )
                        
                        articles.append(article)
                    
                    except Exception as e:
                        logger.warning(f"Failed to parse RSS item: {e}")
                        continue
            
            except Exception as e:
                logger.warning(f"Failed to fetch RSS feed {feed_url}: {e}")
                continue
        
        logger.info(f"Scraped {len(articles)} articles from RSS feeds")
        return articles
    
    def _matches_keywords(self, text: str) -> bool:
        """检查文本是否包含关键词"""
        if not self.config.keywords:
            return True
        
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in self.config.keywords)
    
    async def close(self):
        """关闭 HTTP 客户端"""
        await self.client.aclose()
