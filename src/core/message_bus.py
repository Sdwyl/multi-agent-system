"""
消息总线模块
基于Redis的发布/订阅消息系统
"""

import asyncio
import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field

import redis.asyncio as redis

from ..utils.config import get_config
from ..utils.logger import get_logger


class MessageType(Enum):
    """消息类型枚举"""
    TASK = "task"                      # 任务消息
    RESULT = "result"                  # 结果消息
    EVENT = "event"                    # 事件消息
    BROADCAST = "broadcast"            # 广播消息
    DIRECT = "direct"                  # 直接消息
    HEARTBEAT = "heartbeat"            # 心跳消息
    ERROR = "error"                    # 错误消息
    STATUS = "status"                  # 状态消息


@dataclass
class Message:
    """消息结构"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_type: MessageType = MessageType.TASK
    sender: str = ""
    receiver: str = ""                 # 空字符串表示广播
    channel: str = ""
    content: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    correlation_id: str = ""
    priority: int = 5
    ttl: int = 300                     # 消息TTL，单位秒
    
    def to_json(self) -> str:
        """序列化为JSON"""
        return json.dumps({
            "id": self.id,
            "message_type": self.message_type.value,
            "sender": self.sender,
            "receiver": self.receiver,
            "channel": self.channel,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "priority": self.priority,
            "ttl": self.ttl
        }, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Message':
        """从JSON反序列化"""
        data = json.loads(json_str)
        return cls(
            id=data["id"],
            message_type=MessageType(data["message_type"]),
            sender=data["sender"],
            receiver=data["receiver"],
            channel=data["channel"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            correlation_id=data["correlation_id"],
            priority=data["priority"],
            ttl=data["ttl"]
        )


class MessageBus:
    """
    消息总线
    基于Redis的发布/订阅模式，支持任务队列
    """
    
    _instance: Optional['MessageBus'] = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化消息总线"""
        if self._initialized:
            return
        self._initialized = True
        
        self.logger = get_logger()
        self.config = get_config()
        
        # Redis连接
        self._redis: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        
        # 本地订阅者（用于没有Redis的情况）
        self._local_subscribers: Dict[str, Set[Callable]] = {}
        
        # 任务队列
        self._task_queues: Dict[str, asyncio.Queue] = {}
        
        # 运行状态
        self._running = False
        self._listener_tasks: List[asyncio.Task] = []
        
        # 消息处理器
        self._handlers: Dict[str, Callable] = {}
    
    async def connect(self) -> None:
        """连接到Redis"""
        try:
            redis_config = self.config.redis
            
            # 构建Redis连接URL
            password = redis_config.get("password")
            if password:
                url = f"redis://:{password}@{redis_config['host']}:{redis_config['port']}/{redis_config.get('db', 0)}"
            else:
                url = f"redis://{redis_config['host']}:{redis_config['port']}/{redis_config.get('db', 0)}"
            
            self._redis = redis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=self.config.redis.get("max_connections", 50)
            )
            
            # 测试连接
            await self._redis.ping()
            self.logger.info("Redis连接成功")
            
        except Exception as e:
            self.logger.warning(f"Redis连接失败，使用本地消息总线: {e}")
            self._redis = None
    
    async def disconnect(self) -> None:
        """断开Redis连接"""
        self._running = False
        
        # 取消监听任务
        for task in self._listener_tasks:
            task.cancel()
        await asyncio.gather(*self._listener_tasks, return_exceptions=True)
        self._listener_tasks.clear()
        
        # 关闭Redis连接
        if self._pubsub:
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
        
        self.logger.info("消息总线已断开")
    
    async def publish(self, message: Message) -> int:
        """
        发布消息
        
        Args:
            message: 消息对象
            
        Returns:
            订阅者数量
        """
        channel = message.channel
        if not channel:
            channel = f"agent:{message.receiver}" if message.receiver else "agent:broadcast"
        
        try:
            if self._redis:
                # Redis发布
                subscriber_count = await self._redis.publish(channel, message.to_json())
                self.logger.debug(f"消息已发布到 {channel}: {message.id}, 订阅者: {subscriber_count}")
                return subscriber_count
            else:
                # 本地发布
                await self._local_publish(channel, message)
                return len(self._local_subscribers.get(channel, set()))
                
        except Exception as e:
            self.logger.error(f"发布消息失败: {e}")
            return 0
    
    async def _local_publish(self, channel: str, message: Message) -> None:
        """本地发布消息"""
        subscribers = self._local_subscribers.get(channel, set())
        for callback in subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                self.logger.error(f"本地消息处理异常: {e}")
    
    async def subscribe(self, channel: str, callback: Callable) -> None:
        """
        订阅频道
        
        Args:
            channel: 频道名称
            callback: 回调函数
        """
        if self._redis:
            # Redis订阅
            if not self._pubsub:
                self._pubsub = self._redis.pubsub()
            
            await self._pubsub.subscribe(channel)
            self.logger.info(f"订阅频道: {channel}")
            
            # 启动监听任务
            if not self._running:
                self._running = True
                self._listener_tasks.append(asyncio.create_task(self._listen_redis()))
        else:
            # 本地订阅
            if channel not in self._local_subscribers:
                self._local_subscribers[channel] = set()
            self._local_subscribers[channel].add(callback)
            self.logger.info(f"本地订阅频道: {channel}")
    
    async def unsubscribe(self, channel: str, callback: Callable = None) -> None:
        """
        取消订阅
        
        Args:
            channel: 频道名称
            callback: 特定回调函数，为None则取消整个频道
        """
        if self._redis and self._pubsub:
            if callback is None:
                await self._pubsub.unsubscribe(channel)
                self.logger.info(f"取消订阅频道: {channel}")
        else:
            if channel in self._local_subscribers:
                if callback:
                    self._local_subscribers[channel].discard(callback)
                else:
                    del self._local_subscribers[channel]
    
    async def _listen_redis(self) -> None:
        """监听Redis消息"""
        try:
            while self._running:
                try:
                    message = await self._pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0
                    )
                    if message and message['type'] == 'message':
                        try:
                            msg = Message.from_json(message['data'])
                            # 触发本地处理器
                            handler = self._handlers.get(message['channel'])
                            if handler:
                                if asyncio.iscoroutinefunction(handler):
                                    await handler(msg)
                                else:
                                    handler(msg)
                        except Exception as e:
                            self.logger.error(f"处理消息异常: {e}")
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"监听消息异常: {e}")
                    await asyncio.sleep(1)
        except Exception as e:
            self.logger.error(f"Redis监听异常: {e}")
    
    # ==================== 任务队列操作 ====================
    
    async def enqueue(self, queue_name: str, message: Message) -> bool:
        """
        入队消息到指定队列
        
        Args:
            queue_name: 队列名称
            message: 消息对象
            
        Returns:
            是否成功
        """
        try:
            if self._redis:
                # Redis队列
                queue_key = f"queue:{queue_name}"
                priority_score = 100 - message.priority  # 优先级高的分数低
                await self._redis.zadd(
                    queue_key,
                    {message.to_json(): priority_score}
                )
                self.logger.debug(f"消息入队: {queue_name}, id={message.id}")
                return True
            else:
                # 本地队列
                if queue_name not in self._task_queues:
                    self._task_queues[queue_name] = asyncio.Queue()
                await self._task_queues[queue_name].put(message)
                return True
                
        except Exception as e:
            self.logger.error(f"入队失败: {e}")
            return False
    
    async def dequeue(self, queue_name: str, timeout: float = 1.0) -> Optional[Message]:
        """
        出队消息
        
        Args:
            queue_name: 队列名称
            timeout: 超时时间
            
        Returns:
            消息对象，如果没有消息则返回None
        """
        try:
            if self._redis:
                # Redis队列
                queue_key = f"queue:{queue_name}"
                result = await self._redis.zpopmin(queue_key, 1)
                if result:
                    _, json_str = result[0]
                    return Message.from_json(json_str)
                return None
            else:
                # 本地队列
                if queue_name in self._task_queues:
                    return await asyncio.wait_for(
                        self._task_queues[queue_name].get(),
                        timeout=timeout
                    )
                return None
                
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            self.logger.error(f"出队失败: {e}")
            return None
    
    async def get_queue_size(self, queue_name: str) -> int:
        """获取队列长度"""
        try:
            if self._redis:
                queue_key = f"queue:{queue_name}"
                return await self._redis.zcard(queue_key)
            else:
                return self._task_queues.get(queue_name, asyncio.Queue()).qsize()
        except Exception as e:
            self.logger.error(f"获取队列长度失败: {e}")
            return 0
    
    async def clear_queue(self, queue_name: str) -> bool:
        """清空队列"""
        try:
            if self._redis:
                queue_key = f"queue:{queue_name}"
                await self._redis.delete(queue_key)
            else:
                if queue_name in self._task_queues:
                    while not self._task_queues[queue_name].empty():
                        try:
                            self._task_queues[queue_name].get_nowait()
                        except asyncio.QueueEmpty:
                            break
            return True
        except Exception as e:
            self.logger.error(f"清空队列失败: {e}")
            return False
    
    # ==================== 键值操作 ====================
    
    async def set_value(self, key: str, value: Any, ttl: int = None) -> bool:
        """设置键值"""
        try:
            if self._redis:
                await self._redis.set(key, json.dumps(value, ensure_ascii=False), ex=ttl)
                return True
            return False
        except Exception as e:
            self.logger.error(f"设置值失败: {e}")
            return False
    
    async def get_value(self, key: str) -> Optional[Any]:
        """获取键值"""
        try:
            if self._redis:
                value = await self._redis.get(key)
                if value:
                    return json.loads(value)
            return None
        except Exception as e:
            self.logger.error(f"获取值失败: {e}")
            return None
    
    async def delete_value(self, key: str) -> bool:
        """删除键值"""
        try:
            if self._redis:
                await self._redis.delete(key)
                return True
            return False
        except Exception as e:
            self.logger.error(f"删除值失败: {e}")
            return False
    
    # ==================== 消息路由 ====================
    
    def register_handler(self, channel: str, handler: Callable) -> None:
        """注册消息处理器"""
        self._handlers[channel] = handler
        self.logger.debug(f"注册消息处理器: {channel}")
    
    def unregister_handler(self, channel: str) -> None:
        """取消注册消息处理器"""
        if channel in self._handlers:
            del self._handlers[channel]
    
    # ==================== 辅助方法 ====================
    
    def get_all_queues(self) -> List[str]:
        """获取所有队列名称"""
        if self._redis:
            # 返回Redis中的队列键
            return []  # 需要scan操作
        return list(self._task_queues.keys())
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        status = {
            "redis_connected": False,
            "local_mode": False,
            "subscribers": 0,
            "queues": {}
        }
        
        if self._redis:
            try:
                await self._redis.ping()
                status["redis_connected"] = True
            except Exception:
                pass
        else:
            status["local_mode"] = True
        
        status["subscribers"] = len(self._local_subscribers)
        for queue_name in self._task_queues:
            status["queues"][queue_name] = self._task_queues[queue_name].qsize()
        
        return status


# 全局消息总线实例
_message_bus: Optional[MessageBus] = None


async def get_message_bus() -> MessageBus:
    """获取消息总线实例"""
    global _message_bus
    if _message_bus is None:
        _message_bus = MessageBus()
        await _message_bus.connect()
    return _message_bus
