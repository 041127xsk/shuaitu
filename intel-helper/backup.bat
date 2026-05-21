@echo off
chcp 65001 >nul
REM 率土战报情报库 - 一键备份脚本

cd /d "%~dp0"

echo ==================================
echo 率土战报情报库 - 一键备份
echo ==================================
echo.

python scripts\backup_data.py

echo.
pause
