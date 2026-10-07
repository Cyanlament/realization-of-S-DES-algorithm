# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：把 S-DES 桌面程序打成一个单文件 exe。

用法（在项目根目录）：
    .venv\\Scripts\\python.exe -m PyInstaller --noconfirm S-DES.spec

产物：dist\\S-DES.exe
"""
import os
from pathlib import Path
import PySide6

# 图标由 QPainter 绘制，字体使用系统字体。
project_root = Path(SPECPATH)
qt_directory = Path(PySide6.__file__).parent
runtime_binaries = [(str(qt_directory / name), ".") for name in
                    ("VCRUNTIME140.dll", "VCRUNTIME140_1.dll")]

# SDES_CONSOLE=1 生成带控制台输出的自检版本。
console_mode = os.environ.get("SDES_CONSOLE") == "1"
exe_name = "S-DES-console" if console_mode else "S-DES"

hidden_imports = [
    # Qt 界面模块。
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    # 算法与命令行模块。
    "sdes.cli",
    "sdes.core",
    "sdes.encoding",
    "sdes.analysis",
]

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=runtime_binaries,
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 排除桌面程序未使用的库。
    excludes=[
        "tkinter",
        "unittest",
        "pydoc_data",
        "test",
        "PIL",
        "docx",
        "numpy",
        "matplotlib",
    ],
    noarchive=False,
)

# Qt 使用 Windows 自带的 ICU，其他工具的同名 DLL 可能导出不同符号。
a.binaries = [entry for entry in a.binaries
              if not Path(entry[0]).name.lower().startswith("icu")]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=console_mode,   # 默认窗口程序；SDES_CONSOLE=1 时带控制台用于自检
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
