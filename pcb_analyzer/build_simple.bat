@echo off
chcp 65001 >nul
echo ========================================
echo PCB 分析工具 - 简单打包
echo ========================================
echo.

echo 1. 检查 PyInstaller...
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller 未安装，正在安装...
    python -m pip install pyinstaller
)

echo.
echo 2. 打包主程序...
pyinstaller --name=pcb_analyzer --onefile --console main.py

echo.
echo 3. 打包验证工具...
pyinstaller --name=validate_accuracy --onefile --console validate_accuracy.py

echo.
echo 4. 打包对比工具...
pyinstaller --name=visual_compare --onefile --console visual_compare.py

echo.
echo 5. 创建发布目录...
if not exist release mkdir release
if not exist release\input mkdir release\input
if not exist release\output mkdir release\output

echo.
echo 6. 复制文件...
copy dist\pcb_analyzer.exe release\
copy dist\validate_accuracy.exe release\
copy dist\visual_compare.exe release\
copy README.md release\
copy USER_GUIDE.md release\
copy HANDOFF.md release\

echo.
echo ========================================
echo 打包完成!
echo ========================================
echo.
echo 发布包位置: release\
echo.
echo 使用方法:
echo   1. 将 Gerber 文件放入 release\input\
echo   2. 运行: release\pcb_analyzer.exe -i input -o output
echo.
pause
