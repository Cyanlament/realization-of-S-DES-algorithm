"""Command-line interface, also usable for external-group vector exchange."""
import argparse
import json
from pathlib import Path

from .analysis import brute_force, collisions_for_plaintext, parse_pairs
from .core import decrypt_block, encrypt_block, parse_bits, trace_block, transform_bytes
from .encoding import decode_plaintext, encode_plaintext, parse_ciphertext, render_ciphertext


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S-DES 实验：严格使用要求.pdf中的 S-box")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for operation in ("encrypt", "decrypt"):
        child = subparsers.add_parser(operation)
        child.add_argument("data", help="8位二进制分组或文本")
        child.add_argument("--key", required=True, help="10位二进制密钥")
        child.add_argument("--text", choices=("ASCII", "UTF-8"))
        child.add_argument("--format", choices=("Hex", "Base64", "转义字节"), default="Hex")
        child.add_argument("--trace", action="store_true")
    crack = subparsers.add_parser("crack")
    crack.add_argument("--pairs-file", type=Path, required=True)
    collision = subparsers.add_parser("collisions")
    collision.add_argument("plaintext")
    try:
        args = parser.parse_args(argv)
        if args.command == "crack":
            result = brute_force(parse_pairs(args.pairs_file.read_text(encoding="utf-8"))).to_dict()
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "collisions":
            groups = collisions_for_plaintext(parse_bits(args.plaintext, 8, "明文"))
            print(json.dumps({f"{cipher:08b}": [f"{key:010b}" for key in keys]
                              for cipher, keys in groups.items() if len(keys) > 1}, indent=2))
        else:
            key = parse_bits(args.key, 10, "密钥")
            decrypt = args.command == "decrypt"
            if args.text:
                if args.trace:
                    raise ValueError("--trace 只适用于单个二进制分组")
                data = parse_ciphertext(args.data, args.format) if decrypt else encode_plaintext(args.data, args.text)
                result = transform_bytes(data, key, decrypt)
                print(decode_plaintext(result, args.text) if decrypt else render_ciphertext(result, args.format))
            else:
                block = parse_bits(args.data, 8)
                if args.trace:
                    print(json.dumps(trace_block(block, key, decrypt), ensure_ascii=False, indent=2))
                else:
                    result = decrypt_block(block, key) if decrypt else encrypt_block(block, key)
                    print(f"{result:08b}")
        return 0
    except (ValueError, OSError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
