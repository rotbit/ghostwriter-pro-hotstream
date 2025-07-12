#!/usr/bin/env python3
"""
快速测试 Nitter 适配器
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from hotstream.plugins.platforms.twitter_adapter import TwitterAdapter
from loguru import logger

async def test_nitter():
    """测试 Nitter 适配器"""
    print("🚀 测试 Nitter 适配器...")
    
    # 创建适配器实例
    adapter = TwitterAdapter("https://nitter.poast.org")
    
    try:
        # 初始化
        print("📡 连接 Nitter 实例...")
        if not await adapter.authenticate({}):
            print("❌ Nitter 连接失败")
            return
        
        print("✅ Nitter 连接成功")
        
        # 测试账号监控
        test_accounts = ["elonmusk", "openai"]
        print(f"👀 监控账号: {', '.join(test_accounts)}")
        
        tweets = []
        async for tweet in adapter.monitor_accounts(test_accounts, limit=5):
            tweets.append(tweet)
            print(f"📝 @{tweet.author}: {tweet.content[:100]}...")
        
        print(f"\n✅ 测试完成！获得 {len(tweets)} 条推文")
        
        # 显示详细信息
        if tweets:
            print("\n📊 推文详情:")
            for i, tweet in enumerate(tweets, 1):
                print(f"\n{i}. @{tweet.author}")
                print(f"   内容: {tweet.content}")
                print(f"   时间: {tweet.created_at}")
                print(f"   链接: {tweet.url}")
                print(f"   来源: {tweet.metadata.get('nitter_instance', 'N/A')}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await adapter.cleanup()
        print("🧹 清理完成")

if __name__ == "__main__":
    asyncio.run(test_nitter())