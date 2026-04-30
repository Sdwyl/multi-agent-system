"""
Agent测试模块
测试各Agent的基本功能
"""

import asyncio
import pytest
from datetime import datetime

# 导入被测试的模块
import sys
sys.path.insert(0, 'src')

from src.core.agent_base import AgentBase, AgentMessage, AgentStatus, AgentType
from src.agents.orchestrator import OrchestratorAgent
from src.agents.content_agent import ContentAgent
from src.agents.data_agent import DataAgent
from src.agents.monitor_agent import MonitorAgent
from src.agents.executor_agent import ExecutorAgent


class TestAgentBase:
    """测试Agent基类"""
    
    @pytest.mark.asyncio
    async def test_agent_creation(self):
        """测试Agent创建"""
        class TestAgent(AgentBase):
            async def process_message(self, message):
                return None
            
            async def execute_task(self, task):
                return {"success": True, "result": "test"}
        
        agent = TestAgent(
            agent_id="test_agent",
            agent_type=AgentType.CUSTOM,
            name="测试Agent"
        )
        
        assert agent.agent_id == "test_agent"
        assert agent.name == "测试Agent"
        assert agent.status == AgentStatus.IDLE
    
    @pytest.mark.asyncio
    async def test_agent_initialize(self):
        """测试Agent初始化"""
        class TestAgent(AgentBase):
            async def process_message(self, message):
                return None
            
            async def execute_task(self, task):
                return {"success": True}
        
        agent = TestAgent("test", AgentType.CUSTOM)
        await agent.initialize()
        
        assert agent.status == AgentStatus.IDLE
    
    @pytest.mark.asyncio
    async def test_agent_execute_task(self):
        """测试Agent任务执行"""
        class TestAgent(AgentBase):
            async def process_message(self, message):
                return None
            
            async def execute_task(self, task):
                return {"success": True, "result": task.get("data", "default")}
        
        agent = TestAgent("test", AgentType.CUSTOM)
        await agent.initialize()
        
        result = await agent.send_task({"data": "test_data"})
        
        assert result["success"] == True
        assert result["result"] == "test_data"


class TestOrchestratorAgent:
    """测试调度Agent"""
    
    @pytest.mark.asyncio
    async def test_orchestrator_creation(self):
        """测试调度Agent创建"""
        agent = OrchestratorAgent()
        await agent.initialize()
        
        assert agent.agent_id == "orchestrator"
        assert agent.name == "调度协调器"
        assert agent.status == AgentStatus.IDLE
    
    @pytest.mark.asyncio
    async def test_register_agent(self):
        """测试Agent注册"""
        orchestrator = OrchestratorAgent()
        await orchestrator.initialize()
        
        content_agent = ContentAgent()
        await content_agent.initialize()
        
        result = orchestrator.register_agent(content_agent)
        
        assert result == True
        assert "content" in orchestrator._registered_agents
    
    @pytest.mark.asyncio
    async def test_dispatch_task(self):
        """测试任务分发"""
        orchestrator = OrchestratorAgent()
        await orchestrator.initialize()
        
        content_agent = ContentAgent()
        await content_agent.initialize()
        orchestrator.register_agent(content_agent)
        
        result = await orchestrator._dispatch_task({
            "agent": "content",
            "action": "generate",
            "params": {"topic": "测试主题"}
        })
        
        assert result is not None


class TestContentAgent:
    """测试内容生成Agent"""
    
    @pytest.mark.asyncio
    async def test_content_agent_creation(self):
        """测试内容生成Agent创建"""
        agent = ContentAgent()
        await agent.initialize()
        
        assert agent.agent_id == "content"
        assert agent.name == "内容生成器"
    
    @pytest.mark.asyncio
    async def test_generate_content(self):
        """测试内容生成"""
        agent = ContentAgent()
        await agent.initialize()
        
        result = await agent._generate_content({
            "topic": "人工智能",
            "content_type": "article",
            "length": "short"
        })
        
        assert result["success"] == True
        assert "content" in result
        assert "topic" in result
    
    @pytest.mark.asyncio
    async def test_social_post(self):
        """测试社交媒体帖子生成"""
        agent = ContentAgent()
        await agent.initialize()
        
        result = await agent._generate_social_post({
            "topic": "新品发布",
            "platform": "weibo"
        })
        
        assert result["success"] == True
        assert result["platform"] == "weibo"


class TestDataAgent:
    """测试数据分析Agent"""
    
    @pytest.mark.asyncio
    async def test_data_agent_creation(self):
        """测试数据分析Agent创建"""
        agent = DataAgent()
        await agent.initialize()
        
        assert agent.agent_id == "data"
        assert agent.name == "数据分析器"
    
    @pytest.mark.asyncio
    async def test_collect_data(self):
        """测试数据采集"""
        agent = DataAgent()
        await agent.initialize()
        
        result = await agent._collect_data({
            "source": "internal",
            "data_type": "user",
            "time_range": "1d"
        })
        
        assert result["success"] == True
        assert "data" in result
        assert result["count"] > 0
    
    @pytest.mark.asyncio
    async def test_analyze_data(self):
        """测试数据分析"""
        agent = DataAgent()
        await agent.initialize()
        
        # 先采集数据
        collect_result = await agent._collect_data({
            "source": "internal",
            "data_type": "user"
        })
        
        # 分析数据
        result = await agent._analyze_data({
            "data": collect_result["data"],
            "analysis_type": "basic"
        })
        
        assert result["success"] == True
        assert "result" in result
    
    @pytest.mark.asyncio
    async def test_statistics(self):
        """测试统计计算"""
        agent = DataAgent()
        await agent.initialize()
        
        result = await agent._calculate_statistics({
            "values": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        })
        
        assert result["success"] == True
        assert result["mean"] == 5.5
        assert result["min"] == 1
        assert result["max"] == 10


class TestMonitorAgent:
    """测试监控Agent"""
    
    @pytest.mark.asyncio
    async def test_monitor_agent_creation(self):
        """测试监控Agent创建"""
        agent = MonitorAgent()
        await agent.initialize()
        
        assert agent.agent_id == "monitor"
        assert agent.name == "系统监控器"
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """测试健康检查"""
        agent = MonitorAgent()
        await agent.initialize()
        
        result = await agent._check_system_health()
        
        assert "timestamp" in result
        assert "cpu" in result
        assert "memory" in result
        assert "overall_status" in result
    
    @pytest.mark.asyncio
    async def test_metrics(self):
        """测试指标获取"""
        agent = MonitorAgent()
        await agent.initialize()
        
        result = await agent._get_detailed_metrics({
            "metric_type": "cpu"
        })
        
        assert result["success"] == True
        assert "metrics" in result
        assert "cpu" in result["metrics"]


class TestExecutorAgent:
    """测试执行Agent"""
    
    @pytest.mark.asyncio
    async def test_executor_agent_creation(self):
        """测试执行Agent创建"""
        agent = ExecutorAgent()
        await agent.initialize()
        
        assert agent.agent_id == "executor"
        assert agent.name == "任务执行器"
        
        await agent.cleanup()
    
    @pytest.mark.asyncio
    async def test_send_notification(self):
        """测试发送通知"""
        agent = ExecutorAgent()
        await agent.initialize()
        
        result = await agent._send_notification({
            "channel": "log",
            "title": "测试通知",
            "content": "这是一条测试通知"
        })
        
        assert result["success"] == True
        assert result["channel"] == "log"
        
        await agent.cleanup()
    
    @pytest.mark.asyncio
    async def test_batch_execution(self):
        """测试批量执行"""
        agent = ExecutorAgent()
        await agent.initialize()
        
        result = await agent._execute_batch({
            "tasks": [
                {"action": "send_notification", "channel": "log", "title": "Task 1"},
                {"action": "send_notification", "channel": "log", "title": "Task 2"}
            ],
            "parallel": True
        })
        
        assert result["total"] == 2
        assert result["success_count"] == 2
        
        await agent.cleanup()


class TestWorkflowIntegration:
    """测试工作流集成"""
    
    @pytest.mark.asyncio
    async def test_multi_agent_workflow(self):
        """测试多Agent工作流"""
        # 创建Agent
        orchestrator = OrchestratorAgent()
        await orchestrator.initialize()
        
        content_agent = ContentAgent()
        await content_agent.initialize()
        
        data_agent = DataAgent()
        await data_agent.initialize()
        
        # 注册Agent
        orchestrator.register_agent(content_agent)
        orchestrator.register_agent(data_agent)
        
        # 模拟工作流
        # 1. 数据采集
        data_result = await data_agent._collect_data({
            "source": "internal",
            "data_type": "user"
        })
        
        # 2. 内容生成
        content_result = await content_agent._generate_content({
            "topic": f"用户数据分析报告 - {data_result['count']}条记录"
        })
        
        # 3. 发送通知
        executor = ExecutorAgent()
        await executor.initialize()
        
        notification_result = await executor._send_notification({
            "channel": "log",
            "title": "工作流完成",
            "content": f"生成了{len(content_result.get('content', ''))}字的内容"
        })
        
        await executor.cleanup()
        
        assert data_result["success"] == True
        assert content_result["success"] == True
        assert notification_result["success"] == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
