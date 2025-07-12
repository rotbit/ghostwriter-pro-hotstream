#!/usr/bin/env python3
"""
测试真实的 Twitter 适配器
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from hotstream.core.framework import HotStreamFramework


async def test_twitter_adapter():
    """测试 Twitter 适配器"""
    
    print("=== 测试真实 Twitter 适配器 ===\n")
    
    framework = HotStreamFramework()
    
    try:
        # 初始化框架
        print("1. 初始化框架...")
        if not await framework.initialize():
            print("❌ 框架初始化失败")
            return
        
        print("✅ 框架初始化成功")
        
        # 检查平台支持
        platforms = framework.list_supported_platforms()
        print(f"✅ 支持的平台: {platforms}")
        
        if "twitter" not in platforms:
            print("❌ Twitter 平台不可用")
            return
        
        # 测试搜索
        print("\n2. 开始 Twitter 搜索...")
        print("📋 搜索关键字: ['Python', 'AI']")
        print("📋 限制: 每个关键字最多5条")
        print("🌐 浏览器将会打开，您可以观察搜索过程")
        print()
        
        # 执行搜索
        results = await framework.execute_immediate_search(
            platform="twitter",
            keywords=["Python", "AI"], 
            limit=10  # 总共10条，每个关键字5条
        )
        
        print(f"\n3. 搜索结果统计")
        print(f"✅ 总共获得: {len(results)} 条推文")
        
        # 显示详细结果
        if results:
            print(f"\n4. 推文详情:")
            for i, tweet in enumerate(results, 1):
                print(f"\n--- 推文 {i} ---")
                print(f"📝 内容: {tweet.content[:100]}{'...' if len(tweet.content) > 100 else ''}")
                print(f"👤 作者: {tweet.author}")
                print(f"🔗 链接: {tweet.url}")
                print(f"📅 时间: {tweet.created_at}")
                print(f"💬 回复: {tweet.metadata.get('reply_count', 0)}")
                print(f"🔄 转发: {tweet.metadata.get('retweet_count', 0)}")
                print(f"❤️ 点赞: {tweet.metadata.get('like_count', 0)}")
        else:
            print("⚠️ 没有获得任何推文数据")
            print("可能的原因:")
            print("- 网络连接问题")
            print("- Twitter 页面结构变化")
            print("- 被 Twitter 限流")
        
        print(f"\n5. 测试完成!")
        
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断测试")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\n6. 清理资源...")
        await framework.stop()
        print("✅ 清理完成")


async def test_single_keyword():
    """测试单个关键字搜索"""
    
    print("=== 测试单个关键字搜索 ===\n")
    
    framework = HotStreamFramework()
    
    try:
        await framework.initialize()
        
        keyword = input("请输入要搜索的关键字: ").strip()
        if not keyword:
            keyword = "ChatGPT"
            print(f"使用默认关键字: {keyword}")
        
        limit = 5
        print(f"搜索关键字: '{keyword}'")
        print(f"结果限制: {limit} 条")
        print("浏览器即将打开...\n")
        
        results = await framework.execute_immediate_search(
            platform="twitter",
            keywords=[keyword],
            limit=limit
        )
        
        print(f"\n搜索完成! 获得 {len(results)} 条结果\n")
        
        for i, tweet in enumerate(results, 1):
            print(f"推文 {i}:")
            print(f"  内容: {tweet.content}")
            print(f"  作者: @{tweet.author}")
            print(f"  链接: {tweet.url}")
            print()
    
    except Exception as e:
        print(f"搜索失败: {e}")
    
    finally:
        await framework.stop()


def main():
    """主函数"""
    print("选择测试模式:")
    print("1. 完整测试 (多关键字)")
    print("2. 单关键字测试")
    print("3. 退出")
    
    choice = input("\n请选择 (1-3): ").strip()
    
    if choice == "1":
        asyncio.run(test_twitter_adapter())
    elif choice == "2":
        asyncio.run(test_single_keyword())
    elif choice == "3":
        print("退出")
    else:
        print("无效选择")


if __name__ == "__main__":
    main()