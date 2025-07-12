"""
任务调度系统
"""

import asyncio
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from crontab import CronTab
from loguru import logger
from enum import Enum

from .interfaces import TaskConfig, TaskStatus


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self):
        self._scheduled_tasks: Dict[str, Dict[str, Any]] = {}
        self._task_handlers: Dict[str, Callable] = {}
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._task_status: Dict[str, TaskStatus] = {}
        
    async def initialize(self) -> None:
        """初始化调度器"""
        logger.info("任务调度器初始化")
    
    async def start(self) -> None:
        """启动调度器"""
        if self._running:
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("任务调度器启动")
    
    async def stop(self) -> None:
        """停止调度器"""
        if not self._running:
            return
        
        self._running = False
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        logger.info("任务调度器停止")
    
    async def _scheduler_loop(self) -> None:
        """调度器主循环"""
        while self._running:
            try:
                now = datetime.now()
                
                # 检查所有定时任务
                for task_id, task_info in self._scheduled_tasks.items():
                    if await self._should_run_task(task_id, task_info, now):
                        asyncio.create_task(self._execute_task(task_id, task_info))
                
                # 每10秒检查一次
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"调度器循环错误: {e}")
                await asyncio.sleep(10)
    
    async def _should_run_task(self, task_id: str, task_info: Dict[str, Any], now: datetime) -> bool:
        """检查任务是否应该运行"""
        # 检查任务状态
        if self._task_status.get(task_id) == TaskStatus.RUNNING:
            return False
        
        schedule = task_info.get("schedule")
        if not schedule:
            return False
        
        last_run = task_info.get("last_run")
        
        try:
            # 解析 cron 表达式
            cron = CronTab(schedule)
            
            # 如果是第一次运行
            if not last_run:
                return True
            
            # 检查自上次运行以来是否到了执行时间
            next_run = cron.next(last_run)
            return now >= last_run + timedelta(seconds=next_run)
            
        except Exception as e:
            logger.error(f"解析任务计划失败 {task_id}: {e}")
            return False
    
    async def _execute_task(self, task_id: str, task_info: Dict[str, Any]) -> None:
        """执行任务"""
        try:
            self._task_status[task_id] = TaskStatus.RUNNING
            task_info["last_run"] = datetime.now()
            
            logger.info(f"开始执行调度任务: {task_id}")
            
            # 获取任务处理器
            handler = self._task_handlers.get(task_id)
            if not handler:
                logger.error(f"任务处理器不存在: {task_id}")
                self._task_status[task_id] = TaskStatus.FAILED
                return
            
            # 执行任务
            await handler(task_info["config"])
            
            self._task_status[task_id] = TaskStatus.COMPLETED
            logger.info(f"调度任务执行完成: {task_id}")
            
        except Exception as e:
            logger.error(f"调度任务执行失败 {task_id}: {e}")
            self._task_status[task_id] = TaskStatus.FAILED
    
    async def add_scheduled_task(self, task_config: TaskConfig) -> bool:
        """添加定时任务"""
        try:
            if not task_config.schedule:
                logger.warning(f"任务没有设置计划: {task_config.task_id}")
                return False
            
            # 验证 cron 表达式
            try:
                CronTab(task_config.schedule)
            except Exception as e:
                logger.error(f"无效的 cron 表达式 {task_config.schedule}: {e}")
                return False
            
            self._scheduled_tasks[task_config.task_id] = {
                "config": task_config,
                "schedule": task_config.schedule,
                "last_run": None,
                "created_at": datetime.now()
            }
            
            self._task_status[task_config.task_id] = TaskStatus.PENDING
            
            logger.info(f"添加定时任务: {task_config.task_id}, 计划: {task_config.schedule}")
            return True
            
        except Exception as e:
            logger.error(f"添加定时任务失败: {e}")
            return False
    
    async def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        try:
            if task_id in self._scheduled_tasks:
                del self._scheduled_tasks[task_id]
            
            if task_id in self._task_handlers:
                del self._task_handlers[task_id]
            
            if task_id in self._task_status:
                del self._task_status[task_id]
            
            logger.info(f"移除任务: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"移除任务失败: {e}")
            return False
    
    def register_task_handler(self, task_id: str, handler: Callable) -> None:
        """注册任务处理器"""
        self._task_handlers[task_id] = handler
        logger.debug(f"注册任务处理器: {task_id}")
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        return self._task_status.get(task_id)
    
    def list_scheduled_tasks(self) -> List[str]:
        """列出所有定时任务"""
        return list(self._scheduled_tasks.keys())
    
    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        task_info = self._scheduled_tasks.get(task_id)
        if task_info:
            return {
                "task_id": task_id,
                "schedule": task_info["schedule"],
                "last_run": task_info["last_run"],
                "created_at": task_info["created_at"],
                "status": self._task_status.get(task_id, TaskStatus.PENDING)
            }
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取调度器统计信息"""
        status_counts = {}
        for status in TaskStatus:
            status_counts[status.value] = sum(
                1 for s in self._task_status.values() if s == status
            )
        
        return {
            "running": self._running,
            "total_scheduled_tasks": len(self._scheduled_tasks),
            "task_status_counts": status_counts
        }