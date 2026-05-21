@echo off
REM 率土战报情报库 - Windows 启动脚本

cd /d "%~dp0"

echo ==================================
echo 率土战报情报库启动脚本
echo ==================================

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到 Python
    pause
    exit /b 1
)

REM 安装依赖
echo.
echo [1/3] 检查依赖...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo 安装依赖...
    pip install -r requirements.txt
)

REM 初始化数据库
echo.
echo [2/3] 初始化数据库...
python -m backend.seed

REM 启动服务
echo.
echo [3/3] 启动服务...
echo 访问地址: http://localhost:8000
echo API文档: http://localhost:8000/docs
echo.
echo 按 Ctrl+C 停止服务
echo.

REM 延迟打开浏览器
start /MIN cmd /c "timeout /t 2 /nobreak >nul ^&^& start http://localhost:8000"

python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

pause
