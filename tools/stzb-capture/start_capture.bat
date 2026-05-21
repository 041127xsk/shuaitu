@echo off
cd /d "%~dp0"
echo ============================================
echo   stzbHelper Battle Report Capture Tool
echo ============================================
echo.
echo Starting stzbHelper...
start "" stzbHelper.exe
timeout /t 3 /nobreak >nul
echo.
echo [1] stzbHelper started!
echo [2] Please open 主公簿 in game to activate
echo [3] Then go to battle report page
echo.
echo Press any key to start auto-scroll (5000 swipes)...
pause >nul
echo.
echo Starting auto-scroll...
"C:\Users\27557\AppData\Local\Programs\Python\Python312\python.exe" auto_scroll_reports.py --count 5000 --delay 0.1 --duration 100
echo.
echo ============================================
echo Scroll complete! Importing data...
echo ============================================
"C:\Users\27557\AppData\Local\Programs\Python\Python312\python.exe" import_stzb_helper.py
echo.
echo ============================================
echo All done!
echo ============================================
pause
