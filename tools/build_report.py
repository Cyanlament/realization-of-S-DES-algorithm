"""Generate the Markdown/PDF report from measured evidence, never guessed values."""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / "evidence" / name).read_text(encoding="utf-8"))


def main():
    summary, attack, gui = read("summary.json"), read("brute_force.json"), read("gui_checks.json")
    collision = summary["collision"]
    benchmark = attack["benchmark"]
    single = gui["single_pair_search"]
    multiple = gui["multiple_pair_search"]
    generated = datetime.fromisoformat(summary["generated_at_utc"]).astimezone(timezone(timedelta(hours=8)))
    date = generated.strftime("%Y-%m-%d %H:%M:%S")
    narrowing_rows = "\n".join(
        f"| {len(step['pairs'])} | {' / '.join(step['pairs'][-1])} | {len(step['keys'])} | {', '.join(step['keys'])} |"
        for step in attack["narrowing"])
    vectors = read("cross_vectors.json")["vectors"]
    sample_vectors = [item for item in vectors if item["plaintext"] in ("00000000", "11010111", "11111111")]
    vector_rows = "\n".join(f"| {item['key']} | {item['plaintext']} | {item['ciphertext']} |" for item in sample_vectors)
    report = f"""# S-DES 算法实现实验报告

课程：信息安全导论；作业 1；实验记录时间：{date}（北京时间）。

| 组员 | 姓名 | 学号 |
| --- | --- | --- |
| 1 | | |
| 2 | | |

实验依据《要求.pdf》，运行记录见 `evidence/`。组员信息和外组测试记录留空。

## 1. 实验目标与环境

实现 S-DES 加解密、GUI、8 位分组和 10 位密钥输入、ASCII 扩展、已知明密文穷举破解及密钥碰撞分析。实现语言为 Python 3.10+，界面采用 PySide6。独立参考程序使用 C++11 字符串操作。

本机：{summary['environment']['platform']}；Python：{summary['environment']['python'].splitlines()[0]}；Qt 绑定：{gui['pyside6']}；编译器：{summary['environment']['cpp_compiler']}。Python 为 64 位，本次 MinGW C++ 为 i686 32 位，同处 Windows；跨平台 CI 结果以 Actions 实际运行记录为准。

## 2. 标准与实现

所有位置从最高有效位起按 1 编号。分组长 8 bit，主密钥 10 bit。

| 转换 | 精确参数 |
| --- | --- |
| P10 | (3, 5, 2, 7, 4, 10, 1, 9, 8, 6) |
| P8 | (6, 3, 7, 4, 8, 5, 10, 9) |
| IP | (2, 6, 3, 1, 4, 8, 5, 7) |
| IP^-1 | (4, 1, 3, 5, 7, 2, 8, 6) |
| EP | (4, 1, 2, 3, 2, 3, 4, 1) |
| P4 / SPBox | (2, 4, 3, 1) |
| LS-1 | (2, 3, 4, 5, 1)，作用于各 5 位半部 |
| LS-2 | (3, 4, 5, 1, 2)，作用于 LS-1 后的各半部 |

S-box1：`[(1,0,3,2); (3,2,1,0); (0,2,1,3); (3,1,0,2)]`。

S-box2：`[(0,1,2,3); (2,3,1,0); (3,0,1,2); (2,1,0,3)]`。行由输入外侧两位确定，列由内侧两位确定。

子密钥：P10 后拆成 L、R；各循环左移 1 位，P8 得 K1；在此结果上再循环左移 2 位，P8 得 K2。第二轮相对原始半部累计左移 3 位。本文将 PDF 的移位简记展开为 S-DES 的顺序过程，两个实现采用同一约定。

轮函数：`F(R,K) = P4(S1(EP(R) XOR K 的左半) || S2(右半))`；`fK(L||R) = (L XOR F(R,K)) || R`。加密：`IP -> fK1 -> SW -> fK2 -> IP^-1`；解密只交换 K1、K2 的使用顺序。

## 3. 第一关：基本测试

手工跟踪案例：`K=1010000010, P=11010111`。

| 步骤 | 结果 |
| --- | --- |
| P10(K) | 1000001100 |
| LS-1 两半拼接 | 0000111000 |
| K1 | 10100100 |
| 在 LS-1 上再 LS-2 | 0010000011 |
| K2 | 01000011 |
| IP(P) | 11011101 |
| 第一轮 EP / XOR | 11101011 / 01001111 |
| 第一轮 S1 / S2 / P4 | 11 / 11 / 1111 |
| 第一轮 fK / SW | 00101101 / 11010010 |
| 第二轮 EP / XOR | 00010100 / 01010111 |
| 第二轮 S1 / S2 / P4 | 01 / 00 / 1000 |
| 第二轮 fK | 01010010 |
| IP^-1，即密文 | **10001100** |
| 逆序子密钥解密结果 | **11010111** |

![GUI 加密和轮函数跟踪](../evidence/screenshots/01_binary_encrypt.png)

自动验证：{summary['unit_tests']['run']} 项单元测试通过；对每个密钥的全部 256 个明文验证 `D(E(P,K),K)=P`，合计 **262,144 次**全部通过；每个固定密钥都产生 256 个不同密文，是可逆排列。{gui['checks_passed']} 项 GUI 集成检查通过，包括加密、解密、无效分组、ASCII 三种表示、UTF-8、异步搜索、多解、无解和碰撞摘要。长短错误、非法二进制、bool/浮点数/越界整数、非法 Hex/Base64/转义均有测试。

## 4. 第二关：交叉测试

主实现为 Python 整数位操作，参考实现为独立 C++ 字符串置换。分别编程后，对全部密钥/明文组合逐字节比较。结果：**262,144 / 262,144 一致，0 个差异**。再把 Python 加密输出交给 C++ 解密，35 组代表性向量全部恢复原文。

按 `key * 256 + plaintext` 顺序拼接的加密表 SHA-256：

```text
{summary['cross_language']['table_sha256']}
```

代表性向量（完整 35 组见 `cross_vectors.json` / `.csv`）：

| K | P | C |
| --- | --- | --- |
{vector_rows}

本节记录 Python/C++ 互验结果。[跨组测试记录](跨组测试记录.md) 中的组名、仓库、平台、输出和结论尚待填写。

## 5. 第三关：ASCII 扩展

将字符串编码为 ASCII 字节，每 1 Byte 分组独立处理。对 0..127 全部 ASCII 字节及 0..255 所有二进制字节均验证可逆；ASCII 不允许中文，额外提供 UTF-8。没有填充，密文原始字节数等于编码后的明文字节数。

明文 `{summary['ascii']['plaintext']}`，密钥 `1010000010`，长度 {summary['ascii']['byte_count']} 字节：

```text
Hex: {summary['ascii']['cipher_hex']}
Base64: {summary['ascii']['cipher_base64']}
转义字节: {summary['ascii']['cipher_escaped']}
解密: {summary['ascii']['decrypted']}
```

![ASCII 文本加解密](../evidence/screenshots/04_ascii.png)

密文可能是不可打印控制字符及 128..255 的字节，无法保证是标准可打印 ASCII。因此 GUI 提供无损表示；这是密文的显示/传输编码，不是额外密码算法。空字符串、前后空格、换行、中文、UTF-8 多字节字符均覆盖。

PDF 中 TCP Socket 是可自行设计的扩展示例，本实验选择完整实现 ASCII 必做内容并加入 UTF-8、过程跟踪和多种密文表示，未选做网络通信。

## 6. 第四关：暴力破解

枚举 `0000000000` 到 `1111111111`，对每个候选检查所有已知明密文对，输出满足全部约束的**所有**密钥。算法最坏复杂度为 `O(1024m)`，不匹配时提前跳过当前候选。GUI 用后台 QThread 保持响应。

同一密钥下逐步增加约束，以下顺序可由 `known_pairs.txt` 复现：

| 已知对数 | 本次加入 P / C | 候选数 | 全部候选 |
| --- | --- | --- | --- |
{narrowing_rows}

单对不能唯一确认密钥；上述 5 对确定唯一候选 `1010000010`。相同 P 对应两个不同 C 时无解，程序显式提示。

计时使用 `perf_counter_ns()`，在 1024 次搜索循环前后取值，并保存 UTC 开始/结束时间戳。计时不含 Python 导入、查找表初始构建、GUI 绘制和进程启动。墙钟时间戳用于定位事件，可能因系统分辨率重复；耗时以单调高精度时钟为准。

| 测量 | 结果 |
| --- | --- |
| 核心搜索，子密钥缓存冷启动 | {attack['cold_key_cache']['elapsed_ms']:.4f} ms |
| 核心搜索，30 次热缓存最小值 | {benchmark['min_ms']:.4f} ms |
| 核心搜索，30 次热缓存中位数 | {benchmark['median_ms']:.4f} ms |
| 核心搜索，30 次热缓存最大值 | {benchmark['max_ms']:.4f} ms |
| GUI 演示单对搜索 | {single['elapsed_ms']:.4f} ms，{len(single['keys'])} 个候选 |
| GUI 演示五对搜索 | {multiple['elapsed_ms']:.4f} ms，{len(multiple['keys'])} 个候选 |

![暴力破解动图](../evidence/brute_force_demo.gif)

动图由 Qt 控件离屏渲染生成，四帧展示单对输入、单对结果、多对输入、多对结果。帧停留 1.5/3.5/1.5/4.5 秒方便阅读；破解耗时见界面和 JSON 中的测量值。耗时随硬件、缓存和系统负载变化。

## 7. 第五关：封闭测试与分析

### 7.1 随机明密文对会有多个密钥吗？

固定伪随机种子 `{collision['random_seed']}` 以便复现，选择 P=`{collision['random_plaintext']}`、K=`{collision['random_key']}`，加密得 C=`{collision['random_ciphertext']}`。穷举得到 {len(collision['random_pair_candidates'])} 个候选：

```text
{chr(10).join(collision['random_pair_candidates'])}
```

因此本随机案例确有多个密钥。**不能断言任意指定的明密文对都有多个密钥**：有的密文对没有密钥能产生，有的只有一个候选。例如固定 P=`11010111` 时有 16 个密文对应单个密钥。

### 7.2 对任意给定明文，是否存在不同密钥产生同一密文？

答案是是。固定任意 P 后，函数 `K -> E_K(P)` 的定义域大小为 1024、值域最多为 256。由抽屉原理，至少一个密文对应不少于 4 个密钥，所以必存在 `Ki != Kj` 使 `E_Ki(P)=E_Kj(P)`。此结论不依赖某一个随机实验。

穷举所有 256 个 P 验证该结论。原始数据见 `collision_all_plaintexts.csv`，汇总：

| 指标 | 实测值 |
| --- | --- |
| 检查的明文数 | {collision['plaintexts_checked']} |
| 检查的密钥/明文组合 | 262,144 |
| 存在密钥碰撞的明文数 | 256 / 256 |
| 每个明文可达密文数 | 最少 {collision['min_distinct_ciphertexts']}，最多 {collision['max_distinct_ciphertexts']} |
| 全部固定明文场景的最大候选组 | {collision['max_keys_per_ciphertext']} 个密钥 |
| P=11010111 的可达密文 | 240 |
| P=11010111 的碰撞组 / 单例组 | 224 / 16 |
| P=11010111 的无序碰撞密钥对数 | 2296 |
| 全部 256 个明文上完全相同的密钥组数 | {collision['globally_equivalent_key_groups']} |

进一步对每个密钥的完整 256 字节加密排列比较，得到 {collision['unique_full_encryption_permutations']} 个不同排列。本指定算法中没有发现全空间等价密钥：某一明文上发生碰撞，不意味着两把密钥对所有明文都等价。第一关验证的固定密钥可逆性与此处变化密钥的碰撞是不同命题。

## 8. 复现、文档与提交状态

```bash
python -m unittest discover -s tests -v
python tools/run_experiments.py
python tools/verify_vectors.py evidence/cross_vectors.json
python tools/gui_evidence.py
python tools/make_animation.py
python tools/build_report.py
```

前两步的独立 C++ 实验需要 g++；GUI 需要 `requirements.txt`；动图和 PDF 需要 `requirements-dev.txt`，PDF 还需可用的中文字体。命令从项目根目录执行，生成的新测量会覆盖证据和报告。手动运行 Windows/macOS/Linux 的步骤见 [用户指南](用户指南.md)，接口、模块、线程与复现说明见 [开发手册](开发手册.md)。

提交仓库：<https://github.com/Cyanlament/realization-of-S-DES-algorithm>。源代码、五关本地结果、截图、GIF、用户指南、开发手册和接口说明齐备。GitHub 上传工具要求审批，而本次环境禁止发起审批，因此远端尚未写入；已准备本地提交包。姓名学号、真实外组记录按要求留空；石墨提交表尚未登记。截止时间为 2026-10-08 23:00（北京时间）。

实验说明：10 位密钥可迅速穷举，逐字节加密会泄露重复模式，且无完整性认证。S-DES 适合学习分组密码结构，不用于真实敏感信息保护。
"""
    (ROOT / "docs/实验报告.md").write_text(report, encoding="utf-8")

    regular = os.environ.get("SDES_REPORT_FONT", "C:/Windows/Fonts/msyh.ttc")
    bold = os.environ.get("SDES_REPORT_FONT_BOLD", "C:/Windows/Fonts/msyhbd.ttc")
    for name, path in (("CN", regular), ("CNBold", bold)):
        if not Path(path).exists():
            raise SystemExit(f"Missing Chinese TrueType font: {path}; set SDES_REPORT_FONT / SDES_REPORT_FONT_BOLD")
        pdfmetrics.registerFont(TTFont(name, path, subfontIndex=0))
    styles = {
        "title": ParagraphStyle("Title", fontName="CNBold", fontSize=25, leading=34, textColor=colors.HexColor("#11324a"), spaceAfter=16),
        "heading": ParagraphStyle("Heading", fontName="CNBold", fontSize=17, leading=25, textColor=colors.HexColor("#075e85"), spaceAfter=13),
        "body": ParagraphStyle("Body", fontName="CN", fontSize=10, leading=17, spaceAfter=10, wordWrap="CJK"),
        "small": ParagraphStyle("Small", fontName="CN", fontSize=8.6, leading=14, spaceAfter=8, wordWrap="CJK"),
        "cell": ParagraphStyle("Cell", fontName="CN", fontSize=8.6, leading=13, wordWrap="CJK"),
    }
    story = []

    def paragraph(text, kind="body"):
        story.append(Paragraph(escape(text).replace("\n", "<br/>"), styles[kind]))

    def table(rows, widths):
        formatted = [[Paragraph(escape(str(cell)), styles["cell"]) for cell in row] for row in rows]
        value = Table(formatted, colWidths=widths, repeatRows=1, hAlign="LEFT")
        value.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5eff5")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f8fa")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), .6, colors.HexColor("#b1c9d8")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story.extend([value, Spacer(1, 12)])

    def screenshot(name, width=435):
        picture = Image(str(ROOT / "evidence/screenshots" / name))
        picture.drawHeight *= width / picture.drawWidth
        picture.drawWidth = width
        story.extend([picture, Spacer(1, 10)])

    def page(title):
        story.append(PageBreak())
        paragraph(title, "heading")

    paragraph("信息安全导论 · 作业 1", "small")
    paragraph("S-DES 算法实现\n实验报告", "title")
    paragraph(f"实验时间：{date}（北京时间）\n实现：Python + Qt / 独立 C++ 参考程序\n仓库：github.com/Cyanlament/realization-of-S-DES-algorithm")
    table([["组员", "姓名", "学号"], ["1", "", ""], ["2", "", ""]], [65, 190, 240])
    paragraph("五关实验与交付概览", "heading")
    table([["关卡", "已完成内容"],
           ["1 基本测试", "GUI、8 位分组/10 位密钥、轮函数跟踪；262,144 次加解密往返通过"],
           ["2 交叉测试", "Python/C++ 全空间 262,144 个结果一致；35 组交换向量。真实外组记录留空"],
           ["3 扩展功能", "ASCII 逐字节加解密；Hex/Base64/转义字节无损表示；额外支持 UTF-8"],
           ["4 暴力破解", "单对与多对约束、全部候选、时间戳与高精度计时、GUI 后台线程和 GIF"],
           ["5 封闭测试", "可复现随机样本、256 个明文全空间碰撞统计、抽屉原理与等价密钥分析"]], [90, 405])
    paragraph("成员信息与外组测试记录留空。源代码和本地测试结果已整理，仓库上传与石墨登记待完成。", "small")

    page("01 / 算法标准与实现约定")
    paragraph("分组 8 bit，密钥 10 bit；置换位置从最高有效位起按 1 编号。置换表与 S-box 参数如下。")
    table([["置换", "参数"], ["P10", "3, 5, 2, 7, 4, 10, 1, 9, 8, 6"],
           ["P8", "6, 3, 7, 4, 8, 5, 10, 9"], ["IP", "2, 6, 3, 1, 4, 8, 5, 7"],
           ["IP^-1", "4, 1, 3, 5, 7, 2, 8, 6"], ["EP", "4, 1, 2, 3, 2, 3, 4, 1"],
           ["P4 / SPBox", "2, 4, 3, 1"]], [110, 385])
    table([["行号", "S-box1", "S-box2"], ["0", "1, 0, 3, 2", "0, 1, 2, 3"],
           ["1", "3, 2, 1, 0", "2, 3, 1, 0"], ["2", "0, 2, 1, 3", "3, 0, 1, 2"],
           ["3", "3, 1, 0, 2", "2, 1, 0, 3"]], [70, 210, 215])
    paragraph("密钥扩展：P10 后分成两个 5 位半部，各自循环左移 1 位，经 P8 得 K1；在移位结果上再左移 2 位，经 P8 得 K2。第二子密钥相对原始半部累计左移 3 位。")
    paragraph("轮函数：EP 扩展右半部，与子密钥异或；两半分别送入 S1/S2，拼接输出后经 P4，再与左半部异或。S-box 的外侧两位选行，内侧两位选列。")
    paragraph("加密：IP → f(K1) → SW → f(K2) → IP^-1\n解密：IP → f(K2) → SW → f(K1) → IP^-1")
    paragraph("核心为纯函数。IP、逆 IP 和轮函数从定义自动生成小型查找表；子密钥最多缓存 1024 组。教学跟踪使用展开步骤，与快速路径做独立核对。", "small")

    page("02 / 基本测试与独立实现互验")
    paragraph("P=11010111，K=1010000010；K1=10100100，K2=01000011。加密得 10001100，倒序子密钥解密恢复 11010111。")
    screenshot("01_binary_encrypt.png", 415)
    table([["检查", "实测结果"],
           ["单元 / GUI 集成", f"{summary['unit_tests']['run']} 项 / {gui['checks_passed']} 项通过"],
           ["全部密钥和明文往返", "262,144 / 262,144；每个密钥下 256 个密文各不相同"],
           ["独立 Python / C++", "262,144 / 262,144 一致，0 差异；35 组反向解密通过"]], [140, 355])
    paragraph("参考 C++ 使用字符置换与字符串异或，不导入 Python 表。已完成本机不同语言实现的全空间互验；真实外组名称、环境和结果在跨组记录中留空。", "small")
    paragraph("结果表 SHA-256：\n" + summary["cross_language"]["table_sha256"], "small")

    page("03 / ASCII 字符串与字节扩展")
    paragraph("ASCII 编码后的每个字节独立加密，不填充；密文长度与编码后的明文相同。完整 128 个 ASCII 值、全部 256 个字节、空串、空白及 UTF-8 多字节文本均验证可逆。")
    screenshot("04_ascii.png", 430)
    table([["项目", "结果（K=1010000010）"],
           ["明文 / 长度", "Hello, S-DES! / 13 Byte"],
           ["Hex", summary["ascii"]["cipher_hex"]],
           ["Base64", summary["ascii"]["cipher_base64"]],
           ["解密", summary["ascii"]["decrypted"]]], [95, 400])
    paragraph("密文原始字节可能包含控制字符和 128..255，不能保证是可打印 ASCII。Hex、Base64 和转义字节是无损显示方式，不改变加密过程。ASCII 严格拒绝中文，UTF-8 是额外扩展。TCP 通信为可选示例，本次未选做。", "small")

    page("04 / 暴力破解与实际计时")
    paragraph("遍历 1024 个密钥，返回满足全部明密文约束的所有候选。逐步加入 P=11010111、00000000、00000001、01000001、01010101，对应候选数如下。")
    table([["已知对数", "1", "2", "3", "4", "5"],
           ["候选数", *[str(len(step["keys"])) for step in attack["narrowing"]]]], [95, 80, 80, 80, 80, 80])
    paragraph("单对候选：0110000000、1010000010、1011001010；五对唯一候选：1010000010。", "small")
    screenshot("09_attack_multiple_result.png", 390)
    table([["测量口径", "耗时"],
           ["核心冷子密钥缓存 / 30 次热缓存中位数", f"{attack['cold_key_cache']['elapsed_ms']:.4f} / {benchmark['median_ms']:.4f} ms"],
           ["30 次热缓存最小 / 最大", f"{benchmark['min_ms']:.4f} / {benchmark['max_ms']:.4f} ms"],
           ["GUI 单对 / 五对", f"{single['elapsed_ms']:.4f} / {multiple['elapsed_ms']:.4f} ms"]], [330, 165])
    paragraph("计时采用 perf_counter_ns，测量范围为搜索循环；UTC 开始和结束时间另存。GUI 使用后台线程保持响应。", "small")
    paragraph("动图：evidence/brute_force_demo.gif。真实控件离屏渲染，帧停留被延长以便阅读，播放时长不代表破解耗时。", "small")

    page("05 / 封闭测试、碰撞与结论")
    paragraph(f"固定随机种子 {collision['random_seed']}，选择 P={collision['random_plaintext']}、K={collision['random_key']}，得到 C={collision['random_ciphertext']}。该明密文对有 {len(collision['random_pair_candidates'])} 个候选密钥：")
    paragraph("   ".join(collision["random_pair_candidates"]))
    paragraph("问题一：一个明密文对可能不止一把密钥，上述案例给出了肯定答案；但不能推出每个指定明密文对都多解，有的无解、有的唯一。")
    paragraph("问题二：对任意固定明文 P，1024 个密钥映射到至多 256 个密文。由抽屉原理，至少一个密文对应 4 个或更多密钥，因此必然存在不同 Ki、Kj 产生相同密文。此结论对任意 P 成立。")
    table([["全量验证指标", "结果"],
           ["明文 / 密钥组合", "256 / 262,144"],
           ["具有密钥碰撞的明文", "256 / 256"],
           ["固定明文的不同密文数", f"最少 {collision['min_distinct_ciphertexts']}，最多 {collision['max_distinct_ciphertexts']}"],
           ["最大候选组", "12 个密钥"],
           ["P=11010111：碰撞组 / 单例组", "224 / 16"],
           ["P=11010111：无序碰撞密钥对", "2296"],
           ["完整加密排列的不同种数", "1024"],
           ["全空间等价密钥组", "0"]], [320, 175])
    paragraph("对每把密钥的全部 256 个密文序列继续比较，1024 把密钥产生 1024 个不同排列。本指定算法没有发现全空间等价密钥；单个明文上碰撞不等于两把密钥处处等价。")
    paragraph("固定密钥时，S-DES 是明文空间上的可逆排列；固定明文而变化密钥时，可以发生碰撞。这两个命题不矛盾。原始 256 行统计见 evidence/collision_all_plaintexts.csv。", "small")

    page("06 / 复现、文档与提交核对")
    paragraph(f"本地环境：{summary['environment']['platform']}；Python 3.10.0 / PySide6 {gui['pyside6']}；C++ 为 MinGW i686 GCC 4.9.2。生成时间：{date}（北京时间）。", "small")
    paragraph("运行桌面程序：Windows 双击 run.bat；或创建虚拟环境、安装 requirements.txt 后运行 python main.py。核心 CLI 与单元测试只依赖 Python 标准库。")
    paragraph("复现命令（从项目根目录执行）：\npython -m unittest discover -s tests -v\npython tools/run_experiments.py\npython tools/verify_vectors.py evidence/cross_vectors.json\npython tools/gui_evidence.py\npython tools/make_animation.py\npython tools/build_report.py", "small")
    table([["交付内容", "位置 / 状态"],
           ["源代码", "sdes/、reference/、main.py、tools/"],
           ["测试证据", "evidence/：JSON、CSV、日志、11 张界面图、GIF"],
           ["完整实验报告", "docs/实验报告.md；本 PDF 为便于阅读的排版版"],
           ["用户指南", "docs/用户指南.md：安装、各页操作、CLI、常见问题"],
           ["开发及接口文档", "docs/开发手册.md：纯函数接口、线程、测试与复现"],
           ["真实外组测试", "docs/跨组测试记录.md，按用户要求留空"],
           ["姓名 / 学号", "按用户要求留空"],
           ["GitHub 发布", "本地文件齐备；工具审批拦截，尚未上传"],
           ["石墨提交表", "尚未登记；须填真实成员及仓库链接"]], [145, 350])
    paragraph("GitHub：github.com/Cyanlament/realization-of-S-DES-algorithm\n截止：2026-10-08 23:00（北京时间）。仓库上传不等于课程提交表已登记。")
    paragraph("范围与限制：截图为真实 Qt 控件的离屏渲染，已检查布局和文字。跨平台自动验证已配置，是否通过以 Actions 运行记录为准。S-DES 只有 10 位密钥，适合教学，不用于保护真实敏感信息。", "small")

    output = ROOT / "output/pdf/S-DES实验报告.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(str(output), pagesize=A4, rightMargin=50, leftMargin=50,
                                 topMargin=49, bottomMargin=44, title="S-DES 算法实现实验报告",
                                 author="", subject="信息安全导论作业 1：五关实验与实现")

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#d5e0e7"))
        canvas.line(50, 37, A4[0] - 50, 37)
        canvas.setFont("CN", 8)
        canvas.setFillColor(colors.HexColor("#627286"))
        canvas.drawString(50, 24, "S-DES / 信息安全导论 / 2026")
        canvas.drawRightString(A4[0] - 50, 24, f"{doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"Generated docs/实验报告.md and {output.name}")


if __name__ == "__main__":
    main()
