#!/bin/bash

# Auto Trading Agent 启动脚本
# 用于同时启动后端API和前端开发服务器

echo "=========================================="
echo "  Auto Trading Agent - 启动脚本"
echo "=========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 检查Python依赖
echo -e "${YELLOW}[1/4] 检查Python依赖...${NC}"
cd "$PROJECT_DIR"
pip3 install -q -r requirements.txt 2>/dev/null
echo -e "${GREEN}✓ Python依赖已安装${NC}"

# 检查Node依赖
echo -e "${YELLOW}[2/4] 检查前端依赖...${NC}"
cd "$PROJECT_DIR/frontend"
if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    pnpm install --silent
fi
echo -e "${GREEN}✓ 前端依赖已安装${NC}"

# 启动后端
echo -e "${YELLOW}[3/4] 启动后端API服务...${NC}"
cd "$PROJECT_DIR"
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
python3 -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo -e "${GREEN}✓ 后端服务已启动 (PID: $BACKEND_PID)${NC}"

# 等待后端启动
sleep 3

# 启动前端
echo -e "${YELLOW}[4/4] 启动前端开发服务...${NC}"
cd "$PROJECT_DIR/frontend"
pnpm dev &
FRONTEND_PID=$!
echo -e "${GREEN}✓ 前端服务已启动 (PID: $FRONTEND_PID)${NC}"

echo ""
echo "=========================================="
echo -e "${GREEN}  所有服务已启动!${NC}"
echo "=========================================="
echo ""
echo "  后端API:  http://localhost:8000"
echo "  前端界面: http://localhost:3000"
echo "  API文档:  http://localhost:8000/docs"
echo ""
echo "  按 Ctrl+C 停止所有服务"
echo "=========================================="

# 捕获退出信号
trap "echo '正在停止服务...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# 等待
wait
