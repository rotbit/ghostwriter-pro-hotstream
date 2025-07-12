"""
配置管理器
"""

import os
import json
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from loguru import logger


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._find_config_file()
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _find_config_file(self) -> str:
        """查找配置文件"""
        # 查找顺序：当前目录 -> 配置目录 -> 用户目录
        search_paths = [
            "hotstream.yaml",
            "hotstream.yml", 
            "hotstream.json",
            "configs/hotstream.yaml",
            "configs/hotstream.yml",
            "configs/hotstream.json",
            os.path.expanduser("~/.hotstream/config.yaml"),
            os.path.expanduser("~/.hotstream/config.yml"),
            os.path.expanduser("~/.hotstream/config.json"),
        ]
        
        for path in search_paths:
            if os.path.exists(path):
                return path
        
        # 如果没有找到配置文件，使用默认路径
        return "configs/hotstream.yaml"
    
    def _load_config(self) -> None:
        """加载配置文件"""
        if not os.path.exists(self.config_path):
            logger.warning(f"配置文件不存在: {self.config_path}，使用默认配置")
            self._config = self._get_default_config()
            return
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if self.config_path.endswith(('.yaml', '.yml')):
                    self._config = yaml.safe_load(f) or {}
                else:
                    self._config = json.load(f)
            
            # 合并默认配置
            default_config = self._get_default_config()
            self._config = self._merge_configs(default_config, self._config)
            
            logger.info(f"配置文件加载成功: {self.config_path}")
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "framework": {
                "name": "HotStream",
                "version": "0.1.0",
                "debug": False,
                "log_level": "INFO"
            },
            "plugins": {
                "auto_discover": True,
                "plugin_dirs": []
            },
            "scheduler": {
                "enabled": True,
                "check_interval": 60,
                "max_concurrent_tasks": 10
            },
            "storage": {
                "default_type": "json",
                "output_dir": "output",
                "compression": False
            },
            "crawler": {
                "user_agent": "HotStream/0.1.0",
                "timeout": 30,
                "retry_count": 3,
                "delay_range": [1, 3],
                "concurrent_requests": 5
            },
            "platforms": {
                "twitter": {
                    "enabled": True,
                    "rate_limit": {
                        "requests_per_minute": 100,
                        "requests_per_hour": 1000
                    }
                },
                "medium": {
                    "enabled": True,
                    "rate_limit": {
                        "requests_per_minute": 60,
                        "requests_per_hour": 500
                    }
                },
                "zhihu": {
                    "enabled": True,
                    "rate_limit": {
                        "requests_per_minute": 50,
                        "requests_per_hour": 300
                    }
                },
                "juejin": {
                    "enabled": True,
                    "rate_limit": {
                        "requests_per_minute": 40,
                        "requests_per_hour": 200
                    }
                }
            },
            "security": {
                "encrypt_credentials": True,
                "proxy_rotation": True,
                "user_agent_rotation": True
            },
            "monitoring": {
                "enabled": True,
                "metrics_interval": 300,
                "log_file": "logs/hotstream.log"
            }
        }
    
    def _merge_configs(self, default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """合并配置"""
        result = default.copy()
        
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """设置配置值"""
        keys = key.split('.')
        config = self._config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def save(self, path: Optional[str] = None) -> bool:
        """保存配置到文件"""
        save_path = path or self.config_path
        
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            with open(save_path, 'w', encoding='utf-8') as f:
                if save_path.endswith(('.yaml', '.yml')):
                    yaml.dump(self._config, f, default_flow_style=False, allow_unicode=True)
                else:
                    json.dump(self._config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"配置保存成功: {save_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            return False
    
    def reload(self) -> None:
        """重新加载配置"""
        self._load_config()
        logger.info("配置重新加载完成")
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self._config.copy()
    
    def get_platform_config(self, platform: str) -> Dict[str, Any]:
        """获取平台配置"""
        return self.get(f"platforms.{platform}", {})
    
    def get_storage_config(self) -> Dict[str, Any]:
        """获取存储配置"""
        return self.get("storage", {})
    
    def get_crawler_config(self) -> Dict[str, Any]:
        """获取爬虫配置"""
        return self.get("crawler", {})
    
    def is_platform_enabled(self, platform: str) -> bool:
        """检查平台是否启用"""
        return self.get(f"platforms.{platform}.enabled", False)