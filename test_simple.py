#!/usr/bin/env python3
"""
简单的 Playwright 测试
"""

import asyncio
from playwright.async_api import async_playwright


async def test_basic_playwright():
    """基本的 Playwright 测试"""
    print("=== 基本 Playwright 测试 ===")
    
    try:
        playwright = await async_playwright().start()
        print("✅ Playwright 启动成功")
        
        browser = await playwright.chromium.launch(headless=False)
        print("✅ 浏览器启动成功")
        
        page = await browser.new_page()
        print("✅ 页面创建成功")
        
        await page.goto("https://www.google.com")
        print("✅ 页面导航成功")
        
        title = await page.title()
        print(f"✅ 页面标题: {title}")
        
        # 等待几秒让用户看到浏览器
        await asyncio.sleep(3)
        
        await browser.close()
        print("✅ 浏览器关闭成功")
        
        await playwright.stop()
        print("✅ Playwright 停止成功")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_twitter_page():
    """测试访问 Twitter 页面"""
    print("\n=== Twitter 页面测试 ===")
    
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=False,
            slow_mo=1000
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        
        page = await context.new_page()
        
        print("🌐 访问 Twitter 搜索页面...")
        await page.goto("https://twitter.com/search?q=python&src=typed_query&f=live")
        
        await asyncio.sleep(5)
        
        title = await page.title()
        print(f"✅ 页面标题: {title}")
        
        # 查找推文元素
        tweets = await page.query_selector_all('[data-testid="tweet"]')
        print(f"✅ 找到 {len(tweets)} 个推文元素")
        
        if tweets:
            # 获取第一个推文的内容
            first_tweet = tweets[0]
            content_element = await first_tweet.query_selector('[data-testid="tweetText"]')
            if content_element:
                content = await content_element.inner_text()
                print(f"✅ 第一条推文: {content[:100]}...")
        
        await asyncio.sleep(3)
        
        await browser.close()
        await playwright.stop()
        
    except Exception as e:
        print(f"❌ Twitter 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("选择测试:")
    print("1. 基本 Playwright 测试")
    print("2. Twitter 页面测试")
    
    choice = input("请选择 (1-2): ").strip()
    
    if choice == "1":
        asyncio.run(test_basic_playwright())
    elif choice == "2":
        asyncio.run(test_twitter_page())
    else:
        print("无效选择")