"""
API路由模块
定义系统的RESTful API接口
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ..models.schemas import (
    AgentInfo, AgentCreate, AgentUpdate, AgentStats,
    TaskCreate, TaskInfo, TaskListResponse,
    WorkflowCreate, WorkflowInfo, WorkflowExecuteRequest, WorkflowExecuteResponse,
    MessageSendRequest, MessageInfo,
    HealthCheckResponse, SystemStats,
    BaseResponse, ErrorResponse
)
from ..core.agent_base import AgentStatus
from ..core.message_bus import Message, MessageType
from ..utils.logger import get_logger

logger = get_logger()

# 创建路由
router = APIRouter(prefix="/api/v1", tags=["API"])

# 全局存储（实际项目中应使用数据库）
_tasks: Dict[str, TaskInfo] = {}
_workflows: Dict[str, WorkflowInfo] = {}
_messages: List[MessageInfo] = []

# Agent引用（由主程序注入）
_agents: Dict[str, Any] = {}
_orchestrator: Any = None
_message_bus: Any = None
_scheduler: Any = None


def init_routes(agents: Dict, orchestrator, message_bus, scheduler):
    """初始化路由，注入依赖"""
    global _agents, _orchestrator, _message_bus, _scheduler
    _agents = agents
    _orchestrator = orchestrator
    _message_bus = message_bus
    _scheduler = scheduler


# ==================== 健康检查 ====================

@router.get("/health", response_model=HealthCheckResponse, tags=["系统"])
async def health_check():
    """健康检查接口"""
    components = {}
    
    # 检查Redis
    if _message_bus:
        components["message_bus"] = await _message_bus.health_check()
    
    # 检查各Agent
    for agent_id, agent in _agents.items():
        components[f"agent_{agent_id}"] = {
            "status": agent.status.value,
            "running": agent._running if hasattr(agent, '_running') else False
        }
    
    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now(),
        components=components
    )


@router.get("/stats", response_model=SystemStats, tags=["系统"])
async def get_system_stats():
    """获取系统统计信息"""
    total_agents = len(_agents)
    active_agents = sum(1 for a in _agents.values() if a.status in [AgentStatus.RUNNING, AgentStatus.PROCESSING])
    
    task_stats = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
    for task in _tasks.values():
        if task.status == "pending":
            task_stats["pending"] += 1
        elif task.status == "running":
            task_stats["running"] += 1
        elif task.status == "completed":
            task_stats["completed"] += 1
        elif task.status == "failed":
            task_stats["failed"] += 1
    
    return SystemStats(
        total_agents=total_agents,
        active_agents=active_agents,
        total_tasks=len(_tasks),
        pending_tasks=task_stats["pending"],
        running_tasks=task_stats["running"],
        completed_tasks=task_stats["completed"],
        failed_tasks=task_stats["failed"],
        total_workflows=len(_workflows),
        running_workflows=0
    )


# ==================== Agent管理 ====================

@router.get("/agents", response_model=List[AgentInfo], tags=["Agent"])
async def list_agents():
    """获取所有Agent列表"""
    agents = []
    for agent_id, agent in _agents.items():
        agents.append(AgentInfo(
            agent_id=agent.agent_id,
            name=agent.name,
            type=agent.agent_type.value,
            status=agent.status.value,
            config=agent.config,
            stats=AgentStats(**agent.stats),
            last_active=datetime.now()
        ))
    return agents


@router.get("/agents/{agent_id}", response_model=AgentInfo, tags=["Agent"])
async def get_agent(agent_id: str):
    """获取指定Agent信息"""
    if agent_id not in _agents:
        raise HTTPException(status_code=404, detail=f"Agent不存在: {agent_id}")
    
    agent = _agents[agent_id]
    return AgentInfo(
        agent_id=agent.agent_id,
        name=agent.name,
        type=agent.agent_type.value,
        status=agent.status.value,
        config=agent.config,
        stats=AgentStats(**agent.stats),
        last_active=datetime.now()
    )


@router.post("/agents", response_model=AgentInfo, tags=["Agent"])
async def create_agent(agent_data: AgentCreate):
    """创建新Agent（仅支持自定义Agent）"""
    # 这里简化处理，实际应该根据类型创建对应的Agent
    return AgentInfo(
        agent_id=str(uuid.uuid4()),
        name=agent_data.name,
        type=agent_data.type,
        status="idle",
        config=agent_data.config
    )


@router.put("/agents/{agent_id}", response_model=AgentInfo, tags=["Agent"])
async def update_agent(agent_id: str, agent_data: AgentUpdate):
    """更新Agent配置"""
    if agent_id not in _agents:
        raise HTTPException(status_code=404, detail=f"Agent不存在: {agent_id}")
    
    agent = _agents[agent_id]
    
    if agent_data.name:
        agent.name = agent_data.name
    if agent_data.config:
        agent.config.update(agent_data.config)
    
    return AgentInfo(
        agent_id=agent.agent_id,
        name=agent.name,
        type=agent.agent_type.value,
        status=agent.status.value,
        config=agent.config,
        stats=AgentStats(**agent.stats)
    )


@router.get("/agents/{agent_id}/tasks", response_model=List[TaskInfo], tags=["Agent"])
async def get_agent_tasks(agent_id: str):
    """获取Agent的任务列表"""
    if agent_id not in _agents:
        raise HTTPException(status_code=404, detail=f"Agent不存在: {agent_id}")
    
    agent_tasks = [task for task in _tasks.values() if task.agent_id == agent_id]
    return agent_tasks


# ==================== 任务管理 ====================

@router.post("/tasks", response_model=TaskInfo, tags=["任务"])
async def create_task(task_data: TaskCreate):
    """创建新任务"""
    task_id = str(uuid.uuid4())
    
    task = TaskInfo(
        id=task_id,
        name=task_data.name,
        type=task_data.type,
        status="pending",
        params=task_data.params,
        agent_id=task_data.agent_id,
        workflow_id=task_data.workflow_id,
        created_at=datetime.now()
    )
    
    _tasks[task_id] = task
    
    # 如果指定了Agent，直接执行
    if task_data.agent_id and task_data.agent_id in _agents:
        agent = _agents[task_data.agent_id]
        task.status = "running"
        task.started_at = datetime.now()
        
        try:
            result = await agent.send_task({
                "type": task_data.type,
                **task_data.params
            })
            
            task.result = result
            task.status = "completed" if result.get("success") else "failed"
            task.completed_at = datetime.now()
            
            if "elapsed" in result:
                task.elapsed = result["elapsed"]
                
        except Exception as e:
            task.status = "failed"
            task.error = str(e)
            task.completed_at = datetime.now()
    
    return task


@router.get("/tasks", response_model=TaskListResponse, tags=["任务"])
async def list_tasks(
    status: Optional[str] = Query(None, description="任务状态过滤"),
    agent_id: Optional[str] = Query(None, description="Agent ID过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量")
):
    """获取任务列表"""
    filtered_tasks = list(_tasks.values())
    
    if status:
        filtered_tasks = [t for t in filtered_tasks if t.status == status]
    if agent_id:
        filtered_tasks = [t for t in filtered_tasks if t.agent_id == agent_id]
    
    # 排序
    filtered_tasks.sort(key=lambda x: x.created_at, reverse=True)
    
    # 分页
    total = len(filtered_tasks)
    start = (page - 1) * page_size
    end = start + page_size
    items = filtered_tasks[start:end]
    
    return TaskListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/tasks/{task_id}", response_model=TaskInfo, tags=["任务"])
async def get_task(task_id: str):
    """获取任务详情"""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    
    return _tasks[task_id]


@router.delete("/tasks/{task_id}", response_model=BaseResponse, tags=["任务"])
async def cancel_task(task_id: str):
    """取消任务"""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    
    task = _tasks[task_id]
    
    if task.status in ["completed", "failed", "cancelled"]:
        return BaseResponse(success=False, message="任务已完成或已取消")
    
    task.status = "cancelled"
    task.completed_at = datetime.now()
    
    return BaseResponse(success=True, message="任务已取消")


# ==================== 工作流管理 ====================

@router.post("/workflows", response_model=WorkflowInfo, tags=["工作流"])
async def create_workflow(workflow_data: WorkflowCreate):
    """创建新工作流"""
    workflow_id = str(uuid.uuid4())
    
    # 构建工作流步骤
    steps = []
    for step_data in workflow_data.steps:
        steps.append(WorkflowStepInfo(
            id=str(uuid.uuid4()),
            name=step_data.name,
            agent=step_data.agent,
            action=step_data.action,
            params=step_data.params,
            condition=step_data.condition,
            retry=step_data.retry,
            timeout=step_data.timeout
        ))
    
    workflow = WorkflowInfo(
        id=workflow_id,
        name=workflow_data.name,
        description=workflow_data.description,
        workflow_type=workflow_data.workflow_type,
        steps=steps,
        status="created",
        created_at=datetime.now()
    )
    
    _workflows[workflow_id] = workflow
    
    return workflow


@router.get("/workflows", response_model=List[WorkflowInfo], tags=["工作流"])
async def list_workflows():
    """获取工作流列表"""
    return list(_workflows.values())


@router.get("/workflows/{workflow_id}", response_model=WorkflowInfo, tags=["工作流"])
async def get_workflow(workflow_id: str):
    """获取工作流详情"""
    if workflow_id not in _workflows:
        raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_id}")
    
    return _workflows[workflow_id]


@router.post("/workflows/execute", response_model=WorkflowExecuteResponse, tags=["工作流"])
async def execute_workflow(request: WorkflowExecuteRequest):
    """执行工作流"""
    workflow_id = request.workflow_id
    workflow_data = request.workflow
    
    if not workflow_id and not workflow_data:
        raise HTTPException(status_code=400, detail="必须提供workflow_id或workflow定义")
    
    # 如果使用已创建的工作流
    if workflow_id and workflow_id in _workflows:
        existing_workflow = _workflows[workflow_id]
        # 转换为执行格式
        from ..core.workflow import Workflow as CoreWorkflow, WorkflowStep, WorkflowType
        
        core_workflow = CoreWorkflow(
            name=existing_workflow.name,
            description=existing_workflow.description,
            workflow_type=WorkflowType(existing_workflow.workflow_type.value)
        )
        
        for step in existing_workflow.steps:
            core_workflow.steps.append(WorkflowStep(
                name=step.name,
                agent=step.agent,
                action=step.action,
                params=step.params,
                condition=step.condition,
                retry=step.retry,
                timeout=step.timeout
            ))
        
        workflow_id = None  # 使用新ID执行
    else:
        # 从请求创建工作流
        from ..core.workflow import Workflow as CoreWorkflow, WorkflowStep, WorkflowType
        
        core_workflow = CoreWorkflow(
            name=workflow_data.name,
            description=workflow_data.description,
            workflow_type=WorkflowType(workflow_data.workflow_type.value)
        )
        
        for step_data in workflow_data.steps:
            core_workflow.steps.append(WorkflowStep(
                name=step_data.name,
                agent=step_data.agent,
                action=step_data.action,
                params=step_data.params,
                condition=step_data.condition,
                retry=step_data.retry,
                timeout=step_data.timeout
            ))
    
    # 注册步骤处理器
    from ..core.workflow import get_workflow_engine
    engine = get_workflow_engine()
    
    for agent_id, agent in _agents.items():
        for action in ["execute", "generate", "analyze", "send", "collect"]:
            async def make_handler(a, act):
                async def handler(**kwargs):
                    return await a.execute_task({"action": act, **kwargs})
                return handler
            engine.register_step_handler(agent_id, act, await make_handler(agent, action))
    
    # 执行工作流
    try:
        result = await engine.execute_workflow(core_workflow, request.data, workflow_id)
        return WorkflowExecuteResponse(
            success=result.get("success", False),
            workflow_id=result.get("workflow_id", ""),
            workflow_name=result.get("workflow_name", ""),
            result=result.get("result"),
            error=result.get("error"),
            elapsed=result.get("elapsed", 0)
        )
    except Exception as e:
        return WorkflowExecuteResponse(
            success=False,
            workflow_id=str(uuid.uuid4()),
            workflow_name=core_workflow.name,
            error=str(e),
            elapsed=0
        )


@router.delete("/workflows/{workflow_id}", response_model=BaseResponse, tags=["工作流"])
async def delete_workflow(workflow_id: str):
    """删除工作流"""
    if workflow_id not in _workflows:
        raise HTTPException(status_code=404, detail=f"工作流不存在: {workflow_id}")
    
    del _workflows[workflow_id]
    
    return BaseResponse(success=True, message="工作流已删除")


# ==================== 消息管理 ====================

@router.post("/messages/send", response_model=MessageInfo, tags=["消息"])
async def send_message(message_data: MessageSendRequest):
    """发送消息"""
    message = Message(
        sender="api",
        receiver=message_data.receiver,
        message_type=MessageType.TASK,
        channel=f"agent:{message_data.receiver}",
        content=message_data.content,
        correlation_id=message_data.correlation_id or str(uuid.uuid4()),
        priority=message_data.priority
    )
    
    if _message_bus:
        await _message_bus.publish(message)
    
    return MessageInfo(
        id=message.id,
        sender=message.sender,
        receiver=message.receiver,
        message_type=message.message_type.value,
        content=message.content,
        timestamp=message.timestamp,
        correlation_id=message.correlation_id,
        priority=message.priority
    )


@router.get("/messages", response_model=List[MessageInfo], tags=["消息"])
async def list_messages(
    sender: Optional[str] = Query(None, description="发送者过滤"),
    receiver: Optional[str] = Query(None, description="接收者过滤"),
    limit: int = Query(50, ge=1, le=100, description="返回数量")
):
    """获取消息列表"""
    filtered = _messages
    
    if sender:
        filtered = [m for m in filtered if m.sender == sender]
    if receiver:
        filtered = [m for m in filtered if m.receiver == receiver]
    
    return filtered[-limit:]


# ==================== 日志接口 ====================

@router.get("/logs", tags=["日志"])
async def get_logs(
    level: Optional[str] = Query(None, description="日志级别"),
    keyword: Optional[str] = Query(None, description="关键词"),
    limit: int = Query(50, ge=1, le=200, description="返回数量")
):
    """获取系统日志"""
    # 实际项目中应该从日志系统获取
    logs = [
        {
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "logger": "system",
            "message": "系统运行正常"
        }
    ]
    
    if keyword:
        logs = [l for l in logs if keyword.lower() in l["message"].lower()]
    
    return {"logs": logs[-limit:], "total": len(logs)}
