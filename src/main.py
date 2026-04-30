"""
多Agent协同运营自动化系统 - 主入口
"""

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .utils.config import get_config
from .utils.logger import setup_logger, get_logger
from .core.message_bus import get_message_bus
from .core.scheduler import TaskScheduler
from .agents import (
    OrchestratorAgent,
    ContentAgent,
    DataAgent,
    MonitorAgent,
    ExecutorAgent
)
from .api.routes import router, init_routes


# 全局变量
_config = None
_logger = None
_agents = {}
_orchestrator = None
_message_bus = None
_scheduler = None


async def init_agents():
    """初始化所有Agent"""
    global _agents, _orchestrator
    
    logger = get_logger()
    config = get_config()
    
    # 获取Agent配置
    agents_config = config.get_agents_config()
    
    logger.info("开始初始化Agent...")
    
    # 初始化调度Agent
    orchestrator = OrchestratorAgent(
        agent_id="orchestrator",
        config=agents_config.get("orchestrator", {})
    )
    await orchestrator.initialize()
    _agents["orchestrator"] = orchestrator
    
    # 初始化内容生成Agent
    if agents_config.get("content", {}).get("enabled", True):
        content_agent = ContentAgent(
            agent_id="content",
            config=agents_config.get("content", {})
        )
        await content_agent.initialize()
        _agents["content"] = content_agent
        orchestrator.register_agent(content_agent)
        logger.info("内容生成Agent已注册")
    
    # 初始化数据分析Agent
    if agents_config.get("data", {}).get("enabled", True):
        data_agent = DataAgent(
            agent_id="data",
            config=agents_config.get("data", {})
        )
        await data_agent.initialize()
        _agents["data"] = data_agent
        orchestrator.register_agent(data_agent)
        logger.info("数据分析Agent已注册")
    
    # 初始化监控Agent
    if agents_config.get("monitor", {}).get("enabled", True):
        monitor_agent = MonitorAgent(
            agent_id="monitor",
            config=agents_config.get("monitor", {})
        )
        await monitor_agent.initialize()
        _agents["monitor"] = monitor_agent
        orchestrator.register_agent(monitor_agent)
        await monitor_agent.start()  # 启动监控循环
        logger.info("监控Agent已注册并启动")
    
    # 初始化执行Agent
    if agents_config.get("executor", {}).get("enabled", True):
        executor_agent = ExecutorAgent(
            agent_id="executor",
            config=agents_config.get("executor", {})
        )
        await executor_agent.initialize()
        _agents["executor"] = executor_agent
        orchestrator.register_agent(executor_agent)
        logger.info("执行Agent已注册")
    
    # 注册Agent到调度器
    _orchestrator = orchestrator
    
    logger.info(f"Agent初始化完成，共 {len(_agents)} 个Agent")


async def start_agents():
    """启动所有Agent"""
    logger = get_logger()
    
    for agent_id, agent in _agents.items():
        if agent_id != "monitor":  # monitor已在init_agents中启动
            await agent.start()
        logger.info(f"Agent已启动: {agent.name}")


async def stop_agents():
    """停止所有Agent"""
    logger = get_logger()
    
    for agent_id, agent in _agents.items():
        try:
            await agent.cleanup()
            logger.info(f"Agent已停止: {agent.name}")
        except Exception as e:
            logger.error(f"停止Agent失败 {agent.name}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global _message_bus, _scheduler
    
    # 启动阶段
    logger = get_logger()
    logger.info("=" * 50)
    logger.info("多Agent协同运营自动化系统启动中...")
    logger.info("=" * 50)
    
    # 初始化消息总线
    _message_bus = await get_message_bus()
    
    # 初始化调度器
    _scheduler = TaskScheduler()
    await _scheduler.start()
    
    # 初始化Agent
    await init_agents()
    
    # 启动Agent
    await start_agents()
    
    # 初始化API路由
    init_routes(_agents, _orchestrator, _message_bus, _scheduler)
    
    logger.info("=" * 50)
    logger.info("系统启动完成!")
    logger.info("API文档: http://localhost:8000/docs")
    logger.info("=" * 50)
    
    yield
    
    # 关闭阶段
    logger.info("系统正在关闭...")
    
    # 停止Agent
    await stop_agents()
    
    # 停止调度器
    if _scheduler:
        await _scheduler.stop()
    
    # 断开消息总线
    if _message_bus:
        await _message_bus.disconnect()
    
    logger.info("系统已关闭")


def create_app() -> FastAPI:
    """创建FastAPI应用"""
    config = get_config()
    app_config = config.app
    
    app = FastAPI(
        title="多Agent协同运营自动化系统",
        description="基于Python的多Agent智能自动化框架，用于构建、管理和协调多个AI Agent协同工作",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # 添加CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_config.get("cors_origins", ["*"]),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册路由
    app.include_router(router)
    
    # 根路径
    @app.get("/", tags=["首页"])
    async def root():
        return {
            "name": "多Agent协同运营自动化系统",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/v1/health"
        }
    
    return app


# 创建应用实例
app = create_app()


def main():
    """主函数"""
    import uvicorn
    
    config = get_config()
    app_config = config.app
    
    # 设置日志
    log_config = config.get("logging", {})
    setup_logger(
        level=log_config.get("level", "INFO"),
        log_file=log_config.get("sink")
    )
    
    # 启动服务器
    uvicorn.run(
        "src.main:app",
        host=app_config.get("host", "0.0.0.0"),
        port=app_config.get("port", 8000),
        reload=app_config.get("debug", False),
        log_level=app_config.get("log_level", "info").lower()
    )


if __name__ == "__main__":
    main()
