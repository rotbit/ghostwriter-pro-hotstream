#!/usr/bin/env python3
"""
测试完整的数据处理流程
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from hotstream.core.framework import HotStreamFramework
from hotstream.core.interfaces import Task
from loguru import logger


async def test_complete_flow():
    """测试完整的数据处理流程"""
    logger.info("🚀 开始测试完整数据处理流程...")
    
    # 创建框架实例
    framework = HotStreamFramework()
    
    try:
        # 初始化框架
        logger.info("📡 初始化框架...")
        if not await framework.initialize():
            logger.error("❌ 框架初始化失败")
            return
        
        logger.info("✅ 框架初始化成功")
        
        # 启动调度器
        logger.info("🔧 启动调度器...")
        await framework.scheduler.start()
        
        # 创建Twitter搜索任务
        logger.info("📝 创建Twitter搜索任务...")
        task_id = f"test_search_{int(datetime.now().timestamp())}"
        
        if await framework.create_search_task(
            task_id=task_id,
            name="测试Twitter搜索",
            platform="twitter",
            keywords=["OpenAI", "AI"],
            limit=5
        ):
            logger.info(f"✅ 搜索任务创建成功: {task_id}")
        else:
            logger.error(f"❌ 搜索任务创建失败: {task_id}")
            return
        
        # 创建Twitter监控任务
        monitor_task_id = f"test_monitor_{int(datetime.now().timestamp())}"
        
        if await framework.create_monitor_task(
            task_id=monitor_task_id,
            name="测试Twitter监控",
            platform="twitter",
            accounts=["openai"],
            limit=3
        ):
            logger.info(f"✅ 监控任务创建成功: {monitor_task_id}")
        else:
            logger.error(f"❌ 监控任务创建失败: {monitor_task_id}")
        
        # 等待任务处理
        logger.info("⏳ 等待任务处理...")
        for i in range(30):  # 等待30秒
            await asyncio.sleep(1)
            
            # 检查任务状态
            stats = await framework.get_task_stats()
            logger.info(f"📊 任务统计: {stats}")
            
            # 如果没有正在处理的任务，表示完成
            if stats.get('processing_tasks', 0) == 0 and i > 10:
                logger.info("✅ 所有任务处理完成")
                break
        
        # 获取最终统计
        final_stats = await framework.get_task_stats()
        logger.info(f"📈 最终统计: {final_stats}")
        
        logger.info("🎉 完整流程测试完成！")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 停止框架
        logger.info("🧹 清理资源...")
        await framework.stop()


async def test_manual_task():
    """测试手动创建任务"""
    logger.info("🔧 测试手动任务创建...")
    
    from hotstream.core.task_manager import MongoTaskManager
    from hotstream.core.interfaces import TaskStatus
    
    # 创建任务管理器
    task_manager = MongoTaskManager()
    
    try:
        if await task_manager.initialize():
            logger.info("✅ 任务管理器初始化成功")
            
            # 创建测试任务
            task = Task(
                task_id=f"manual_test_{int(datetime.now().timestamp())}",
                name="手动测试任务",
                platform="twitter",
                task_type="monitor",
                accounts=["elonmusk"],
                status=TaskStatus.PENDING.value,
                options={"limit": 3},
                created_at=datetime.utcnow()
            )
            
            # 保存任务
            if await task_manager.save_task(task):
                logger.info(f"✅ 任务保存成功: {task.task_id}")
                
                # 查询任务
                retrieved_task = await task_manager.get_task(task.task_id)
                if retrieved_task:
                    logger.info(f"✅ 任务查询成功: {retrieved_task.task_id}")
                else:
                    logger.error("❌ 任务查询失败")
            else:
                logger.error("❌ 任务保存失败")
        else:
            logger.error("❌ 任务管理器初始化失败")
    
    except Exception as e:
        logger.error(f"❌ 手动任务测试失败: {e}")
    
    finally:
        await task_manager.cleanup()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="测试完整数据处理流程")
    parser.add_argument("--manual", action="store_true", help="仅测试手动任务创建")
    args = parser.parse_args()
    
    if args.manual:
        asyncio.run(test_manual_task())
    else:
        asyncio.run(test_complete_flow())