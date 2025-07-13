"""
任务级日志处理器 - 将日志存储到MongoDB对应任务的logs字段
"""

import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from loguru import logger as base_logger
from .task_manager import MongoTaskManager


class TaskLogger:
    """任务级日志处理器"""
    
    def __init__(self, task_id: str, task_manager: MongoTaskManager, worker_id: Optional[str] = None):
        self.task_id = task_id
        self.task_manager = task_manager
        self.worker_id = worker_id or f"worker_{id(asyncio.current_task())}"
        
        # 日志队列，用于批量写入优化
        self._log_queue = []
        self._batch_size = 10
        self._flush_interval = 5.0  # 5秒强制刷新
        self._last_flush = datetime.utcnow()
    
    async def _should_flush(self) -> bool:
        """判断是否应该刷新日志到数据库"""
        now = datetime.utcnow()
        return (
            len(self._log_queue) >= self._batch_size or
            (now - self._last_flush).total_seconds() >= self._flush_interval
        )
    
    async def _flush_logs(self) -> None:
        """刷新日志队列到数据库"""
        if not self._log_queue:
            return
        
        try:
            # 批量写入日志
            for log_entry in self._log_queue:
                await self.task_manager.append_log(
                    self.task_id,
                    log_entry["level"],
                    log_entry["message"],
                    log_entry["worker_id"]
                )
            
            self._log_queue.clear()
            self._last_flush = datetime.utcnow()
            
        except Exception as e:
            base_logger.error(f"刷新任务日志失败: {e}")
    
    async def log(self, level: str, message: str) -> None:
        """记录日志"""
        try:
            # 添加到队列
            self._log_queue.append({
                "level": level,
                "message": message,
                "worker_id": self.worker_id,
                "timestamp": datetime.utcnow()
            })
            
            # 检查是否需要刷新
            if await self._should_flush():
                await self._flush_logs()
            
            # 同时输出到控制台
            log_method = getattr(base_logger, level.lower(), base_logger.info)
            log_method(f"[{self.task_id}] {message}")
            
        except Exception as e:
            base_logger.error(f"记录任务日志失败: {e}")
    
    async def debug(self, message: str) -> None:
        """记录DEBUG级别日志"""
        await self.log("DEBUG", message)
    
    async def info(self, message: str) -> None:
        """记录INFO级别日志"""
        await self.log("INFO", message)
    
    async def warning(self, message: str) -> None:
        """记录WARNING级别日志"""
        await self.log("WARNING", message)
    
    async def error(self, message: str) -> None:
        """记录ERROR级别日志"""
        await self.log("ERROR", message)
    
    async def flush(self) -> None:
        """强制刷新所有待写入的日志"""
        await self._flush_logs()
    
    async def close(self) -> None:
        """关闭日志处理器，刷新所有待写入的日志"""
        await self.flush()


class TaskLoggerContext:
    """任务日志上下文管理器"""
    
    def __init__(self, task_id: str, task_manager: MongoTaskManager, worker_id: Optional[str] = None):
        self.task_logger = TaskLogger(task_id, task_manager, worker_id)
    
    async def __aenter__(self):
        return self.task_logger
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.task_logger.close()


def create_task_logger(task_id: str, task_manager: MongoTaskManager, worker_id: Optional[str] = None) -> TaskLoggerContext:
    """创建任务日志处理器上下文"""
    return TaskLoggerContext(task_id, task_manager, worker_id)