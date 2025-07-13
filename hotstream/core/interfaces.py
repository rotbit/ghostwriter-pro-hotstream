"""
核心接口定义
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, AsyncIterator
from pydantic import BaseModel
from enum import Enum
from datetime import datetime


class TaskStatus(Enum):
    PENDING = 0
    RUNNING = 1
    COMPLETED = 2
    FAILED = 3
    CANCELLED = 4


class DataItem(BaseModel):
    """标准化数据项"""
    id: str
    platform: str
    content: str
    title: Optional[str] = None  # 标题字段，用于去重
    author: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[str] = None
    metadata: Dict[str, Any] = {}
    raw_data: Dict[str, Any] = {}
    task_id: Optional[str] = None  # 关联的任务ID
    
    def get_dedup_key(self) -> str:
        """生成去重键，基于标题和任务ID"""
        import hashlib
        # 使用标题和任务ID组合生成唯一键
        title_text = self.title or self.content[:100]  # 如果没有标题，使用内容前100字符
        key_content = f"{self.task_id or 'unknown'}_{title_text}_{self.platform}"
        return hashlib.md5(key_content.encode('utf-8')).hexdigest()


class SearchOptions(BaseModel):
    """搜索选项"""
    limit: int = 100
    since: Optional[str] = None
    until: Optional[str] = None
    sort_by: str = "relevance"
    filters: Dict[str, Any] = {}


class TaskConfig(BaseModel):
    """任务配置"""
    task_id: str
    name: str
    platform: str
    keywords: List[str]
    schedule: Optional[str] = None
    options: SearchOptions = SearchOptions()
    storage_config: Dict[str, Any] = {}
    retry_count: int = 3
    timeout: int = 300


class LogEntry(BaseModel):
    """日志条目"""
    timestamp: datetime
    level: str  # DEBUG, INFO, WARNING, ERROR
    message: str
    worker_id: Optional[str] = None


class Task(BaseModel):
    """数据库任务模型"""
    task_id: str
    name: str
    platform: str
    task_type: str = "search"  # search, monitor
    keywords: List[str] = []
    accounts: List[str] = []  # 监控账号
    schedule: Optional[str] = None
    status: int = 0  # 0=pending, 1=running, 2=completed, 3=failed, 4=cancelled
    priority: int = 5  # 1=highest, 10=lowest, 5=normal
    immediate: bool = False  # 是否立即执行
    options: Dict[str, Any] = {}
    storage_config: Dict[str, Any] = {}
    retry_count: int = 3
    current_retry: int = 0
    timeout: int = 300
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    error_message: Optional[str] = None
    result_count: int = 0
    progress: float = 0.0  # 进度百分比 0.0-1.0
    worker_id: Optional[str] = None  # 处理该任务的工作进程ID
    logs: List[LogEntry] = []  # 执行过程中的日志


class RateLimitInfo(BaseModel):
    """限流信息"""
    requests_per_minute: int
    requests_per_hour: int
    remaining: int
    reset_time: Optional[str] = None


class PlatformAdapter(ABC):
    """平台适配器接口"""
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """平台名称"""
        pass
    
    @abstractmethod
    async def authenticate(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """认证"""
        pass
    
    @abstractmethod
    async def search(self, keywords: List[str], options: SearchOptions) -> AsyncIterator[DataItem]:
        """搜索数据"""
        pass
    
    @abstractmethod
    async def get_rate_limit(self) -> RateLimitInfo:
        """获取限流信息"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """清理资源"""
        pass


class DataExtractor(ABC):
    """数据提取器接口"""
    
    @abstractmethod
    async def extract(self, raw_data: Dict[str, Any]) -> DataItem:
        """提取数据"""
        pass
    
    @abstractmethod
    def validate(self, data: DataItem) -> bool:
        """验证数据"""
        pass


class StorageAdapter(ABC):
    """存储适配器接口"""
    
    @abstractmethod
    async def save(self, items: List[DataItem], task_id: Optional[str] = None) -> bool:
        """保存数据"""
        pass
    
    @abstractmethod
    async def query(self, filters: Dict[str, Any]) -> List[DataItem]:
        """查询数据"""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """关闭连接"""
        pass


class TaskManager(ABC):
    """任务管理器接口"""
    
    @abstractmethod
    async def get_pending_tasks(self, limit: int = 10) -> List[Task]:
        """获取待处理的任务"""
        pass
    
    @abstractmethod
    async def update_task_status(self, task_id: str, status: int, **kwargs) -> bool:
        """更新任务状态"""
        pass
    
    @abstractmethod
    async def save_task(self, task: Task) -> bool:
        """保存任务"""
        pass
    
    @abstractmethod
    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        pass


class Plugin(ABC):
    """插件基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """插件名称"""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """插件版本"""
        pass
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化插件"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """清理插件"""
        pass