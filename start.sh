#!/bin/bash

# Auto Trading Agent startup script
# Starts both the backend API and frontend dev server

echo "=========================================="
echo "  Auto Trading Agent - Startup Script"
echo "=========================================="

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check Python dependencies
echo -e "${YELLOW}[1/4] Checking Python dependencies...${NC}"
cd "$PROJECT_DIR"
pip3 install -q -r requirements.txt 2>/dev/null
echo -e "${GREEN}✓ Python dependencies installed${NC}"

# Check Node dependencies
echo -e "${YELLOW}[2/4] Checking frontend dependencies...${NC}"
cd "$PROJECT_DIR/frontend"
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    pnpm install --silent
fi
echo -e "${GREEN}✓ Frontend dependencies installed${NC}"

# Start backend
echo -e "${YELLOW}[3/4] Starting backend API service...${NC}"
cd "$PROJECT_DIR"
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"
python3 -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo -e "${GREEN}✓ Backend service started (PID: $BACKEND_PID)${NC}"

# Wait for backend to start
sleep 3

# Start frontend
echo -e "${YELLOW}[4/4] Starting frontend dev server...${NC}"
cd "$PROJECT_DIR/frontend"
pnpm dev &
FRONTEND_PID=$!
echo -e "${GREEN}✓ Frontend service started (PID: $FRONTEND_PID)${NC}"

echo ""
echo "=========================================="
echo -e "${GREEN}  All services started!${NC}"
echo "=========================================="
echo ""
echo "  Backend API:  http://localhost:8000"
echo "  Frontend UI:  http://localhost:3000"
echo "  API Docs:     http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop all services"
echo "=========================================="

# Capture exit signals
trap "echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# Wait
wait
