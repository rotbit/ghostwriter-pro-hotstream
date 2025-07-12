"""
插件管理器
"""

import os
import sys
import importlib
import inspect
from typing import Dict, List, Type, Any, Optional
from pathlib import Path
from loguru import logger

from .interfaces import Plugin, PlatformAdapter, DataExtractor, StorageAdapter


class PluginManager:
    """插件管理器"""
    
    def __init__(self, plugin_dirs: Optional[List[str]] = None):
        self.plugin_dirs = plugin_dirs or []
        self.plugins: Dict[str, Plugin] = {}
        self.platform_adapters: Dict[str, Type[PlatformAdapter]] = {}
        self.data_extractors: Dict[str, Type[DataExtractor]] = {}
        self.storage_adapters: Dict[str, Type[StorageAdapter]] = {}
        
        # 添加默认插件目录
        self._add_default_plugin_dirs()
    
    def _add_default_plugin_dirs(self):
        """添加默认插件目录"""
        current_dir = Path(__file__).parent.parent
        default_dirs = [
            str(current_dir / "plugins" / "platforms"),
            str(current_dir / "plugins" / "extractors"),
            str(current_dir / "plugins" / "storages"),
        ]
        
        for dir_path in default_dirs:
            if dir_path not in self.plugin_dirs:
                self.plugin_dirs.append(dir_path)
    
    async def discover_plugins(self) -> None:
        """发现并加载所有插件"""
        logger.info("开始发现插件...")
        
        for plugin_dir in self.plugin_dirs:
            if not os.path.exists(plugin_dir):
                logger.warning(f"插件目录不存在: {plugin_dir}")
                continue
            
            self._scan_directory(plugin_dir)
        
        logger.info(f"插件发现完成，共加载 {len(self.plugins)} 个插件")
    
    def _scan_directory(self, directory: str) -> None:
        """扫描目录中的插件"""
        path = Path(directory)
        
        # 添加到 Python 路径
        if str(path.parent) not in sys.path:
            sys.path.insert(0, str(path.parent))
        
        for file_path in path.rglob("*.py"):
            if file_path.name.startswith("__") or file_path.name.startswith("test_"):
                continue
            
            try:
                self._load_plugin_from_file(file_path)
            except Exception as e:
                logger.error(f"加载插件失败 {file_path}: {e}")
    
    def _load_plugin_from_file(self, file_path: Path) -> None:
        """从文件加载插件"""
        try:
            # 找到项目根目录（包含 hotstream 包的目录）
            hotstream_root = None
            for parent in file_path.parents:
                if (parent / "hotstream").exists():
                    hotstream_root = parent
                    break
            
            if not hotstream_root:
                logger.error(f"无法找到项目根目录: {file_path}")
                return
            
            # 构建相对于项目根目录的模块名
            relative_path = file_path.relative_to(hotstream_root)
            module_name = str(relative_path.with_suffix("")).replace(os.sep, ".")
            
            # 确保项目根目录在 Python 路径中
            if str(hotstream_root) not in sys.path:
                sys.path.insert(0, str(hotstream_root))
            
            # 导入模块
            module = importlib.import_module(module_name)
            
            # 查找插件类
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if obj.__module__ != module.__name__:
                    continue
                
                # 检查是否是插件类
                if issubclass(obj, PlatformAdapter) and obj != PlatformAdapter:
                    self.platform_adapters[obj.platform_name] = obj
                    logger.info(f"发现平台适配器: {obj.platform_name}")
                
                elif issubclass(obj, DataExtractor) and obj != DataExtractor:
                    self.data_extractors[name] = obj
                    logger.info(f"发现数据提取器: {name}")
                
                elif issubclass(obj, StorageAdapter) and obj != StorageAdapter:
                    self.storage_adapters[name] = obj
                    logger.info(f"发现存储适配器: {name}")
                
                elif issubclass(obj, Plugin) and obj != Plugin:
                    plugin_instance = obj()
                    self.plugins[plugin_instance.name] = plugin_instance
                    logger.info(f"发现插件: {plugin_instance.name}")
        
        except Exception as e:
            logger.error(f"导入模块失败 {module_name}: {e}")
    
    def get_platform_adapter(self, platform_name: str) -> Optional[Type[PlatformAdapter]]:
        """获取平台适配器"""
        return self.platform_adapters.get(platform_name)
    
    def get_data_extractor(self, extractor_name: str) -> Optional[Type[DataExtractor]]:
        """获取数据提取器"""
        return self.data_extractors.get(extractor_name)
    
    def get_storage_adapter(self, adapter_name: str) -> Optional[Type[StorageAdapter]]:
        """获取存储适配器"""
        return self.storage_adapters.get(adapter_name)
    
    def get_plugin(self, plugin_name: str) -> Optional[Plugin]:
        """获取插件实例"""
        return self.plugins.get(plugin_name)
    
    def list_platforms(self) -> List[str]:
        """列出所有可用平台"""
        return list(self.platform_adapters.keys())
    
    def list_extractors(self) -> List[str]:
        """列出所有数据提取器"""
        return list(self.data_extractors.keys())
    
    def list_storages(self) -> List[str]:
        """列出所有存储适配器"""
        return list(self.storage_adapters.keys())
    
    def list_plugins(self) -> List[str]:
        """列出所有插件"""
        return list(self.plugins.keys())
    
    async def initialize_plugin(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """初始化插件"""
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            logger.error(f"插件不存在: {plugin_name}")
            return False
        
        try:
            return await plugin.initialize(config)
        except Exception as e:
            logger.error(f"插件初始化失败 {plugin_name}: {e}")
            return False
    
    async def cleanup_all(self) -> None:
        """清理所有插件"""
        for plugin in self.plugins.values():
            try:
                await plugin.cleanup()
            except Exception as e:
                logger.error(f"插件清理失败 {plugin.name}: {e}")
    
    async def cleanup(self) -> None:
        """清理所有插件（cleanup_all的别名）"""
        await self.cleanup_all()