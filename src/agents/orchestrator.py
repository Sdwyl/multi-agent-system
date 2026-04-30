"""
调度Agent (Orchestrator)
负责任务分发、协调和状态管理
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.agent_base import AgentBase, AgentMessage, AgentStatus, AgentType
from ..core.message_bus import Message, MessageType
from ..core.workflow import WorkflowEngine, Workflow, WorkflowType
from ..utils.logger import get_logger
from ..utils.config import get_config


class OrchestratorAgent(AgentBase):
    """
    调度Agent
    负责协调其他Agent，处理任务分发和结果汇总
    """
    
    def __init__(self, agent_id: str = "orchestrator", config: Dict[str, Any] = None):
        """
        初始化调度Agent
        
        Args:
            agent_id: Agent唯一标识
            config: Agent配置
        """
        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.ORCHESTRATOR,
            name="调度协调器",
            config=config or {}
        )
        
        # 任务队列
        self._pending_tasks: Dict[str, Dict[str, Any]] = {}
        self._running_tasks: Dict[str, Dict[str, Any]] = {}
        self._completed_tasks: Dict[str, Dict[str, Any]] = {}
        
        # 注册的Agent
        self._registered_agents: Dict[str, AgentBase] = {}
        
        # 工作流引擎
        self._workflow_engine: Optional[WorkflowEngine] = None
        
        # 消息总线引用
        self._message_bus = None
    
    async def initialize(self) -> None:
        """初始化调度Agent"""
        await super().initialize()
        
        # 初始化工作流引擎
        self._workflow_engine = WorkflowEngine()
        
        # 注册默认任务处理器
        self.register_message_handler("task_create", self._handle_task_create)
        self.register_message_handler("task_status", self._handle_task_status)
        self.register_message_handler("task_cancel", self._handle_task_cancel)
        self.register_message_handler("workflow_execute", self._handle_workflow_execute)
        self.register_message_handler("agent_register", self._handle_agent_register)
        self.register_message_handler("agent_unregister", self._handle_agent_unregister)
        
        self.logger.info("调度Agent初始化完成")
    
    def register_agent(self, agent: AgentBase) -> bool:
        """
        注册Agent到调度器
        
        Args:
            agent: Agent实例
            
        Returns:
            是否成功
        """
        if agent.agent_id in self._registered_agents:
            self.logger.warning(f"Agent已注册: {agent.agent_id}")
            return False
        
        self._registered_agents[agent.agent_id] = agent
        self.logger.info(f"Agent已注册: {agent.name}")
        return True
    
    def unregister_agent(self, agent_id: str) -> bool:
        """
        注销Agent
        
        Args:
            agent_id: Agent ID
            
        Returns:
            是否成功
        """
        if agent_id in self._registered_agents:
            agent = self._registered_agents.pop(agent_id)
            self.logger.info(f"Agent已注销: {agent.name}")
            return True
        return False
    
    def get_registered_agents(self) -> List[Dict[str, Any]]:
        """获取所有注册的Agent"""
        return [
            {
                "agent_id": agent.agent_id,
                "name": agent.name,
                "type": agent.agent_type.value,
                "status": agent.status.value
            }
            for agent in self._registered_agents.values()
        ]
    
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """处理消息"""
        # 调度Agent主要处理协调类消息
        return None
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务"""
        task_type = task.get("type", "")
        
        if task_type == "dispatch":
            return await self._dispatch_task(task)
        elif task_type == "coordinate":
            return await self._coordinate_task(task)
        elif task_type == "monitor":
            return await self._monitor_agents(task)
        elif task_type == "workflow":
            return await self._execute_workflow(task)
        else:
            return {"success": False, "error": f"未知任务类型: {task_type}"}
    
    async def _dispatch_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        分发任务到指定Agent
        
        Args:
            task: 任务定义
            
        Returns:
            任务执行结果
        """
        target_agent = task.get("agent")
        action = task.get("action", "execute")
        params = task.get("params", {})
        
        if not target_agent:
            return {"success": False, "error": "未指定目标Agent"}
        
        # 查找目标Agent
        agent = self._registered_agents.get(target_agent)
        if not agent:
            return {"success": False, "error": f"Agent不存在: {target_agent}"}
        
        # 创建任务
        task_id = str(uuid.uuid4())
        task_info = {
            "id": task_id,
            "name": task.get("name", "未命名任务"),
            "agent_id": target_agent,
            "action": action,
            "params": params,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        
        self._pending_tasks[task_id] = task_info
        self._running_tasks[task_id] = task_info
        
        try:
            # 执行任务
            self.logger.info(f"分发任务到 {target_agent}: {task_id}")
            result = await agent.send_task({
                "type": action,
                **params
            })
            
            task_info["status"] = "completed" if result.get("success") else "failed"
            task_info["result"] = result
            task_info["completed_at"] = datetime.now().isoformat()
            
            return result
            
        except Exception as e:
            self.logger.error(f"任务执行失败: {e}")
            task_info["status"] = "failed"
            task_info["error"] = str(e)
            return {"success": False, "error": str(e)}
        finally:
            # 移动到已完成
            if task_id in self._running_tasks:
                del self._running_tasks[task_id]
            self._completed_tasks[task_id] = task_info
    
    async def _coordinate_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        协调多个Agent执行复杂任务
        
        Args:
            task: 任务定义
            
        Returns:
            协调结果
        """
        sub_tasks = task.get("sub_tasks", [])
        if not sub_tasks:
            return {"success": False, "error": "没有子任务"}
        
        results = []
        for sub_task in sub_tasks:
            result = await self._dispatch_task(sub_task)
            results.append(result)
            
            # 如果某个任务失败，根据配置决定是否继续
            if not result.get("success") and task.get("stop_on_error", True):
                break
        
        # 汇总结果
        success_count = sum(1 for r in results if r.get("success"))
        return {
            "success": success_count == len(results),
            "total": len(results),
            "success_count": success_count,
            "failed_count": len(results) - success_count,
            "results": results
        }
    
    async def _monitor_agents(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        监控所有Agent状态
        
        Args:
            task: 任务参数
            
        Returns:
            监控结果
        """
        agent_status = []
        for agent_id, agent in self._registered_agents.items():
            agent_status.append({
                "agent_id": agent_id,
                "name": agent.name,
                "status": agent.status.value,
                "stats": agent.stats
            })
        
        return {
            "success": True,
            "total_agents": len(self._registered_agents),
            "agents": agent_status,
            "pending_tasks": len(self._pending_tasks),
            "running_tasks": len(self._running_tasks),
            "completed_tasks": len(self._completed_tasks)
        }
    
    async def _execute_workflow(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工作流
        
        Args:
            task: 工作流任务
            
        Returns:
            工作流执行结果
        """
        workflow_data = task.get("workflow")
        initial_data = task.get("data", {})
        
        if not workflow_data:
            return {"success": False, "error": "未提供工作流定义"}
        
        # 构建工作流对象
        workflow = self._build_workflow(workflow_data)
        
        # 执行工作流
        if self._workflow_engine:
            result = await self._workflow_engine.execute_workflow(
                workflow,
                initial_data
            )
            return result
        else:
            return {"success": False, "error": "工作流引擎未初始化"}
    
    def _build_workflow(self, workflow_data: Dict[str, Any]) -> Workflow:
        """构建工作流对象"""
        from ..core.workflow import WorkflowStep, WorkflowType
        
        workflow_type = WorkflowType(workflow_data.get("type", "sequential"))
        
        workflow = Workflow(
            name=workflow_data.get("name", "工作流"),
            description=workflow_data.get("description"),
            workflow_type=workflow_type
        )
        
        # 构建步骤
        for step_data in workflow_data.get("steps", []):
            step = WorkflowStep(
                name=step_data.get("name", ""),
                agent=step_data.get("agent", ""),
                action=step_data.get("action", ""),
                params=step_data.get("params", {}),
                condition=step_data.get("condition"),
                retry=step_data.get("retry", 1),
                timeout=step_data.get("timeout", 300)
            )
            workflow.steps.append(step)
        
        return workflow
    
    # ==================== 消息处理器 ====================
    
    async def _handle_task_create(self, message: AgentMessage) -> AgentMessage:
        """处理任务创建"""
        task_data = message.content.get("task", {})
        task_id = str(uuid.uuid4())
        
        task_info = {
            "id": task_id,
            "name": task_data.get("name", "未命名任务"),
            "type": task_data.get("type", "dispatch"),
            "params": task_data.get("params", {}),
            "agent": task_data.get("agent"),
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        
        self._pending_tasks[task_id] = task_info
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="task_created",
            content={"task_id": task_id, "task": task_info},
            correlation_id=message.correlation_id
        )
    
    async def _handle_task_status(self, message: AgentMessage) -> AgentMessage:
        """处理任务状态查询"""
        task_id = message.content.get("task_id")
        
        if task_id:
            task = self._pending_tasks.get(task_id) or \
                   self._running_tasks.get(task_id) or \
                   self._completed_tasks.get(task_id)
            return AgentMessage(
                sender=self.agent_id,
                receiver=message.sender,
                message_type="task_status_response",
                content={"task": task},
                correlation_id=message.correlation_id
            )
        else:
            # 返回所有任务
            return AgentMessage(
                sender=self.agent_id,
                receiver=message.sender,
                message_type="task_status_response",
                content={
                    "pending": list(self._pending_tasks.values()),
                    "running": list(self._running_tasks.values()),
                    "completed": list(self._completed_tasks.values())
                },
                correlation_id=message.correlation_id
            )
    
    async def _handle_task_cancel(self, message: AgentMessage) -> AgentMessage:
        """处理任务取消"""
        task_id = message.content.get("task_id")
        
        if task_id in self._pending_tasks:
            del self._pending_tasks[task_id]
            return AgentMessage(
                sender=self.agent_id,
                receiver=message.sender,
                message_type="task_cancelled",
                content={"task_id": task_id},
                correlation_id=message.correlation_id
            )
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="error",
            content={"error": "任务不存在或无法取消"},
            correlation_id=message.correlation_id
        )
    
    async def _handle_workflow_execute(self, message: AgentMessage) -> AgentMessage:
        """处理工作流执行"""
        workflow_data = message.content.get("workflow", {})
        initial_data = message.content.get("data", {})
        
        workflow = self._build_workflow(workflow_data)
        
        if self._workflow_engine:
            result = await self._workflow_engine.execute_workflow(
                workflow,
                initial_data
            )
            return AgentMessage(
                sender=self.agent_id,
                receiver=message.sender,
                message_type="workflow_result",
                content=result,
                correlation_id=message.correlation_id
            )
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="error",
            content={"error": "工作流引擎未初始化"},
            correlation_id=message.correlation_id
        )
    
    async def _handle_agent_register(self, message: AgentMessage) -> AgentMessage:
        """处理Agent注册"""
        agent_info = message.content.get("agent")
        if agent_info:
            # agent_info应该是已实例化的Agent
            if hasattr(agent_info, 'agent_id'):
                self.register_agent(agent_info)
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="agent_registered",
            content={"agents": self.get_registered_agents()},
            correlation_id=message.correlation_id
        )
    
    async def _handle_agent_unregister(self, message: AgentMessage) -> AgentMessage:
        """处理Agent注销"""
        agent_id = message.content.get("agent_id")
        success = self.unregister_agent(agent_id) if agent_id else False
        
        return AgentMessage(
            sender=self.agent_id,
            receiver=message.sender,
            message_type="agent_unregistered",
            content={"success": success, "agent_id": agent_id},
            correlation_id=message.correlation_id
        )
    
    def get_tasks_summary(self) -> Dict[str, Any]:
        """获取任务摘要"""
        return {
            "pending": len(self._pending_tasks),
            "running": len(self._running_tasks),
            "completed": len(self._completed_tasks),
            "pending_tasks": list(self._pending_tasks.values())[:10],
            "running_tasks": list(self._running_tasks.values())[:10]
        }
