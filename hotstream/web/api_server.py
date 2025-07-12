"""
API 服务器
"""

import asyncio
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import uvicorn

from ..core.framework import HotStreamFramework
from ..core.interfaces import TaskConfig, SearchOptions
from .api_models import (
    APIResponse, SearchRequest, SearchResponse, TaskCreateRequest,
    TaskResponse, TaskListResponse, TaskExecuteRequest,
    FrameworkStatusResponse, PlatformListResponse
)


class APIServer:
    """API 服务器"""
    
    def __init__(self, framework: HotStreamFramework, host: str = "0.0.0.0", port: int = 8000):
        self.framework = framework
        self.host = host
        self.port = port
        self.app = FastAPI(
            title="HotStream API",
            description="多平台数据抓取框架 API",
            version="0.1.0"
        )
        
        # 添加 CORS 中间件
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        self._setup_routes()
    
    def _setup_routes(self):
        """设置路由"""
        
        @self.app.get("/", response_model=APIResponse)
        async def root():
            """根路径"""
            return APIResponse(
                success=True,
                message="HotStream API 服务运行中",
                data={"version": "0.1.0"}
            )
        
        @self.app.get("/health", response_model=APIResponse)
        async def health_check():
            """健康检查"""
            stats = self.framework.get_framework_stats()
            return APIResponse(
                success=True,
                message="服务健康",
                data=stats
            )
        
        @self.app.post("/search", response_model=SearchResponse)
        async def immediate_search(request: SearchRequest):
            """立即搜索"""
            try:
                results = await self.framework.execute_immediate_search(
                    platform=request.platform,
                    keywords=request.keywords,
                    limit=request.limit,
                    since=request.since,
                    until=request.until,
                    sort_by=request.sort_by,
                    filters=request.filters
                )
                
                # 转换为字典格式
                data = [item.dict() for item in results]
                
                return SearchResponse(
                    success=True,
                    message=f"搜索完成，获得 {len(results)} 条数据",
                    data=data
                )
                
            except Exception as e:
                logger.error(f"搜索失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/platforms", response_model=PlatformListResponse)
        async def list_platforms():
            """获取支持的平台列表"""
            try:
                platforms = self.framework.list_supported_platforms()
                return PlatformListResponse(
                    success=True,
                    message="获取平台列表成功",
                    data=platforms
                )
            except Exception as e:
                logger.error(f"获取平台列表失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/tasks", response_model=APIResponse)
        async def create_task(request: TaskCreateRequest):
            """创建任务"""
            try:
                task_config = TaskConfig(
                    task_id=request.task_id,
                    name=request.name,
                    platform=request.platform,
                    keywords=request.keywords,
                    schedule=request.schedule,
                    options=SearchOptions(limit=request.limit),
                    storage_config=request.storage_config,
                    retry_count=request.retry_count,
                    timeout=request.timeout
                )
                
                success = await self.framework.add_task(task_config)
                
                if success:
                    return APIResponse(
                        success=True,
                        message=f"任务创建成功: {request.task_id}",
                        data={"task_id": request.task_id}
                    )
                else:
                    raise HTTPException(status_code=400, detail="任务创建失败")
                    
            except Exception as e:
                logger.error(f"创建任务失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/tasks", response_model=TaskListResponse)
        async def list_tasks():
            """获取任务列表"""
            try:
                task_ids = self.framework.list_tasks()
                tasks = []
                
                for task_id in task_ids:
                    config = self.framework.get_task_config(task_id)
                    status = self.framework.get_task_status(task_id)
                    
                    if config:
                        tasks.append(TaskResponse(
                            task_id=config.task_id,
                            name=config.name,
                            platform=config.platform,
                            keywords=config.keywords,
                            schedule=config.schedule,
                            status=status or "pending"
                        ))
                
                return TaskListResponse(
                    success=True,
                    message="获取任务列表成功",
                    data=tasks
                )
                
            except Exception as e:
                logger.error(f"获取任务列表失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/tasks/{task_id}", response_model=APIResponse)
        async def get_task(task_id: str):
            """获取任务详情"""
            try:
                config = self.framework.get_task_config(task_id)
                if not config:
                    raise HTTPException(status_code=404, detail="任务不存在")
                
                status = self.framework.get_task_status(task_id)
                
                task_info = TaskResponse(
                    task_id=config.task_id,
                    name=config.name,
                    platform=config.platform,
                    keywords=config.keywords,
                    schedule=config.schedule,
                    status=status or "pending"
                )
                
                return APIResponse(
                    success=True,
                    message="获取任务详情成功",
                    data=task_info.dict()
                )
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"获取任务详情失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/tasks/{task_id}/execute", response_model=APIResponse)
        async def execute_task(task_id: str, background_tasks: BackgroundTasks):
            """立即执行任务"""
            try:
                config = self.framework.get_task_config(task_id)
                if not config:
                    raise HTTPException(status_code=404, detail="任务不存在")
                
                # 在后台执行任务
                background_tasks.add_task(self._execute_task_background, task_id)
                
                return APIResponse(
                    success=True,
                    message=f"任务 {task_id} 已开始执行",
                    data={"task_id": task_id}
                )
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"执行任务失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/tasks/{task_id}", response_model=APIResponse)
        async def delete_task(task_id: str):
            """删除任务"""
            try:
                success = await self.framework.remove_task(task_id)
                
                if success:
                    return APIResponse(
                        success=True,
                        message=f"任务删除成功: {task_id}",
                        data={"task_id": task_id}
                    )
                else:
                    raise HTTPException(status_code=404, detail="任务不存在")
                    
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"删除任务失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/status", response_model=FrameworkStatusResponse)
        async def get_framework_status():
            """获取框架状态"""
            try:
                stats = self.framework.get_framework_stats()
                return FrameworkStatusResponse(
                    success=True,
                    message="获取框架状态成功",
                    data=stats
                )
            except Exception as e:
                logger.error(f"获取框架状态失败: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    async def _execute_task_background(self, task_id: str):
        """后台执行任务"""
        try:
            results = await self.framework.execute_task(task_id)
            logger.info(f"后台任务执行完成: {task_id}, 获得 {len(results)} 条数据")
        except Exception as e:
            logger.error(f"后台任务执行失败 {task_id}: {e}")
    
    async def start(self):
        """启动 API 服务器"""
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        logger.info(f"API 服务器启动: http://{self.host}:{self.port}")
        await server.serve()
    
    def run(self):
        """运行 API 服务器（同步版本）"""
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )