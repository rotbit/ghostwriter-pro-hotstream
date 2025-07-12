#!/usr/bin/env python3
"""
Medium 适配器快速测试脚本
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from hotstream.plugins.platforms.medium_adapter import MediumAdapter
from hotstream.core.interfaces import SearchOptions
from loguru import logger

# 配置日志
logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


async def test_medium_anonymous():
    """测试匿名模式访问Medium"""
    print("\n" + "="*60)
    print("🔍 测试 Medium 匿名模式")
    print("="*60)
    
    adapter = MediumAdapter()
    
    try:
        # 测试初始化（匿名模式）
        print("📡 初始化 Medium 适配器（匿名模式）...")
        success = await adapter.authenticate()
        
        if not success:
            print("❌ Medium 适配器初始化失败")
            return False
            
        print("✅ Medium 适配器初始化成功")
        
        # 测试搜索
        print("\n🔍 开始搜索测试...")
        keywords = ["Python", "AI"]
        options = SearchOptions(limit=3)
        
        articles_found = 0
        async for article in adapter.search(keywords, options):
            articles_found += 1
            print(f"\n📖 文章 {articles_found}:")
            print(f"   标题: {article.metadata.get('title', 'N/A')}")
            print(f"   作者: {article.author}")
            print(f"   作者链接: {article.metadata.get('author_url', 'N/A')}")
            print(f"   文章链接: {article.url or 'N/A'}")
            print(f"   发布时间: {article.metadata.get('publish_time', 'N/A')}")
            print(f"   时间戳: {article.metadata.get('publish_timestamp', 'N/A')}")
            print(f"   点赞数: {article.metadata.get('claps', 'N/A')}")
            print(f"   评论数: {article.metadata.get('comments', 'N/A')}")
            print(f"   内容预览: {article.content[:100] if article.content else 'N/A'}...")
            print(f"   关键词: {article.metadata.get('keyword', 'N/A')}")
            
        if articles_found > 0:
            print(f"\n✅ 成功找到 {articles_found} 篇文章")
            return True
        else:
            print("\n⚠️  未找到文章")
            return False
            
    except Exception as e:
        print(f"❌ 测试过程中出错: {e}")
        return False
    finally:
        await adapter.cleanup()
        print("🧹 资源清理完成")


async def test_medium_with_login():
    """测试登录模式访问Medium"""
    print("\n" + "="*60)
    print("🔐 测试 Medium 登录模式")
    print("="*60)
    
    # 检查是否为交互模式
    import sys
    if not sys.stdin.isatty():
        print("⏭️  非交互模式，跳过登录测试")
        return True
    
    try:
        # 获取用户输入的登录信息
        print("请输入 Medium 登录信息（可选，直接回车跳过）:")
        email = input("📧 邮箱: ").strip()
        
        if not email:
            print("⏭️  跳过登录测试")
            return True
            
        password = input("🔒 密码: ").strip()
        
        if not password:
            print("⚠️  密码为空，跳过登录测试")
            return True
    except (EOFError, KeyboardInterrupt):
        print("\n⏭️  跳过登录测试")
        return True
    
    adapter = MediumAdapter()
    
    try:
        # 测试登录
        print("\n📡 初始化 Medium 适配器（登录模式）...")
        credentials = {
            "email": email,
            "password": password
        }
        
        success = await adapter.authenticate(credentials)
        
        if not success:
            print("❌ Medium 登录失败")
            return False
            
        print("✅ Medium 登录成功")
        
        # 测试搜索
        print("\n🔍 开始登录状态搜索测试...")
        keywords = ["技术"]
        options = SearchOptions(limit=2)
        
        articles_found = 0
        async for article in adapter.search(keywords, options):
            articles_found += 1
            print(f"\n📖 文章 {articles_found}:")
            print(f"   标题: {article.metadata.get('title', 'N/A')}")
            print(f"   作者: {article.author}")
            print(f"   文章链接: {article.url or 'N/A'}")
            print(f"   发布时间: {article.metadata.get('publish_time', 'N/A')}")
            print(f"   时间戳: {article.metadata.get('publish_timestamp', 'N/A')}")
            print(f"   点赞数: {article.metadata.get('claps', 'N/A')}")
            print(f"   内容预览: {article.content[:100] if article.content else 'N/A'}...")
            
        if articles_found > 0:
            print(f"\n✅ 登录模式成功找到 {articles_found} 篇文章")
            return True
        else:
            print("\n⚠️  登录模式未找到文章")
            return False
            
    except Exception as e:
        print(f"❌ 登录测试过程中出错: {e}")
        return False
    finally:
        await adapter.cleanup()
        print("🧹 资源清理完成")


async def test_medium_rate_limit():
    """测试速率限制"""
    print("\n" + "="*60)
    print("⏱️  测试 Medium 速率限制")
    print("="*60)
    
    adapter = MediumAdapter()
    
    try:
        # 获取速率限制信息
        rate_limit = await adapter.get_rate_limit()
        
        print(f"📊 速率限制信息:")
        print(f"   每分钟请求数: {rate_limit.requests_per_minute}")
        print(f"   每小时请求数: {rate_limit.requests_per_hour}")
        print(f"   剩余请求数: {rate_limit.remaining}")
        
        return True
        
    except Exception as e:
        print(f"❌ 获取速率限制信息失败: {e}")
        return False
    finally:
        await adapter.cleanup()


async def test_multiple_keywords():
    """测试多关键词搜索"""
    print("\n" + "="*60)
    print("🔍 测试多关键词搜索")
    print("="*60)
    
    adapter = MediumAdapter()
    
    try:
        success = await adapter.authenticate()
        if not success:
            print("❌ Medium 适配器初始化失败")
            return False
            
        print("✅ Medium 适配器初始化成功")
        
        # 测试多个关键词
        keywords = ["Python编程", "机器学习", "Web开发"]
        options = SearchOptions(limit=6)  # 每个关键词2篇文章
        
        print(f"\n🔍 搜索关键词: {', '.join(keywords)}")
        
        keyword_results = {}
        total_articles = 0
        
        async for article in adapter.search(keywords, options):
            total_articles += 1
            keyword = article.metadata.get('keyword', 'Unknown')
            
            if keyword not in keyword_results:
                keyword_results[keyword] = 0
            keyword_results[keyword] += 1
            
            print(f"\n📖 文章 {total_articles} (关键词: {keyword}):")
            print(f"   标题: {article.metadata.get('title', 'N/A')}")
            print(f"   作者: {article.author}")
            print(f"   文章链接: {article.url or 'N/A'}")
            print(f"   发布时间: {article.metadata.get('publish_time', 'N/A')}")
            print(f"   时间戳: {article.metadata.get('publish_timestamp', 'N/A')}")
            print(f"   点赞数: {article.metadata.get('claps', 'N/A')}")
            print(f"   内容预览: {article.content[:80] if article.content else 'N/A'}...")
            
        print(f"\n📊 搜索结果统计:")
        for keyword, count in keyword_results.items():
            print(f"   {keyword}: {count} 篇文章")
        print(f"   总计: {total_articles} 篇文章")
        
        return total_articles > 0
        
    except Exception as e:
        print(f"❌ 多关键词测试失败: {e}")
        return False
    finally:
        await adapter.cleanup()


async def main():
    """主测试函数"""
    print("🚀 Medium 适配器测试开始")
    print("本测试将验证 Medium 适配器的各项功能")
    
    test_results = []
    
    # 测试1: 匿名模式
    result1 = await test_medium_anonymous()
    test_results.append(("匿名模式测试", result1))
    
    # 测试2: 速率限制
    result2 = await test_medium_rate_limit()
    test_results.append(("速率限制测试", result2))
    
    # 测试3: 多关键词搜索
    result3 = await test_multiple_keywords()
    test_results.append(("多关键词测试", result3))
    
    # 测试4: 登录模式（可选）
    result4 = await test_medium_with_login()
    test_results.append(("登录模式测试", result4))
    
    # 输出测试结果
    print("\n" + "="*60)
    print("📋 测试结果汇总")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📊 测试统计:")
    print(f"   通过: {passed}")
    print(f"   失败: {failed}")
    print(f"   总计: {len(test_results)}")
    
    if failed == 0:
        print("\n🎉 所有测试通过！Medium 适配器工作正常")
        return 0
    else:
        print(f"\n⚠️  有 {failed} 个测试失败，请检查配置和网络连接")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⏹️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 测试程序异常: {e}")
        sys.exit(1)