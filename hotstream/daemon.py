"""
后台守护进程
"""

import asyncio
import signal
import sys
from typing import Optional
from loguru import logger

from .core.framework import HotStreamFramework
from .web.api_server import APIServer


class HotStreamDaemon:
    """HotStream 守护进程"""
    
    def __init__(self, config_path: Optional[str] = None, api_host: str = "0.0.0.0", api_port: int = 8000):
        self.config_path = config_path
        self.api_host = api_host
        self.api_port = api_port
        
        self.framework: Optional[HotStreamFramework] = None
        self.api_server: Optional[APIServer] = None
        self._running = False
        self._shutdown_event = asyncio.Event()
    
    async def start(self):
        """启动守护进程"""
        try:
            logger.info("启动 HotStream 守护进程...")
            
            # 初始化框架
            self.framework = HotStreamFramework(self.config_path)
            if not await self.framework.initialize():
                logger.error("框架初始化失败")
                return False
            
            # 创建 API 服务器
            self.api_server = APIServer(
                framework=self.framework,
                host=self.api_host,
                port=self.api_port
            )
            
            # 设置信号处理
            self._setup_signal_handlers()
            
            self._running = True
            
            # 启动框架（包含调度器）
            framework_task = asyncio.create_task(self._run_framework())
            
            # 启动 API 服务器
            api_task = asyncio.create_task(self.api_server.start())
            
            logger.info(f"HotStream 守护进程启动完成")
            logger.info(f"API 服务地址: http://{self.api_host}:{self.api_port}")
            logger.info("按 Ctrl+C 停止服务")
            
            # 等待任一任务完成或收到停止信号
            done, pending = await asyncio.wait(
                [framework_task, api_task, asyncio.create_task(self._shutdown_event.wait())],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # 取消剩余任务
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            return True
            
        except Exception as e:
            logger.error(f"守护进程启动失败: {e}")
            return False
        finally:
            await self._cleanup()
    
    async def _run_framework(self):
        """运行框架主循环"""
        try:
            # 启动调度器
            await self.framework.scheduler.start()
            
            # 注册任务处理器
            for task_id in self.framework.list_tasks():
                self.framework.scheduler.register_task_handler(
                    task_id, 
                    self._handle_scheduled_task
                )
            
            # 保持运行状态
            while self._running and not self._shutdown_event.is_set():
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"框架运行错误: {e}")
        finally:
            if self.framework:
                await self.framework.scheduler.stop()
    
    async def _handle_scheduled_task(self, task_config):
        """处理定时任务"""
        try:
            logger.info(f"执行定时任务: {task_config.task_id}")
            results = await self.framework.execute_task(task_config.task_id)
            logger.info(f"定时任务完成: {task_config.task_id}, 处理了 {len(results)} 条数据")
        except Exception as e:
            logger.error(f"定时任务执行失败 {task_config.task_id}: {e}")
    
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"收到信号 {signum}，准备停止服务...")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def stop(self):
        """停止守护进程"""
        if not self._running:
            return
        
        logger.info("正在停止 HotStream 守护进程...")
        self._running = False
        self._shutdown_event.set()
    
    async def _cleanup(self):
        """清理资源"""
        try:
            if self.framework:
                await self.framework.stop()
            logger.info("HotStream 守护进程已停止")
        except Exception as e:
            logger.error(f"清理资源失败: {e}")


async def run_daemon(config_path: Optional[str] = None, host: str = "0.0.0.0", port: int = 8000):
    """运行守护进程"""
    daemon = HotStreamDaemon(config_path, host, port)
    return await daemon.start()