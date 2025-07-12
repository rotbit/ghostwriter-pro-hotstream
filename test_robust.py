#!/usr/bin/env python3
"""
鲁棒性测试 Twitter 适配器
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from hotstream.plugins.platforms.twitter_adapter import TwitterAdapter
from hotstream.core.interfaces import SearchOptions


async def test_twitter_robust():
    """鲁棒性测试"""
    
    print("=== Twitter 适配器鲁棒性测试 ===\n")
    
    adapter = TwitterAdapter()
    
    try:
        # 1. 测试初始化
        print("1. 测试适配器初始化...")
        success = await adapter.authenticate({})
        
        if not success:
            print("❌ 适配器初始化失败")
            return
        
        print("✅ 适配器初始化成功")
        
        # 2. 检查状态
        print("\n2. 检查适配器状态...")
        print(f"   认证状态: {adapter.authenticated}")
        print(f"   浏览器存在: {adapter.browser is not None}")
        print(f"   页面存在: {adapter.page is not None}")
        if adapter.page:
            print(f"   页面关闭状态: {adapter.page.is_closed()}")
        
        # 3. 测试简单搜索
        print("\n3. 测试简单搜索...")
        
        try:
            # 创建搜索选项
            options = SearchOptions(limit=2)
            
            print("🔍 开始搜索关键字: 'AI'")
            results = []
            
            async for item in adapter.search(['AI'], options):
                results.append(item)
                print(f"📝 找到推文: {item.content[:80]}...")
                if len(results) >= 2:
                    break
            
            print(f"\n✅ 搜索完成，共获得 {len(results)} 条结果")
            
            # 显示详细结果
            for i, item in enumerate(results, 1):
                print(f"\n--- 推文 {i} ---")
                print(f"ID: {item.id}")
                print(f"作者: @{item.author}")
                print(f"内容: {item.content}")
                print(f"链接: {item.url}")
                print(f"时间: {item.created_at}")
                
        except Exception as e:
            print(f"❌ 搜索过程出错: {e}")
            import traceback
            traceback.print_exc()
        
        # 4. 测试页面状态
        print(f"\n4. 最终状态检查...")
        if adapter.page and not adapter.page.is_closed():
            try:
                title = await adapter.page.title()
                url = adapter.page.url
                print(f"   当前页面标题: {title}")
                print(f"   当前页面URL: {url}")
            except:
                print("   无法获取页面信息")
        else:
            print("   页面已关闭或不存在")
            
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断测试")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n5. 清理资源...")
        try:
            await adapter.cleanup()
            print("✅ 清理完成")
        except Exception as e:
            print(f"⚠️ 清理时出现错误: {e}")


async def test_page_navigation():
    """测试页面导航"""
    print("=== 页面导航测试 ===\n")
    
    adapter = TwitterAdapter()
    
    try:
        # 初始化
        if not await adapter.authenticate({}):
            print("❌ 初始化失败")
            return
        
        print("✅ 适配器初始化成功")
        
        # 测试导航到 Twitter 主页
        print("🌐 导航到 Twitter 主页...")
        await adapter.page.goto("https://twitter.com", timeout=30000)
        
        title = await adapter.page.title()
        print(f"✅ 页面标题: {title}")
        
        # 等待一下
        await asyncio.sleep(2)
        
        # 测试导航到搜索页面
        print("🔍 导航到搜索页面...")
        await adapter.page.goto("https://twitter.com/search?q=test", timeout=30000)
        
        title = await adapter.page.title()
        print(f"✅ 搜索页面标题: {title}")
        
        # 等待页面加载
        await asyncio.sleep(3)
        
        # 检查是否有推文元素
        tweets = await adapter.page.query_selector_all('[data-testid="tweet"]')
        print(f"📊 找到推文元素数量: {len(tweets)}")
        
        if tweets:
            # 尝试提取第一个推文的内容
            first_tweet = tweets[0]
            content_element = await first_tweet.query_selector('[data-testid="tweetText"]')
            if content_element:
                content = await content_element.inner_text()
                print(f"📝 第一条推文内容: {content[:100]}...")
            else:
                print("⚠️ 无法提取推文内容")
        
        print("✅ 页面导航测试完成")
        
    except Exception as e:
        print(f"❌ 页面导航测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await adapter.cleanup()


def main():
    """主函数"""
    print("选择测试类型:")
    print("1. 鲁棒性测试")
    print("2. 页面导航测试")
    print("3. 退出")
    
    choice = input("\n请选择 (1-3): ").strip()
    
    if choice == "1":
        asyncio.run(test_twitter_robust())
    elif choice == "2":
        asyncio.run(test_page_navigation())
    elif choice == "3":
        print("退出")
    else:
        print("无效选择")


if __name__ == "__main__":
    main()