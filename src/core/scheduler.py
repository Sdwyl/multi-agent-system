"""
任务调度器模块
基于APScheduler的任务调度系统
"""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from ..utils.config import get_config
from ..utils.logger import get_logger


class TriggerType(Enum):
    """触发器类型"""
    INTERVAL = "interval"              # 间隔触发
    CRON = "cron"                      # Cron表达式触发
    DATE = "date"                      # 一次性日期触发


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"                 # 等待中
    RUNNING = "running"                 # 运行中
    COMPLETED = "completed"             # 已完成
    FAILED = "failed"                   # 失败
    CANCELLED = "cancelled"            # 已取消


@dataclass
class ScheduledTask:
    """计划任务"""
    id: str
    name: str
    func: Callable
    trigger_type: TriggerType
    trigger_args: Dict[str, Any]
    args: tuple = ()
    kwargs: Dict[str, Any] = None
    status: TaskStatus = TaskStatus.PENDING
    next_run_time: datetime = None
    last_run_time: datetime = None
    run_count: int = 0
    max_runs: int = None
    enabled: bool = True
    
    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}


class TaskScheduler:
    """
    任务调度器
    支持间隔触发、Cron触发和一次性触发
    """
    
    _instance: Optional['TaskScheduler'] = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化调度器"""
        if self._initialized:
            return
        self._initialized = True
        
        self.logger = get_logger()
        self.config = get_config()
        
        # 创建调度器
        jobstores = {
            'default': MemoryJobStore()
        }
        
        scheduler_config = self.config.scheduler
        executors = {
            'default': {
                'type': 'threadpool',
                'max_workers': scheduler_config.get('max_workers', 5)
            }
        }
        job_defaults = scheduler_config.get('job_defaults', {})
        
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=scheduler_config.get('timezone', 'Asia/Shanghai')
        )
        
        # 任务存储
        self._tasks: Dict[str, ScheduledTask] = {}
        
        # 事件回调
        self._event_callbacks: Dict[str, Callable] = {}
        
        # 运行状态
        self._running = False
    
    def _create_trigger(self, trigger_type: TriggerType, trigger_args: Dict[str, Any]):
        """创建触发器"""
        if trigger_type == TriggerType.INTERVAL:
            return IntervalTrigger(**trigger_args)
        elif trigger_type == TriggerType.CRON:
            return CronTrigger(**trigger_args)
        elif trigger_type == TriggerType.DATE:
            return DateTrigger(**trigger_args)
        else:
            raise ValueError(f"不支持的触发器类型: {trigger_type}")
    
    def _job_listener(self, event):
        """任务执行监听器"""
        if event.exception:
            self.logger.error(f"任务执行异常: {event.job_id}, error: {event.exception}")
            if event.job_id in self._tasks:
                self._tasks[event.job_id].status = TaskStatus.FAILED
        else:
            self.logger.debug(f"任务执行完成: {event.job_id}")
            if event.job_id in self._tasks:
                self._tasks[event.job_id].run_count += 1
                self._tasks[event.job_id].last_run_time = datetime.now()
                
                # 检查是否达到最大执行次数
                task = self._tasks[event.job_id]
                if task.max_runs and task.run_count >= task.max_runs:
                    self.remove_job(event.job_id)
                    task.status = TaskStatus.COMPLETED
    
    async def start(self) -> None:
        """启动调度器"""
        if self._running:
            return
        
        # 注册事件监听器
        self.scheduler.add_listener(
            self._job_listener,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )
        
        self.scheduler.start()
        self._running = True
        self.logger.info("任务调度器已启动")
    
    async def stop(self) -> None:
        """停止调度器"""
        if not self._running:
            return
        
        self.scheduler.shutdown(wait=True)
        self._running = False
        self.logger.info("任务调度器已停止")
    
    def add_interval_job(
        self,
        func: Callable,
        name: str,
        seconds: int = None,
        minutes: int = None,
        hours: int = None,
        start_date: datetime = None,
        end_date: datetime = None,
        max_runs: int = None,
        args: tuple = None,
        kwargs: Dict[str, Any] = None,
        id: str = None
    ) -> str:
        """
        添加间隔执行任务
        
        Args:
            func: 执行函数
            name: 任务名称
            seconds/minutes/hours: 间隔时间
            start_date: 开始时间
            end_date: 结束时间
            max_runs: 最大执行次数
            args: 位置参数
            kwargs: 关键字参数
            id: 任务ID
            
        Returns:
            任务ID
        """
        job_id = id or str(uuid.uuid4())
        
        trigger_args = {}
        if seconds:
            trigger_args['seconds'] = seconds
        if minutes:
            trigger_args['minutes'] = minutes
        if hours:
            trigger_args['hours'] = hours
        if start_date:
            trigger_args['start_date'] = start_date
        if end_date:
            trigger_args['end_date'] = end_date
        
        trigger = IntervalTrigger(**trigger_args)
        
        self.scheduler.add_job(
            func=func,
            trigger=trigger,
            id=job_id,
            name=name,
            args=args or (),
            kwargs=kwargs or {},
            replace_existing=True
        )
        
        # 存储任务信息
        self._tasks[job_id] = ScheduledTask(
            id=job_id,
            name=name,
            func=func,
            trigger_type=TriggerType.INTERVAL,
            trigger_args=trigger_args,
            args=args or (),
            kwargs=kwargs or {},
            max_runs=max_runs
        )
        
        self.logger.info(f"添加间隔任务: {name}, id={job_id}")
        return job_id
    
    def add_cron_job(
        self,
        func: Callable,
        name: str,
        cron_expr: str = None,
        year: int = None,
        month: int = None,
        day: int = None,
        hour: int = None,
        minute: int = None,
        second: int = None,
        day_of_week: str = None,
        max_runs: int = None,
        args: tuple = None,
        kwargs: Dict[str, Any] = None,
        id: str = None
    ) -> str:
        """
        添加Cron表达式任务
        
        Args:
            func: 执行函数
            name: 任务名称
            cron_expr: Cron表达式（简化形式）
            year/month/day/hour/minute/second/day_of_week: 各字段
            max_runs: 最大执行次数
            args: 位置参数
            kwargs: 关键字参数
            id: 任务ID
            
        Returns:
            任务ID
        """
        job_id = id or str(uuid.uuid4())
        
        trigger_args = {}
        if year:
            trigger_args['year'] = year
        if month:
            trigger_args['month'] = month
        if day:
            trigger_args['day'] = day
        if hour is not None:
            trigger_args['hour'] = hour
        if minute is not None:
            trigger_args['minute'] = minute
        if second is not None:
            trigger_args['second'] = second
        if day_of_week:
            trigger_args['day_of_week'] = day_of_week
        
        trigger = CronTrigger(**trigger_args)
        
        self.scheduler.add_job(
            func=func,
            trigger=trigger,
            id=job_id,
            name=name,
            args=args or (),
            kwargs=kwargs or {},
            replace_existing=True
        )
        
        # 存储任务信息
        self._tasks[job_id] = ScheduledTask(
            id=job_id,
            name=name,
            func=func,
            trigger_type=TriggerType.CRON,
            trigger_args=trigger_args,
            args=args or (),
            kwargs=kwargs or {},
            max_runs=max_runs
        )
        
        self.logger.info(f"添加Cron任务: {name}, id={job_id}")
        return job_id
    
    def add_date_job(
        self,
        func: Callable,
        name: str,
        run_date: datetime,
        args: tuple = None,
        kwargs: Dict[str, Any] = None,
        id: str = None
    ) -> str:
        """
        添加一次性任务
        
        Args:
            func: 执行函数
            name: 任务名称
            run_date: 执行时间
            args: 位置参数
            kwargs: 关键字参数
            id: 任务ID
            
        Returns:
            任务ID
        """
        job_id = id or str(uuid.uuid4())
        
        trigger = DateTrigger(run_date=run_date)
        
        self.scheduler.add_job(
            func=func,
            trigger=trigger,
            id=job_id,
            name=name,
            args=args or (),
            kwargs=kwargs or {},
            replace_existing=True
        )
        
        # 存储任务信息
        self._tasks[job_id] = ScheduledTask(
            id=job_id,
            name=name,
            func=func,
            trigger_type=TriggerType.DATE,
            trigger_args={'run_date': run_date.isoformat()},
            args=args or (),
            kwargs=kwargs or {}
        )
        
        self.logger.info(f"添加一次性任务: {name}, id={job_id}, run_date={run_date}")
        return job_id
    
    def run_job(self, job_id: str) -> bool:
        """
        立即执行任务
        
        Args:
            job_id: 任务ID
            
        Returns:
            是否成功
        """
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                job.modify(next_run_time=datetime.now())
                self.logger.info(f"触发立即执行任务: {job_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"触发任务失败: {e}")
            return False
    
    def remove_job(self, job_id: str) -> bool:
        """
        移除任务
        
        Args:
            job_id: 任务ID
            
        Returns:
            是否成功
        """
        try:
            self.scheduler.remove_job(job_id)
            if job_id in self._tasks:
                self._tasks[job_id].status = TaskStatus.CANCELLED
                del self._tasks[job_id]
            self.logger.info(f"移除任务: {job_id}")
            return True
        except Exception as e:
            self.logger.error(f"移除任务失败: {e}")
            return False
    
    def pause_job(self, job_id: str) -> bool:
        """暂停任务"""
        try:
            self.scheduler.pause_job(job_id)
            if job_id in self._tasks:
                self._tasks[job_id].enabled = False
            return True
        except Exception as e:
            self.logger.error(f"暂停任务失败: {e}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """恢复任务"""
        try:
            self.scheduler.resume_job(job_id)
            if job_id in self._tasks:
                self._tasks[job_id].enabled = True
            return True
        except Exception as e:
            self.logger.error(f"恢复任务失败: {e}")
            return False
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        job = self.scheduler.get_job(job_id)
        if job and job_id in self._tasks:
            task = self._tasks[job_id]
            return {
                "id": task.id,
                "name": task.name,
                "status": task.status.value,
                "trigger_type": task.trigger_type.value,
                "next_run_time": task.next_run_time.isoformat() if task.next_run_time else None,
                "last_run_time": task.last_run_time.isoformat() if task.last_run_time else None,
                "run_count": task.run_count,
                "max_runs": task.max_runs,
                "enabled": task.enabled
            }
        return None
    
    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """获取所有任务"""
        jobs = []
        for job_id, task in self._tasks.items():
            jobs.append({
                "id": task.id,
                "name": task.name,
                "status": task.status.value,
                "trigger_type": task.trigger_type.value,
                "next_run_time": task.next_run_time.isoformat() if task.next_run_time else None,
                "last_run_time": task.last_run_time.isoformat() if task.last_run_time else None,
                "run_count": task.run_count,
                "max_runs": task.max_runs,
                "enabled": task.enabled
            })
        return jobs
    
    def register_event_callback(self, event_type: str, callback: Callable) -> None:
        """注册事件回调"""
        self._event_callbacks[event_type] = callback
    
    def get_stats(self) -> Dict[str, Any]:
        """获取调度器统计"""
        return {
            "running": self._running,
            "total_tasks": len(self._tasks),
            "pending_tasks": sum(1 for t in self._tasks.values() if t.status == TaskStatus.PENDING),
            "running_tasks": sum(1 for t in self._tasks.values() if t.status == TaskStatus.RUNNING),
            "completed_tasks": sum(1 for t in self._tasks.values() if t.status == TaskStatus.COMPLETED),
            "failed_tasks": sum(1 for t in self._tasks.values() if t.status == TaskStatus.FAILED)
        }


# 需要导入 dataclass
from dataclasses import dataclass
