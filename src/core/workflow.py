"""
工作流引擎模块
支持串行、并行、条件分支等复杂工作流
"""

import asyncio
import uuid
import operator
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

from ..utils.logger import get_logger


class WorkflowType(Enum):
    """工作流类型"""
    SEQUENTIAL = "sequential"          # 串行执行
    PARALLEL = "parallel"              # 并行执行
    CONDITIONAL = "conditional"        # 条件分支
    LOOP = "loop"                       # 循环执行


class StepStatus(Enum):
    """步骤状态"""
    PENDING = "pending"                # 等待执行
    RUNNING = "running"                # 执行中
    SUCCESS = "success"                # 成功
    FAILED = "failed"                  # 失败
    SKIPPED = "skipped"                # 跳过


@dataclass
class WorkflowStep:
    """工作流步骤"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    agent: str = ""                    # 执行的Agent名称
    action: str = ""                   # 执行的动作
    params: Dict[str, Any] = field(default_factory=dict)  # 步骤参数
    condition: str = ""                # 条件表达式
    retry: int = 1                     # 重试次数
    timeout: int = 300                 # 超时时间（秒）
    depends_on: List[str] = field(default_factory=list)    # 依赖步骤
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "agent": self.agent,
            "action": self.action,
            "params": self.params,
            "condition": self.condition,
            "retry": self.retry,
            "timeout": self.timeout,
            "depends_on": self.depends_on
        }


@dataclass
class WorkflowContext:
    """工作流执行上下文"""
    workflow_id: str
    data: Dict[str, Any] = field(default_factory=dict)     # 工作流数据
    results: Dict[str, Any] = field(default_factory=dict)   # 步骤执行结果
    step_status: Dict[str, StepStatus] = field(default_factory=dict)  # 步骤状态
    start_time: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_result(self, step_id: str) -> Any:
        """获取指定步骤的结果"""
        return self.results.get(step_id)
    
    def set_result(self, step_id: str, result: Any) -> None:
        """设置指定步骤的结果"""
        self.results[step_id] = result
    
    def get_step_status(self, step_id: str) -> StepStatus:
        """获取步骤状态"""
        return self.step_status.get(step_id, StepStatus.PENDING)
    
    def set_step_status(self, step_id: str, status: StepStatus) -> None:
        """设置步骤状态"""
        self.step_status[step_id] = status


@dataclass
class Workflow:
    """工作流定义"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    workflow_type: WorkflowType = WorkflowType.SEQUENTIAL
    steps: List[WorkflowStep] = field(default_factory=list)
    branches: List['Workflow'] = field(default_factory=list)  # 并行分支
    true_branch: 'Workflow' = None                             # 条件为真分支
    false_branch: 'Workflow' None                              # 条件为假分支
    condition: str = ""                                         # 条件表达式
    max_parallel: int = 10                                      # 最大并行数
    on_error: str = "stop"                                     # 错误处理: stop/continue/skip
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "workflow_type": self.workflow_type.value,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at.isoformat(),
            "enabled": self.enabled
        }


class WorkflowEngine:
    """
    工作流引擎
    支持串行、并行、条件分支工作流的执行
    """
    
    def __init__(self):
        """初始化工作流引擎"""
        self.logger = get_logger()
        self._step_handlers: Dict[str, Callable] = {}
        self._running_workflows: Dict[str, WorkflowContext] = {}
    
    def register_step_handler(self, agent: str, action: str, handler: Callable) -> None:
        """
        注册步骤处理器
        
        Args:
            agent: Agent名称
            action: 动作名称
            handler: 处理函数
        """
        key = f"{agent}:{action}"
        self._step_handlers[key] = handler
        self.logger.debug(f"注册步骤处理器: {key}")
    
    async def execute_workflow(
        self,
        workflow: Workflow,
        initial_data: Dict[str, Any] = None,
        workflow_id: str = None
    ) -> Dict[str, Any]:
        """
        执行工作流
        
        Args:
            workflow: 工作流定义
            initial_data: 初始数据
            workflow_id: 工作流执行ID
            
        Returns:
            执行结果
        """
        exec_id = workflow_id or str(uuid.uuid4())
        context = WorkflowContext(
            workflow_id=exec_id,
            data=initial_data or {}
        )
        
        self._running_workflows[exec_id] = context
        self.logger.info(f"开始执行工作流: {workflow.name}, id={exec_id}")
        
        try:
            start_time = datetime.now()
            
            if workflow.workflow_type == WorkflowType.SEQUENTIAL:
                result = await self._execute_sequential(workflow, context)
            elif workflow.workflow_type == WorkflowType.PARALLEL:
                result = await self._execute_parallel(workflow, context)
            elif workflow.workflow_type == WorkflowType.CONDITIONAL:
                result = await self._execute_conditional(workflow, context)
            elif workflow.workflow_type == WorkflowType.LOOP:
                result = await self._execute_loop(workflow, context)
            else:
                raise ValueError(f"不支持的工作流类型: {workflow.workflow_type}")
            
            elapsed = (datetime.now() - start_time).total_seconds()
            
            return {
                "success": True,
                "workflow_id": exec_id,
                "workflow_name": workflow.name,
                "result": result,
                "context": context.data,
                "elapsed": elapsed,
                "steps_completed": len(context.results)
            }
            
        except Exception as e:
            self.logger.error(f"工作流执行失败: {e}")
            return {
                "success": False,
                "workflow_id": exec_id,
                "error": str(e)
            }
        finally:
            if exec_id in self._running_workflows:
                del self._running_workflows[exec_id]
    
    async def _execute_sequential(self, workflow: Workflow, context: WorkflowContext) -> Any:
        """执行串行工作流"""
        for step in workflow.steps:
            # 检查条件
            if step.condition and not self._evaluate_condition(step.condition, context):
                context.set_step_status(step.id, StepStatus.SKIPPED)
                self.logger.info(f"步骤跳过 (条件不满足): {step.name}")
                continue
            
            # 执行步骤
            result = await self._execute_step(step, context)
            context.set_result(step.id, result)
            
            # 检查依赖
            if not result.get("success", False) and workflow.on_error == "stop":
                context.set_step_status(step.id, StepStatus.FAILED)
                raise Exception(f"步骤执行失败: {step.name}")
        
        return context.data
    
    async def _execute_parallel(self, workflow: Workflow, context: WorkflowContext) -> Any:
        """执行并行工作流"""
        # 获取所有可执行的步骤（无依赖或依赖已满足）
        executable_steps = []
        for step in workflow.steps:
            if self._can_execute_step(step, context):
                executable_steps.append(step)
        
        if not executable_steps:
            return context.data
        
        # 限制并行数
        max_parallel = min(len(executable_steps), workflow.max_parallel)
        
        # 创建并行任务
        tasks = []
        for step in executable_steps[:max_parallel]:
            task = self._execute_step(step, context)
            tasks.append((step, task))
        
        # 等待所有任务完成
        results = await asyncio.gather(
            *[t[1] for t in tasks],
            return_exceptions=True
        )
        
        # 处理结果
        for i, (step, _) in enumerate(tasks):
            result = results[i]
            if isinstance(result, Exception):
                context.set_result(step.id, {"success": False, "error": str(result)})
                if workflow.on_error == "stop":
                    raise result
            else:
                context.set_result(step.id, result)
        
        # 如果还有剩余步骤，继续执行
        remaining = executable_steps[max_parallel:]
        if remaining:
            for step in remaining:
                result = await self._execute_step(step, context)
                context.set_result(step.id, result)
        
        return context.data
    
    async def _execute_conditional(self, workflow: Workflow, context: WorkflowContext) -> Any:
        """执行条件分支工作流"""
        condition_result = self._evaluate_condition(workflow.condition, context)
        
        if condition_result and workflow.true_branch:
            return await self.execute_workflow(workflow.true_branch, context.data)
        elif not condition_result and workflow.false_branch:
            return await self.execute_workflow(workflow.false_branch, context.data)
        
        return context.data
    
    async def _execute_loop(self, workflow: Workflow, context: WorkflowContext) -> Any:
        """执行循环工作流"""
        max_iterations = context.data.get("_loop_max_iterations", 10)
        current_iteration = context.data.get("_loop_iteration", 0)
        
        while current_iteration < max_iterations:
            context.data["_loop_iteration"] = current_iteration
            
            try:
                await self._execute_sequential(workflow, context)
            except Exception as e:
                if workflow.on_error == "stop":
                    raise
                self.logger.warning(f"循环步骤执行异常: {e}")
            
            current_iteration += 1
            
            # 检查退出条件
            if "_loop_exit_condition" in context.data:
                if self._evaluate_condition(context.data["_loop_exit_condition"], context):
                    break
        
        return context.data
    
    async def _execute_step(self, step: WorkflowStep, context: WorkflowContext) -> Dict[str, Any]:
        """
        执行单个步骤
        
        Args:
            step: 步骤定义
            context: 执行上下文
            
        Returns:
            执行结果
        """
        context.set_step_status(step.id, StepStatus.RUNNING)
        self.logger.info(f"执行步骤: {step.name}")
        
        # 查找处理器
        handler_key = f"{step.agent}:{step.action}"
        handler = self._step_handlers.get(handler_key)
        
        if not handler:
            return {
                "success": False,
                "error": f"未找到处理器: {handler_key}"
            }
        
        # 执行（带重试）
        last_error = None
        for attempt in range(step.retry):
            try:
                # 构建执行参数
                exec_params = {
                    **step.params,
                    "context": context,
                    "step_id": step.id
                }
                
                # 执行处理函数
                if asyncio.iscoroutinefunction(handler):
                    result = await asyncio.wait_for(
                        handler(**exec_params),
                        timeout=step.timeout
                    )
                else:
                    result = await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: handler(**exec_params)
                    )
                
                context.set_step_status(step.id, StepStatus.SUCCESS)
                return {"success": True, "data": result}
                
            except asyncio.TimeoutError:
                last_error = f"步骤执行超时: {step.name}"
                self.logger.warning(f"{last_error}, 重试 {attempt + 1}/{step.retry}")
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"步骤执行异常: {e}, 重试 {attempt + 1}/{step.retry}")
        
        context.set_step_status(step.id, StepStatus.FAILED)
        return {"success": False, "error": last_error}
    
    def _can_execute_step(self, step: WorkflowStep, context: WorkflowContext) -> bool:
        """检查步骤是否可以执行"""
        for dep_id in step.depends_on:
            status = context.get_step_status(dep_id)
            if status != StepStatus.SUCCESS:
                return False
        return True
    
    def _evaluate_condition(self, condition: str, context: WorkflowContext) -> bool:
        """
        评估条件表达式
        
        支持的表达式格式:
        - data.key == value
        - data.key > value
        - data.key < value
        - data.key in [value1, value2]
        - data.key not in [value1, value2]
        - results.step_id.success
        """
        if not condition:
            return True
        
        try:
            # 简单的表达式解析
            condition = condition.strip()
            
            # 处理比较操作符
            operators = {
                '==': operator.eq,
                '!=': operator.ne,
                '>': operator.gt,
                '>=': operator.ge,
                '<': operator.lt,
                '<=': operator.le,
                ' in ': lambda a, b: a in b,
                ' not in ': lambda a, b: a not in b
            }
            
            for op_str, op_func in operators.items():
                if op_str in condition:
                    left, right = condition.split(op_str, 1)
                    left = left.strip()
                    right = right.strip()
                    
                    # 获取左值
                    if left.startswith('data.'):
                        key = left[5:]
                        left_value = self._get_nested_value(context.data, key)
                    elif left.startswith('results.'):
                        key = left[8:]
                        step_id, result_key = key.split('.', 1) if '.' in key else (key, None)
                        step_result = context.get_result(step_id)
                        left_value = step_result.get(result_key) if step_result else None
                    else:
                        left_value = context.data.get(left)
                    
                    # 解析右值
                    right_value = self._parse_value(right)
                    
                    return op_func(left_value, right_value)
            
            # 默认返回True（无条件）
            return True
            
        except Exception as e:
            self.logger.warning(f"条件评估失败: {condition}, {e}")
            return False
    
    def _get_nested_value(self, data: Dict, key: str) -> Any:
        """获取嵌套字典的值"""
        keys = key.split('.')
        value = data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None
        return value
    
    def _parse_value(self, value_str: str) -> Any:
        """解析值字符串"""
        value_str = value_str.strip()
        
        # 布尔值
        if value_str.lower() == 'true':
            return True
        if value_str.lower() == 'false':
            return False
        if value_str.lower() == 'none' or value_str.lower() == 'null':
            return None
        
        # 数字
        try:
            if '.' in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            pass
        
        # 列表
        if value_str.startswith('[') and value_str.endswith(']'):
            items = value_str[1:-1].split(',')
            return [self._parse_value(i.strip()) for i in items]
        
        # 字符串（去除引号）
        if (value_str.startswith('"') and value_str.endswith('"')) or \
           (value_str.startswith("'") and value_str.endswith("'")):
            return value_str[1:-1]
        
        return value_str
    
    def get_running_workflow(self, workflow_id: str) -> Optional[WorkflowContext]:
        """获取正在运行的工作流上下文"""
        return self._running_workflows.get(workflow_id)
    
    def list_running_workflows(self) -> List[str]:
        """列出所有正在运行的工作流ID"""
        return list(self._running_workflows.keys())


# 全局工作流引擎实例
_workflow_engine: Optional[WorkflowEngine] = None


def get_workflow_engine() -> WorkflowEngine:
    """获取工作流引擎实例"""
    global _workflow_engine
    if _workflow_engine is None:
        _workflow_engine = WorkflowEngine()
    return _workflow_engine
