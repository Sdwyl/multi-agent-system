# 多Agent协同运营自动化系统

## 项目简介

多Agent协同运营自动化系统（Multi-Agent Orchestration System）是一个基于Python的智能自动化框架，用于构建、管理和协调多个AI Agent协同工作。该系统适用于内容创作、数据分析、运营监控、流程自动化等多种场景。

## 核心特性

- **多Agent架构**：支持5种专业Agent协同工作
- **异步消息总线**：基于Redis的发布/订阅模式
- **可配置工作流**：支持串行、并行、条件分支
- **RESTful API**：完整的接口支持
- **任务调度**：基于APScheduler的定时任务
- **容器化部署**：Docker一键启动
- **LLM集成**：支持OpenAI兼容接口

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Gateway                              │
│                     (FastAPI + Routes)                          │
└─────────────────────────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────┐
│                      Message Bus (Redis)                        │
│              发布/订阅 + 任务队列 + 事件通知                      │
└─────────────────────────────────────────────────────────────────┘
                                │
    ┌──────────┬──────────┬──────────┬──────────┬──────────┐
    │          │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼          │
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐      │
│调度Agent│ │内容Agent│ │数据Agent│ │监控Agent│ │执行Agent│      │
│Orches- │ │Content  │ │Data    │ │Monitor │ │Executor │      │
│trator  │ │Agent    │ │Agent   │ │Agent   │ │Agent    │      │
└────────┘ └────────┘ └────────┘ └────────┘ └────────┘      │
                                │                           │
                                └───────────────────────────┘
                                               │
                    ┌──────────────────────────┘
                    ▼
            ┌─────────────────┐
            │  Workflow Engine│
            │   (工作流引擎)    │
            └─────────────────┘
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
┌────────┐   ┌────────┐   ┌────────┐
│  SQLite │   │  Redis │   │  LLM   │
│(数据库) │   │(缓存)  │   │(模型)  │
└────────┘   └────────┘   └────────┘
```

## Agent职责

| Agent | 功能描述 |
|-------|----------|
| **Orchestrator (调度Agent)** | 任务分发、协调、状态管理 |
| **Content (内容Agent)** | 文案创作、内容生成、SEO优化 |
| **Data (数据Agent)** | 数据采集、统计分析、报表生成 |
| **Monitor (监控Agent)** | 系统监控、异常检测、告警通知 |
| **Executor (执行Agent)** | 邮件发送、通知推送、外部API调用 |

## 快速开始

### 环境要求

- Python 3.10+
- Redis 6.0+
- Docker & Docker Compose (可选)

### 本地安装

```bash
# 克隆项目
git clone https://github.com/your-repo/multi-agent-system.git
cd multi-agent-system

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 启动Redis (需要先安装Redis)
redis-server

# 运行系统
python src/main.py
```

### Docker部署

```bash
# 一键启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

### 验证服务

```bash
# 检查系统状态
curl http://localhost:8000/api/v1/health

# 获取Agent列表
curl http://localhost:8000/api/v1/agents

# 创建任务
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试任务",
    "type": "content_generation",
    "params": {"topic": "AI技术发展"}
  }'
```

## API文档

启动服务后访问: http://localhost:8000/docs

### 主要接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/v1/health | 健康检查 |
| GET | /api/v1/agents | 获取所有Agent |
| GET | /api/v1/agents/{id} | 获取指定Agent |
| POST | /api/v1/tasks | 创建任务 |
| GET | /api/v1/tasks | 获取任务列表 |
| GET | /api/v1/tasks/{id} | 获取任务详情 |
| POST | /api/v1/workflows | 创建工作流 |
| GET | /api/v1/workflows/{id} | 获取工作流状态 |
| POST | /api/v1/messages/send | 发送消息 |
| GET | /api/v1/logs | 获取日志 |

## 配置说明

### 默认配置 (config/default.yaml)

```yaml
app:
  name: "multi-agent-system"
  host: "0.0.0.0"
  port: 8000
  debug: false
  log_level: "INFO"

redis:
  host: "localhost"
  port: 6379
  db: 0
  password: null

database:
  type: "sqlite"
  path: "./data/agent.db"

llm:
  provider: "openai"
  api_key: "${OPENAI_API_KEY}"
  base_url: "https://api.openai.com/v1"
  model: "gpt-3.5-turbo"
  temperature: 0.7
  max_tokens: 2000

scheduler:
  timezone: "Asia/Shanghai"
  max_workers: 5
```

### Agent配置 (config/agents.yaml)

```yaml
agents:
  orchestrator:
    enabled: true
    priority: 10
    max_concurrent_tasks: 10
  
  content:
    enabled: true
    priority: 5
    llm_model: "gpt-3.5-turbo"
    output_format: "markdown"
  
  data:
    enabled: true
    priority: 5
    data_sources: ["internal", "external"]
  
  monitor:
    enabled: true
    priority: 8
    check_interval: 60
    alert_threshold: 3
  
  executor:
    enabled: true
    priority: 6
    max_retries: 3
```

## 工作流示例

### 串行工作流

```json
{
  "name": "内容创作流程",
  "type": "sequential",
  "steps": [
    {"agent": "data", "action": "collect_trends"},
    {"agent": "content", "action": "generate"},
    {"agent": "executor", "action": "publish"}
  ]
}
```

### 并行工作流

```json
{
  "name": "多渠道发布",
  "type": "parallel",
  "branches": [
    {"agent": "executor", "action": "send_email"},
    {"agent": "executor", "action": "send_wechat"},
    {"agent": "executor", "action": "send_sms"}
  ]
}
```

### 条件分支工作流

```json
{
  "name": "智能分发",
  "type": "conditional",
  "condition": "data.sentiment == 'positive'",
  "true_branch": {"agent": "content", "action": "generate_promotion"},
  "false_branch": {"agent": "content", "action": "generate_neutral"}
}
```

## 项目结构

```
multi-agent-system/
├── README.md              # 项目说明
├── requirements.txt       # Python依赖
├── Dockerfile             # Docker镜像
├── docker-compose.yml     # 容器编排
├── config/
│   ├── default.yaml       # 默认配置
│   └── agents.yaml        # Agent配置
├── src/
│   ├── main.py            # 入口文件
│   ├── core/              # 核心模块
│   │   ├── agent_base.py  # Agent基类
│   │   ├── scheduler.py   # 任务调度
│   │   ├── message_bus.py # 消息总线
│   │   └── workflow.py    # 工作流引擎
│   ├── agents/             # Agent实现
│   │   ├── orchestrator.py
│   │   ├── content_agent.py
│   │   ├── data_agent.py
│   │   ├── monitor_agent.py
│   │   └── executor_agent.py
│   ├── api/               # API接口
│   │   └── routes.py
│   ├── models/            # 数据模型
│   │   └── schemas.py
│   └── utils/             # 工具函数
│       ├── logger.py
│       └── config.py
├── tests/                 # 测试
│   └── test_agents.py
└── scripts/
    └── start.sh           # 启动脚本
```

## 扩展指南

### 添加新Agent

1. 继承 `AgentBase` 类
2. 实现 `initialize()`, `execute()`, `cleanup()` 方法
3. 在 `agents.yaml` 中注册
4. 更新 `src/agents/__init__.py`

### 自定义工作流节点

```python
from src.core.workflow import WorkflowNode, NodeType

class CustomNode(WorkflowNode):
    def __init__(self):
        super().__init__(NodeType.TASK, "custom_node")
    
    async def execute(self, context: dict) -> dict:
        # 自定义逻辑
        return {"result": "success"}
```

### 集成新LLM

修改 `config/default.yaml` 中的 `llm` 配置：

```yaml
llm:
  provider: "custom"
  api_key: "your-key"
  base_url: "https://your-llm-api.com/v1"
  model: "your-model"
```

## 日志查看

```bash
# 实时查看日志
tail -f logs/agent.log

# 查看错误日志
grep ERROR logs/agent.log

# 按时间过滤
grep "2024-01-01 10:" logs/agent.log
```

## 监控指标

系统提供以下监控指标：

- `agent_tasks_total`: 各Agent处理的任务总数
- `agent_tasks_success`: 成功任务数
- `agent_tasks_failed`: 失败任务数
- `agent_response_time`: 响应时间
- `queue_depth`: 队列深度
- `workflow_execution_time`: 工作流执行时间

