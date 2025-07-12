from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def scrape_twitter_trending():
    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(locale="en-US")
        page = context.new_page()

        try:
            # 打开 Twitter Trending 页面
            print("🚀 正在加载 Twitter Trending 页面...")
            page.goto("https://twitter.com/i/trends", timeout=30000)
            page.wait_for_load_state("networkidle")

            # 获取所有 trend 元素（注意结构可能因地区/UI变动）
            trend_elements = page.query_selector_all('div[aria-label*="Trending now"] span')

            print("🔥 抓取到的趋势话题（前 10 条）：\n")
            count = 0
            for el in trend_elements:
                text = el.inner_text().strip()
                # 排除空行或重复
                if text and not text.startswith("#") and len(text) > 2:
                    print(f"{count + 1}. {text}")
                    count += 1
                if count >= 10:
                    break

        except PlaywrightTimeoutError:
            print("❌ 页面加载超时")
        except Exception as e:
            print(f"❌ 抓取失败: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    scrape_twitter_trending()