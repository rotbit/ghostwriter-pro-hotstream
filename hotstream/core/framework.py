"""
HotStream 核心框架
"""

import asyncio
from typing import Dict, List, Any, Optional
from loguru import logger

from .plugin_manager import PluginManager
from .enhanced_scheduler import EnhancedTaskScheduler
from .data_processor import DataProcessor
from .interfaces import TaskConfig, TaskStatus, DataItem, Task
from ..config.config_manager import ConfigManager


class HotStreamFramework:
    """HotStream 框架主类"""
    
    def __init__(self, config_path: Optional[str] = None):
        # 初始化配置管理器
        self.config = ConfigManager(config_path)
        
        # 初始化核心组件
        plugin_dirs = self.config.get('plugins.plugin_dirs', [])
        self.plugin_manager = PluginManager(plugin_dirs)
        self.scheduler = EnhancedTaskScheduler(self.config.data)
        self.data_processor = DataProcessor()
        
        # 运行状态
        self._running = False
        self._tasks: Dict[str, TaskConfig] = {}
        
        logger.info("HotStream 框架初始化完成")
    
    async def initialize(self) -> bool:
        """初始化框架"""
        try:
            # 发现并加载插件
            await self.plugin_manager.discover_plugins()
            
            # 初始化调度器
            if not await self.scheduler.initialize():
                return False
            
            # 初始化数据处理器
            await self.data_processor.initialize(self.plugin_manager)
            
            logger.info("框架初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"框架初始化失败: {e}")
            return False
    
    async def start(self) -> None:
        """启动框架"""
        if not await self.initialize():
            raise RuntimeError("框架初始化失败")
        
        self._running = True
        logger.info("HotStream 框架启动")
        
        # 启动调度器
        await self.scheduler.start()
        
        try:
            # 保持运行
            while self._running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("收到停止信号")
        finally:
            await self.stop()
    
    async def stop(self) -> None:
        """停止框架"""
        if not self._running:
            return
        
        self._running = False
        logger.info("正在停止 HotStream 框架...")
        
        # 停止调度器
        await self.scheduler.stop()
        
        # 清理插件
        await self.plugin_manager.cleanup_all()
        
        # 清理数据处理器
        await self.data_processor.cleanup()
        
        logger.info("HotStream 框架已停止")
    
    async def add_task(self, task_config: TaskConfig) -> bool:
        """添加任务"""
        try:
            # 验证平台是否支持
            if not self.plugin_manager.get_platform_adapter(task_config.platform):
                logger.error(f"不支持的平台: {task_config.platform}")
                return False
            
            # 添加到任务列表
            self._tasks[task_config.task_id] = task_config
            
            # 添加到调度器
            if task_config.schedule:
                await self.scheduler.add_scheduled_task(task_config)
            
            logger.info(f"任务添加成功: {task_config.task_id}")
            return True
            
        except Exception as e:
            logger.error(f"添加任务失败: {e}")
            return False
    
    async def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        try:
            if task_id in self._tasks:
                task_config = self._tasks.pop(task_id)
                await self.scheduler.remove_task(task_id)
                logger.info(f"任务移除成功: {task_id}")
                return True
            else:
                logger.warning(f"任务不存在: {task_id}")
                return False
                
        except Exception as e:
            logger.error(f"移除任务失败: {e}")
            return False
    
    async def execute_task(self, task_id: str) -> List[DataItem]:
        """立即执行任务"""
        if task_id not in self._tasks:
            raise ValueError(f"任务不存在: {task_id}")
        
        task_config = self._tasks[task_id]
        logger.info(f"开始执行任务: {task_id}")
        
        try:
            # 执行数据抓取
            results = await self.data_processor.process_task(task_config)
            
            logger.info(f"任务执行完成: {task_id}, 获得 {len(results)} 条数据")
            return results
            
        except Exception as e:
            logger.error(f"任务执行失败 {task_id}: {e}")
            raise
    
    async def execute_immediate_search(
        self, 
        platform: str, 
        keywords: List[str],
        **options
    ) -> List[DataItem]:
        """立即执行搜索"""
        from .interfaces import SearchOptions
        
        # 创建临时任务配置
        task_config = TaskConfig(
            task_id=f"immediate_{platform}_{hash(str(keywords))}",
            name="即时搜索",
            platform=platform,
            keywords=keywords,
            options=SearchOptions(**options)
        )
        
        return await self.data_processor.process_task(task_config)
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        return self.scheduler.get_task_status(task_id)
    
    def list_tasks(self) -> List[str]:
        """列出所有任务"""
        return list(self._tasks.keys())
    
    def get_task_config(self, task_id: str) -> Optional[TaskConfig]:
        """获取任务配置"""
        return self._tasks.get(task_id)
    
    def list_supported_platforms(self) -> List[str]:
        """列出支持的平台"""
        return self.plugin_manager.list_platforms()
    
    def get_framework_stats(self) -> Dict[str, Any]:
        """获取框架统计信息"""
        return {
            "running": self._running,
            "total_tasks": len(self._tasks),
            "supported_platforms": len(self.plugin_manager.list_platforms()),
            "loaded_plugins": len(self.plugin_manager.list_plugins()),
            "scheduler_stats": self.scheduler.get_stats() if hasattr(self.scheduler, 'get_stats') else {}
        }
    
    async def create_search_task(self, task_id: str, name: str, platform: str, 
                               keywords: List[str], priority: int = 5, 
                               immediate: bool = False, storage_type: str = "mongodb",
                               **options) -> bool:
        """创建搜索任务到数据库"""
        try:
            from datetime import datetime
            
            task = Task(
                task_id=task_id,
                name=name,
                platform=platform,
                task_type="search",
                keywords=keywords,
                priority=priority,
                immediate=immediate,
                options=options,
                storage_config={"type": storage_type},
                created_at=datetime.utcnow()
            )
            
            return await self.scheduler.add_immediate_task(task)
            
        except Exception as e:
            logger.error(f"创建搜索任务失败: {e}")
            return False
    
    async def create_monitor_task(self, task_id: str, name: str, platform: str,
                                accounts: List[str], priority: int = 5,
                                immediate: bool = False, storage_type: str = "mongodb",
                                **options) -> bool:
        """创建监控任务到数据库"""
        try:
            from datetime import datetime
            
            task = Task(
                task_id=task_id,
                name=name,
                platform=platform,
                task_type="monitor",
                accounts=accounts,
                priority=priority,
                immediate=immediate,
                options=options,
                storage_config={"type": storage_type},
                created_at=datetime.utcnow()
            )
            
            return await self.scheduler.add_immediate_task(task)
            
        except Exception as e:
            logger.error(f"创建监控任务失败: {e}")
            return False
    
    async def get_task_stats(self) -> Dict[str, Any]:
        """获取任务统计信息"""
        try:
            if hasattr(self.scheduler, 'get_task_stats'):
                return await self.scheduler.get_task_stats()
            else:
                return self.get_framework_stats()
        except Exception as e:
            logger.error(f"获取任务统计失败: {e}")
            return {}