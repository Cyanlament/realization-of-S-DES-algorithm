@echo off
setlocal
chcp 65001 >nul
if not defined SDES_LOG set "SDES_LOG=%~dp0startup.log"
cd /d "%~dp0"
if errorlevel 1 goto error
> "%SDES_LOG%" echo [S-DES] Starting at %date% %time%

if exist ".venv\Scripts\python.exe" goto check_dependencies
echo [1/3] 正在创建 Python 虚拟环境...
py -3 -c "import sys; sys.exit(sys.version_info < (3, 10))" >> "%SDES_LOG%" 2>&1
if errorlevel 1 goto try_python
py -3 -m venv .venv >> "%SDES_LOG%" 2>&1
goto environment_ready

:try_python
python -c "import sys; sys.exit(sys.version_info < (3, 10))" >> "%SDES_LOG%" 2>&1
if errorlevel 1 goto missing_python
python -m venv .venv >> "%SDES_LOG%" 2>&1

:environment_ready
if errorlevel 1 goto error
if not exist ".venv\Scripts\python.exe" goto error

:check_dependencies
echo [2/3] 正在检查 Qt 图形界面依赖...
".venv\Scripts\python.exe" -c "from PySide6.QtWidgets import QApplication" >> "%SDES_LOG%" 2>&1
if not errorlevel 1 goto launch
echo 首次运行需要安装依赖，请等待。详细进度记录在 startup.log 中。
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --progress-bar off -r requirements.txt >> "%SDES_LOG%" 2>&1
if errorlevel 1 goto error

:launch
echo [3/3] 正在打开 S-DES 实验室，请保留此窗口...
".venv\Scripts\python.exe" -u main.py %* >> "%SDES_LOG%" 2>&1
if errorlevel 1 goto error
exit /b 0

:missing_python
echo 未找到 Python 3.10 或更新版本，请安装 Python 后再运行。
goto error

:error
echo.
echo 启动失败。详细原因如下，日志位置："%SDES_LOG%"
if exist "%SDES_LOG%" type "%SDES_LOG%"
if /i not "%~1"=="--smoke-test" pause
exit /b 1
