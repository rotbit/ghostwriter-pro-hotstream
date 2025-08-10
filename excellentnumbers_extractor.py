# filename: excellentnumbers_scraper_mongo.py
"""
Usage:
  pip install playwright bs4 lxml pymongo
  python -m playwright install

  python excellentnumbers_scraper_mongo.py
    # 或在你自己的代码里：
    # from excellentnumbers_scraper_mongo import ExcellentNumbersScraper
    # scraper = ExcellentNumbersScraper(mongo_host="127.0.0.1", mongo_user="root", mongo_password="pwd")
    # scraper.run("https://excellentnumbers.com/categories/Pennsylvania/582")
"""

import asyncio
import re
import time
from typing import List, Dict, Optional
from urllib.parse import urljoin
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from pymongo import MongoClient, ASCENDING, ReplaceOne


class ExcellentNumbersScraper:
    # US/CA 常见电话格式
    PHONE_RE = re.compile(
        r"""
        (?<!\d)
        (?:\+1[\s.\-]?)?
        \(?\d{3}\)?
        [\s.\-]?
        \d{3}
        [\s.\-]?
        \d{4}
        (?!\d)
        """,
        re.VERBOSE,
    )
    # 价格格式 $1,234 或 $99.99
    PRICE_RE = re.compile(r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?")
    NEXT_TEXT_CANDIDATES = {"next", ">", "»", "next »", "older", "下一页"}

    def __init__(
        self,
        mongo_host: str,
        mongo_user: str = "",
        mongo_password: str = "",
        mongo_port: int = 27017,
        mongo_db: str = "excellentnumbers",
        mongo_collection: str = "numbers",
        headless: bool = True,
        page_timeout_ms: int = 60_000,
        page_pause_sec: float = 0.8,
        user_agent: Optional[str] = None,
    ):
        """
        只需传 Mongo 的 IP、用户、密码（若无认证可留空 user/password）。
        你也可直接传 mongo_uri 覆盖。
        """
        # Playwright 配置
        self.headless = headless
        self.page_timeout_ms = page_timeout_ms
        self.page_pause_sec = page_pause_sec
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        )

        # MongoDB 连接
    
        uri = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/?authSource=extra_numbers"
         
        self.mongo = MongoClient(uri)
        self.col = self.mongo[mongo_db][mongo_collection]
        # 唯一索引：phone+price
        self.col.create_index([("phone", ASCENDING)], unique=True)

    # ---------- Playwright 基础 ----------
    async def _get_page_html(self, page, url: str) -> str:
        await page.goto(url, wait_until="load", timeout=self.page_timeout_ms)
        await page.wait_for_timeout(800)  # 等一会给前端渲染
        return await page.content()

    # ---------- 提取逻辑（先站点特化，失败再通用） ----------
    @classmethod
    def _clean_phone(cls, s: str) -> str:
        digits = re.sub(r"\D", "", s)
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) == 10:
            return f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
        return s.strip()

    @classmethod
    def _extract_site_specific(cls, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        针对 excellentnumbers.com 的常见卡片/列表做的特化提取：
        - 在同一块容器里，寻找电话文本（a 标签或纯文本）与 $ 价格。
        - 若站点结构调整，可能失效；届时会回落到通用解析。
        """
        results = []
        # 常见容器：卡片、列表项、表格行等
        containers = soup.select("div, li, article, tr, section")
        for c in containers:
            text = c.get_text(" ", strip=True)
            if not text:
                continue
            phones = cls.PHONE_RE.findall(text)
            prices = cls.PRICE_RE.findall(text)
            if not phones or not prices:
                continue
            results.append({"phone": cls._clean_phone(phones[0]), "price": prices[0].replace(" ", "")})
        # 去重
        dedup = {(r["phone"], r["price"]): r for r in results}
        return list(dedup.values())

    @classmethod
    def _extract_generic(cls, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """通用回退方案：在块级容器中用正则配对电话号码+价格。"""
        results = []
        for block in soup.select("div, li, article, tr, section"):
            t = block.get_text(" ", strip=True)
            if not t:
                continue
            phones = cls.PHONE_RE.findall(t)
            prices = cls.PRICE_RE.findall(t)
            if phones and prices:
                results.append({"phone": cls._clean_phone(phones[0]), "price": prices[0].replace(" ", "")})
        dedup = {(r["phone"], r["price"]): r for r in results}
        return list(dedup.values())

    @classmethod
    def _extract_pairs_from_html(cls, html: str) -> List[Dict[str, str]]:
        soup = BeautifulSoup(html, "lxml")
        rows = cls._extract_site_specific(soup)
        if not rows:
            rows = cls._extract_generic(soup)
        return rows

    # ---------- 分页 ----------
    @classmethod
    def _find_next_url(cls, html: str, current_url: str) -> Optional[str]:
        soup = BeautifulSoup(html, "lxml")
        pagers = soup.select('nav, ul.pagination, div.pagination, div.pager, footer, div[role="navigation"]') or [soup]

        def is_next_text(s: str) -> bool:
            s_norm = s.strip().lower()
            return s_norm in cls.NEXT_TEXT_CANDIDATES or "next" in s_norm

        for container in pagers:
            for a in container.select("a[href]"):
                label = a.get_text(" ", strip=True)
                if is_next_text(label):
                    href = a.get("href")
                    if href:
                        return urljoin(current_url, href)

        link = soup.select_one('a[rel="next"][href]')
        return urljoin(current_url, link["href"]) if link else None

    # ---------- MongoDB 批量写入 ----------
    def _bulk_upsert(self, rows: List[Dict[str, str]], source_url: str):
        if not rows:
            return
        now = datetime.now(timezone.utc)
        ops = []
        for r in rows:
            key = {"phone": r["phone"], "price": r["price"]}
            doc = {**key, "source_url": source_url,"source":"excellent_number", "crawled_at": now}
            ops.append(ReplaceOne(key, doc, upsert=True))
        result = self.col.bulk_write(ops, ordered=False)
        print(
            f"[MONGO] upserted={getattr(result, 'upserted_count', 0) or 0}, "
            f"modified={getattr(result, 'modified_count', 0) or 0}"
        )

    # ---------- 抓取主流程 ----------
    async def scrape(self, url: str) -> List[Dict[str, str]]:
        """抓取并返回本轮抓到的 (phone, price) 去重列表（同时已写入 Mongo）。"""
        all_rows: List[Dict[str, str]] = []
        visited = set()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(user_agent=self.user_agent)
            page = await context.new_page()

            cur = url
            while cur and cur not in visited:
                visited.add(cur)
                print(f"[INFO] Fetching: {cur}")
                try:
                    html = await self._get_page_html(page, cur)
                except PlaywrightTimeoutError:
                    print(f"[WARN] Timeout loading {cur}, skip.")
                    break

                rows = self._extract_pairs_from_html(html)
                print(f"[INFO] Found {len(rows)} items on this page.")
                self._bulk_upsert(rows, source_url=cur)
                all_rows.extend(rows)

                nxt = self._find_next_url(html, cur)
                if nxt and nxt not in visited:
                    time.sleep(self.page_pause_sec)
                    cur = nxt
                else:
                    cur = None

            await context.close()
            await browser.close()

        # 结果再去重
        dedup = {(r["phone"], r["price"]): r for r in all_rows}
        return list(dedup.values())

    # ---------- 便捷入口 ----------
    def run(self, url: str) -> List[Dict[str, str]]:
        return asyncio.run(self.scrape(url))


if __name__ == "__main__":
    # ✅ 修改为你的 MongoDB 连接信息
    scraper = ExcellentNumbersScraper(
        mongo_host="43.159.58.235",   # 你的 Mongo IP
        mongo_user="extra_numbers",        # 你的用户名（无账号可留空）
        mongo_password="RsBWd3hTAZeR7kC4",  # 你的密码（无账号可留空）
        mongo_port=27017,         # 端口默认 27017
        mongo_db="extra_numbers",
        mongo_collection="numbers",
        headless=True,
    )

    start_url = "https://excellentnumbers.com/categories/Pennsylvania/582?sort=newest&sortcode="
    data = scraper.run(start_url)
    print(f"[DONE] Got {len(data)} unique rows this run.")
