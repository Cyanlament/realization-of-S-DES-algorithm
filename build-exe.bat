@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo [S-DES] 正在打包单文件 exe...

if not exist ".venv\Scripts\python.exe" (
    echo 未找到虚拟环境，请先运行 run.bat 完成环境初始化。
    exit /b 1
)

".venv\Scripts\python.exe" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo 正在安装 PyInstaller...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q pyinstaller
    if errorlevel 1 (
        echo PyInstaller 安装失败，请检查网络或代理设置。
        exit /b 1
    )
)

".venv\Scripts\python.exe" -m PyInstaller --noconfirm S-DES.spec
if errorlevel 1 (
    echo 打包失败，错误信息见上方输出。
    exit /b 1
)

echo.
echo 打包完成：dist\S-DES.exe
echo 可直接把该文件复制到任意 Windows 电脑双击运行，无需安装 Python。
exit /b 0
