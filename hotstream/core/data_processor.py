"""
数据处理器
"""

import asyncio
from typing import Dict, List, Any, Optional, AsyncIterator
from loguru import logger

from .interfaces import (
    TaskConfig, DataItem, PlatformAdapter, 
    DataExtractor, StorageAdapter
)
from .plugin_manager import PluginManager


class DataProcessor:
    """数据处理器"""
    
    def __init__(self):
        self.plugin_manager: Optional[PluginManager] = None
        self._platform_instances: Dict[str, PlatformAdapter] = {}
        self._storage_instances: Dict[str, StorageAdapter] = {}
    
    async def initialize(self, plugin_manager: PluginManager) -> None:
        """初始化数据处理器"""
        self.plugin_manager = plugin_manager
        logger.info("数据处理器初始化完成")
    
    async def process_task(self, task_config: TaskConfig) -> List[DataItem]:
        """处理数据抓取任务"""
        try:
            logger.info(f"开始处理任务: {task_config.task_id}")
            
            # 获取平台适配器
            adapter = await self._get_platform_adapter(task_config.platform)
            if not adapter:
                raise ValueError(f"无法获取平台适配器: {task_config.platform}")
            
            # 抓取数据
            raw_items = []
            async for item in adapter.search(task_config.keywords, task_config.options):
                raw_items.append(item)
                
                # 限制单次抓取数量
                if len(raw_items) >= task_config.options.limit:
                    break
            
            logger.info(f"抓取到 {len(raw_items)} 条原始数据")
            
            # 数据清洗和验证
            processed_items = await self._process_items(raw_items, task_config)
            
            # 保存数据
            if task_config.storage_config and processed_items:
                await self._save_items(processed_items, task_config.storage_config)
            
            logger.info(f"任务处理完成: {task_config.task_id}, 处理 {len(processed_items)} 条数据")
            return processed_items
            
        except Exception as e:
            logger.error(f"任务处理失败 {task_config.task_id}: {e}")
            raise
    
    async def _get_platform_adapter(self, platform_name: str) -> Optional[PlatformAdapter]:
        """获取平台适配器实例"""
        # 检查是否已有实例且状态正常
        if platform_name in self._platform_instances:
            adapter = self._platform_instances[platform_name]
            # 对于 Twitter 适配器，检查页面是否还活着
            if hasattr(adapter, 'page') and adapter.page and not adapter.page.is_closed():
                return adapter
            elif hasattr(adapter, 'authenticated') and adapter.authenticated:
                return adapter
            else:
                # 实例已损坏，重新创建
                logger.warning(f"平台适配器 {platform_name} 实例已损坏，重新创建")
                try:
                    await adapter.cleanup()
                except:
                    pass
                del self._platform_instances[platform_name]
        
        # 创建新实例
        adapter_class = self.plugin_manager.get_platform_adapter(platform_name)
        if not adapter_class:
            logger.error(f"未找到平台适配器: {platform_name}")
            return None
        
        try:
            adapter = adapter_class()
            self._platform_instances[platform_name] = adapter
            logger.info(f"创建平台适配器实例: {platform_name}")
            return adapter
            
        except Exception as e:
            logger.error(f"创建平台适配器失败 {platform_name}: {e}")
            return None
    
    async def _process_items(self, items: List[DataItem], task_config: TaskConfig) -> List[DataItem]:
        """处理数据项"""
        processed_items = []
        
        for item in items:
            try:
                # 数据验证
                if await self._validate_item(item):
                    # 数据清洗
                    cleaned_item = await self._clean_item(item, task_config)
                    if cleaned_item:
                        processed_items.append(cleaned_item)
                else:
                    logger.debug(f"数据验证失败，跳过: {item.id}")
                    
            except Exception as e:
                logger.error(f"处理数据项失败 {item.id}: {e}")
                continue
        
        # 去重
        processed_items = await self._deduplicate_items(processed_items)
        
        return processed_items
    
    async def _validate_item(self, item: DataItem) -> bool:
        """验证数据项"""
        # 基本验证
        if not item.id or not item.platform or not item.content:
            return False
        
        # 内容长度验证
        if len(item.content.strip()) < 10:
            return False
        
        return True
    
    async def _clean_item(self, item: DataItem, task_config: TaskConfig) -> Optional[DataItem]:
        """清洗数据项"""
        try:
            # 清理内容
            cleaned_content = self._clean_text(item.content)
            if not cleaned_content:
                return None
            
            # 创建清洗后的数据项
            cleaned_item = DataItem(
                id=item.id,
                platform=item.platform,
                content=cleaned_content,
                author=item.author,
                url=item.url,
                created_at=item.created_at,
                metadata={
                    **item.metadata,
                    "task_id": task_config.task_id,
                    "keywords": task_config.keywords,
                    "processed_at": str(asyncio.get_event_loop().time())
                },
                raw_data=item.raw_data
            )
            
            return cleaned_item
            
        except Exception as e:
            logger.error(f"清洗数据失败: {e}")
            return None
    
    def _clean_text(self, text: str) -> str:
        """清理文本内容"""
        if not text:
            return ""
        
        # 移除多余的空白字符
        cleaned = " ".join(text.split())
        
        # 移除特殊字符（保留基本标点）
        # 这里可以根据需要添加更多清理规则
        
        return cleaned.strip()
    
    async def _deduplicate_items(self, items: List[DataItem]) -> List[DataItem]:
        """去重数据项"""
        seen_ids = set()
        unique_items = []
        
        for item in items:
            if item.id not in seen_ids:
                seen_ids.add(item.id)
                unique_items.append(item)
        
        logger.info(f"去重完成: {len(items)} -> {len(unique_items)}")
        return unique_items
    
    async def _save_items(self, items: List[DataItem], storage_config: Dict[str, Any]) -> None:
        """保存数据项"""
        storage_type = storage_config.get("type", "json")
        
        try:
            storage_adapter = await self._get_storage_adapter(storage_type, storage_config)
            if storage_adapter:
                await storage_adapter.save(items)
                logger.info(f"数据保存成功: {len(items)} 条，存储类型: {storage_type}")
            else:
                logger.error(f"无法获取存储适配器: {storage_type}")
                
        except Exception as e:
            logger.error(f"保存数据失败: {e}")
            raise
    
    async def _get_storage_adapter(self, storage_type: str, config: Dict[str, Any]) -> Optional[StorageAdapter]:
        """获取存储适配器实例"""
        instance_key = f"{storage_type}_{hash(str(config))}"
        
        # 检查是否已有实例
        if instance_key in self._storage_instances:
            return self._storage_instances[instance_key]
        
        # 创建新实例
        adapter_class = self.plugin_manager.get_storage_adapter(f"{storage_type.title()}StorageAdapter")
        if not adapter_class:
            logger.error(f"未找到存储适配器: {storage_type}")
            return None
        
        try:
            adapter = adapter_class(**config)
            self._storage_instances[instance_key] = adapter
            logger.info(f"创建存储适配器实例: {storage_type}")
            return adapter
            
        except Exception as e:
            logger.error(f"创建存储适配器失败 {storage_type}: {e}")
            return None
    
    async def cleanup(self) -> None:
        """清理资源"""
        # 清理平台适配器
        for adapter in self._platform_instances.values():
            try:
                await adapter.cleanup()
            except Exception as e:
                logger.error(f"清理平台适配器失败: {e}")
        
        # 清理存储适配器
        for adapter in self._storage_instances.values():
            try:
                await adapter.close()
            except Exception as e:
                logger.error(f"清理存储适配器失败: {e}")
        
        self._platform_instances.clear()
        self._storage_instances.clear()
        
        logger.info("数据处理器清理完成")