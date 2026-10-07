"""Visual tokens and typography shared by the native desktop views."""
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

COLORS = {
    "canvas": "#EEF2F5", "surface": "#FFFFFF", "sidebar": "#F8FAFC",
    "ink": "#203344", "muted": "#677B8C", "line": "#DEE6ED",
    "accent": "#176D86", "accent_hover": "#125C73", "accent_press": "#0D495D",
    "accent_soft": "#E2EFF3", "field": "#F5F8FA", "hover": "#EDF2F6",
    "disabled": "#93A5B3", "error": "#AB3E35", "error_soft": "#FCF0EE",
    "success": "#247969", "zero": "#7D909F", "focus": "#5497AB",
}

FONTS = {"body": "Microsoft YaHei", "display": "Segoe UI", "mono": "Cascadia Mono"}


def configure_fonts(app):
    """Use installed faces consistently in native and offscreen Qt rendering."""
    for filename in ("msyh.ttc", "msyhbd.ttc", "segoeui.ttf", "segoeuib.ttf", "CascadiaMono.ttf", "seguiemj.ttf"):
        path = Path("C:/Windows/Fonts") / filename
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))
    available = set(QFontDatabase.families())
    if "Segoe UI Emoji" in available:
        QFontDatabase.addApplicationEmojiFontFamily("Segoe UI Emoji")
    candidates = {
        "body": ("Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "DejaVu Sans"),
        "display": ("Segoe UI", "Helvetica Neue", "DejaVu Sans"),
        "mono": ("Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono"),
    }
    for role, names in candidates.items():
        FONTS[role] = next((name for name in names if name in available), app.font().family())
    app.setFont(font("body", 13))


def font(role="body", size=13, weight=QFont.Weight.Normal):
    result = QFont(FONTS[role])
    result.setPixelSize(size)
    result.setWeight(weight)
    return result


def stylesheet():
    color, face = COLORS, FONTS
    return f"""
        QMainWindow, QWidget#workspace {{ background: {color['canvas']}; }}
        QWidget {{ color: {color['ink']}; font-family: '{face['body']}'; font-size: 13px; }}
        QLabel {{ background: transparent; border: none; }}
        QFrame#sidebar {{ background: {color['sidebar']}; border-right: 1px solid {color['line']}; }}
        QLabel#brand {{ font-family: '{face['display']}'; font-size: 24px; font-weight: 700; }}
        QLabel#pageTitle {{ font-size: 26px; font-weight: 600; }}
        QLabel#sectionTitle {{ font-size: 15px; font-weight: 600; }}
        QLabel#muted, QLabel#pageDescription {{ color: {color['muted']}; }}
        QLabel#caption {{ color: {color['muted']}; font-size: 11px; }}
        QLabel#mono {{ font-family: '{face['mono']}'; }}
        QLabel#statValue {{ font-family: '{face['mono']}'; font-size: 26px; font-weight: 500; }}
        QLabel#bitMeta {{ font-family: '{face['mono']}'; color: {color['muted']}; font-size: 12px; }}
        QFrame#panel {{ background: {color['surface']}; border: 1px solid {color['line']}; border-radius: 12px; }}
        QFrame#divider {{ background: {color['line']}; border: none; max-height: 1px; }}
        QFrame#roundPanel {{ background: {color['field']}; border: none; border-radius: 8px; }}
        QScrollArea, QStackedWidget {{ background: transparent; border: none; }}
        QScrollArea > QWidget > QWidget {{ background: transparent; }}
        QPushButton {{ background: {color['accent']}; color: {color['surface']}; border: 1px solid {color['accent']};
            border-radius: 7px; padding: 9px 17px; font-weight: 500; }}
        QPushButton:hover {{ background: {color['accent_hover']}; border-color: {color['accent_hover']}; }}
        QPushButton:pressed {{ background: {color['accent_press']}; padding-top: 10px; padding-bottom: 8px; }}
        QPushButton:focus {{ border: 2px solid {color['focus']}; padding: 8px 16px; }}
        QPushButton:disabled {{ background: {color['field']}; color: {color['disabled']}; border-color: {color['line']}; }}
        QPushButton#secondary {{ background: {color['surface']}; color: {color['ink']}; border-color: {color['line']}; }}
        QPushButton#secondary:hover, QPushButton#ghost:hover {{ background: {color['hover']}; }}
        QPushButton#ghost {{ color: {color['accent']}; background: transparent; border-color: transparent; padding: 6px 9px; }}
        QPushButton#ghost:disabled {{ color: {color['disabled']}; }}
        QPushButton#secondary:disabled {{ background: {color['field']}; color: {color['disabled']}; border-color: {color['line']}; }}
        QPushButton#nav {{ background: transparent; border: 1px solid transparent; color: {color['muted']};
            text-align: left; padding: 12px 14px; border-radius: 8px; font-weight: 400; }}
        QPushButton#nav:hover {{ background: {color['hover']}; color: {color['ink']}; }}
        QPushButton#nav:checked {{ background: {color['accent_soft']}; color: {color['accent']}; font-weight: 600; }}
        QPushButton#nav:focus {{ border-color: {color['focus']}; }}
        QFrame#segments {{ background: {color['field']}; border-radius: 7px; border: 1px solid {color['line']}; }}
        QPushButton#segment {{ background: transparent; color: {color['muted']}; border: 1px solid transparent;
            border-radius: 5px; padding: 5px 18px; font-weight: 400; }}
        QPushButton#segment:checked {{ background: {color['surface']}; color: {color['accent']}; border-color: {color['line']}; font-weight: 600; }}
        QPushButton#segment:focus {{ border-color: {color['focus']}; }}
        QLineEdit, QPlainTextEdit, QComboBox {{ background: {color['field']}; border: 1px solid {color['line']};
            border-radius: 7px; padding: 10px 12px; selection-background-color: {color['accent_soft']};
            selection-color: {color['ink']}; }}
        QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{ border-color: {color['focus']}; background: {color['surface']}; }}
        QLineEdit[state="error"] {{ border-color: {color['error']}; background: {color['error_soft']}; }}
        QLineEdit#binaryInput {{ font-family: '{face['mono']}'; font-size: 21px; padding: 11px 14px; }}
        QLineEdit#keyInput {{ font-family: '{face['mono']}'; font-size: 17px; }}
        QPlainTextEdit {{ font-family: '{face['mono']}'; font-size: 14px; }}
        QPlainTextEdit#documentEditor {{ border: none; background: transparent; border-radius: 0; padding: 0; font-size: 16px; }}
        QPlainTextEdit#candidateEditor {{ border: none; background: transparent; padding: 0; font-size: 23px; }}
        QComboBox {{ min-width: 88px; padding-right: 27px; }}
        QComboBox::drop-down {{ border: none; width: 25px; }}
        QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
        QComboBox QAbstractItemView {{ background: {color['surface']}; border: 1px solid {color['line']};
            selection-background-color: {color['accent_soft']}; selection-color: {color['ink']}; padding: 4px; }}
        QLabel#muted[state="error"] {{ color: {color['error']}; }}
        QLabel#muted[state="success"] {{ color: {color['success']}; }}
        QProgressBar {{ background: {color['field']}; border: none; border-radius: 3px; height: 6px; }}
        QProgressBar::chunk {{ background: {color['accent']}; border-radius: 3px; }}
        QTableWidget {{ background: {color['surface']}; border: none; gridline-color: {color['line']};
            alternate-background-color: {color['field']}; selection-background-color: {color['accent_soft']};
            selection-color: {color['ink']}; }}
        QTableWidget::item {{ padding: 9px 10px; border-bottom: 1px solid {color['line']}; }}
        QHeaderView::section {{ background: {color['surface']}; color: {color['muted']}; padding: 10px;
            border: none; border-bottom: 1px solid {color['line']}; text-align: left; font-weight: 400; }}
        QScrollBar:vertical {{ background: transparent; width: 6px; margin: 2px 0; }}
        QScrollBar::handle:vertical {{ background: {color['line']}; min-height: 28px; border-radius: 3px; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        QToolTip {{ background: {color['ink']}; color: {color['surface']}; padding: 6px 9px; border: none; }}
    """
