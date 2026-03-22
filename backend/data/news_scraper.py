"""
Financial News Scraper Module
Supports scraping crypto-related financial news from multiple sources
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
    """News Article"""
    title: str = Field(..., description="News title")
    url: str = Field(..., description="News URL")
    source: str = Field(..., description="News source")
    published_at: datetime = Field(..., description="PublishTime")
    summary: Optional[str] = Field(None, description="News summary")
    content: Optional[str] = Field(None, description="News body")
    tags: List[str] = Field(default_factory=list, description="Tags")
    
    # AI analysis result (populated by NewsAnalyzer)
    importance_stars: Optional[int] = Field(None, ge=1, le=5, description="Importance rating (1-5)")
    impact_level: Optional[str] = Field(None, description="Impact level")
    impact_direction: Optional[str] = Field(None, description="Impact direction")
    key_points: List[str] = Field(default_factory=list, description="Key takeaways")


class NewsScraperConfig(BaseModel):
    """NewsScrapeconfiguration"""
    sources: List[str] = Field(
        default=["coindesk", "cointelegraph", "cryptonews"],
        description="News source list"
    )
    max_articles_per_source: int = Field(default=10, description="Max articles to scrape per source")
    time_range_hours: int = Field(default=24, description="Scrape time range (hours)")
    keywords: List[str] = Field(
        default=["bitcoin", "ethereum", "crypto", "blockchain", "defi"],
        description="Keyword filter"
    )
    timeout: int = Field(default=10, description="Request timeout (seconds)")


class NewsScraper:
    """Financial News Scraper"""
    
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
        Scrape news from all configured sources
        
        Args:
            symbol: Optional trading symbol for filtering relevant news
        
        Returns:
            News ArticleList
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
        
        # Sort by publish time
        all_articles.sort(key=lambda x: x.published_at, reverse=True)
        
        logger.info(f"Scraped {len(all_articles)} articles from {len(self.config.sources)} sources")
        return all_articles
    
    async def _scrape_coindesk(self, symbol: Optional[str] = None) -> List[NewsArticle]:
        """Scrape CoinDesk News"""
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
                    
                    # Keyword filter
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
        """Scrape CoinTelegraph News"""
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
                    
                    # Keyword filter
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
        """Scrape CryptoNews News"""
        articles = []
        
        try:
            url = "https://cryptonews.com/news/"
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            cutoff_time = datetime.now(datetime.now().astimezone().tzinfo) - timedelta(hours=self.config.time_range_hours)
            
            # Find news list
            news_items = soup.select(".news-item, .article-item")[:self.config.max_articles_per_source]
            
            for item in news_items:
                try:
                    title_elem = item.select_one("h3, h2, .title")
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    
                    # Keyword filter
                    if not self._matches_keywords(title):
                        continue
                    
                    link_elem = item.select_one("a")
                    url = link_elem.get("href", "") if link_elem else ""
                    if url and not url.startswith("http"):
                        url = f"https://cryptonews.com{url}"
                    
                    # Try to get timestamp
                    time_elem = item.select_one("time, .date, .time")
                    published_at = datetime.now()  # DefaultCurrentTime
                    
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
        Scrape generic RSS feeds
        Can configure multiple RSS feed URLs
        """
        articles = []
        
        # Configurable RSS source list
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
        """Check if text contains keywords"""
        if not self.config.keywords:
            return True
        
        text_lower = text.lower()
        return any(keyword.lower() in text_lower for keyword in self.config.keywords)
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
