# S-DES 算法实现

信息安全导论 · 作业 1。一个用于探索 S-DES 分组加密、密钥搜索和碰撞现象的桌面工具。

| 组员 | 姓名 | 学号 |
| --- | --- | --- |
| 1 | 蔡旭涛 | 20240947 |
| 2 | 扶满 | 20245177 |

## 1 启动

Windows 可直接双击 [dist/S-DES.exe](dist/S-DES.exe)，无需安装 Python 或 Qt。

运行源码版时，安装 Python 3.10 或更新版本后双击 **`run.bat`**。首次启动自动创建项目虚拟环境并安装 Qt 依赖。

启动失败时，控制台会保留错误信息，同目录的 `startup.log` 保存详细输出。

也可手动运行：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

macOS / Linux：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

## 2 打包独立 exe

没有 Python 环境的电脑可直接运行打包好的程序。双击 **`build-exe.bat`**，或在项目根目录执行：

```powershell
.venv\Scripts\python.exe -m pip install pyinstaller
.venv\Scripts\python.exe -m PyInstaller --noconfirm S-DES.spec
```

产物为 **`dist\S-DES.exe`**（单文件，约 36 MB）。把它复制到任意 Windows 电脑双击即可运行，目标机无需安装 Python 或 Qt。打包配置见 `S-DES.spec`，界面图标和字体均不依赖外部资源文件。

图形界面包括二进制加解密与轮函数跟踪、ASCII/UTF-8 文本、已知明密文暴力破解、密钥碰撞分析。

![分组加密界面](evidence/screenshots/01_binary_encrypt.png)

## 3 实验成果

| 要求 | 实现与证据 |
| --- | --- |
| 第一关：基本测试 | 8 位数据、10 位密钥、GUI 交互；262,144 次加解密往返全部通过 |
| 第二关：交叉测试 | Python/C++ 的 262,144 个加密结果一致；35 组解密验证通过；与其他小组的交叉测试均通过 |
| 第三关：扩展功能 | 按字节处理 ASCII；Hex、Base64、转义字节无损密文；额外支持 UTF-8 |
| 第四关：暴力破解 | 单组/多组已知明密文、全部候选密钥、纳秒计时、开始结束时间戳、Qt 后台线程、动图 |
| 第五关：封闭测试 | 256 个明文 × 1024 个密钥的碰撞统计、可复现随机案例、抽屉原理分析 |
| 文档与规范 | 纯函数密码核心、模块化 GUI、用户指南、开发手册、接口说明、实验报告 |

本地测试环境为 Windows。仓库配置了 Windows/Linux/macOS 验证工作流，运行记录见 Actions。

## 4 文档入口

- [Word 报告](docs/S-DES实验报告.docx) / [PDF 报告](output/pdf/S-DES实验报告.pdf) / [在线阅读](docs/实验报告.md)
- [用户指南](docs/用户指南.md)
- [开发手册与接口文档](docs/开发手册.md)
- [要求逐项核对及提交记录](docs/要求核对.md)
- [跨组测试记录](docs/跨组测试记录.md)
- [机器可读结果汇总](evidence/summary.json)

## 5 暴力破解演示

![暴力破解动图](evidence/brute_force_demo.gif)

动图依次展示单对输入、单对结果、多对输入和多对结果。画面有阅读停留，搜索耗时见界面及 [计时记录](evidence/gui_checks.json)。

## 6 快速验证

核心算法和命令行只使用 Python 标准库，无需安装 Qt：

```bash
python -m unittest discover -s tests -v
python -m sdes encrypt 11010111 --key 1010000010
python -m sdes decrypt 10001100 --key 1010000010
python -m sdes crack --pairs-file evidence/known_pairs.txt
python tools/verify_vectors.py evidence/cross_vectors.json
```

加密输出 `10001100`，解密输出 `11010111`。重新生成全部数值实验还需要 `g++`：

```bash
python tools/run_experiments.py
```

## 7 目录

```text
main.py                    桌面程序入口
run.bat                    启动脚本（自动建 venv 并安装依赖）
build-exe.bat              打包脚本，生成 dist\S-DES.exe
S-DES.spec                 PyInstaller 打包配置
dist/S-DES.exe             Windows 单文件程序
sdes/                      算法、编码、破解、GUI、CLI
reference/                 独立 C++ 字符串实现
tests/                     核心和边界测试
tools/                     全量实验、GUI 检查、动图、报告生成
evidence/                  JSON / CSV / 日志 / 截图 / GIF
docs/                      Word 报告、Markdown 报告、指南和开发手册
output/pdf/                PDF 实验报告
.github/workflows/         跨平台自动验证
```

S-DES 的密钥空间只有 1024，属于教学密码。该实验逐字节独立加密，不具备实际安全通信所需的强度和完整性认证。
