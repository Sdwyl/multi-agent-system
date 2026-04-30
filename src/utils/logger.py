"""
日志模块
提供统一的日志记录功能
"""

import sys
import logging
from pathlib import Path
from typing import Optional
from loguru import logger as _logger

# 默认日志格式
DEFAULT_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
    "<level>{message}</level>"
)


class Logger:
    """日志记录器封装类"""
    
    _instance: Optional['Logger'] = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化日志记录器"""
        if self._initialized:
            return
        self._initialized = True
        self._logger = _logger
        self._setup_default_handlers()
    
    def _setup_default_handlers(self) -> None:
        """设置默认的日志处理器"""
        # 移除默认处理器
        self._logger.remove()
        
        # 创建日志目录
        log_dir = Path(__file__).parent.parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # 控制台处理器
        self._logger.add(
            sys.stdout,
            format=DEFAULT_FORMAT,
            level="INFO",
            colorize=True
        )
        
        # 文件处理器 - 按大小轮转
        self._logger.add(
            log_dir / "agent.log",
            format=DEFAULT_FORMAT,
            level="DEBUG",
            rotation="500 MB",
            retention="7 days",
            compression="zip",
            encoding="utf-8"
        )
        
        # 错误日志单独文件
        self._logger.add(
            log_dir / "error.log",
            format=DEFAULT_FORMAT,
            level="ERROR",
            rotation="100 MB",
            retention="30 days",
            encoding="utf-8"
        )
    
    def setup_from_config(self, level: str = "INFO", log_file: str = None) -> None:
        """
        根据配置设置日志
        
        Args:
            level: 日志级别
            log_file: 日志文件路径
        """
        # 清除现有处理器
        self._logger.remove()
        
        # 控制台处理器
        self._logger.add(
            sys.stdout,
            format=DEFAULT_FORMAT,
            level=level,
            colorize=True
        )
        
        # 文件处理器
        if log_file:
            self._logger.add(
                log_file,
                format=DEFAULT_FORMAT,
                level="DEBUG",
                rotation="500 MB",
                retention="7 days",
                encoding="utf-8"
            )
    
    def debug(self, message: str, *args, **kwargs) -> None:
        """记录调试日志"""
        self._logger.debug(message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs) -> None:
        """记录信息日志"""
        self._logger.info(message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs) -> None:
        """记录警告日志"""
        self._logger.warning(message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs) -> None:
        """记录错误日志"""
        self._logger.error(message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs) -> None:
        """记录严重错误日志"""
        self._logger.critical(message, *args, **kwargs)
    
    def exception(self, message: str, *args, **kwargs) -> None:
        """记录异常日志（自动包含堆栈信息）"""
        self._logger.exception(message, *args, **kwargs)


# 全局日志实例
_logger_instance: Optional[Logger] = None


def setup_logger(level: str = "INFO", log_file: str = None) -> Logger:
    """
    设置并返回日志记录器
    
    Args:
        level: 日志级别
        log_file: 日志文件路径
        
    Returns:
        Logger实例
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = Logger()
    _logger_instance.setup_from_config(level, log_file)
    return _logger_instance


def get_logger() -> Logger:
    """获取日志记录器实例"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = Logger()
    return _logger_instance
