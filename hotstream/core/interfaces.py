"""
核心接口定义
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, AsyncIterator
from pydantic import BaseModel
from enum import Enum


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DataItem(BaseModel):
    """标准化数据项"""
    id: str
    platform: str
    content: str
    author: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[str] = None
    metadata: Dict[str, Any] = {}
    raw_data: Dict[str, Any] = {}


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
    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
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
    async def save(self, items: List[DataItem]) -> bool:
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