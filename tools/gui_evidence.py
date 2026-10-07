"""Run Qt integration checks and save widget screenshots."""
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6 import __version__ as qt_binding_version
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication
from sdes.encoding import parse_ciphertext
from sdes.gui import MainWindow


def main():
    output = ROOT / "evidence" / "screenshots"
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    # Windows offscreen rendering needs explicit font registration.
    for filename in ("msyh.ttc", "msyhbd.ttc", "consola.ttf"):
        font_path = Path("C:/Windows/Fonts") / filename
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    app.processEvents()
    checks = []

    def check(condition, label):
        if not condition:
            raise AssertionError(label)
        checks.append(label)

    def capture(name):
        app.processEvents()
        if not window.grab().save(str(output / name)):
            raise RuntimeError(f"Failed to save {name}")

    window.process_block()
    check(window.block_output.text() == "10001100", "GUI binary encryption")
    capture("01_binary_encrypt.png")
    window.block_reuse.click()
    check(window.block_input.text() == "10001100" and window.block_decrypt
          and not window.block_output.text(), "GUI reuse result switches to decryption and clears prior result")
    window.block_run.click()
    check(window.block_output.text() == "11010111", "GUI binary decryption")
    capture("02_binary_decrypt.png")
    window.block_input.setText("123")
    window.process_block()
    check("输入错误" in window.block_status.text() and not window.block_output.text(), "GUI input validation clears stale block output")
    capture("03_validation.png")
    window.block_input.setText("11010111")
    window.process_block()

    window.tabs.setCurrentIndex(1)
    original = "Hello, S-DES!"
    for mode in ("Hex", "Base64", "转义字节"):
        window.cipher_format.setCurrentText(mode)
        window.plaintext.setPlainText(original)
        window.process_text()
        window.plaintext.clear()
        window.process_text(True)
        check(window.plaintext.toPlainText() == original, "GUI ASCII roundtrip / " + mode)
    window.cipher_format.setCurrentText("Hex")
    window.process_text()
    capture("04_ascii.png")
    expected_bytes = parse_ciphertext(window.ciphertext.toPlainText(), "Hex")
    for mode in ("Base64", "转义字节", "Hex"):
        window.cipher_format.setCurrentText(mode)
        check(parse_ciphertext(window.ciphertext.toPlainText(), mode) == expected_bytes,
              "GUI format switch preserves existing ciphertext / " + mode)
    window.ciphertext.setPlainText("invalid hex")
    window.cipher_format.setCurrentText("Base64")
    check(window.cipher_format.currentText() == "Hex" and window.ciphertext.toPlainText() == "invalid hex"
          and window.text_status.property("state") == "error", "GUI invalid ciphertext keeps prior format and input")
    window.text_encoding.setCurrentText("UTF-8")
    unicode_sample = "信息安全：S-DES 🔐"
    window.plaintext.setPlainText(unicode_sample)
    window.process_text()
    window.plaintext.clear()
    window.process_text(True)
    check(window.plaintext.toPlainText() == unicode_sample, "GUI UTF-8 roundtrip")
    capture("05_unicode.png")

    window.tabs.setCurrentIndex(2)
    window.pair_input.setPlainText("11010111 10001100")
    capture("06_attack_before.png")

    def run_search():
        window.start_search()
        deadline = time.monotonic() + 10
        while window.worker.isRunning() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.001)
        check(not window.worker.isRunning(), "GUI search thread completed")
        # Deliver queued result and finished signals after QThread exits.
        app.processEvents()
        check(window.last_search is not None, "GUI result delivered")
        check(window.search_button.isEnabled(), "GUI search button reenabled")

    run_search()
    single = window.last_search.to_dict()
    check(642 in window.last_search.keys and len(window.last_search.keys) > 1, "GUI displays every single-pair candidate")
    capture("07_attack_single_pair.png")
    window.pair_input.setPlainText((ROOT / "evidence/known_pairs.txt").read_text(encoding="utf-8"))
    check(window.last_search is None and not window.search_result.toPlainText()
          and window.search_count.text() == "—", "GUI changed pairs clear prior search results")
    capture("08_attack_multiple_before.png")
    run_search()
    multiple = window.last_search.to_dict()
    check(window.last_search.keys == (642,), "GUI multiple pairs recover unique key")
    capture("09_attack_multiple_result.png")
    window.pair_input.setPlainText("00000000 00000000\n00000000 00000001")
    run_search()
    check(window.last_search.keys == (), "GUI conflicting pairs produce no matches")
    capture("10_attack_no_match.png")

    window.tabs.setCurrentIndex(3)
    window.process_collisions()
    check("240" in window.collision_status.text(), "GUI collision summary")
    capture("11_collisions.png")
    # Save minimum-size layout checks separately from the report screenshots.
    review = ROOT / "tmp/ui-review"
    review.mkdir(parents=True, exist_ok=True)
    window.resize(980, 690)
    navigation_ok, layout_ok = [], []
    for index, item in enumerate(window.nav_buttons):
        item.click()
        app.processEvents()
        page = window.tabs.currentWidget()
        app.processEvents()
        navigation_ok.append(window.tabs.currentIndex() == index and item.isChecked()
                             and window.page_title.text() == window.PAGE_NAMES[index])
        layout_ok.append(page.widget().width() <= page.viewport().width()
                         and page.horizontalScrollBar().maximum() == 0)
        window.grab().save(str(review / f"minimum_{index}.png"))
    check(all(navigation_ok), "GUI sidebar switches content and heading")
    check(window.width() == 980 and window.height() == 690 and all(layout_ok),
          "GUI all four pages fit the minimum width without hidden horizontal content")
    window.close()
    data = {"rendering": "PySide6 widgets with QT_QPA_PLATFORM=offscreen",
            "pyside6": qt_binding_version, "checks_passed": len(checks), "checks": checks,
            "single_pair_search": single, "multiple_pair_search": multiple,
            "gif_note": "Frame durations: 1500, 3500, 1500, 4500 ms. Search durations are recorded in elapsed_ns."}
    (ROOT / "evidence/gui_checks.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
