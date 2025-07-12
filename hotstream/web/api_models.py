"""
API 数据模型
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from enum import Enum

from ..core.interfaces import TaskStatus


class APIResponse(BaseModel):
    """API 响应基类"""
    success: bool
    message: str
    data: Any = None


class SearchRequest(BaseModel):
    """搜索请求"""
    platform: str
    keywords: List[str]
    limit: int = 100
    since: Optional[str] = None
    until: Optional[str] = None
    sort_by: str = "relevance"
    filters: Dict[str, Any] = {}


class SearchResponse(APIResponse):
    """搜索响应"""
    data: Optional[List[Dict[str, Any]]] = None


class TaskCreateRequest(BaseModel):
    """创建任务请求"""
    task_id: str
    name: str
    platform: str
    keywords: List[str]
    schedule: Optional[str] = None
    limit: int = 100
    storage_config: Dict[str, Any] = {}
    retry_count: int = 3
    timeout: int = 300


class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str
    name: str
    platform: str
    keywords: List[str]
    schedule: Optional[str] = None
    status: TaskStatus
    created_at: Optional[str] = None
    last_run: Optional[str] = None


class TaskListResponse(APIResponse):
    """任务列表响应"""
    data: Optional[List[TaskResponse]] = None


class TaskExecuteRequest(BaseModel):
    """执行任务请求"""
    task_id: str


class FrameworkStatusResponse(APIResponse):
    """框架状态响应"""
    data: Optional[Dict[str, Any]] = None


class PlatformListResponse(APIResponse):
    """平台列表响应"""
    data: Optional[List[str]] = None