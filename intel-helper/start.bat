@echo off
chcp 65001 >nul
REM 率土战报情报库 - 一键启动脚本

cd /d "%~dp0"

echo ==================================
echo 率土战报情报库 - 一键启动
echo ==================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

REM 启动
python scripts\start_dev.py

pause
