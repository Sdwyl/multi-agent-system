#!/bin/bash
# 多Agent协同运营自动化系统启动脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 目录设置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  多Agent协同运营自动化系统启动脚本    ${NC}"
echo -e "${GREEN}========================================${NC}"

# 检查Python版本
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.10"
if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}错误: 需要Python 3.10+, 当前版本: $PYTHON_VERSION${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python版本: $PYTHON_VERSION"

# 创建必要目录
mkdir -p logs data

# 检查配置文件
if [ ! -f "config/default.yaml" ]; then
    echo -e "${RED}错误: 配置文件不存在: config/default.yaml${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} 配置文件检查通过"

# 检查依赖
if ! pip show fastapi > /dev/null 2>&1; then
    echo -e "${YELLOW}警告: 依赖未安装，正在安装...${NC}"
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo -e "${RED}错误: 依赖安装失败${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✓${NC} 依赖检查通过"

# 检查Redis连接
if command -v redis-cli &> /dev/null; then
    if redis-cli -h ${REDIS_HOST:-localhost} -p ${REDIS_PORT:-6379} ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Redis连接正常"
    else
        echo -e "${YELLOW}警告: Redis连接失败，请确保Redis服务正在运行${NC}"
        echo -e "${YELLOW}提示: 可以使用 docker-compose up -d redis 启动Redis${NC}"
    fi
else
    echo -e "${YELLOW}警告: redis-cli未安装，跳过Redis连接检查${NC}"
fi

# 启动应用
echo ""
echo -e "${GREEN}正在启动多Agent系统...${NC}"
echo -e "${GREEN}API文档地址: http://localhost:8000/docs${NC}"
echo -e "${GREEN}按Ctrl+C停止服务${NC}"
echo ""

# 使用uvicorn启动应用
exec python -m uvicorn src.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level info
