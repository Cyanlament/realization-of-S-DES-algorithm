"""S-DES desktop window and background key search."""
import json
import sys
from datetime import datetime

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QFrame,
    QHBoxLayout, QHeaderView, QLineEdit, QMainWindow, QPlainTextEdit,
    QProgressBar, QScrollArea, QStackedWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from .analysis import brute_force, collisions_for_plaintext, parse_pairs
from .core import encrypt_block, parse_bits, trace_block, transform_bytes
from .encoding import decode_plaintext, encode_plaintext, parse_ciphertext, render_ciphertext
from .ui_theme import configure_fonts, font, stylesheet
from .ui_widgets import BitReadout, CollisionHistogram, RoundDetails, Select, button, divider, icon, label, panel, status


class SearchWorker(QThread):
    progress = Signal(int)
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, pairs, parent=None):
        super().__init__(parent)
        self.pairs = tuple(pairs)

    def run(self):
        try:
            self.result_ready.emit(brute_force(self.pairs, self.progress.emit, self.isInterruptionRequested))
        except Exception as error:
            self.failed.emit(str(error))


def editor(placeholder="", readonly=False, role=None):
    widget = QPlainTextEdit()
    widget.setPlaceholderText(placeholder)
    widget.setReadOnly(readonly)
    widget.setMinimumWidth(0)
    if role:
        widget.setObjectName(role)
    return widget


def line_input(value, role="keyInput", name=""):
    widget = QLineEdit(value)
    widget.setObjectName(role)
    widget.setAccessibleName(name)
    widget.setMinimumWidth(0)
    return widget


def heading_row(title, trailing=None):
    row = QHBoxLayout()
    row.addWidget(label(title, "sectionTitle"))
    row.addStretch()
    if trailing:
        row.addWidget(trailing)
    return row


class MainWindow(QMainWindow):
    PAGE_NAMES = ("分组加解密", "文本加解密", "暴力破解", "碰撞分析")
    PAGE_DESCRIPTIONS = (
        "输入一组数据，查看每一轮变换。",
        "在文字与密文之间转换。",
        "用已知的明密文对，寻找匹配的密钥。",
        "固定明文，观察不同密钥产生的密文。",
    )

    def __init__(self):
        super().__init__()
        configure_fonts(QApplication.instance())
        self.setWindowTitle("S-DES · 密码工作台")
        self.resize(1180, 820)
        self.setMinimumSize(980, 690)
        self.worker = None
        self.last_search = None
        self.block_decrypt = False
        self._text_format = "Hex"
        root = QWidget()
        root.setObjectName("workspace")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(182)
        navigation = QVBoxLayout(sidebar)
        navigation.setContentsMargins(18, 30, 18, 22)
        navigation.setSpacing(8)
        navigation.addWidget(label("S-DES", "brand"))
        navigation.addWidget(label("密码工作台", "muted"))
        navigation.addSpacing(30)
        self.nav_group = QButtonGroup(self)
        self.nav_buttons = []
        for index, (name, glyph) in enumerate(zip(self.PAGE_NAMES, ("block", "text", "search", "collision"))):
            item = button(name, kind="nav")
            item.setCheckable(True)
            item.setIcon(icon(glyph))
            item.setToolTip(name)
            self.nav_group.addButton(item, index)
            self.nav_buttons.append(item)
            navigation.addWidget(item)
        navigation.addStretch()
        navigation.addWidget(divider())
        navigation.addSpacing(6)
        navigation.addWidget(label("分组  8 bit\n密钥  10 bit", "caption"))
        root_layout.addWidget(sidebar)

        workspace = QVBoxLayout()
        workspace.setContentsMargins(28, 28, 28, 24)
        workspace.setSpacing(18)
        header = QVBoxLayout()
        header.setSpacing(7)
        self.page_title = label(self.PAGE_NAMES[0], "pageTitle")
        self.page_description = label(self.PAGE_DESCRIPTIONS[0], "pageDescription")
        header.addWidget(self.page_title)
        header.addWidget(self.page_description)
        workspace.addLayout(header)
        self.tabs = QStackedWidget()
        workspace.addWidget(self.tabs, 1)
        root_layout.addLayout(workspace, 1)
        self.build_block_tab()
        self.build_text_tab()
        self.build_search_tab()
        self.build_collision_tab()
        self.nav_group.idClicked.connect(self.tabs.setCurrentIndex)
        self.tabs.currentChanged.connect(self.page_changed)
        self.page_changed(0)
        self.setCentralWidget(root)
        self.setStyleSheet(stylesheet())
        self.run_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.run_shortcut.activated.connect(self.run_current_page)

    def page_changed(self, index):
        self.page_title.setText(self.PAGE_NAMES[index])
        self.page_description.setText(self.PAGE_DESCRIPTIONS[index])
        self.nav_buttons[index].setChecked(True)

    def add_page(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        self.tabs.addWidget(scroll)
        return layout

    def run_current_page(self):
        index = self.tabs.currentIndex()
        if index == 0:
            self.process_block(self.block_decrypt)
        elif index == 1:
            self.process_text()
        elif index == 2:
            self.start_search()
        else:
            self.process_collisions()

    def build_block_tab(self):
        layout = self.add_page()
        top = QHBoxLayout()
        top.setSpacing(16)
        inputs, form = panel()
        segments = QFrame()
        segments.setObjectName("segments")
        segment_layout = QHBoxLayout(segments)
        segment_layout.setContentsMargins(3, 3, 3, 3)
        segment_layout.setSpacing(2)
        self.block_modes = QButtonGroup(self)
        for decrypt, title in ((False, "加密"), (True, "解密")):
            item = button(title, kind="segment")
            item.setCheckable(True)
            self.block_modes.addButton(item, int(decrypt))
            item.clicked.connect(lambda checked=False, mode=decrypt: self.set_block_mode(mode))
            segment_layout.addWidget(item)
        self.block_modes.button(0).setChecked(True)
        form.addLayout(heading_row("输入", segments))
        self.block_input_label = label("明文分组  ·  8 位", "muted")
        form.addWidget(self.block_input_label)
        self.block_input = line_input("11010111", "binaryInput", "输入分组")
        form.addWidget(self.block_input)
        form.addWidget(label("密钥  ·  10 位", "muted"))
        self.block_key = line_input("1010000010", name="分组密钥")
        form.addWidget(self.block_key)
        actions = QHBoxLayout()
        self.block_run = button("运行加密  →", lambda: self.process_block(self.block_decrypt))
        self.block_run.setToolTip("Ctrl + Enter")
        actions.addWidget(self.block_run)
        actions.addStretch()
        actions.addWidget(button("载入示例", self.load_block_example, "ghost"))
        form.addLayout(actions)
        top.addWidget(inputs, 4)

        output, result = panel()
        self.block_result_title = label("加密结果", "sectionTitle")
        result.addWidget(self.block_result_title)
        result.addStretch()
        self.block_output = BitReadout()
        result.addWidget(self.block_output)
        self.block_meta = label("HEX  —     DEC  —", "bitMeta")
        result.addWidget(self.block_meta)
        result.addStretch()
        self.block_status = label("运行后显示结果", "muted", True)
        result.addWidget(self.block_status)
        result_actions = QHBoxLayout()
        self.block_copy = button("复制结果", self.copy_block, "secondary")
        self.block_reuse = button("用作输入", self.reuse_block, "ghost")
        self.block_copy.setEnabled(False)
        self.block_reuse.setEnabled(False)
        result_actions.addWidget(self.block_copy)
        result_actions.addWidget(self.block_reuse)
        result_actions.addStretch()
        result.addLayout(result_actions)
        top.addWidget(output, 5)
        layout.addLayout(top)

        trace, trace_layout = panel()
        trace_layout.addLayout(heading_row("运算过程", label("两轮 Feistel", "caption")))
        self.trace_path = label("IP  --------     →     SW  --------     →     输出  --------", "bitMeta")
        self.trace_path.setWordWrap(True)
        trace_layout.addWidget(self.trace_path)
        rounds = QHBoxLayout()
        rounds.setSpacing(14)
        self.round_views = [RoundDetails(1), RoundDetails(2)]
        for view in self.round_views:
            rounds.addWidget(view, 1)
        trace_layout.addLayout(rounds)
        layout.addWidget(trace)
        layout.addStretch()
        self.block_input.textChanged.connect(self.clear_block_result)
        self.block_key.textChanged.connect(self.clear_block_result)

    def set_block_mode(self, decrypt, clear=True):
        self.block_decrypt = decrypt
        self.block_modes.button(int(decrypt)).setChecked(True)
        operation = "解密" if decrypt else "加密"
        self.block_input_label.setText(("密文" if decrypt else "明文") + "分组  ·  8 位")
        self.block_result_title.setText(operation + "结果")
        self.block_run.setText("运行" + operation + "  →")
        if clear:
            self.clear_block_result()

    def clear_block_result(self):
        self.block_output.clear()
        self.block_meta.setText("HEX  —     DEC  —")
        status(self.block_status, "运行后显示结果")
        self.block_copy.setEnabled(False)
        self.block_reuse.setEnabled(False)
        self.trace_path.setText("IP  --------     →     SW  --------     →     输出  --------")
        for view in self.round_views:
            view.set_data()

    def process_block(self, decrypt=False):
        self.set_block_mode(decrypt, clear=False)
        self.clear_block_result()
        try:
            result = trace_block(parse_bits(self.block_input.text(), 8), parse_bits(self.block_key.text(), 10, "密钥"), decrypt)
            self.block_output.setText(result["output"])
            value = int(result["output"], 2)
            self.block_meta.setText(f"HEX  {value:02X}     DEC  {value}")
            for widget, data in zip(self.round_views, result["rounds"]):
                widget.set_data(data)
            self.trace_path.setText(f"IP  {result['ip']}     →     SW  {result['rounds'][0]['sw']}     →     输出  {result['output']}")
            status(self.block_status, "解密完成" if decrypt else "加密完成", "success")
            self.block_copy.setEnabled(True)
            self.block_reuse.setEnabled(True)
        except ValueError as error:
            status(self.block_status, "输入错误：" + str(error), "error")

    def load_block_example(self):
        self.block_key.setText("1010000010")
        self.block_input.setText("11101000" if self.block_decrypt else "11010111")
        self.process_block(self.block_decrypt)

    def copy_block(self):
        if self.block_output.text():
            QApplication.clipboard().setText(self.block_output.text())
            status(self.block_status, "结果已复制", "success")

    def reuse_block(self):
        result, next_mode = self.block_output.text(), not self.block_decrypt
        if result:
            self.block_input.setText(result)
            self.set_block_mode(next_mode)
            self.block_input.setFocus()

    def build_text_tab(self):
        layout = self.add_page()
        controls, control_layout = panel(18)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(18)
        self.text_key = line_input("1010000010", name="文本密钥")
        self.text_encoding = Select()
        self.text_encoding.addItems(["ASCII", "UTF-8"])
        self.text_encoding.setAccessibleName("明文编码")
        self.cipher_format = Select()
        self.cipher_format.addItems(["Hex", "Base64", "转义字节"])
        self.cipher_format.setAccessibleName("密文格式")
        for title, widget, stretch in (("密钥", self.text_key, 2), ("明文编码", self.text_encoding, 1), ("密文格式", self.cipher_format, 1)):
            column = QVBoxLayout()
            column.setSpacing(8)
            column.addWidget(label(title, "muted"))
            column.addWidget(widget)
            toolbar.addLayout(column, stretch)
        control_layout.addLayout(toolbar)
        layout.addWidget(controls)
        columns = QHBoxLayout()
        columns.setSpacing(16)
        plaintext_panel, plain = panel()
        plain.addLayout(heading_row("明文", button("加密  →", lambda: self.process_text(False))))
        plain.addWidget(divider())
        self.plaintext = editor("输入文字…", role="documentEditor")
        self.plaintext.setAccessibleName("明文")
        self.plaintext.setPlainText("Hello, S-DES!")
        self.plaintext.setMinimumHeight(300)
        plain.addWidget(self.plaintext, 1)
        plain.addWidget(label("保留空格与换行", "caption"))
        columns.addWidget(plaintext_panel, 1)
        ciphertext_panel, cipher = panel()
        cipher.addLayout(heading_row("密文", button("←  解密", lambda: self.process_text(True), "secondary")))
        cipher.addWidget(divider())
        self.ciphertext = editor("加密结果会显示在这里，也可以粘贴已有密文。", role="documentEditor")
        self.ciphertext.setAccessibleName("密文")
        self.ciphertext.setMinimumHeight(300)
        cipher.addWidget(self.ciphertext, 1)
        cipher_actions = QHBoxLayout()
        cipher_actions.addWidget(label("可切换 Hex、Base64 或转义字节", "caption"))
        cipher_actions.addStretch()
        cipher_actions.addWidget(button("复制", lambda: QApplication.clipboard().setText(self.ciphertext.toPlainText()), "ghost"))
        cipher.addLayout(cipher_actions)
        columns.addWidget(ciphertext_panel, 1)
        layout.addLayout(columns, 1)
        self.text_status = label("", "muted", True)
        layout.addWidget(self.text_status)
        self.cipher_format.currentTextChanged.connect(self.convert_text_format)

    def convert_text_format(self, representation):
        previous = self._text_format
        try:
            text = self.ciphertext.toPlainText()
            if text:
                self.ciphertext.setPlainText(render_ciphertext(parse_ciphertext(text, previous), representation))
            self._text_format = representation
            status(self.text_status, "")
        except ValueError:
            self.cipher_format.blockSignals(True)
            self.cipher_format.setCurrentText(previous)
            self.cipher_format.blockSignals(False)
            status(self.text_status, "请先修正密文，再切换格式。", "error")

    def process_text(self, decrypt=False):
        try:
            key = parse_bits(self.text_key.text(), 10, "密钥")
            mode, representation = self.text_encoding.currentText(), self.cipher_format.currentText()
            if decrypt:
                data = parse_ciphertext(self.ciphertext.toPlainText(), representation)
                self.plaintext.setPlainText(decode_plaintext(transform_bytes(data, key, True), mode))
            else:
                data = encode_plaintext(self.plaintext.toPlainText(), mode)
                self.ciphertext.setPlainText(render_ciphertext(transform_bytes(data, key), representation))
            status(self.text_status, f"{'解密' if decrypt else '加密'}完成  ·  {len(data)} 字节  ·  {mode}", "success")
        except ValueError as error:
            status(self.text_status, "输入错误：" + str(error), "error")

    def build_search_tab(self):
        layout = self.add_page()
        columns = QHBoxLayout()
        columns.setSpacing(16)
        known_panel, known = panel()
        known_panel.setMaximumWidth(360)
        known.addLayout(heading_row("已知明密文", button("多组示例", self.load_search_example, "ghost")))
        known.addWidget(label("每行一组，用空格分隔。", "muted"))
        self.pair_input = editor("11010111 11101000")
        self.pair_input.setAccessibleName("已知明密文对")
        self.pair_input.setPlainText("11010111 11101000")
        self.pair_input.setMinimumHeight(270)
        known.addWidget(self.pair_input, 1)
        known.addWidget(label("明文 8 位     密文 8 位", "caption"))
        actions = QHBoxLayout()
        self.search_button = button("搜索密钥", self.start_search)
        self.cancel_button = button("停止", self.cancel_search, "secondary")
        self.cancel_button.setEnabled(False)
        actions.addWidget(self.search_button, 1)
        actions.addWidget(self.cancel_button)
        known.addLayout(actions)
        columns.addWidget(known_panel, 4)
        result_panel, result = panel()
        result.addLayout(heading_row("搜索结果", button("复制候选", self.copy_candidates, "ghost")))
        stats = QHBoxLayout()
        self.search_checked, self.search_count, self.search_time = label("—", "statValue"), label("—", "statValue"), label("—", "statValue")
        for caption, value in (("已检查 / 1024", self.search_checked), ("候选密钥", self.search_count), ("耗时 / ms", self.search_time)):
            column = QVBoxLayout()
            column.setSpacing(6)
            column.addWidget(label(caption, "caption"))
            column.addWidget(value)
            stats.addLayout(column, 1)
        result.addLayout(stats)
        self.search_progress = QProgressBar()
        self.search_progress.setRange(0, 1024)
        self.search_progress.setValue(0)
        self.search_progress.setTextVisible(False)
        self.search_progress.setFixedHeight(6)
        result.addWidget(self.search_progress)
        self.search_status = label("添加已知明密文对后开始搜索。", "muted", True)
        result.addWidget(self.search_status)
        self.search_result = editor("候选密钥会显示在这里", True, "candidateEditor")
        self.search_result.setMinimumHeight(205)
        result.addWidget(self.search_result, 1)
        result.addWidget(divider())
        self.search_timestamps = label("开始 —\n结束 —", "caption", True)
        result.addWidget(self.search_timestamps)
        columns.addWidget(result_panel, 6)
        layout.addLayout(columns, 1)
        self.pair_input.textChanged.connect(self.reset_search_result)

    def load_search_example(self):
        if self.worker is not None and self.worker.isRunning():
            return
        self.pair_input.setPlainText("\n".join(f"{value:08b} {encrypt_block(value, 642):08b}" for value in (215, 0, 1, 65, 85)))

    def reset_search_result(self):
        self.last_search = None
        self.search_result.clear()
        self.search_progress.setValue(0)
        for widget in (self.search_checked, self.search_count, self.search_time):
            widget.setText("—")
        self.search_timestamps.setText("开始 —\n结束 —")
        status(self.search_status, "准备就绪")

    def start_search(self):
        if self.worker is not None and self.worker.isRunning():
            return
        try:
            pairs = parse_pairs(self.pair_input.toPlainText())
        except ValueError as error:
            status(self.search_status, "输入错误：" + str(error), "error")
            return
        self.reset_search_result()
        self.search_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.pair_input.setReadOnly(True)
        status(self.search_status, "正在搜索…")
        if self.worker is not None:
            self.worker.deleteLater()
        self.worker = SearchWorker(pairs, self)
        self.worker.progress.connect(self.update_search_progress)
        self.worker.result_ready.connect(self.finish_search)
        self.worker.failed.connect(self.search_failed)
        self.worker.finished.connect(self.search_thread_finished)
        self.worker.start()

    def update_search_progress(self, checked):
        self.search_progress.setValue(checked)
        self.search_checked.setText(str(checked))

    def finish_search(self, result):
        self.last_search = result
        self.update_search_progress(result.checked)
        self.search_count.setText(str(len(result.keys)))
        self.search_time.setText(f"{result.elapsed_ns / 1_000_000:.3f}")
        self.search_result.setPlainText("\n".join(f"{key:010b}" for key in result.keys))
        if result.cancelled:
            message = "已停止，显示当前找到的候选。"
        elif not result.keys:
            message = "没有匹配密钥，请检查明密文。"
        elif len(result.keys) == 1:
            message = "找到唯一候选密钥"
        else:
            message = f"找到 {len(result.keys)} 个候选，可添加更多已知对继续筛选。"
        status(self.search_status, message, "success" if result.keys and not result.cancelled else "neutral")
        times = [datetime.fromisoformat(value).astimezone() for value in (result.started_at, result.ended_at)]
        self.search_timestamps.setText(f"开始  {times[0].isoformat(timespec='milliseconds')}\n结束  {times[1].isoformat(timespec='milliseconds')}")
        self.search_timestamps.setToolTip(f"计时：{result.elapsed_ns} ns\n{result.started_at}\n{result.ended_at}")

    def copy_candidates(self):
        if self.last_search and self.last_search.keys:
            QApplication.clipboard().setText("\n".join(f"{key:010b}" for key in self.last_search.keys))

    def search_failed(self, message):
        status(self.search_status, "搜索失败：" + message, "error")

    def search_thread_finished(self):
        self.search_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.pair_input.setReadOnly(False)

    def cancel_search(self):
        if self.worker is not None:
            self.worker.requestInterruption()

    def build_collision_tab(self):
        layout = self.add_page()
        controls, form = panel()
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(label("明文分组", "muted"))
        self.collision_input = line_input("11010111", "keyInput", "碰撞分析明文")
        self.collision_input.setMaximumWidth(225)
        row.addWidget(self.collision_input)
        row.addWidget(button("分析碰撞", self.process_collisions))
        row.addStretch()
        form.addLayout(row)
        self.collision_status = label("分析后查看密文分布和重复密钥。", "muted", True)
        form.addWidget(self.collision_status)
        self.collision_histogram = CollisionHistogram()
        form.addWidget(self.collision_histogram)
        form.addWidget(label("每个密文对应的密钥数量", "caption"))
        layout.addWidget(controls)
        table_panel, table_layout = panel()
        table_layout.addLayout(heading_row("碰撞列表", label("仅显示有多个密钥的密文", "caption")))
        self.collision_table = QTableWidget(0, 3)
        self.collision_table.setHorizontalHeaderLabels(["密文", "密钥数", "候选密钥"])
        self.collision_table.verticalHeader().hide()
        self.collision_table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.collision_table.setColumnWidth(0, 118)
        self.collision_table.setColumnWidth(1, 72)
        self.collision_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.collision_table.setShowGrid(False)
        self.collision_table.setAlternatingRowColors(True)
        self.collision_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.collision_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.collision_table.setMinimumHeight(235)
        self.collision_table.setWordWrap(True)
        self.collision_table.setAccessibleName("密钥碰撞列表")
        self.collision_table.horizontalHeader().sectionResized.connect(self.collision_table.resizeRowsToContents)
        table_layout.addWidget(self.collision_table)
        layout.addWidget(table_panel, 1)

    def process_collisions(self):
        self.collision_table.setRowCount(0)
        self.collision_histogram.set_groups({})
        try:
            groups = collisions_for_plaintext(parse_bits(self.collision_input.text(), 8))
            collided = [(cipher, keys) for cipher, keys in groups.items() if len(keys) > 1]
            status(self.collision_status, f"{len(groups)} 种密文   ·   {len(collided)} 组碰撞   ·   最多 {max(map(len, groups.values()))} 个密钥 / 密文")
            self.collision_histogram.set_groups(groups)
            self.collision_table.setRowCount(len(collided))
            for row, (cipher, keys) in enumerate(collided):
                for column, value in enumerate((f"{cipher:08b}", str(len(keys)), "   ".join(f"{key:010b}" for key in keys))):
                    item = QTableWidgetItem(value)
                    item.setFont(font("mono", 12))
                    self.collision_table.setItem(row, column, item)
            self.collision_table.resizeRowsToContents()
        except ValueError as error:
            status(self.collision_status, "输入错误：" + str(error), "error")

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait()
        event.accept()


def run(smoke_test=False):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    if smoke_test:
        def check_startup():
            exit_code = 0
            try:
                if not window.isVisible():
                    raise RuntimeError("Main window is not visible")
                window.process_block()
                if window.block_output.text() != "11101000":
                    raise RuntimeError("Default GUI encryption did not succeed")
                print("SDES_LAUNCH_OK " + json.dumps({"platform": app.platformName(), "window_visible": window.isVisible(),
                                                       "ciphertext": window.block_output.text()}), flush=True)
            except Exception as error:
                print("SDES_LAUNCH_FAILED " + str(error), flush=True)
                exit_code = 1
            finally:
                window.close()
                app.exit(exit_code)
        QTimer.singleShot(500, check_startup)
    sys.exit(app.exec())
