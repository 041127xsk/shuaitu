@echo off
echo ========================================
echo   Building 战报助手 v1.0
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] Cleaning old build...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "战报助手.spec" del "战报助手.spec"

echo [2/3] Building with PyInstaller...
"C:\Users\27557\AppData\Local\Programs\Python\Python312\Scripts\pyinstaller.exe" ^
    --onefile ^
    --windowed ^
    --name "战报助手" ^
    --add-data "battle_assistant;battle_assistant" ^
    --hidden-import battle_assistant.core ^
    --hidden-import battle_assistant.gui ^
    --hidden-import openpyxl ^
    --hidden-import sqlite3 ^
    battle_assistant/main.py

echo [3/3] Creating distribution package...
if not exist "dist\战报助手" mkdir "dist\战报助手"
copy "dist\战报助手.exe" "dist\战报助手\"
copy "tools\stzbHelper.exe" "dist\战报助手\"
copy "tools\stzb-capture\auto_scroll_reports.py" "dist\战报助手\"
copy "tools\stzb-capture\import_stzb_helper.py" "dist\战报助手\"

echo.
echo ========================================
echo   Build complete!
echo   Output: dist\战报助手\
echo ========================================
pause
