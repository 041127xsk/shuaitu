#!/bin/bash
# 率土战报情报库 - 启动脚本

cd "$(dirname "$0")"

echo "=================================="
echo "率土战报情报库启动脚本"
echo "=================================="

# 检查 Python
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "错误: 未找到 Python"
        exit 1
    fi
    PYTHON=python
else
    PYTHON=python3
fi

# 安装依赖
echo ""
echo "[1/3] 检查依赖..."
if ! $PYTHON -c "import fastapi" 2>/dev/null; then
    echo "安装依赖..."
    $PYTHON -m pip install -r requirements.txt
fi

# 初始化数据库
echo ""
echo "[2/3] 初始化数据库..."
$PYTHON -m backend.seed

# 启动服务
echo ""
echo "[3/3] 启动服务..."
echo "访问地址: http://localhost:8000"
echo "API文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

$PYTHON -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
