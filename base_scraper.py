from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import json
import time

class BaseScraper(ABC):
    """抽象爬虫基类"""
    
    def __init__(self, base_url: str, output_filename: str = None):
        self.base_url = base_url
        self.output_filename = output_filename or self._default_filename()
        self.raw_data: List[Dict] = []
        self.processed_data: Dict[str, Any] = {}
    
    @abstractmethod
    def _default_filename(self) -> str:
        """返回默认的输出文件名"""
        pass
    
    @abstractmethod
    async def fetch_data(self) -> List[Dict[str, Any]]:
        """
        数据获取 - 从目标网站获取原始数据
        Returns:
            List[Dict]: 原始数据列表
        """
        pass
    
    @abstractmethod
    def parse_data(self, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        数据解析 - 将原始数据解析成结构化数据
        Args:
            raw_data: 原始数据
        Returns:
            Dict: 解析后的结构化数据
        """
        pass
    
    @abstractmethod
    def store_data(self, data: Dict[str, Any], filename: str = None) -> str:
        """
        数据存储 - 将处理后的数据存储到文件
        Args:
            data: 处理后的数据
            filename: 可选的文件名
        Returns:
            str: 存储文件的路径
        """
        pass
    
    async def execute(self) -> str:
        """
        执行接口 - 完整的数据抓取流程
        Returns:
            str: 输出文件路径
        """
        try:
            print(f"开始执行数据抓取任务...")
            
            # 1. 数据获取
            print("步骤 1/3: 获取数据...")
            self.raw_data = await self.fetch_data()
            print(f"获取到 {len(self.raw_data)} 条原始数据")
            
            # 2. 数据解析
            print("步骤 2/3: 解析数据...")
            self.processed_data = self.parse_data(self.raw_data)
            
            # 3. 数据存储
            print("步骤 3/3: 存储数据...")
            output_path = self.store_data(self.processed_data, self.output_filename)
            
            print(f"任务完成！数据已保存到: {output_path}")
            return output_path
            
        except Exception as e:
            print(f"执行过程中出现错误: {e}")
            raise
    
    def get_summary(self) -> Dict[str, Any]:
        """获取数据摘要信息"""
        if not self.processed_data:
            return {"error": "没有处理过的数据"}
        
        return {
            "raw_data_count": len(self.raw_data),
            "processed_data_keys": list(self.processed_data.keys()),
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
        }