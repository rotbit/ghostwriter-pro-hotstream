"""
Twitter 平台适配器 - 基于 Playwright + Nitter 实现
"""

import asyncio
import re
from typing import Dict, List, Any, AsyncIterator, Optional
from urllib.parse import quote, urljoin
from loguru import logger
from playwright.async_api import async_playwright, Browser, Page, Playwright

from ...core.interfaces import PlatformAdapter, DataItem, SearchOptions, RateLimitInfo


class TwitterAdapter(PlatformAdapter):
    """Twitter 平台适配器 - 使用 Playwright 访问 Nitter 实例"""
    
    platform_name = "twitter"
    
    def __init__(self, nitter_instance: str = "https://nitter.poast.org"):
        self.nitter_instance = nitter_instance.rstrip('/')
        self.authenticated = False
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.rate_limit = RateLimitInfo(
            requests_per_minute=60,  # Nitter 通常有更高的限制
            requests_per_hour=300,
            remaining=60
        )
        self.monitored_accounts = []
    
    async def authenticate(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """初始化 Playwright 浏览器"""
        try:
            logger.info(f"初始化 Twitter 适配器，使用 Nitter: {self.nitter_instance}")
            
            # 启动 Playwright
            self.playwright = await async_playwright().start()
            
            # 启动浏览器（无头模式）
            self.browser = await self.playwright.chromium.launch(
                headless=False,  # 无头模式，更快
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ]
            )
            
            # 创建页面
            self.page = await self.browser.new_page()
            
            # 设置视口
            await self.page.set_viewport_size({"width": 1280, "height": 800})
            
            # 测试 Nitter 实例
            logger.info(f"测试 Nitter 实例: {self.nitter_instance}")
            await self.page.goto(self.nitter_instance, timeout=30000)
            await self.page.wait_for_load_state("networkidle")

            # 等待页面加载
            await asyncio.sleep(60)
            
            # 检查页面是否加载成功
            title = await self.page.title()
            if "nitter" in title.lower() or "twitter" in title.lower():
                logger.info("Nitter 实例连接成功")
                self.authenticated = True
                
                # 从配置中获取监控账号列表
                self.monitored_accounts = credentials.get('monitored_accounts', [])
                if self.monitored_accounts:
                    logger.info(f"已配置监控账号: {', '.join(self.monitored_accounts)}")
                
                return True
            else:
                logger.error(f"Nitter 实例响应异常，页面标题: {title}")
                return False
            
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
                    
                logger.info(f"在 Nitter 搜索关键字: {keyword}")
                
                # 导航到搜索页面
                search_url = f"{self.nitter_instance}/search?f=tweets&q={quote(keyword)}"
                await self.page.goto(search_url, timeout=30000)
                
                # 等待搜索结果加载
                await asyncio.sleep(3)
                
                # 滚动页面加载更多内容（如果需要）
                for _ in range(2):
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
                    await asyncio.sleep(0.5)
                
                logger.info(f"关键字 '{keyword}' 搜索完成，获得 {len(tweets)} 条数据")
                
                # 关键字之间的延迟
                if keyword != keywords[-1] and total_found < options.limit:
                    await asyncio.sleep(1)
                    
        except Exception as e:
            logger.error(f"Twitter 搜索失败: {e}")
            raise
    
    async def monitor_accounts(self, accounts: List[str], limit: int = 50) -> AsyncIterator[DataItem]:
        """监控指定账号的最新推文"""
        if not self.authenticated:
            await self.authenticate({})
        
        logger.info(f"开始监控账号: {', '.join(accounts)}")
        
        total_found = 0
        for account in accounts:
            if total_found >= limit:
                break
                
            account_tweets = await self._get_account_tweets(account, limit - total_found)
            
            for tweet in account_tweets:
                if total_found >= limit:
                    break
                    
                yield tweet
                total_found += 1
                
                # 更新限流信息
                self.rate_limit.remaining -= 1
                await asyncio.sleep(0.5)
    
    async def _get_account_tweets(self, username: str, max_count: int) -> List[DataItem]:
        """获取指定账号的推文"""
        tweets = []
        
        try:
            # 导航到用户页面
            profile_url = f"{self.nitter_instance}/{username}"
            logger.info(f"访问用户页面: {profile_url}")
            
            await self.page.goto(profile_url, timeout=30000)
            await asyncio.sleep(3)
            
            # 滚动加载更多推文
            for _ in range(2):
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
            
            # 提取推文
            tweets = await self._extract_tweets(f"account:{username}", max_count)
            logger.info(f"用户 {username} 获得 {len(tweets)} 条推文")
            
        except Exception as e:
            logger.error(f"获取账号 {username} 推文失败: {e}")
        
        return tweets
    
    async def _extract_tweets(self, keyword: str, max_count: int) -> List[DataItem]:
        """从 Nitter 页面提取推文数据"""
        tweets = []
        
        try:
            # 等待推文容器加载
            await self.page.wait_for_selector('.timeline-item', timeout=10000)
            
            # 查找推文元素
            tweet_elements = await self.page.query_selector_all('.timeline-item')
            logger.info(f"找到 {len(tweet_elements)} 个推文元素")
            
            for i, tweet_element in enumerate(tweet_elements[:max_count]):
                try:
                    # 提取推文内容
                    content_element = await tweet_element.query_selector('.tweet-content')
                    content = ""
                    if content_element:
                        content = await content_element.inner_text()
                    
                    if not content or len(content.strip()) < 10:
                        continue
                    
                    # 提取用户名
                    username_element = await tweet_element.query_selector('.username')
                    username = ""
                    if username_element:
                        username_text = await username_element.inner_text()
                        username = username_text.lstrip('@') if username_text else ""
                    
                    # 提取推文链接
                    tweet_link_element = await tweet_element.query_selector('.tweet-link')
                    tweet_url = ""
                    if tweet_link_element:
                        href = await tweet_link_element.get_attribute('href')
                        if href:
                            if href.startswith('/'):
                                # 相对链接，转换为完整的 Twitter 链接
                                tweet_url = f"https://twitter.com{href}"
                            else:
                                tweet_url = href.replace(self.nitter_instance, "https://twitter.com")
                    
                    # 提取时间
                    time_element = await tweet_element.query_selector('.tweet-date')
                    timestamp = ""
                    if time_element:
                        # 获取 title 属性中的完整时间戳
                        title = await time_element.get_attribute('title')
                        if title:
                            timestamp = title
                        else:
                            # 如果没有 title，尝试解析显示的相对时间
                            time_text = await time_element.inner_text()
                            timestamp = self._parse_relative_time(time_text)
                    
                    # 提取互动数据
                    metrics = await self._extract_tweet_metrics(tweet_element)
                    
                    # 创建数据项
                    tweet_id = f"nitter_{keyword}_{abs(hash(content))}_{i}"
                    
                    item = DataItem(
                        id=tweet_id,
                        platform=self.platform_name,
                        content=content,
                        author=username or "unknown",
                        url=tweet_url or f"{self.nitter_instance}/search?q={quote(keyword)}",
                        created_at=timestamp,
                        metadata={
                            "keyword": keyword,
                            "retweet_count": metrics.get("retweet_count", 0),
                            "like_count": metrics.get("like_count", 0),
                            "reply_count": metrics.get("reply_count", 0),
                            "quote_count": metrics.get("quote_count", 0),
                            "nitter_instance": self.nitter_instance
                        },
                        raw_data={
                            "source": "nitter_playwright_adapter",
                            "search_keyword": keyword,
                            "extraction_method": "playwright_nitter"
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
            # 查找互动统计元素
            stat_elements = await tweet_element.query_selector_all('.tweet-stats .tweet-stat')
            
            for stat_element in stat_elements:
                try:
                    # 获取统计数字
                    stat_text = await stat_element.inner_text()
                    
                    # 提取数字
                    numbers = re.findall(r'\d+', stat_text)
                    count = int(numbers[0]) if numbers else 0
                    
                    # 获取图标类名来判断类型
                    icon_element = await stat_element.query_selector('i, .icon')
                    if icon_element:
                        class_list = await icon_element.get_attribute('class')
                        class_str = class_list or ""
                        
                        if 'retweet' in class_str or 'repeat' in class_str:
                            metrics["retweet_count"] = count
                        elif 'heart' in class_str or 'like' in class_str:
                            metrics["like_count"] = count
                        elif 'reply' in class_str or 'comment' in class_str:
                            metrics["reply_count"] = count
                        elif 'quote' in class_str:
                            metrics["quote_count"] = count
                            
                except Exception as e:
                    logger.debug(f"解析单个统计失败: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"提取互动指标失败: {e}")
            
        return metrics
    
    def _parse_relative_time(self, time_text: str) -> str:
        """解析相对时间为ISO格式"""
        try:
            import datetime
            now = datetime.datetime.now()
            
            if 'min' in time_text:
                minutes = int(re.findall(r'\d+', time_text)[0])
                timestamp = now - datetime.timedelta(minutes=minutes)
            elif 'h' in time_text:
                hours = int(re.findall(r'\d+', time_text)[0])
                timestamp = now - datetime.timedelta(hours=hours)
            elif 'd' in time_text:
                days = int(re.findall(r'\d+', time_text)[0])
                timestamp = now - datetime.timedelta(days=days)
            else:
                # 如果无法解析，使用当前时间
                timestamp = now
            
            return timestamp.isoformat() + "Z"
            
        except:
            # 解析失败时返回当前时间
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