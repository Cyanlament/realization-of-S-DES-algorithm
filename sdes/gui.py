"""Qt desktop UI; cryptographic functions stay independent from widgets."""
import json
import sys
from datetime import datetime

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPlainTextEdit, QProgressBar, QPushButton, QTabWidget,
    QVBoxLayout, QWidget,
)

from .analysis import brute_force, collisions_for_plaintext, parse_pairs
from .core import parse_bits, trace_block, transform_bytes
from .encoding import decode_plaintext, encode_plaintext, parse_ciphertext, render_ciphertext


class SearchWorker(QThread):
    progress = Signal(int)
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, pairs, parent=None):
        super().__init__(parent)
        self.pairs = tuple(pairs)

    def run(self):
        try:
            result = brute_force(self.pairs, self.progress.emit, self.isInterruptionRequested)
            self.result_ready.emit(result)
        except Exception as error:
            self.failed.emit(str(error))


def text_area(placeholder="", readonly=False):
    editor = QPlainTextEdit()
    editor.setPlaceholderText(placeholder)
    editor.setReadOnly(readonly)
    editor.setFont(QFont("Consolas", 11))
    return editor


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("S-DES 实验室 | 信息安全导论 · 作业 1")
        self.resize(1040, 820)
        self.worker = None
        self.last_search = None
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 22, 28, 18)
        title = QLabel("S-DES 实验室")
        title.setObjectName("title")
        layout.addWidget(title)
        subtitle = QLabel("8 位分组 / 10 位密钥    ·    严格采用实验要求中的 S-box2")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self.build_block_tab()
        self.build_text_tab()
        self.build_search_tab()
        self.build_collision_tab()
        footer = QLabel("教学实验：每字节独立处理。密钥空间为 1024，不适用于实际敏感信息保护。")
        footer.setObjectName("subtitle")
        layout.addWidget(footer)
        self.setCentralWidget(root)
        self.setStyleSheet("""
            QMainWindow { background: #f3f5f8; }
            QWidget { color: #172b40; font-family: 'Microsoft YaHei UI'; font-size: 14px; }
            QLabel#title { font-size: 29px; font-weight: 700; }
            QLabel#subtitle { color: #627286; font-size: 12px; padding-bottom: 8px; }
            QTabWidget::pane { border: 1px solid #d7e0e8; background: white; border-radius: 4px; }
            QTabBar::tab { padding: 13px 24px; background: #e7edf3; margin-right: 3px; }
            QTabBar::tab:selected { background: white; color: #075e85; font-weight: 700; }
            QLineEdit, QPlainTextEdit, QComboBox { background: #fcfdff; border: 1px solid #b9c9d6;
                border-radius: 4px; padding: 8px; selection-background-color: #b9dfed; }
            QPushButton { background: #075e85; color: white; border: none; border-radius: 4px;
                padding: 10px 20px; font-weight: 600; }
            QPushButton:disabled { background: #aebdc8; }
            QPushButton:hover { background: #08749e; }
            QProgressBar { border: 1px solid #b9c9d6; border-radius: 4px; text-align: center; height: 22px; }
            QProgressBar::chunk { background: #62bad0; }
        """)

    def add_tab(self, label):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        self.tabs.addTab(page, label)
        return layout

    def build_block_tab(self):
        layout = self.add_tab("01  分组加解密")
        form = QFormLayout()
        self.block_key = QLineEdit("1010000010")
        self.block_input = QLineEdit("11010111")
        form.addRow("密钥 K · 10 bit", self.block_key)
        form.addRow("输入分组 · 8 bit", self.block_input)
        layout.addLayout(form)
        row = QHBoxLayout()
        for title, decrypt in (("加密", False), ("解密", True)):
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, decrypt=decrypt: self.process_block(decrypt))
            row.addWidget(button)
        layout.addLayout(row)
        self.block_status = QLabel("输入明文后点击加密；解密时输入密文。")
        layout.addWidget(self.block_status)
        self.block_output = QLineEdit()
        self.block_output.setReadOnly(True)
        self.block_output.setPlaceholderText("结果分组")
        layout.addWidget(self.block_output)
        copy = QPushButton("复制结果")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.block_output.text()))
        layout.addWidget(copy)
        layout.addWidget(QLabel("轮函数跟踪 / 子密钥、扩展置换、异或与 S-box 输出"))
        self.block_trace = text_area(readonly=True)
        layout.addWidget(self.block_trace, 1)

    def process_block(self, decrypt=False):
        self.block_output.clear()
        self.block_trace.clear()
        try:
            result = trace_block(parse_bits(self.block_input.text(), 8),
                                 parse_bits(self.block_key.text(), 10, "密钥"), decrypt)
            self.block_output.setText(result["output"])
            lines = [f"K1 = {result['subkeys'][0]}    K2 = {result['subkeys'][1]}",
                     f"IP = {result['ip']}"]
            for step in result["rounds"]:
                lines.extend([f"第 {step['round']} 轮：子密钥 {step['subkey']}",
                              f"  EP={step['ep']}   XOR={step['xor']}",
                              f"  S1={step['s1']}  S2={step['s2']}  P4={step['p4']}  fK={step['fk']}"])
                if "sw" in step:
                    lines.append(f"  SW={step['sw']}")
            lines.append(f"IP^-1 = {result['output']}")
            self.block_trace.setPlainText("\n".join(lines))
            self.block_status.setText(("解密" if decrypt else "加密") + "完成 · 输出 8 位分组")
        except ValueError as error:
            self.block_status.setText("输入错误：" + str(error))

    def build_text_tab(self):
        layout = self.add_tab("02  文本扩展")
        form = QFormLayout()
        self.text_key = QLineEdit("1010000010")
        self.text_encoding = QComboBox()
        self.text_encoding.addItems(["ASCII", "UTF-8"])
        self.cipher_format = QComboBox()
        self.cipher_format.addItems(["Hex", "Base64", "转义字节"])
        form.addRow("密钥 K", self.text_key)
        form.addRow("明文编码", self.text_encoding)
        form.addRow("密文表示", self.cipher_format)
        layout.addLayout(form)
        layout.addWidget(QLabel("明文 / 每 1 Byte 独立加密，保留空格与换行"))
        self.plaintext = text_area()
        self.plaintext.setPlainText("Hello, S-DES!")
        layout.addWidget(self.plaintext, 1)
        buttons = QHBoxLayout()
        encrypt = QPushButton("明文 → 加密")
        decrypt = QPushButton("密文 → 解密")
        encrypt.clicked.connect(lambda: self.process_text(False))
        decrypt.clicked.connect(lambda: self.process_text(True))
        buttons.addWidget(encrypt)
        buttons.addWidget(decrypt)
        layout.addLayout(buttons)
        layout.addWidget(QLabel("密文 / 原始字节可含不可打印值，用所选格式无损表示"))
        self.ciphertext = text_area()
        layout.addWidget(self.ciphertext, 1)
        self.text_status = QLabel("ASCII 为必做扩展；UTF-8 支持中文。密文格式切换后请重新加密。")
        self.text_status.setWordWrap(True)
        layout.addWidget(self.text_status)

    def process_text(self, decrypt=False):
        try:
            key = parse_bits(self.text_key.text(), 10, "密钥")
            mode, representation = self.text_encoding.currentText(), self.cipher_format.currentText()
            if decrypt:
                data = parse_ciphertext(self.ciphertext.toPlainText(), representation)
                output = decode_plaintext(transform_bytes(data, key, True), mode)
                self.plaintext.setPlainText(output)
            else:
                data = encode_plaintext(self.plaintext.toPlainText(), mode)
                output = render_ciphertext(transform_bytes(data, key), representation)
                self.ciphertext.setPlainText(output)
            self.text_status.setText(f"{'解密' if decrypt else '加密'}完成 · {len(data)} 个字节 · {mode} / {representation}")
        except ValueError as error:
            self.text_status.setText("输入错误：" + str(error))

    def build_search_tab(self):
        layout = self.add_tab("03  暴力破解")
        layout.addWidget(QLabel("输入使用同一密钥的明密文对，每行格式：8 位明文 空格 8 位密文"))
        self.pair_input = text_area()
        self.pair_input.setPlainText("11010111 10001100")
        self.pair_input.setMaximumHeight(125)
        layout.addWidget(self.pair_input)
        row = QHBoxLayout()
        self.search_button = QPushButton("遍历全部 1024 个密钥")
        self.cancel_button = QPushButton("停止")
        self.cancel_button.setEnabled(False)
        self.search_button.clicked.connect(self.start_search)
        self.cancel_button.clicked.connect(self.cancel_search)
        row.addWidget(self.search_button)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)
        self.search_progress = QProgressBar()
        self.search_progress.setRange(0, 1024)
        self.search_progress.setValue(0)
        layout.addWidget(self.search_progress)
        self.search_status = QLabel("等待开始。候选密钥可能不唯一；增加独立明密文对可进一步筛选。")
        self.search_status.setWordWrap(True)
        layout.addWidget(self.search_status)
        self.search_result = text_area(readonly=True)
        layout.addWidget(self.search_result, 1)
        self.pair_input.textChanged.connect(self.reset_search_result)

    def reset_search_result(self):
        self.last_search = None
        self.search_result.clear()
        self.search_progress.setValue(0)
        self.search_status.setText("已修改明密文对，等待重新搜索。")

    def start_search(self):
        if self.worker is not None and self.worker.isRunning():
            return
        try:
            pairs = parse_pairs(self.pair_input.toPlainText())
        except ValueError as error:
            self.search_status.setText("输入错误：" + str(error))
            return
        self.last_search = None
        self.search_result.clear()
        self.search_progress.setValue(0)
        self.search_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.pair_input.setReadOnly(True)
        self.search_status.setText("正在搜索 · " + datetime.now().astimezone().isoformat(timespec="milliseconds"))
        self.worker = SearchWorker(pairs, self)
        self.worker.progress.connect(self.search_progress.setValue)
        self.worker.result_ready.connect(self.finish_search)
        self.worker.failed.connect(self.search_failed)
        self.worker.finished.connect(self.search_thread_finished)
        self.worker.start()

    def finish_search(self, result):
        self.last_search = result
        data = result.to_dict()
        state = "已停止（部分结果）" if result.cancelled else "搜索完成"
        self.search_status.setText(f"{state} · 检查 {result.checked}/1024 · 候选 {len(result.keys)} 个 · 耗时 {data['elapsed_ms']:.3f} ms")
        lines = [f"开始时间（UTC）：{result.started_at}", f"结束时间（UTC）：{result.ended_at}",
                 f"单调高精度计时：{result.elapsed_ns} ns = {data['elapsed_ms']:.3f} ms", "",
                 "候选密钥（全部）:", *data["keys"]]
        if not result.keys:
            lines.append("没有满足全部已知明密文对的密钥。")
        elif len(result.keys) == 1:
            lines.append("当前已知明密文对确定了唯一候选密钥。")
        else:
            lines.append("存在多个候选，不能仅凭这些明密文对断言某一个是真实密钥。")
        self.search_result.setPlainText("\n".join(lines))

    def search_failed(self, message):
        self.search_status.setText("搜索失败：" + message)

    def search_thread_finished(self):
        self.search_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.pair_input.setReadOnly(False)

    def cancel_search(self):
        if self.worker is not None:
            self.worker.requestInterruption()

    def build_collision_tab(self):
        layout = self.add_tab("04  碰撞分析")
        layout.addWidget(QLabel("固定一个明文分组，按密文汇总全部 1024 个密钥。"))
        self.collision_input = QLineEdit("11010111")
        layout.addWidget(self.collision_input)
        button = QPushButton("分析该明文的密钥碰撞")
        button.clicked.connect(self.process_collisions)
        layout.addWidget(button)
        self.collision_status = QLabel("1024 个密钥映射到至多 256 个密文，至少存在一组密钥碰撞。")
        self.collision_status.setWordWrap(True)
        layout.addWidget(self.collision_status)
        self.collision_output = text_area(readonly=True)
        layout.addWidget(self.collision_output, 1)

    def process_collisions(self):
        self.collision_output.clear()
        try:
            groups = collisions_for_plaintext(parse_bits(self.collision_input.text(), 8))
            collided = [(cipher, keys) for cipher, keys in groups.items() if len(keys) > 1]
            self.collision_status.setText(f"覆盖 {len(groups)} 个密文 · {len(collided)} 组碰撞 · 最大 {max(map(len, groups.values()))} 个密钥/密文")
            self.collision_output.setPlainText("\n".join(
                f"密文 {cipher:08b} | {len(keys)} 个密钥\n  " + "  ".join(f"{key:010b}" for key in keys)
                for cipher, keys in collided))
        except ValueError as error:
            self.collision_status.setText("输入错误：" + str(error))

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait()
        event.accept()


def run():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
