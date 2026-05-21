@echo off
chcp 65001 >nul
REM 率土战报情报库 - 一键导出脚本

cd /d "%~dp0"

echo ==================================
echo 率土战报情报库 - 一键导出
echo ==================================
echo.

python scripts\export_all.py

echo.
pause
