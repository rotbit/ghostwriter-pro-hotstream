"""
Medium 平台适配器 - 基于 Playwright 实现
"""

import asyncio
import re
from typing import Dict, List, Any, AsyncIterator, Optional
from urllib.parse import quote, urljoin
from datetime import datetime
from loguru import logger
from playwright.async_api import async_playwright, Browser, Page, Playwright

from ...core.interfaces import PlatformAdapter, DataItem, SearchOptions, RateLimitInfo


class MediumAdapter(PlatformAdapter):
    """Medium 平台适配器 - 使用 Playwright 访问 Medium"""
    
    platform_name = "medium"
    
    def __init__(self):
        self.authenticated = False
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.rate_limit = RateLimitInfo(
            requests_per_minute=30,  # Medium 有较严格的限制
            requests_per_hour=150,
            remaining=30
        )
        self.base_url = "https://medium.com"
        self.email = None
        self.password = None
    
    async def authenticate(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """初始化 Playwright 浏览器并登录 Medium"""
        try:
            logger.info("初始化 Medium 适配器")
            
            # 启动 Playwright
            self.playwright = await async_playwright().start()
            
            # 启动浏览器
            self.browser = await self.playwright.chromium.launch(
                headless=False,  # Medium 检测机器人，建议使用有头模式
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ]
            )
            
            # 创建页面
            self.page = await self.browser.new_page()
            
            # 设置视口
            await self.page.set_viewport_size({"width": 1366, "height": 768})
            
            # 如果提供了认证信息，尝试登录
            if credentials and credentials.get('email') and credentials.get('password'):
                self.email = credentials.get('email')
                self.password = credentials.get('password')
                
                if await self._login():
                    logger.info("Medium 登录成功")
                    self.authenticated = True
                    return True
                else:
                    logger.warning("Medium 登录失败，将以匿名模式运行")
            
            # 即使没有登录，也测试页面访问
            await self.page.goto(self.base_url, timeout=30000)
            await self.page.wait_for_load_state("networkidle")
            
            # 检查页面是否加载成功
            title = await self.page.title()
            if "medium" in title.lower():
                logger.info("Medium 页面访问成功（匿名模式）")
                self.authenticated = True
                return True
            else:
                logger.error(f"Medium 页面响应异常，页面标题: {title}")
                return False
            
        except Exception as e:
            logger.error(f"Medium 适配器初始化失败: {e}")
            await self.cleanup()
            return False
    
    async def _login(self) -> bool:
        """登录 Medium"""
        try:
            logger.info("开始登录 Medium")
            
            # 访问登录页面
            await self.page.goto(f"{self.base_url}/m/signin", timeout=30000)
            await self.page.wait_for_load_state("networkidle")
            
            # 查找并点击"Sign in with email"按钮
            email_button_selector = 'button:has-text("Sign in with email"), a:has-text("Sign in with email")'
            try:
                await self.page.wait_for_selector(email_button_selector, timeout=10000)
                await self.page.click(email_button_selector)
                await asyncio.sleep(2)
            except:
                logger.info("未找到邮箱登录按钮，尝试直接输入邮箱")
            
            # 输入邮箱
            email_input_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[placeholder*="email" i]',
                'input[placeholder*="Email" i]'
            ]
            
            email_filled = False
            for selector in email_input_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=5000)
                    await self.page.fill(selector, self.email)
                    email_filled = True
                    logger.info("邮箱输入成功")
                    break
                except:
                    continue
            
            if not email_filled:
                logger.error("未找到邮箱输入框")
                return False
            
            # 点击继续按钮
            continue_selectors = [
                'button:has-text("Continue")',
                'button:has-text("Next")',
                'button[type="submit"]',
                'input[type="submit"]'
            ]
            
            for selector in continue_selectors:
                try:
                    await self.page.click(selector)
                    await asyncio.sleep(3)
                    break
                except:
                    continue
            
            # 输入密码
            password_input_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[placeholder*="password" i]',
                'input[placeholder*="Password" i]'
            ]
            
            password_filled = False
            for selector in password_input_selectors:
                try:
                    await self.page.wait_for_selector(selector, timeout=10000)
                    await self.page.fill(selector, self.password)
                    password_filled = True
                    logger.info("密码输入成功")
                    break
                except:
                    continue
            
            if not password_filled:
                logger.error("未找到密码输入框")
                return False
            
            # 点击登录按钮
            login_selectors = [
                'button:has-text("Sign in")',
                'button:has-text("Log in")',
                'button:has-text("Continue")',
                'button[type="submit"]',
                'input[type="submit"]'
            ]
            
            for selector in login_selectors:
                try:
                    await self.page.click(selector)
                    break
                except:
                    continue
            
            # 等待登录完成
            await asyncio.sleep(5)
            await self.page.wait_for_load_state("networkidle")
            
            # 检查是否登录成功
            current_url = self.page.url
            if "signin" not in current_url and "login" not in current_url:
                logger.info("Medium 登录成功")
                return True
            else:
                logger.error("Medium 登录失败")
                return False
                
        except Exception as e:
            logger.error(f"Medium 登录过程中出错: {e}")
            return False
    
    async def search(self, keywords: List[str], options: SearchOptions) -> AsyncIterator[DataItem]:
        """搜索 Medium 文章"""
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
                
                logger.info(f"搜索关键词: {keyword}")
                
                # 构建搜索URL
                search_url = f"{self.base_url}/search?q={quote(keyword)}"
                await self.page.goto(search_url, timeout=30000)
                await self.page.wait_for_load_state("networkidle")
                await asyncio.sleep(3)
                
                # 等待文章加载
                try:
                    await self.page.wait_for_selector('div[role="link"], article, div[data-testid="story"]', timeout=10000)
                except:
                    logger.warning(f"关键词 '{keyword}' 未找到文章")
                    continue
                
                # 获取文章列表
                articles = await self.page.query_selector_all('div[role="link"], article, div[data-testid="story"]')
                logger.info(f"找到 {len(articles)} 篇文章")
                
                for i, article in enumerate(articles):
                    if total_found >= options.limit:
                        break
                    
                    try:
                        # 提取文章信息
                        data_item = await self._extract_article_data(article, keyword)
                        if data_item:
                            total_found += 1
                            yield data_item
                            
                            # 避免被反爬虫
                            await asyncio.sleep(1)
                    
                    except Exception as e:
                        logger.warning(f"提取文章数据失败: {e}")
                        continue
                
                # 关键词之间的延迟
                await asyncio.sleep(2)
                
        except Exception as e:
            logger.error(f"Medium 搜索失败: {e}")
    
    async def _extract_article_data(self, article_element, keyword: str) -> Optional[DataItem]:
        """从文章元素中提取数据"""
        try:
            # 提取标题
            title_selectors = [
                'h1', 'h2', 'h3',
                '[data-testid="post-preview-title"] h2',
                '[data-testid="post-preview-title"] h3',
                'a[aria-label] h2',
                'a[aria-label] h3',
                '.story-title',
                'article h2',
                'article h3'
            ]
            
            title = ""
            title_element = None
            for selector in title_selectors:
                try:
                    title_element = await article_element.query_selector(selector)
                    if title_element:
                        title = await title_element.inner_text()
                        if title.strip() and len(title) > 5:  # 确保标题有意义
                            break
                except:
                    continue
            
            if not title:
                logger.debug("未找到文章标题，跳过")
                return None
            
            # 提取作者 - 改进选择器
            author_selectors = [
                '[data-testid="post-preview-author"] a',
                'a[rel="author"]',
                'a[href*="/@"]',
                '[data-testid="post-preview-author"] span',
                '.story-author a',
                'p a[href*="/@"]',
                'div a[href*="/@"]'
            ]
            
            author = "Unknown"
            author_url = ""
            for selector in author_selectors:
                try:
                    author_element = await article_element.query_selector(selector)
                    if author_element:
                        author_text = await author_element.inner_text()
                        author_href = await author_element.get_attribute('href')
                        if author_text.strip() and len(author_text.strip()) > 1:
                            # 清理作者名（移除多余的空格和特殊字符）
                            author = author_text.strip().replace('\n', ' ').replace('\t', ' ')
                            author = ' '.join(author.split())  # 合并多个空格
                            if author_href and '/@' in author_href:
                                # 清理作者链接，移除source参数和多余的破折号
                                clean_href = author_href.split('?')[0]  # 移除查询参数
                                author_url = clean_href if clean_href.startswith('http') else f"{self.base_url}{clean_href}"
                            break
                except:
                    continue
            
            # 提取文章预览内容 - 改进选择器
            content_selectors = [
                '[data-testid="post-preview-content"] p',
                '[data-testid="post-preview-content"]',
                '.story-content p',
                '.story-content',
                'article p:not(:has(a[href*="/@"]))',  # 排除作者信息段落
                'div p',
                'p'
            ]
            
            content = ""
            for selector in content_selectors:
                try:
                    content_elements = await article_element.query_selector_all(selector)
                    content_parts = []
                    for element in content_elements[:3]:  # 最多取前3个段落
                        text = await element.inner_text()
                        if text.strip() and len(text.strip()) > 10:
                            # 过滤掉可能是作者信息或日期的文本
                            if not any(indicator in text.lower() for indicator in ['follow', 'member', 'written by', '·', 'min read']):
                                content_parts.append(text.strip())
                    
                    if content_parts:
                        content = ' '.join(content_parts)
                        break
                except:
                    continue
            
            # 提取文章链接 - 优先从data-href属性获取
            url = ""
            
            # 首先尝试从父容器的data-href属性获取
            try:
                data_href = await article_element.get_attribute('data-href')
                if data_href and ('/p/' in data_href or '/s/' in data_href or 'medium.com' in data_href):
                    url = data_href if data_href.startswith('http') else f"{self.base_url}{data_href}"
            except:
                pass
            
            # 如果没有找到，尝试其他选择器
            if not url:
                link_selectors = [
                    'h1 a[href]', 'h2 a[href]', 'h3 a[href]',
                    '[data-testid="post-preview-title"] a[href]',
                    'a[aria-label][href]'
                ]
                
                for selector in link_selectors:
                    try:
                        link_element = await article_element.query_selector(selector)
                        if link_element:
                            href = await link_element.get_attribute('href')
                            if href:
                                # 过滤掉作者链接，只要文章链接
                                if '/@' not in href or ('/p/' in href or '/s/' in href):
                                    if href.startswith('/'):
                                        url = f"{self.base_url}{href}"
                                    elif href.startswith('http'):
                                        url = href
                                    break
                    except:
                        continue
            
            # 提取发布时间 - 改进逻辑并转换为时间戳
            publish_time = ""
            publish_timestamp = None
            
            # 首先查找time标签
            try:
                time_elements = await article_element.query_selector_all('time')
                for time_elem in time_elements:
                    time_text = await time_elem.inner_text()
                    datetime_attr = await time_elem.get_attribute('datetime')
                    if time_text.strip():
                        publish_time = time_text.strip()
                        break
                    elif datetime_attr:
                        publish_time = datetime_attr
                        break
            except:
                pass
            
            # 如果没有找到time标签，查找包含时间关键词的文本
            if not publish_time:
                try:
                    all_elements = await article_element.query_selector_all('span, div, p')
                    import re
                    
                    for elem in all_elements:
                        text = await elem.inner_text()
                        if text and len(text.strip()) < 50:  # 限制长度
                            # 匹配时间格式：如 "5d ago", "2 hours ago", "Jan 15", 等
                            time_patterns = [
                                r'\d+[dhm]\s+ago',  # 5d ago, 2h ago, 30m ago
                                r'\d+\s+(day|hour|minute|week|month|year)s?\s+ago',  # 2 days ago
                                r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+',  # Jan 15
                                r'\d{4}-\d{2}-\d{2}',  # 2023-12-25
                            ]
                            
                            for pattern in time_patterns:
                                if re.search(pattern, text, re.IGNORECASE):
                                    publish_time = text.strip()
                                    break
                            
                            if publish_time:
                                break
                except:
                    pass
            
            # 转换发布时间为时间戳
            if publish_time:
                publish_timestamp = self._convert_time_to_timestamp(publish_time)
            
            # 提取点赞数 - 改进逻辑，基于调试发现
            claps = ""
            try:
                # 查找所有包含数字的span元素
                all_spans = await article_element.query_selector_all('span, div')
                import re
                
                for span in all_spans:
                    text = await span.inner_text()
                    if text and text.strip():
                        # 匹配点赞数格式：纯数字、带K/M/B的数字
                        if re.match(r'^\d+(\.\d+)?[KMB]?$', text.strip()):
                            # 检查父元素是否包含clap相关内容
                            try:
                                parent = await span.query_selector('xpath=..')
                                if parent:
                                    parent_html = await parent.inner_html()
                                    # 如果父元素包含clap相关内容，很可能是点赞数
                                    if 'clap' in parent_html.lower() or '👏' in parent_html:
                                        claps = text.strip()
                                        break
                            except:
                                continue
                        
                        # 备用方案：查找纯数字（如果没有找到带K的）
                        elif not claps and re.match(r'^\d+$', text.strip()):
                            try:
                                parent = await span.query_selector('xpath=..')
                                if parent:
                                    parent_html = await parent.inner_html()
                                    if 'clap' in parent_html.lower() or '👏' in parent_html:
                                        # 确保数字在合理范围内（点赞数通常不会太小）
                                        num = int(text.strip())
                                        if num > 0 and num < 1000000:  # 0-100万之间
                                            claps = text.strip()
                                            break
                            except:
                                continue
            except:
                pass
            
            # 提取评论数
            comments = ""
            comment_selectors = [
                '[data-testid="post-preview-responses"]',
                'button[aria-label*="response"]',
                'a[href*="responses"]',
                'span:has-text("response")'
            ]
            
            for selector in comment_selectors:
                try:
                    comment_element = await article_element.query_selector(selector)
                    if comment_element:
                        comment_text = await comment_element.inner_text()
                        # 提取数字
                        import re
                        numbers = re.findall(r'\d+', comment_text)
                        if numbers:
                            comments = numbers[0]
                            break
                except:
                    continue
            
            # 过滤没有文章链接的记录
            if not url:
                logger.debug(f"跳过没有文章链接的记录: {title}")
                return None
            
            # 生成唯一ID
            import hashlib
            unique_id = hashlib.md5(f"{title}{author}{url}".encode()).hexdigest()
            
            # 构建更丰富的元数据（移除阅读时长）
            metadata = {
                "title": title,
                "keyword": keyword,
                "search_type": "keyword_search",
                "author_url": author_url,
                "publish_time": publish_time,
                "publish_timestamp": publish_timestamp,
                "claps": claps,
                "comments": comments
            }
            
            return DataItem(
                id=unique_id,
                platform="medium",
                content=content[:500],  # 限制内容长度
                author=author,
                url=url,
                created_at=datetime.utcnow().isoformat(),
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"提取文章数据时出错: {e}")
            return None
    
    def _convert_time_to_timestamp(self, time_str: str) -> Optional[int]:
        """将时间字符串转换为时间戳"""
        try:
            import re
            from datetime import datetime, timedelta
            import time
            
            now = datetime.utcnow()
            
            # 处理相对时间格式 (如 "5d ago", "2h ago")
            if 'ago' in time_str.lower():
                # 提取数字和单位
                match = re.search(r'(\d+)\s*([dhm]|day|hour|minute|week|month|year)', time_str.lower())
                if match:
                    number = int(match.group(1))
                    unit = match.group(2)
                    
                    if unit in ['d', 'day']:
                        target_time = now - timedelta(days=number)
                    elif unit in ['h', 'hour']:
                        target_time = now - timedelta(hours=number)
                    elif unit in ['m', 'minute']:
                        target_time = now - timedelta(minutes=number)
                    elif unit in ['week']:
                        target_time = now - timedelta(weeks=number)
                    elif unit in ['month']:
                        target_time = now - timedelta(days=number * 30)  # 近似
                    elif unit in ['year']:
                        target_time = now - timedelta(days=number * 365)  # 近似
                    else:
                        return None
                    
                    return int(target_time.timestamp())
            
            # 处理月份格式 (如 "Jul 4", "Dec 31, 2018")
            month_map = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            
            # 匹配 "Jul 4" 格式
            match = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d+)', time_str.lower())
            if match:
                month_name = match.group(1)
                day = int(match.group(2))
                month = month_map[month_name]
                
                # 如果包含年份
                year_match = re.search(r'\b(20\d{2})\b', time_str)
                if year_match:
                    year = int(year_match.group(1))
                else:
                    # 没有年份，假设是今年或去年
                    year = now.year
                    # 如果这个日期在未来，说明是去年
                    if month > now.month or (month == now.month and day > now.day):
                        year = now.year - 1
                
                try:
                    target_time = datetime(year, month, day)
                    return int(target_time.timestamp())
                except ValueError:
                    return None
            
            # 处理标准日期格式 (如 "2023-12-25")
            match = re.search(r'(\d{4})-(\d{2})-(\d{2})', time_str)
            if match:
                year, month, day = map(int, match.groups())
                try:
                    target_time = datetime(year, month, day)
                    return int(target_time.timestamp())
                except ValueError:
                    return None
            
            # 如果是ISO格式，直接解析
            if 'T' in time_str:
                try:
                    target_time = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    return int(target_time.timestamp())
                except ValueError:
                    return None
            
            return None
            
        except Exception as e:
            logger.debug(f"时间转换失败: {time_str} -> {e}")
            return None
    
    async def get_rate_limit(self) -> RateLimitInfo:
        """获取当前限制信息"""
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
            logger.info("Medium 适配器资源清理完成")
        except Exception as e:
            logger.error(f"清理 Medium 适配器资源失败: {e}")
        finally:
            self.page = None
            self.browser = None
            self.playwright = None
            self.authenticated = False