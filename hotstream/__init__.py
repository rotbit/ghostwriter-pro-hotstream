"""
GhostWriter Pro HotStream - 多平台数据抓取框架

一个支持插件化的数据抓取框架，使用 Playwright 从各大平台抓取数据。
"""

__version__ = "0.1.0"
__author__ = "HotStream Team"

from .core.framework import HotStreamFramework
from .core.plugin_manager import PluginManager
from .core.scheduler import TaskScheduler
from .core.data_processor import DataProcessor

__all__ = [
    "HotStreamFramework",
    "PluginManager", 
    "TaskScheduler",
    "DataProcessor",
]