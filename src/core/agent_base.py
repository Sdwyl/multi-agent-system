"""
Agent基类模块
定义所有Agent的基础结构和通用功能
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field

from ..utils.logger import get_logger


class AgentType(Enum):
    """Agent类型枚举"""
    ORCHESTRATOR = "orchestrator"      # 调度Agent
    CONTENT = "content"                # 内容生成Agent
    DATA = "data"                      # 数据分析Agent
    MONITOR = "monitor"                # 监控Agent
    EXECUTOR = "executor"              # 执行Agent
    CUSTOM = "custom"                  # 自定义Agent


class AgentStatus(Enum):
    """Agent状态枚举"""
    IDLE = "idle"                      # 空闲
    INITIALIZING = "initializing"      # 初始化中
    RUNNING = "running"                # 运行中
    PROCESSING = "processing"         # 处理任务中
    ERROR = "error"                    # 错误状态
    STOPPED = "stopped"                # 已停止


@dataclass
class AgentMessage:
    """Agent消息结构"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender: str = ""                    # 发送者ID
    receiver: str = ""                  # 接收者ID，空字符串表示广播
    message_type: str = "task"          # 消息类型
    content: Dict[str, Any] = field(default_factory=dict)  # 消息内容
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: str = ""            # 关联ID，用于追踪
    priority: int = 5                   # 优先级 1-10
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "sender": self.sender,
            "receiver": self.receiver,
            "message_type": self.message_type,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "priority": self.priority,
            "metadata": self.metadata
        }


class AgentBase(ABC):
    """
    Agent基类
    所有具体Agent都需要继承此类并实现核心方法
    """
    
    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType,
        name: str = None,
        config: Dict[str, Any] = None
    ):
        """
        初始化Agent
        
        Args:
            agent_id: Agent唯一标识
            agent_type: Agent类型
            name: Agent名称
            config: Agent配置
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.name = name or f"{agent_type.value}_{agent_id}"
        self.config = config or {}
        
        self.status = AgentStatus.IDLE
        self.logger = get_logger()
        self._message_handlers: Dict[str, Callable] = {}
        self._running = False
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._handlers: List[asyncio.Task] = []
        
        # 统计信息
        self.stats = {
            "tasks_processed": 0,
            "tasks_success": 0,
            "tasks_failed": 0,
            "total_response_time": 0.0,
            "messages_received": 0,
            "messages_sent": 0
        }
    
    async def initialize(self) -> None:
        """
        初始化Agent
        子类可重写此方法进行初始化操作
        """
        self.logger.info(f"初始化Agent: {self.name}")
        self.status = AgentStatus.INITIALIZING
        
        # 注册默认消息处理器
        self._register_default_handlers()
        
        self.status = AgentStatus.IDLE
        self.logger.info(f"Agent初始化完成: {self.name}")
    
    def _register_default_handlers(self) -> None:
        """注册默认消息处理器"""
        self.register_message_handler("ping", self._handle_ping)
        self.register_message_handler("status", self._handle_status_request)
        self.register_message_handler("config_update", self._handle_config_update)
    
    async def _handle_ping(self, message: AgentMessage) -> AgentMessage:
        """处理ping消息"""
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="pong",
            content={"status": self.status.value},
            correlation_id=message.correlation_id
        )
    
    async def _handle_status_request(self, message: AgentMessage) -> AgentMessage:
        """处理状态查询请求"""
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="status_response",
            content={
                "agent_id": self.agent_id,
                "status": self.status.value,
                "stats": self.stats
            },
            correlation_id=message.correlation_id
        )
    
    async def _handle_config_update(self, message: AgentMessage) -> AgentMessage:
        """处理配置更新"""
        if "config" in message.content:
            self.config.update(message.content["config"])
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="config_updated",
            content={"agent_id": self.agent_id},
            correlation_id=message.correlation_id
        )
    
    def register_message_handler(self, message_type: str, handler: Callable) -> None:
        """
        注册消息处理器
        
        Args:
            message_type: 消息类型
            handler: 处理函数
        """
        self._message_handlers[message_type] = handler
        self.logger.debug(f"注册消息处理器: {self.name} -> {message_type}")
    
    async def handle_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """
        处理接收到的消息
        
        Args:
            message: 收到的消息
            
        Returns:
            响应消息，如果有的话
        """
        self.stats["messages_received"] += 1
        self.logger.debug(f"收到消息 [{self.name}]: type={message.message_type}, from={message.sender}")
        
        # 查找对应的处理器
        handler = self._message_handlers.get(message.message_type)
        if handler:
            try:
                return await handler(message)
            except Exception as e:
                self.logger.error(f"处理消息异常: {e}")
                self.stats["tasks_failed"] += 1
                return AgentMessage(
                    sender=self.agent_id,
                    receiver=message.sender,
                    message_type="error",
                    content={"error": str(e)},
                    correlation_id=message.correlation_id
                )
        else:
            # 如果没有特定处理器，调用通用处理方法
            return await self.process_message(message)
    
    @abstractmethod
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """
        处理消息的核心方法
        子类必须实现此方法
        
        Args:
            message: 收到的消息
            
        Returns:
            响应消息
        """
        pass
    
    @abstractmethod
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行任务的核心方法
        子类必须实现此方法
        
        Args:
            task: 任务参数
            
        Returns:
            任务结果
        """
        pass
    
    async def start(self) -> None:
        """启动Agent"""
        if self._running:
            return
        
        self.logger.info(f"启动Agent: {self.name}")
        self._running = True
        self.status = AgentStatus.RUNNING
        
        # 启动消息处理协程
        self._handlers.append(asyncio.create_task(self._process_queue()))
    
    async def stop(self) -> None:
        """停止Agent"""
        if not self._running:
            return
        
        self.logger.info(f"停止Agent: {self.name}")
        self._running = False
        self.status = AgentStatus.STOPPED
        
        # 取消所有处理任务
        for handler in self._handlers:
            handler.cancel()
        
        # 等待任务完成
        await asyncio.gather(*self._handlers, return_exceptions=True)
        self._handlers.clear()
    
    async def _process_queue(self) -> None:
        """处理消息队列"""
        while self._running:
            try:
                message = await asyncio.wait_for(
                    self._task_queue.get(),
                    timeout=1.0
                )
                await self.handle_message(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"处理队列异常: {e}")
    
    async def send_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送任务给Agent
        
        Args:
            task: 任务参数
            
        Returns:
            任务结果
        """
        self.logger.info(f"执行任务 [{self.name}]: {task.get('type', 'unknown')}")
        start_time = asyncio.get_event_loop().time()
        
        try:
            self.status = AgentStatus.PROCESSING
            result = await self.execute_task(task)
            
            # 更新统计
            elapsed = asyncio.get_event_loop().time() - start_time
            self.stats["tasks_processed"] += 1
            self.stats["tasks_success"] += 1
            self.stats["total_response_time"] += elapsed
            
            self.status = AgentStatus.IDLE
            return {"success": True, "result": result, "elapsed": elapsed}
            
        except Exception as e:
            self.logger.error(f"任务执行失败 [{self.name}]: {e}")
            self.stats["tasks_processed"] += 1
            self.stats["tasks_failed"] += 1
            self.status = AgentStatus.ERROR
            
            return {"success": False, "error": str(e)}
    
    async def cleanup(self) -> None:
        """
        清理资源
        子类可重写此方法进行清理操作
        """
        self.logger.info(f"清理Agent资源: {self.name}")
        await self.stop()
    
    def get_status(self) -> Dict[str, Any]:
        """获取Agent状态"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "type": self.agent_type.value,
            "status": self.status.value,
            "config": self.config,
            "stats": self.stats
        }
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.agent_id}, name={self.name}, status={self.status.value})>"
