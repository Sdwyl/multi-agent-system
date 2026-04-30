"""
监控Agent (Monitor Agent)
负责系统监控、异常检测、告警通知
"""

import asyncio
import psutil
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.agent_base import AgentBase, AgentMessage, AgentStatus, AgentType
from ..utils.logger import get_logger
from ..utils.config import get_config


class MonitorAgent(AgentBase):
    """
    监控Agent
    负责系统监控、异常检测、告警通知
    """
    
    def __init__(self, agent_id: str = "monitor", config: Dict[str, Any] = None):
        """
        初始化监控Agent
        
        Args:
            agent_id: Agent唯一标识
            config: Agent配置
        """
        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.MONITOR,
            name="系统监控器",
            config=config or {}
        )
        
        # 监控配置
        self.check_interval = config.get("check_interval", 60) if config else 60
        self.alert_threshold = config.get("alert_threshold", 3) if config else 3
        
        # 告警历史
        self._alert_history: List[Dict[str, Any]] = []
        self._max_alert_history = 100
        
        # 监控状态
        self._is_monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # 通知通道
        self._notification_channels: List[str] = config.get("notify_channels", ["log"]) if config else ["log"]
    
    async def initialize(self) -> None:
        """初始化监控Agent"""
        await super().initialize()
        
        # 注册监控处理器
        self.register_message_handler("check_status", self._handle_check_status)
        self.register_message_handler("get_metrics", self._handle_get_metrics)
        self.register_message_handler("set_alert", self._handle_set_alert)
        self.register_message_handler("get_alerts", self._handle_get_alerts)
        
        self.logger.info("监控Agent初始化完成")
    
    async def start(self) -> None:
        """启动监控Agent"""
        await super().start()
        
        # 启动持续监控
        if not self._is_monitoring:
            self._is_monitoring = True
            self._monitor_task = asyncio.create_task(self._monitoring_loop())
            self.logger.info("监控系统已启动")
    
    async def stop(self) -> None:
        """停止监控Agent"""
        self._is_monitoring = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        await super().stop()
    
    async def _monitoring_loop(self) -> None:
        """持续监控循环"""
        while self._is_monitoring:
            try:
                # 执行健康检查
                health_status = await self._check_system_health()
                
                # 检查告警条件
                await self._check_alert_conditions(health_status)
                
                # 等待下次检查
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"监控循环异常: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _check_system_health(self) -> Dict[str, Any]:
        """检查系统健康状态"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # 内存使用率
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # 磁盘使用率
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # 进程信息
            process_count = len(psutil.pids())
            
            health_status = {
                "timestamp": datetime.now().isoformat(),
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count,
                    "status": "warning" if cpu_percent > 80 else "normal"
                },
                "memory": {
                    "percent": memory_percent,
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "status": "warning" if memory_percent > 85 else "normal"
                },
                "disk": {
                    "percent": disk_percent,
                    "total_gb": round(disk.total / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "status": "warning" if disk_percent > 90 else "normal"
                },
                "processes": {
                    "count": process_count,
                    "status": "normal"
                },
                "overall_status": "healthy"
            }
            
            # 判断整体状态
            if cpu_percent > 90 or memory_percent > 95 or disk_percent > 95:
                health_status["overall_status"] = "critical"
            elif cpu_percent > 80 or memory_percent > 85 or disk_percent > 90:
                health_status["overall_status"] = "warning"
            
            return health_status
            
        except Exception as e:
            self.logger.error(f"健康检查失败: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "overall_status": "error",
                "error": str(e)
            }
    
    async def _check_alert_conditions(self, health_status: Dict[str, Any]) -> None:
        """检查告警条件"""
        overall_status = health_status.get("overall_status", "healthy")
        
        if overall_status in ["warning", "critical", "error"]:
            alert = {
                "timestamp": datetime.now().isoformat(),
                "level": "warning" if overall_status == "warning" else "critical",
                "status": health_status,
                "message": f"系统状态: {overall_status}"
            }
            
            await self._trigger_alert(alert)
    
    async def _trigger_alert(self, alert: Dict[str, Any]) -> None:
        """触发告警"""
        self._alert_history.append(alert)
        
        # 限制告警历史长度
        if len(self._alert_history) > self._max_alert_history:
            self._alert_history = self._alert_history[-self._max_alert_history:]
        
        # 发送告警通知
        for channel in self._notification_channels:
            await self._send_notification(channel, alert)
        
        self.logger.warning(f"告警触发: {alert['message']}")
    
    async def _send_notification(self, channel: str, alert: Dict[str, Any]) -> None:
        """发送告警通知"""
        if channel == "log":
            self.logger.warning(f"告警通知: {alert}")
        elif channel == "webhook":
            # 可以扩展为发送webhook
            self.logger.info(f"Webhook告警: {alert}")
        elif channel == "email":
            # 可以扩展为发送邮件
            self.logger.info(f"邮件告警: {alert}")
    
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """处理消息"""
        return None
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行监控任务"""
        action = task.get("action", task.get("type", "check"))
        
        if action == "check":
            return await self._check_system_health()
        elif action == "metrics":
            return await self._get_detailed_metrics(task)
        elif action == "alert":
            return await self._get_alert_summary(task)
        elif action == "performance":
            return await self._analyze_performance(task)
        else:
            return {"success": False, "error": f"未知动作: {action}"}
    
    async def _get_detailed_metrics(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取详细指标
        
        Args:
            task: 任务参数
                - metric_type: 指标类型 (cpu/memory/disk/network/all)
                
        Returns:
            详细指标
        """
        metric_type = task.get("metric_type", "all")
        
        self.logger.info(f"获取详细指标: {metric_type}")
        
        metrics = {}
        
        if metric_type in ["cpu", "all"]:
            metrics["cpu"] = {
                "percent": psutil.cpu_percent(interval=1, percpu=True),
                "count": psutil.cpu_count(),
                "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
                "stats": psutil.cpu_stats()._asdict()
            }
        
        if metric_type in ["memory", "all"]:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            metrics["memory"] = {
                "virtual": mem._asdict(),
                "swap": swap._asdict()
            }
        
        if metric_type in ["disk", "all"]:
            partitions = []
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    partitions.append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "fstype": partition.fstype,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent
                    })
                except PermissionError:
                    continue
            metrics["disk"] = {"partitions": partitions}
        
        if metric_type in ["network", "all"]:
            net_io = psutil.net_io_counters()
            metrics["network"] = {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
                "errin": net_io.errin,
                "errout": net_io.errout
            }
        
        if metric_type in ["process", "all"]:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            metrics["process"] = {
                "count": len(processes),
                "top_10_cpu": sorted(processes, key=lambda x: x.get('cpu_percent', 0), reverse=True)[:10],
                "top_10_memory": sorted(processes, key=lambda x: x.get('memory_percent', 0), reverse=True)[:10]
            }
        
        return {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics
        }
    
    async def _get_alert_summary(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """获取告警摘要"""
        hours = task.get("hours", 24)
        min_level = task.get("min_level", "info")
        
        # 过滤指定时间范围内的告警
        cutoff = datetime.now().timestamp() - hours * 3600
        recent_alerts = [
            a for a in self._alert_history
            if datetime.fromisoformat(a["timestamp"]).timestamp() > cutoff
        ]
        
        level_counts = {"critical": 0, "warning": 0, "info": 0}
        for alert in recent_alerts:
            level = alert.get("level", "info")
            level_counts[level] = level_counts.get(level, 0) + 1
        
        return {
            "success": True,
            "period_hours": hours,
            "total_alerts": len(recent_alerts),
            "level_counts": level_counts,
            "recent_alerts": recent_alerts[-10:]  # 最近10条
        }
    
    async def _analyze_performance(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """分析性能"""
        duration = task.get("duration", 60)  # 分析时长（秒）
        samples = task.get("samples", 10)  # 采样次数
        
        self.logger.info(f"性能分析: duration={duration}s, samples={samples}")
        
        sample_interval = duration / samples
        cpu_samples = []
        memory_samples = []
        
        for _ in range(samples):
            cpu_samples.append(psutil.cpu_percent(interval=sample_interval))
            memory_samples.append(psutil.virtual_memory().percent)
        
        return {
            "success": True,
            "duration": duration,
            "samples": samples,
            "cpu": {
                "samples": cpu_samples,
                "avg": round(sum(cpu_samples) / len(cpu_samples), 2),
                "max": max(cpu_samples),
                "min": min(cpu_samples)
            },
            "memory": {
                "samples": memory_samples,
                "avg": round(sum(memory_samples) / len(memory_samples), 2),
                "max": max(memory_samples),
                "min": min(memory_samples)
            },
            "timestamp": datetime.now().isoformat()
        }
    
    # ==================== 消息处理器 ====================
    
    async def _handle_check_status(self, message: AgentMessage) -> AgentMessage:
        """处理状态检查请求"""
        health_status = await self._check_system_health()
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="status_response",
            content=health_status,
            correlation_id=message.correlation_id
        )
    
    async def _handle_get_metrics(self, message: AgentMessage) -> AgentMessage:
        """处理获取指标请求"""
        result = await self._get_detailed_metrics(message.content)
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="metrics_response",
            content=result,
            correlation_id=message.correlation_id
        )
    
    async def _handle_set_alert(self, message: AgentMessage) -> AgentMessage:
        """处理设置告警请求"""
        # 可以动态调整告警阈值
        threshold = message.content.get("threshold")
        if threshold:
            self.alert_threshold = threshold
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="alert_set",
            content={"alert_threshold": self.alert_threshold},
            correlation_id=message.correlation_id
        )
    
    async def _handle_get_alerts(self, message: AgentMessage) -> AgentMessage:
        """处理获取告警请求"""
        hours = message.content.get("hours", 24)
        result = await self._get_alert_summary({"hours": hours})
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="alerts_response",
            content=result,
            correlation_id=message.correlation_id
        )
    
    def get_alert_history(self) -> List[Dict[str, Any]]:
        """获取告警历史"""
        return self._alert_history.copy()
