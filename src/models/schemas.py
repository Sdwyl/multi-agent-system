"""
数据模型模块
定义系统的数据结构和API Schema
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Agent类型"""
    ORCHESTRATOR = "orchestrator"
    CONTENT = "content"
    DATA = "data"
    MONITOR = "monitor"
    EXECUTOR = "executor"


class AgentStatus(str, Enum):
    """Agent状态"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PROCESSING = "processing"
    ERROR = "error"
    STOPPED = "stopped"


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowType(str, Enum):
    """工作流类型"""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    LOOP = "loop"


class StepStatus(str, Enum):
    """步骤状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


# ==================== Agent相关模型 ====================

class AgentStats(BaseModel):
    """Agent统计信息"""
    tasks_processed: int = 0
    tasks_success: int = 0
    tasks_failed: int = 0
    total_response_time: float = 0.0
    messages_received: int = 0
    messages_sent: int = 0


class AgentInfo(BaseModel):
    """Agent信息"""
    agent_id: str
    name: str
    type: AgentType
    status: AgentStatus
    config: Dict[str, Any] = {}
    stats: AgentStats = AgentStats()
    created_at: Optional[datetime] = None
    last_active: Optional[datetime] = None


class AgentCreate(BaseModel):
    """创建Agent请求"""
    name: str = Field(..., description="Agent名称")
    type: AgentType = Field(..., description="Agent类型")
    config: Dict[str, Any] = Field(default_factory=dict, description="Agent配置")


class AgentUpdate(BaseModel):
    """更新Agent请求"""
    name: Optional[str] = None
    status: Optional[AgentStatus] = None
    config: Optional[Dict[str, Any]] = None


# ==================== 任务相关模型 ====================

class TaskParams(BaseModel):
    """任务参数"""
    type: str = Field(..., description="任务类型")
    data: Dict[str, Any] = Field(default_factory=dict, description="任务数据")
    priority: int = Field(default=5, ge=1, le=10, description="优先级")
    timeout: int = Field(default=300, ge=1, description="超时时间（秒）")


class TaskCreate(BaseModel):
    """创建任务请求"""
    name: str = Field(..., description="任务名称")
    type: str = Field(..., description="任务类型")
    params: Dict[str, Any] = Field(default_factory=dict, description="任务参数")
    agent_id: Optional[str] = Field(None, description="指定执行的Agent")
    workflow_id: Optional[str] = Field(None, description="关联的工作流")
    scheduled_time: Optional[datetime] = Field(None, description="计划执行时间")


class TaskInfo(BaseModel):
    """任务信息"""
    id: str
    name: str
    type: str
    status: TaskStatus
    params: Dict[str, Any] = {}
    result: Optional[Dict[str, Any]] = None
    agent_id: Optional[str] = None
    workflow_id: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    elapsed: Optional[float] = None


class TaskListResponse(BaseModel):
    """任务列表响应"""
    items: List[TaskInfo]
    total: int
    page: int
    page_size: int


# ==================== 工作流相关模型 ====================

class WorkflowStepCreate(BaseModel):
    """创建工作流步骤"""
    name: str = Field(..., description="步骤名称")
    agent: str = Field(..., description="Agent名称")
    action: str = Field(..., description="执行动作")
    params: Dict[str, Any] = Field(default_factory=dict, description="步骤参数")
    condition: Optional[str] = Field(None, description="执行条件")
    retry: int = Field(default=1, ge=0, description="重试次数")
    timeout: int = Field(default=300, ge=1, description="超时时间")
    depends_on: List[str] = Field(default_factory=list, description="依赖步骤")


class WorkflowStepInfo(BaseModel):
    """工作流步骤信息"""
    id: str
    name: str
    agent: str
    action: str
    params: Dict[str, Any] = {}
    condition: Optional[str] = None
    status: StepStatus = StepStatus.PENDING
    retry: int = 1
    timeout: int = 300
    result: Optional[Dict[str, Any]] = None
    depends_on: List[str] = []


class WorkflowCreate(BaseModel):
    """创建工作流请求"""
    name: str = Field(..., description="工作流名称")
    description: Optional[str] = Field(None, description="工作流描述")
    workflow_type: WorkflowType = Field(..., description="工作流类型")
    steps: List[WorkflowStepCreate] = Field(default_factory=list, description="工作流步骤")
    condition: Optional[str] = Field(None, description="条件表达式")
    on_error: str = Field(default="stop", description="错误处理: stop/continue/skip")


class WorkflowInfo(BaseModel):
    """工作流信息"""
    id: str
    name: str
    description: Optional[str] = None
    workflow_type: WorkflowType
    steps: List[WorkflowStepInfo] = []
    status: str = "idle"
    created_at: datetime
    updated_at: Optional[datetime] = None


class WorkflowExecuteRequest(BaseModel):
    """执行工作流请求"""
    workflow_id: Optional[str] = Field(None, description="工作流ID")
    workflow: Optional[WorkflowCreate] = Field(None, description="工作流定义")
    data: Dict[str, Any] = Field(default_factory=dict, description="输入数据")


class WorkflowExecuteResponse(BaseModel):
    """执行工作流响应"""
    success: bool
    workflow_id: str
    workflow_name: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    elapsed: float


# ==================== 消息相关模型 ====================

class MessageSendRequest(BaseModel):
    """发送消息请求"""
    receiver: str = Field(..., description="接收者ID")
    message_type: str = Field(default="task", description="消息类型")
    content: Dict[str, Any] = Field(default_factory=dict, description="消息内容")
    priority: int = Field(default=5, ge=1, le=10, description="优先级")
    correlation_id: Optional[str] = Field(None, description="关联ID")


class MessageInfo(BaseModel):
    """消息信息"""
    id: str
    sender: str
    receiver: str
    message_type: str
    content: Dict[str, Any] = {}
    timestamp: datetime
    correlation_id: Optional[str] = None
    priority: int = 5


# ==================== 系统相关模型 ====================

class HealthCheckResponse(BaseModel):
    """健康检查响应"""
    status: str = "healthy"
    version: str = "1.0.0"
    timestamp: datetime
    components: Dict[str, Any] = {}


class SystemStats(BaseModel):
    """系统统计"""
    total_agents: int = 0
    active_agents: int = 0
    total_tasks: int = 0
    pending_tasks: int = 0
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_workflows: int = 0
    running_workflows: int = 0
    uptime: float = 0.0


class LogQuery(BaseModel):
    """日志查询"""
    level: Optional[str] = Field(None, description="日志级别")
    agent_id: Optional[str] = Field(None, description="Agent ID")
    keyword: Optional[str] = Field(None, description="关键词")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)


class LogEntry(BaseModel):
    """日志条目"""
    timestamp: datetime
    level: str
    logger: str
    message: str
    agent_id: Optional[str] = None
    task_id: Optional[str] = None
    metadata: Dict[str, Any] = {}


# ==================== 响应模型 ====================

class BaseResponse(BaseModel):
    """基础响应"""
    success: bool = True
    message: str = ""
    data: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = False
    error: str
    detail: Optional[str] = None
    code: str = "ERROR"
