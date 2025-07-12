"""
基本使用示例
"""

import asyncio
from hotstream.core.framework import HotStreamFramework
from hotstream.core.interfaces import TaskConfig, SearchOptions


async def basic_search_example():
    """基本搜索示例"""
    # 创建框架实例
    framework = HotStreamFramework()
    
    try:
        # 初始化框架
        print("初始化框架...")
        if not await framework.initialize():
            print("框架初始化失败")
            return
        
        # 立即搜索数据
        print("开始搜索...")
        results = await framework.execute_immediate_search(
            platform="twitter",
            keywords=["AI", "机器学习"],
            limit=20
        )
        
        print(f"搜索完成，获得 {len(results)} 条数据")
        
        # 显示结果
        for i, item in enumerate(results[:5]):  # 只显示前5条
            print(f"\n--- 结果 {i+1} ---")
            print(f"ID: {item.id}")
            print(f"平台: {item.platform}")
            print(f"作者: {item.author}")
            print(f"内容: {item.content}")
            print(f"URL: {item.url}")
    
    finally:
        # 清理资源
        await framework.stop()


async def scheduled_task_example():
    """定时任务示例"""
    # 创建框架实例
    framework = HotStreamFramework("configs/hotstream.yaml")
    
    try:
        # 初始化框架
        print("初始化框架...")
        if not await framework.initialize():
            print("框架初始化失败")
            return
        
        # 创建定时任务
        task_config = TaskConfig(
            task_id="daily_ai_news",
            name="每日AI新闻",
            platform="twitter",
            keywords=["AI", "人工智能", "机器学习"],
            schedule="0 9 * * *",  # 每天上午9点
            options=SearchOptions(limit=50),
            storage_config={
                "type": "json",
                "output_dir": "output/daily_news"
            }
        )
        
        # 添加任务
        if await framework.add_task(task_config):
            print("定时任务添加成功")
            
            # 手动执行一次任务
            print("手动执行任务...")
            results = await framework.execute_task("daily_ai_news")
            print(f"任务执行完成，处理了 {len(results)} 条数据")
        else:
            print("任务添加失败")
    
    finally:
        await framework.stop()


async def multi_platform_example():
    """多平台搜索示例"""
    framework = HotStreamFramework()
    
    try:
        if not await framework.initialize():
            print("框架初始化失败")
            return
        
        # 获取支持的平台
        platforms = framework.list_supported_platforms()
        print(f"支持的平台: {platforms}")
        
        # 多平台搜索
        all_results = []
        for platform in platforms[:2]:  # 只测试前2个平台
            try:
                print(f"\n搜索平台: {platform}")
                results = await framework.execute_immediate_search(
                    platform=platform,
                    keywords=["技术"],
                    limit=10
                )
                all_results.extend(results)
                print(f"{platform} 搜索完成，获得 {len(results)} 条数据")
            except Exception as e:
                print(f"{platform} 搜索失败: {e}")
        
        print(f"\n总计获得 {len(all_results)} 条数据")
        
        # 按平台统计
        platform_counts = {}
        for item in all_results:
            platform_counts[item.platform] = platform_counts.get(item.platform, 0) + 1
        
        print("平台统计:")
        for platform, count in platform_counts.items():
            print(f"  {platform}: {count} 条")
    
    finally:
        await framework.stop()


if __name__ == "__main__":
    print("=== HotStream 基本使用示例 ===\n")
    
    print("1. 基本搜索示例")
    asyncio.run(basic_search_example())
    
    print("\n" + "="*50 + "\n")
    
    print("2. 多平台搜索示例")
    asyncio.run(multi_platform_example())
    
    # 注意：定时任务示例需要长时间运行，这里注释掉
    # print("\n" + "="*50 + "\n")
    # print("3. 定时任务示例")
    # asyncio.run(scheduled_task_example())