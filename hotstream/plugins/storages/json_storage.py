"""
JSON 存储适配器
"""

import json
import os
from typing import Dict, List, Any
from datetime import datetime
from pathlib import Path
from loguru import logger

from ...core.interfaces import StorageAdapter, DataItem


class JsonStorageAdapter(StorageAdapter):
    """JSON 文件存储适配器"""
    
    def __init__(self, output_dir: str = "output", **kwargs):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"JSON 存储适配器初始化，输出目录: {self.output_dir}")
    
    async def save(self, items: List[DataItem]) -> bool:
        """保存数据到 JSON 文件"""
        try:
            # 按平台分组
            grouped_items = {}
            for item in items:
                platform = item.platform
                if platform not in grouped_items:
                    grouped_items[platform] = []
                grouped_items[platform].append(item.dict())
            
            # 为每个平台创建文件
            for platform, platform_items in grouped_items.items():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{platform}_{timestamp}.json"
                filepath = self.output_dir / filename
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(platform_items, f, ensure_ascii=False, indent=2)
                
                logger.info(f"保存 {len(platform_items)} 条 {platform} 数据到: {filepath}")
            
            return True
            
        except Exception as e:
            logger.error(f"JSON 存储失败: {e}")
            return False
    
    async def query(self, filters: Dict[str, Any]) -> List[DataItem]:
        """查询数据（简单实现）"""
        try:
            platform = filters.get("platform")
            if not platform:
                raise ValueError("必须指定平台")
            
            results = []
            
            # 查找匹配的文件
            pattern = f"{platform}_*.json"
            for filepath in self.output_dir.glob(pattern):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item_data in data:
                        item = DataItem(**item_data)
                        
                        # 简单过滤
                        if self._match_filters(item, filters):
                            results.append(item)
            
            logger.info(f"查询到 {len(results)} 条数据")
            return results
            
        except Exception as e:
            logger.error(f"JSON 查询失败: {e}")
            return []
    
    def _match_filters(self, item: DataItem, filters: Dict[str, Any]) -> bool:
        """检查数据项是否匹配过滤条件"""
        for key, value in filters.items():
            if key == "platform":
                continue
            
            item_value = getattr(item, key, None)
            if item_value != value:
                return False
        
        return True
    
    async def close(self) -> None:
        """关闭连接（JSON 文件不需要）"""
        logger.debug("JSON 存储适配器关闭")