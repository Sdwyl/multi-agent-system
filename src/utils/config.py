"""
配置管理模块
负责加载和管理系统配置
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class ConfigManager:
    """配置管理器"""
    
    _instance: Optional['ConfigManager'] = None
    _config: Dict[str, Any] = {}
    _agents_config: Dict[str, Any] = {}
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化配置管理器"""
        if self._initialized:
            return
        self._initialized = True
        self._load_configs()
    
    def _load_configs(self) -> None:
        """加载所有配置文件"""
        # 获取配置目录
        config_dir = Path(__file__).parent.parent.parent / "config"
        
        # 加载默认配置
        default_config_path = config_dir / "default.yaml"
        if default_config_path.exists():
            with open(default_config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        
        # 加载Agent配置
        agents_config_path = config_dir / "agents.yaml"
        if agents_config_path.exists():
            with open(agents_config_path, 'r', encoding='utf-8') as f:
                self._agents_config = yaml.safe_load(f) or {}
        
        # 替换环境变量占位符
        self._replace_env_vars(self._config)
        self._replace_env_vars(self._agents_config)
    
    def _replace_env_vars(self, config: Dict[str, Any]) -> None:
        """递归替换配置中的环境变量占位符"""
        for key, value in config.items():
            if isinstance(value, dict):
                self._replace_env_vars(value)
            elif isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                config[key] = os.getenv(env_var, value)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持点号分隔的键路径
        
        Args:
            key: 配置键，如 "app.host"
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def get_agents_config(self, agent_name: str = None) -> Dict[str, Any]:
        """
        获取Agent配置
        
        Args:
            agent_name: Agent名称，如果为None则返回所有Agent配置
            
        Returns:
            Agent配置字典
        """
        if agent_name:
            return self._agents_config.get('agents', {}).get(agent_name, {})
        return self._agents_config.get('agents', {})
    
    def get_workflows_config(self) -> Dict[str, Any]:
        """获取工作流预设配置"""
        return self._agents_config.get('workflows', {})
    
    def reload(self) -> None:
        """重新加载配置"""
        self._load_configs()
    
    @property
    def app(self) -> Dict[str, Any]:
        """获取应用配置"""
        return self._config.get('app', {})
    
    @property
    def redis(self) -> Dict[str, Any]:
        """获取Redis配置"""
        return self._config.get('redis', {})
    
    @property
    def database(self) -> Dict[str, Any]:
        """获取数据库配置"""
        return self._config.get('database', {})
    
    @property
    def llm(self) -> Dict[str, Any]:
        """获取LLM配置"""
        return self._config.get('llm', {})
    
    @property
    def scheduler(self) -> Dict[str, Any]:
        """获取调度器配置"""
        return self._config.get('scheduler', {})


# 全局配置实例
_config_instance: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """获取配置管理器实例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance
