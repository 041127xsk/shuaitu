"""
PCB 分析工具 - EXE 打包脚本
使用 PyInstaller 打包成独立可执行文件
"""

import os
import sys
import subprocess
from pathlib import Path

def check_pyinstaller():
    """检查 PyInstaller 是否安装"""
    try:
        import PyInstaller
        print(f"✓ PyInstaller 已安装 (版本: {PyInstaller.__version__})")
        return True
    except ImportError:
        print("✗ PyInstaller 未安装")
        print("\n正在安装 PyInstaller...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            print("✓ PyInstaller 安装成功")
            return True
        except:
            print("✗ PyInstaller 安装失败")
            return False

def build_main_exe():
    """打包主程序"""
    print("\n" + "="*60)
    print("打包主程序: pcb_analyzer.exe")
    print("="*60)
    
    cmd = [
        "pyinstaller",
        "--name=pcb_analyzer",
        "--onefile",
        "--console",
        "--icon=NONE",
        "--add-data=README.md;.",
        "--add-data=USER_GUIDE.md;.",
        "--add-data=HANDOFF.md;.",
        "--hidden-import=gerbonara",
        "--hidden-import=matplotlib",
        "--hidden-import=numpy",
        "--hidden-import=PIL",
        "--collect-all=gerbonara",
        "--collect-all=matplotlib",
        "main.py"
    ]
    
    try:
        subprocess.check_call(cmd)
        print("\n✓ 主程序打包成功: dist/pcb_analyzer.exe")
        return True
    except Exception as e:
        print(f"\n✗ 打包失败: {e}")
        return False

def build_validator_exe():
    """打包验证工具"""
    print("\n" + "="*60)
    print("打包验证工具: validate_accuracy.exe")
    print("="*60)
    
    cmd = [
        "pyinstaller",
        "--name=validate_accuracy",
        "--onefile",
        "--console",
        "--icon=NONE",
        "--hidden-import=gerbonara",
        "--hidden-import=matplotlib",
        "--hidden-import=numpy",
        "--collect-all=gerbonara",
        "validate_accuracy.py"
    ]
    
    try:
        subprocess.check_call(cmd)
        print("\n✓ 验证工具打包成功: dist/validate_accuracy.exe")
        return True
    except Exception as e:
        print(f"\n✗ 打包失败: {e}")
        return False

def build_compare_exe():
    """打包对比工具"""
    print("\n" + "="*60)
    print("打包对比工具: visual_compare.exe")
    print("="*60)
    
    cmd = [
        "pyinstaller",
        "--name=visual_compare",
        "--onefile",
        "--console",
        "--icon=NONE",
        "--hidden-import=gerbonara",
        "--hidden-import=matplotlib",
        "--hidden-import=numpy",
        "--hidden-import=PIL",
        "--collect-all=gerbonara",
        "--collect-all=matplotlib",
        "visual_compare.py"
    ]
    
    try:
        subprocess.check_call(cmd)
        print("\n✓ 对比工具打包成功: dist/visual_compare.exe")
        return True
    except Exception as e:
        print(f"\n✗ 打包失败: {e}")
        return False

def create_release_package():
    """创建发布包"""
    print("\n" + "="*60)
    print("创建发布包")
    print("="*60)
    
    dist_dir = Path("dist")
    release_dir = Path("release")
    
    # 创建 release 目录
    release_dir.mkdir(exist_ok=True)
    
    # 复制 EXE 文件
    import shutil
    
    files_to_copy = [
        ("dist/pcb_analyzer.exe", "release/pcb_analyzer.exe"),
        ("dist/validate_accuracy.exe", "release/validate_accuracy.exe"),
        ("dist/visual_compare.exe", "release/visual_compare.exe"),
        ("README.md", "release/README.md"),
        ("USER_GUIDE.md", "release/USER_GUIDE.md"),
        ("HANDOFF.md", "release/HANDOFF.md"),
    ]
    
    for src, dst in files_to_copy:
        if Path(src).exists():
            shutil.copy2(src, dst)
            print(f"✓ 复制: {src} -> {dst}")
    
    # 创建示例目录
    (release_dir / "input").mkdir(exist_ok=True)
    (release_dir / "output").mkdir(exist_ok=True)
    
    print("\n✓ 发布包创建完成: release/")
    print("\n包含文件:")
    print("  - pcb_analyzer.exe (主程序)")
    print("  - validate_accuracy.exe (验证工具)")
    print("  - visual_compare.exe (对比工具)")
    print("  - README.md (快速开始)")
    print("  - USER_GUIDE.md (详细使用)")
    print("  - HANDOFF.md (技术文档)")
    print("  - input/ (放入 Gerber 文件)")
    print("  - output/ (输出目录)")

def create_usage_bat():
    """创建使用示例批处理文件"""
    print("\n创建使用示例...")
    
    bat_content = """@echo off
chcp 65001 >nul
echo ========================================
echo PCB Gerber 分析工具
echo ========================================
echo.

:menu
echo 请选择操作:
echo 1. 运行分析 (基本)
echo 2. 运行分析 (调整阈值)
echo 3. 验证准确性
echo 4. 生成对比图
echo 5. 查看帮助
echo 6. 退出
echo.
set /p choice=请输入选项 (1-6): 

if "%choice%"=="1" goto analyze
if "%choice%"=="2" goto analyze_threshold
if "%choice%"=="3" goto validate
if "%choice%"=="4" goto compare
if "%choice%"=="5" goto help
if "%choice%"=="6" goto end

:analyze
echo.
echo 运行分析...
pcb_analyzer.exe -i input -o output
echo.
echo 完成! 请查看 output 目录
pause
goto menu

:analyze_threshold
echo.
set /p threshold=请输入阈值 (默认 2.0): 
if "%threshold%"=="" set threshold=2.0
echo 运行分析 (阈值: %threshold%)...
pcb_analyzer.exe -i input -o output -t %threshold%
echo.
echo 完成! 请查看 output 目录
pause
goto menu

:validate
echo.
echo 验证准确性...
validate_accuracy.exe input output\\pads.csv
echo.
pause
goto menu

:compare
echo.
echo 生成对比图...
visual_compare.exe input\\mask1.gbr output\\pads.csv output
echo.
echo 完成! 请查看 output\\comparison.png 和 output\\difference_map.png
pause
goto menu

:help
echo.
pcb_analyzer.exe --help
echo.
pause
goto menu

:end
echo.
echo 感谢使用!
exit
"""
    
    with open("release/run.bat", "w", encoding="utf-8") as f:
        f.write(bat_content)
    
    print("✓ 创建: release/run.bat (使用示例)")

def main():
    """主函数"""
    print("="*60)
    print("PCB Gerber 分析工具 - EXE 打包")
    print("="*60)
    
    # 检查 PyInstaller
    if not check_pyinstaller():
        print("\n请先安装 PyInstaller:")
        print("  pip install pyinstaller")
        return
    
    # 打包主程序
    if not build_main_exe():
        print("\n主程序打包失败，停止")
        return
    
    # 打包验证工具
    build_validator_exe()
    
    # 打包对比工具
    build_compare_exe()
    
    # 创建发布包
    create_release_package()
    
    # 创建使用示例
    create_usage_bat()
    
    print("\n" + "="*60)
    print("打包完成!")
    print("="*60)
    print("\n发布包位置: release/")
    print("\n使用方法:")
    print("  1. 将 Gerber 文件放入 release/input/")
    print("  2. 双击 release/run.bat")
    print("  3. 或直接运行: release/pcb_analyzer.exe -i input -o output")
    print("\n注意:")
    print("  - 首次运行可能较慢 (解压依赖)")
    print("  - 建议在 SSD 上运行")
    print("  - 需要 Windows 7 或更高版本")

if __name__ == "__main__":
    main()
