"""Small native widgets for bit readouts, round details and collision data."""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QLabel, QLineEdit, QPushButton,
    QToolTip, QVBoxLayout, QWidget,
)

from .ui_theme import COLORS, font


def label(text, role=None, wrap=False):
    widget = QLabel(text)
    if role:
        widget.setObjectName(role)
    widget.setWordWrap(wrap)
    return widget


def status(widget, text, state="neutral"):
    widget.setText(text)
    widget.setProperty("state", state)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def button(text, callback=None, kind=None):
    widget = QPushButton(text)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if kind:
        widget.setObjectName(kind)
    if callback:
        widget.clicked.connect(callback)
    return widget


def panel(padding=20):
    widget = QFrame()
    widget.setObjectName("panel")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(padding, padding, padding, padding)
    layout.setSpacing(14)
    return widget, layout


def divider():
    widget = QFrame()
    widget.setObjectName("divider")
    widget.setFixedHeight(1)
    return widget


def icon(kind, size=20):
    """Use quiet geometric line icons; labels carry the meaning."""
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(COLORS["muted"]), 1.4, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if kind == "block":
        for x in (3, 11):
            for y in (3, 11):
                painter.drawRoundedRect(QRectF(x, y, 5.5, 5.5), 1, 1)
    elif kind == "text":
        for y, length in ((4, 13), (9, 10), (14, 12)):
            painter.drawLine(3, y, 3 + length, y)
    elif kind == "search":
        painter.drawEllipse(QRectF(2.5, 2.5, 10, 10))
        painter.drawLine(11, 11, 17, 17)
    elif kind == "collision":
        path = QPainterPath()
        path.moveTo(3, 4); path.cubicTo(12, 4, 8, 15, 17, 15)
        painter.drawPath(path)
        path = QPainterPath()
        path.moveTo(3, 15); path.cubicTo(12, 15, 8, 4, 17, 4)
        painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


class Select(QComboBox):
    """Keep the native menu and keyboard behavior, with a visible chevron."""
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(COLORS["muted"]), 1.5, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        x, y = self.width() - 18, self.height() // 2
        path = QPainterPath()
        path.moveTo(x - 4, y - 2)
        path.lineTo(x, y + 2)
        path.lineTo(x + 4, y - 2)
        painter.drawPath(path)


class BitReadout(QLineEdit):
    """Read-only QLineEdit semantics with eight measured bit cells."""
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setFrame(False)
        self.setFixedHeight(104)
        self.setMinimumWidth(290)
        self.setAccessibleName("二进制结果")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.textChanged.connect(self.update)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bits = self.text() if len(self.text()) == 8 else "--------"
        gap = 7
        cell = (self.width() - gap * 7) / 8
        for index, bit in enumerate(bits):
            x = index * (cell + gap)
            tile = QRectF(x, 4, cell, 66)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(COLORS["accent_soft"] if bit == "1" else COLORS["field"]))
            painter.drawRoundedRect(tile, 7, 7)
            painter.setPen(QColor(COLORS["accent"] if bit == "1" else COLORS["zero"]))
            painter.setFont(font("mono", 29 if cell > 36 else 24))
            painter.drawText(tile, Qt.AlignmentFlag.AlignCenter, bit)
            painter.setFont(font("mono", 10))
            painter.setPen(QColor(COLORS["muted"]))
            painter.drawText(QRectF(x, 79, cell, 16), Qt.AlignmentFlag.AlignCenter, str(index + 1))
        painter.end()


class RoundDetails(QFrame):
    def __init__(self, number):
        super().__init__()
        self.setObjectName("roundPanel")
        grid = QGridLayout(self)
        grid.setContentsMargins(16, 12, 16, 12)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(7)
        grid.addWidget(label(f"第 {number} 轮", "sectionTitle"), 0, 0)
        self.subkey = label("K  --------", "bitMeta")
        self.subkey.setAlignment(Qt.AlignmentFlag.AlignRight)
        grid.addWidget(self.subkey, 0, 1)
        self.values = {}
        for row, (name, title) in enumerate((("ep", "扩展置换"), ("xor", "异或"),
                                           ("boxes", "S1 / S2"), ("p4", "P4"), ("fk", "轮输出")), 1):
            grid.addWidget(label(title, "muted"), row, 0)
            value = label("—", "mono")
            value.setAlignment(Qt.AlignmentFlag.AlignRight)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(value, row, 1)
            self.values[name] = value
        grid.setColumnStretch(1, 1)

    def set_data(self, data=None):
        self.subkey.setText("K  " + (data["subkey"] if data else "--------"))
        for name, widget in self.values.items():
            text = f"{data['s1']} / {data['s2']}" if data and name == "boxes" else data.get(name, "—") if data else "—"
            widget.setText(text)


class CollisionHistogram(QWidget):
    """A compact view of key counts for every ciphertext, with exact tooltips."""
    def __init__(self):
        super().__init__()
        self.counts = [0] * 256
        self.setFixedHeight(90)
        self.setMouseTracking(True)
        self.setAccessibleName("各密文的候选密钥数量")

    def set_groups(self, groups):
        self.counts = [len(groups.get(cipher, ())) for cipher in range(256)]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        max_count = max(self.counts) or 1
        plot_height = self.height() - 22
        step = self.width() / 256
        painter.setPen(Qt.PenStyle.NoPen)
        for index, count in enumerate(self.counts):
            if count:
                painter.setBrush(QColor(COLORS["accent"] if count > 1 else COLORS["disabled"]))
                height = count / max_count * (plot_height - 4)
                painter.drawRect(QRectF(index * step, plot_height - height, max(1, step - 1), height))
        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(font("mono", 10))
        painter.drawText(QRectF(0, plot_height + 6, 100, 15), Qt.AlignmentFlag.AlignLeft, "00000000")
        painter.drawText(QRectF(self.width() - 100, plot_height + 6, 100, 15), Qt.AlignmentFlag.AlignRight, "11111111")
        painter.end()

    def mouseMoveEvent(self, event):
        index = min(255, max(0, int(event.position().x() * 256 / max(1, self.width()))))
        QToolTip.showText(event.globalPosition().toPoint(), f"{index:08b}  ·  {self.counts[index]} 个密钥", self)
