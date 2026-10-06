"""Unambiguous text/byte conversions for the GUI and CLI."""
import base64
import binascii
import re


def encode_plaintext(text: str, mode: str = "ASCII") -> bytes:
    if mode not in ("ASCII", "UTF-8"):
        raise ValueError("明文编码必须是 ASCII 或 UTF-8")
    try:
        return text.encode("ascii" if mode == "ASCII" else "utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("ASCII 模式只接受 U+0000 至 U+007F；中文请切换 UTF-8") from error


def decode_plaintext(data: bytes, mode: str = "ASCII") -> str:
    if mode not in ("ASCII", "UTF-8"):
        raise ValueError("明文编码必须是 ASCII 或 UTF-8")
    try:
        return data.decode("ascii" if mode == "ASCII" else "utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(f"解密结果不是有效的 {mode} 文本，请检查密钥和编码") from error


def render_ciphertext(data: bytes, mode: str = "Hex") -> str:
    if mode == "Hex":
        return data.hex(" ").upper()
    if mode == "Base64":
        return base64.b64encode(data).decode("ascii")
    if mode == "转义字节":
        return "".join(f"\\x{value:02x}" for value in data)
    raise ValueError("未知密文表示方式")


def parse_ciphertext(text: str, mode: str = "Hex") -> bytes:
    try:
        if mode == "Hex":
            compact = "".join(text.split())
            if len(compact) % 2 or re.fullmatch(r"[0-9a-fA-F]*", compact) is None:
                raise ValueError()
            return bytes.fromhex(compact)
        if mode == "Base64":
            return base64.b64decode(text.strip(), validate=True)
        if mode == "转义字节":
            compact = text.strip()
            if re.fullmatch(r"(?:\\x[0-9a-fA-F]{2})*", compact) is None:
                raise ValueError()
            return bytes(int(compact[offset + 2:offset + 4], 16) for offset in range(0, len(compact), 4))
    except (ValueError, binascii.Error) as error:
        raise ValueError(f"无效的 {mode} 密文，请检查格式") from error
    raise ValueError("未知密文表示方式")
