"""
Twitter 平台适配器 - 真实抓取实现
"""

import asyncio
import re
from typing import Dict, List, Any, AsyncIterator
from loguru import logger
from playwright.async_api import async_playwright, Browser, Page, Playwright

from ...core.interfaces import PlatformAdapter, DataItem, SearchOptions, RateLimitInfo


class TwitterAdapter(PlatformAdapter):
    """Twitter 平台适配器 - 真实抓取实现"""
    
    platform_name = "twitter"
    
    def __init__(self):
        self.authenticated = False
        self.playwright: Playwright = None
        self.browser: Browser = None
        self.page: Page = None
        self.rate_limit = RateLimitInfo(
            requests_per_minute=30,
            requests_per_hour=180,
            remaining=30
        )
    
    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """初始化浏览器和页面"""
        try:
            logger.info("Twitter 适配器初始化...")
            
            # 启动 Playwright
            self.playwright = await async_playwright().start()
            
            # 启动浏览器（可见模式）
            self.browser = await self.playwright.chromium.launch(
                headless=False,
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ],
                slow_mo=1000  # 减慢操作速度
            )
            
            # 创建页面
            self.page = await self.browser.new_page()
            
            # 设置视口
            await self.page.set_viewport_size({"width": 1280, "height": 800})
            
            # 导航到 Twitter
            logger.info("导航到 Twitter...")
            await self.page.goto("https://twitter.com", timeout=30000)
            
            # 等待页面加载
            await asyncio.sleep(10)
            
            self.authenticated = True
            logger.info("Twitter 适配器初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"Twitter 适配器初始化失败: {e}")
            await self.cleanup()
            return False
    
    async def search(self, keywords: List[str], options: SearchOptions) -> AsyncIterator[DataItem]:
        """搜索 Twitter 内容"""
        if not self.authenticated:
            await self.authenticate({})
        
        if not self.page or self.page.is_closed():
            logger.error("页面不可用")
            return
        
        try:
            total_found = 0
            for keyword in keywords:
                if total_found >= options.limit:
                    break
                    
                logger.info(f"搜索 Twitter 关键字: {keyword}")
                
                # 导航到搜索页面
                search_url = f"https://twitter.com/search?q={keyword}&src=typed_query&f=live"
                await self.page.goto(search_url, timeout=30000)
                
                # 等待搜索结果加载
                await asyncio.sleep(3)
                
                # 滚动页面加载更多内容
                for _ in range(3):
                    await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                
                # 提取推文
                tweets = await self._extract_tweets(keyword, options.limit - total_found)
                
                for tweet in tweets:
                    if total_found >= options.limit:
                        break
                    
                    yield tweet
                    total_found += 1
                    
                    # 更新限流信息
                    self.rate_limit.remaining -= 1
                    
                    # 请求间隔
                    await asyncio.sleep(1)
                
                logger.info(f"关键字 '{keyword}' 搜索完成，获得 {len(tweets)} 条数据")
                
                # 关键字之间的延迟
                if keyword != keywords[-1] and total_found < options.limit:
                    await asyncio.sleep(2)
                    
        except Exception as e:
            logger.error(f"Twitter 搜索失败: {e}")
            raise
    
    async def _extract_tweets(self, keyword: str, max_count: int) -> List[DataItem]:
        """从页面提取推文数据"""
        tweets = []
        
        try:
            # 查找推文元素
            tweet_elements = await self.page.query_selector_all('[data-testid="tweet"]')
            logger.info(f"找到 {len(tweet_elements)} 个推文元素")
            
            for i, tweet_element in enumerate(tweet_elements[:max_count]):
                try:
                    # 提取推文内容
                    content_element = await tweet_element.query_selector('[data-testid="tweetText"]')
                    content = await content_element.inner_text() if content_element else ""
                    
                    if not content or len(content.strip()) < 10:
                        continue
                    
                    # 提取用户名
                    username_element = await tweet_element.query_selector('[data-testid="User-Name"] a')
                    username = ""
                    if username_element:
                        href = await username_element.get_attribute('href')
                        if href:
                            username = href.split('/')[-1]
                    
                    # 提取推文链接
                    time_element = await tweet_element.query_selector('time')
                    tweet_url = ""
                    if time_element:
                        parent_link = await time_element.query_selector('xpath=..')
                        if parent_link:
                            href = await parent_link.get_attribute('href')
                            if href:
                                tweet_url = f"https://twitter.com{href}"
                    
                    # 提取时间
                    timestamp = ""
                    if time_element:
                        datetime_attr = await time_element.get_attribute('datetime')
                        if datetime_attr:
                            timestamp = datetime_attr
                    
                    # 提取互动数据
                    metrics = await self._extract_tweet_metrics(tweet_element)
                    
                    # 创建数据项
                    tweet_id = f"twitter_{keyword}_{abs(hash(content))}_{i}"
                    
                    item = DataItem(
                        id=tweet_id,
                        platform=self.platform_name,
                        content=content,
                        author=username or "unknown",
                        url=tweet_url or f"https://twitter.com/search?q={keyword}",
                        created_at=timestamp or self._get_current_timestamp(),
                        metadata={
                            "keyword": keyword,
                            "retweet_count": metrics.get("retweet_count", 0),
                            "like_count": metrics.get("like_count", 0),
                            "reply_count": metrics.get("reply_count", 0),
                            "quote_count": metrics.get("quote_count", 0)
                        },
                        raw_data={
                            "source": "twitter_live_adapter",
                            "search_keyword": keyword,
                            "extraction_method": "playwright"
                        }
                    )
                    
                    tweets.append(item)
                    logger.debug(f"提取推文: {content[:50]}...")
                    
                except Exception as e:
                    logger.warning(f"提取单个推文失败: {e}")
                    continue
            
            return tweets
            
        except Exception as e:
            logger.error(f"提取推文失败: {e}")
            return []
    
    async def _extract_tweet_metrics(self, tweet_element) -> Dict[str, int]:
        """提取推文的互动指标"""
        metrics = {
            "retweet_count": 0,
            "like_count": 0,
            "reply_count": 0,
            "quote_count": 0
        }
        
        try:
            # 查找所有互动按钮
            action_elements = await tweet_element.query_selector_all('[role="group"] [role="button"]')
            
            for element in action_elements:
                try:
                    # 获取按钮的aria-label或其他属性来判断类型
                    aria_label = await element.get_attribute('aria-label')
                    if aria_label:
                        # 使用正则表达式提取数字
                        numbers = re.findall(r'\d+', aria_label)
                        count = int(numbers[0]) if numbers else 0
                        
                        if 'retweet' in aria_label.lower() or 'repost' in aria_label.lower():
                            metrics["retweet_count"] = count
                        elif 'like' in aria_label.lower():
                            metrics["like_count"] = count
                        elif 'repl' in aria_label.lower():
                            metrics["reply_count"] = count
                        elif 'quote' in aria_label.lower():
                            metrics["quote_count"] = count
                            
                except:
                    continue
                    
        except Exception as e:
            logger.debug(f"提取互动指标失败: {e}")
            
        return metrics
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        import datetime
        return datetime.datetime.now().isoformat() + "Z"
    
    async def get_rate_limit(self) -> RateLimitInfo:
        """获取限流信息"""
        return self.rate_limit
    
    async def cleanup(self) -> None:
        """清理资源"""
        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
                
            if self.browser:
                await self.browser.close()
                
            if self.playwright:
                await self.playwright.stop()
                
        except Exception as e:
            logger.error(f"清理资源时出错: {e}")
        finally:
            self.page = None
            self.browser = None
            self.playwright = None
            self.authenticated = False
            logger.info("Twitter 适配器清理完成")