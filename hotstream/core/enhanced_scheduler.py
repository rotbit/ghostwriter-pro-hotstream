"""
增强型任务调度器 - 集成完整数据处理流程
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from loguru import logger

from .interfaces import Task, TaskStatus, TaskManager, PlatformAdapter, DataExtractor, StorageAdapter, SearchOptions
from .task_manager import MongoTaskManager
from .plugin_manager import PluginManager


class EnhancedTaskScheduler:
    """增强型任务调度器 - 集成MongoDB任务管理和完整数据处理流程"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.plugin_manager: Optional[PluginManager] = None
        self.task_manager: Optional[TaskManager] = None
        
        # 运行状态
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._processing_tasks: Dict[str, asyncio.Task] = {}
        
        # 配置参数
        self.check_interval = config.get('scheduler', {}).get('check_interval', 10)  # 10秒轮询
        self.max_concurrent_tasks = config.get('scheduler', {}).get('max_concurrent_tasks', 5)
        self.task_timeout = config.get('scheduler', {}).get('task_timeout', 3600)  # 1小时
        self.priority_check_interval = 3  # 高优先级任务3秒检查一次
        self.heartbeat_interval = 30  # 心跳间隔30秒
        
        # 数据提取器和存储适配器缓存
        self._extractors: Dict[str, DataExtractor] = {}
        self._storage_adapters: Dict[str, StorageAdapter] = {}
    
    async def initialize(self) -> bool:
        """初始化调度器"""
        try:
            # 初始化插件管理器
            plugin_dirs = self.config.get('plugins', {}).get('plugin_dirs', [])
            self.plugin_manager = PluginManager(plugin_dirs)
            await self.plugin_manager.discover_plugins()
            
            # 初始化任务管理器
            mongo_config = self.config.get('mongodb', {})
            mongo_uri = mongo_config.get('uri', 'mongodb://localhost:27017')
            db_name = mongo_config.get('database', 'hotstream')
            
            self.task_manager = MongoTaskManager(mongo_uri, db_name)
            if not await self.task_manager.initialize():
                logger.error("任务管理器初始化失败")
                return False
            
            # 重置运行中的任务状态
            await self.task_manager.reset_running_tasks()
            
            # 初始化数据提取器
            await self._initialize_extractors()
            
            # 初始化存储适配器
            await self._initialize_storage_adapters()
            
            logger.info("增强型任务调度器初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"调度器初始化失败: {e}")
            return False
    
    async def _initialize_extractors(self):
        """初始化数据提取器"""
        try:
            from ..plugins.extractors.base_extractor import (
                TwitterDataExtractor, MediumDataExtractor, 
                ZhihuDataExtractor, JuejinDataExtractor
            )
            
            self._extractors = {
                'twitter': TwitterDataExtractor(),
                'medium': MediumDataExtractor(),
                'zhihu': ZhihuDataExtractor(),
                'juejin': JuejinDataExtractor()
            }
            
            logger.info(f"已初始化 {len(self._extractors)} 个数据提取器")
            
        except Exception as e:
            logger.error(f"初始化数据提取器失败: {e}")
    
    async def _initialize_storage_adapters(self):
        """初始化存储适配器"""
        try:
            from ..plugins.storages.mongo_storage import MongoStorageAdapter
            
            # MongoDB存储
            mongo_config = self.config.get('mongodb', {})
            if mongo_config.get('enabled', True):
                mongo_adapter = MongoStorageAdapter(
                    mongo_uri=mongo_config.get('uri', 'mongodb://localhost:27017'),
                    db_name=mongo_config.get('database', 'hotstream')
                )
                if await mongo_adapter.initialize():
                    self._storage_adapters['mongodb'] = mongo_adapter
            
        except Exception as e:
            logger.error(f"初始化存储适配器失败: {e}")
    
    async def start(self) -> None:
        """启动调度器"""
        if self._running:
            return
        
        self._running = True
        
        # 启动主调度循环（10秒检查一次）
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        
        # 启动优先级任务检查循环（3秒检查一次）
        asyncio.create_task(self._priority_scheduler_loop())
        
        # 启动心跳和清理循环（30秒检查一次）
        asyncio.create_task(self._maintenance_loop())
        
        logger.info("增强型任务调度器启动")
    
    async def stop(self) -> None:
        """停止调度器"""
        if not self._running:
            return
        
        logger.info("正在停止调度器...")
        self._running = False
        
        # 停止主循环
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        # 等待所有处理中的任务完成
        if self._processing_tasks:
            logger.info(f"等待 {len(self._processing_tasks)} 个任务完成...")
            await asyncio.wait(self._processing_tasks.values(), timeout=30)
        
        # 清理资源
        await self._cleanup()
        
        logger.info("调度器停止完成")
    
    async def _scheduler_loop(self) -> None:
        """调度器主循环 - 10秒检查一次普通任务"""
        while self._running:
            try:
                # 获取待处理的任务（普通优先级）
                available_slots = self.max_concurrent_tasks - len(self._processing_tasks)
                if available_slots > 0:
                    pending_tasks = await self.task_manager.get_pending_tasks(
                        available_slots, priority_only=False
                    )
                    
                    await self._process_pending_tasks(pending_tasks)
                
                # 清理已完成的任务
                self._cleanup_completed_tasks()
                
                # 等待下次检查
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"调度器主循环错误: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _priority_scheduler_loop(self) -> None:
        """高优先级任务调度循环 - 3秒检查一次"""
        while self._running:
            try:
                # 检查高优先级和立即执行的任务
                available_slots = self.max_concurrent_tasks - len(self._processing_tasks)
                if available_slots > 0:
                    priority_tasks = await self.task_manager.get_pending_tasks(
                        available_slots, priority_only=True
                    )
                    
                    if priority_tasks:
                        logger.info(f"发现 {len(priority_tasks)} 个高优先级任务")
                        await self._process_pending_tasks(priority_tasks)
                
                await asyncio.sleep(self.priority_check_interval)
                
            except Exception as e:
                logger.error(f"优先级调度循环错误: {e}")
                await asyncio.sleep(self.priority_check_interval)
    
    async def _maintenance_loop(self) -> None:
        """维护循环 - 心跳更新和僵尸任务清理"""
        while self._running:
            try:
                # 清理僵尸任务
                cleaned_count = await self.task_manager.cleanup_stale_tasks(
                    timeout_minutes=self.task_timeout // 60
                )
                
                if cleaned_count > 0:
                    logger.warning(f"清理了 {cleaned_count} 个僵尸任务")
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"维护循环错误: {e}")
                await asyncio.sleep(self.heartbeat_interval)
    
    async def _process_pending_tasks(self, tasks: List[Task]) -> None:
        """处理待处理的任务列表"""
        for task in tasks:
            if task.task_id not in self._processing_tasks:
                # 创建任务处理协程
                task_coroutine = asyncio.create_task(
                    self._process_task(task)
                )
                self._processing_tasks[task.task_id] = task_coroutine
                
                priority_desc = "高优先级" if task.priority <= 3 or task.immediate else "普通"
                logger.info(f"开始处理{priority_desc}任务: {task.task_id}")
    
    def _cleanup_completed_tasks(self) -> None:
        """清理已完成的任务"""
        completed_tasks = []
        for task_id, task_coroutine in self._processing_tasks.items():
            if task_coroutine.done():
                completed_tasks.append(task_id)
        
        for task_id in completed_tasks:
            del self._processing_tasks[task_id]
    
    async def _process_task(self, task: Task) -> None:
        """处理单个任务 - 完整的数据处理流程"""
        start_time = datetime.utcnow()
        worker_id = f"worker_{id(asyncio.current_task())}"
        
        # 创建任务专用日志器
        from .task_logger import create_task_logger
        async with create_task_logger(task.task_id, self.task_manager, worker_id) as task_logger:
            try:
                await task_logger.info(f"开始处理任务: {task.name}")
                
                # 1. 更新任务状态为运行中，设置工作进程ID
                await self.task_manager.update_task_status(
                    task.task_id, 
                    TaskStatus.RUNNING.value,
                    started_at=start_time,
                    worker_id=worker_id
                )
                
                logger.info(f"开始处理任务 {task.task_id}: {task.name}")
                
                # 2. 获取并实例化平台适配器
                await task_logger.info(f"获取平台适配器: {task.platform}")
                platform_adapter_class = self.plugin_manager.get_platform_adapter(task.platform)
                if not platform_adapter_class:
                    raise Exception(f"未找到平台适配器: {task.platform}")
                
                platform_adapter = platform_adapter_class()
                
                # 3. 初始化适配器
                await task_logger.info("开始平台认证...")
                credentials = self.config.get('platforms', {}).get(task.platform, {})
                if not await platform_adapter.authenticate(credentials):
                    raise Exception(f"平台认证失败: {task.platform}")
                
                await task_logger.info("平台认证成功")
                
                # 4. 执行数据采集
                collected_items = []
                
                # 更新进度：开始数据采集
                await self.task_manager.update_heartbeat(task.task_id, 0.2)
                
                if task.task_type == "search" and task.keywords:
                    # 搜索任务
                    search_options = SearchOptions(**task.options)
                    target_count = search_options.limit
                    
                    await task_logger.info(f"开始搜索数据，关键词: {task.keywords}, 目标数量: {target_count}")
                    
                    async for item in platform_adapter.search(task.keywords, search_options):
                        # 确保设置task_id
                        item.task_id = task.task_id
                        collected_items.append(item)
                        
                        # 更新进度和心跳
                        progress = 0.2 + (len(collected_items) / target_count) * 0.4  # 20%-60%
                        await self.task_manager.update_heartbeat(task.task_id, min(progress, 0.6))
                        
                        # 每采集20条记录一次进展
                        if len(collected_items) % 20 == 0:
                            await task_logger.info(f"已采集 {len(collected_items)}/{target_count} 条数据")
                        
                        # 防止单个任务采集过多数据
                        if len(collected_items) >= target_count:
                            break
                
                elif task.task_type == "monitor" and task.accounts:
                    # 监控任务
                    target_count = task.options.get('limit', 50)
                    
                    await task_logger.info(f"开始监控账号: {task.accounts}, 目标数量: {target_count}")
                    
                    if hasattr(platform_adapter, 'monitor_accounts'):
                        async for item in platform_adapter.monitor_accounts(task.accounts, target_count):
                            # 确保设置task_id
                            item.task_id = task.task_id
                            collected_items.append(item)
                            
                            # 更新进度和心跳
                            progress = 0.2 + (len(collected_items) / target_count) * 0.4  # 20%-60%
                            await self.task_manager.update_heartbeat(task.task_id, min(progress, 0.6))
                            
                            # 每采集10条记录一次进展
                            if len(collected_items) % 10 == 0:
                                await task_logger.info(f"已采集 {len(collected_items)}/{target_count} 条数据")
                            
                            if len(collected_items) >= target_count:
                                break
                    else:
                        raise Exception(f"平台 {task.platform} 不支持账号监控")
                
                else:
                    raise Exception(f"不支持的任务类型: {task.task_type}")
                
                await task_logger.info(f"数据采集完成，共采集 {len(collected_items)} 条原始数据")
                logger.info(f"任务 {task.task_id} 采集到 {len(collected_items)} 条原始数据")
            
                # 5. 数据提取和转换
                await self.task_manager.update_heartbeat(task.task_id, 0.6)
                await task_logger.info("开始数据提取和转换...")
                
                extractor = self._extractors.get(task.platform)
                if not extractor:
                    await task_logger.warning(f"未找到 {task.platform} 的数据提取器，使用原始数据")
                    logger.warning(f"未找到 {task.platform} 的数据提取器，使用原始数据")
                    processed_items = collected_items
                else:
                    processed_items = []
                    total_items = len(collected_items)
                    
                    for i, item in enumerate(collected_items):
                        try:
                            # 将DataItem转换为字典，然后用提取器处理
                            raw_data = item.model_dump()
                            processed_item = await extractor.extract(raw_data)
                            
                            # 验证数据
                            if extractor.validate(processed_item):
                                processed_items.append(processed_item)
                            else:
                                await task_logger.warning(f"数据验证失败，跳过: {processed_item.id}")
                                logger.warning(f"数据验证失败，跳过: {processed_item.id}")
                            
                            # 更新进度：60%-80%
                            progress = 0.6 + (i / total_items) * 0.2
                            if i % 10 == 0:  # 每10条更新一次心跳
                                await self.task_manager.update_heartbeat(task.task_id, progress)
                                await task_logger.info(f"数据处理进度: {i+1}/{total_items}")
                        
                        except Exception as extract_error:
                            await task_logger.error(f"数据提取失败: {extract_error}")
                            logger.warning(f"数据提取失败: {extract_error}")
                            continue
                    
                    await task_logger.info(f"数据处理完成，得到 {len(processed_items)} 条有效数据")
                    logger.info(f"任务 {task.task_id} 处理后得到 {len(processed_items)} 条有效数据")
            
                # 6. 数据存储
                await self.task_manager.update_heartbeat(task.task_id, 0.8)
                await task_logger.info("开始数据存储...")
                
                if processed_items:
                    storage_success = False
                    
                    # 尝试存储到配置的存储适配器
                    storage_type = task.storage_config.get('type', 'mongodb')
                    storage_adapter = self._storage_adapters.get(storage_type)
                    
                    await task_logger.info(f"尝试保存到 {storage_type} 存储")
                    
                    if storage_adapter:
                        if await storage_adapter.save(processed_items, task.task_id):
                            storage_success = True
                            await task_logger.info(f"数据已保存到 {storage_type}，关联任务ID: {task.task_id}")
                            logger.info(f"数据已保存到 {storage_type}，关联任务ID: {task.task_id}")
                        else:
                            await task_logger.error(f"保存到 {storage_type} 失败")
                            logger.error(f"保存到 {storage_type} 失败")
                    
                    # 如果主存储失败，尝试备用存储
                    if not storage_success and 'json' in self._storage_adapters:
                        await task_logger.info("尝试使用JSON备用存储")
                        if await self._storage_adapters['json'].save(processed_items, task.task_id):
                            storage_success = True
                            await task_logger.info("数据已保存到JSON备用存储")
                            logger.info("数据已保存到JSON备用存储")
                    
                    if not storage_success:
                        raise Exception("所有存储方式都失败")
                    
                    # 更新进度：90%
                    await self.task_manager.update_heartbeat(task.task_id, 0.9)
                
                # 7. 更新任务状态为完成
                await task_logger.info("任务即将完成，更新状态...")
                await self.task_manager.update_task_status(
                    task.task_id,
                    TaskStatus.COMPLETED.value,
                    completed_at=datetime.utcnow(),
                    result_count=len(processed_items)
                )
                
                # 最终进度：100%
                await self.task_manager.update_heartbeat(task.task_id, 1.0)
                
                # 8. 清理适配器资源
                await platform_adapter.cleanup()
                
                duration = datetime.utcnow() - start_time
                await task_logger.info(f"任务处理完成，耗时 {duration.total_seconds():.1f}秒，结果数量: {len(processed_items)}")
                logger.info(f"任务 {task.task_id} 处理完成，耗时 {duration.total_seconds():.1f}秒")
            
            except Exception as e:
                error_msg = str(e)
                await task_logger.error(f"任务处理失败: {error_msg}")
                logger.error(f"任务 {task.task_id} 处理失败: {error_msg}")
                
                # 检查是否还有重试次数
                next_retry = task.current_retry + 1
                if next_retry <= task.retry_count:
                    # 计算重试延迟（指数退避）
                    retry_delay = min(60 * (2 ** (next_retry - 1)), 300)  # 最大5分钟
                    
                    await task_logger.info(f"任务失败，将在 {retry_delay} 秒后进行第 {next_retry} 次重试")
                    logger.info(f"任务 {task.task_id} 失败，将在 {retry_delay} 秒后进行第 {next_retry} 次重试")
                    
                    # 更新任务为重试状态
                    await self.task_manager.update_task_status(
                        task.task_id,
                        TaskStatus.PENDING.value,
                        error_message=f"重试 {next_retry}/{task.retry_count}: {error_msg}",
                        current_retry=next_retry
                    )
                    
                    # 异步等待后重新调度
                    asyncio.create_task(self._schedule_retry(task.task_id, retry_delay))
                else:
                    # 所有重试次数用完，标记为最终失败
                    await task_logger.error(f"所有重试失败，任务最终失败")
                    await self.task_manager.update_task_status(
                        task.task_id,
                        TaskStatus.FAILED.value,
                        completed_at=datetime.utcnow(),
                        error_message=f"所有重试失败: {error_msg}",
                        current_retry=next_retry
                    )
                    logger.error(f"任务 {task.task_id} 重试 {task.retry_count} 次后最终失败")
    
    async def _schedule_retry(self, task_id: str, delay: float) -> None:
        """调度重试任务"""
        try:
            await asyncio.sleep(delay)
            # 延迟后不需要做额外操作，任务已经被设置为PENDING状态
            # 调度器会在下次循环中自动获取并处理这个任务
            logger.info(f"任务 {task_id} 重试延迟结束，等待调度器处理")
        except Exception as e:
            logger.error(f"调度重试任务失败 {task_id}: {e}")
    
    async def add_immediate_task(self, task: Task) -> bool:
        """添加立即执行的任务"""
        try:
            task.status = TaskStatus.PENDING.value
            task.created_at = datetime.utcnow()
            
            if await self.task_manager.save_task(task):
                logger.info(f"添加立即任务: {task.task_id}")
                return True
            else:
                logger.error(f"保存任务失败: {task.task_id}")
                return False
                
        except Exception as e:
            logger.error(f"添加立即任务失败: {e}")
            return False
    
    async def get_task_stats(self) -> Dict[str, Any]:
        """获取任务统计信息"""
        try:
            stats = await self.task_manager.get_task_stats()
            stats.update({
                "scheduler_running": self._running,
                "processing_tasks": len(self._processing_tasks),
                "max_concurrent_tasks": self.max_concurrent_tasks
            })
            return stats
            
        except Exception as e:
            logger.error(f"获取任务统计失败: {e}")
            return {}
    
    async def _cleanup(self):
        """清理资源"""
        try:
            # 关闭存储适配器
            for adapter in self._storage_adapters.values():
                await adapter.close()
            
            # 关闭任务管理器
            if self.task_manager:
                await self.task_manager.cleanup()
            
            # 关闭插件管理器
            if self.plugin_manager:
                await self.plugin_manager.cleanup()
            
            logger.info("调度器资源清理完成")
            
        except Exception as e:
            logger.error(f"清理资源失败: {e}")