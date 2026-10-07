"""Check encryption and decryption against a JSON vector file."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdes.core import decrypt_block, encrypt_block, parse_bits


def main():
    parser = argparse.ArgumentParser(description="交叉测试：验证 JSON 中的 key/plaintext/ciphertext")
    parser.add_argument("file", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.file.read_text(encoding="utf-8"))
        vectors = payload["vectors"] if isinstance(payload, dict) else payload
        if not isinstance(vectors, list) or not vectors:
            raise ValueError("vectors 必须是非空数组")
        failures = []
        for index, vector in enumerate(vectors, 1):
            key = parse_bits(vector["key"], 10, "密钥")
            plain = parse_bits(vector["plaintext"], 8, "明文")
            cipher = parse_bits(vector["ciphertext"], 8, "密文")
            if encrypt_block(plain, key) != cipher or decrypt_block(cipher, key) != plain:
                failures.append(index)
        print(json.dumps({"total": len(vectors), "passed": len(vectors) - len(failures),
                          "failed_vector_numbers": failures}, ensure_ascii=False, indent=2))
        return 1 if failures else 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
