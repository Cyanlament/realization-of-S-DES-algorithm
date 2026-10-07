"""Rebuild reproducible numerical evidence; needs Python 3.10+ and g++."""
import csv
import hashlib
import io
import json
import platform
import random
import shutil
import statistics
import subprocess
import sys
import unittest
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sdes import core
from sdes.analysis import brute_force, collisions_for_plaintext
from sdes.core import decrypt_block, encrypt_block, trace_block, transform_bytes
from sdes.encoding import decode_plaintext, encode_plaintext, render_ciphertext


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    evidence = ROOT / "evidence"
    evidence.mkdir(exist_ok=True)
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    started = perf_counter()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_sdes.py")
    log = io.StringIO()
    tests = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    (evidence / "unit_tests.txt").write_text(log.getvalue(), encoding="utf-8")
    print(log.getvalue(), flush=True)
    if not tests.wasSuccessful():
        raise SystemExit("Unit tests failed")
    compiler = shutil.which("g++")
    if not compiler:
        raise SystemExit("g++ is required for independent cross-language verification")
    executable = build / ("sdes_reference.exe" if sys.platform == "win32" else "sdes_reference")
    compilation = subprocess.run([compiler, "-std=c++11", "-O2", "-Wall", "-Wextra",
                                 str(ROOT / "reference/sdes_reference.cpp"), "-o", str(executable)],
                                capture_output=True, text=True)
    (evidence / "cpp_build.txt").write_text(compilation.stdout + compilation.stderr, encoding="utf-8")
    compilation.check_returncode()
    table_file = build / "reference_table.bin"
    subprocess.run([str(executable), "--table", str(table_file)], check=True)
    reference = table_file.read_bytes()
    actual = bytes(encrypt_block(plaintext, key) for key in range(1024) for plaintext in range(256))
    assert len(reference) == 262144
    mismatches = sum(first != second for first, second in zip(reference, actual))
    assert mismatches == 0, f"{mismatches} cross-language mismatches"
    print("Cross-language: 262144 / 262144 matched", flush=True)
    compiler_version = subprocess.check_output([compiler, "--version"], text=True).splitlines()[0]

    # Export a small set of vectors for exchanging results between programs.
    vectors = []
    for key in (0, 1, 341, 642, 1023):
        for plaintext in (0, 1, 65, 85, 170, 215, 255):
            cipher = reference[key * 256 + plaintext]
            reference_plain = subprocess.check_output(
                [str(executable), "decrypt", f"{cipher:08b}", f"{key:010b}"], text=True).strip()
            assert reference_plain == f"{plaintext:08b}"
            vectors.append({"key": f"{key:010b}", "plaintext": f"{plaintext:08b}",
                            "ciphertext": f"{cipher:08b}"})
    save_json(evidence / "cross_vectors.json", {"source": "reference/sdes_reference.cpp",
                                               "key_schedule": "LS-1 then cumulative LS-2", "vectors": vectors})
    with (evidence / "cross_vectors.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("key", "plaintext", "ciphertext"))
        writer.writeheader()
        writer.writerows(vectors)
    save_json(evidence / "round_trace.json", trace_block(215, 642))

    sample_text = "Hello, S-DES!"
    cipher = transform_bytes(encode_plaintext(sample_text), 642)
    ascii_result = {"plaintext": sample_text, "key": "1010000010", "byte_count": len(cipher),
                    "cipher_hex": render_ciphertext(cipher),
                    "cipher_base64": render_ciphertext(cipher, "Base64"),
                    "cipher_escaped": render_ciphertext(cipher, "转义字节"),
                    "decrypted": decode_plaintext(transform_bytes(cipher, 642, True))}
    save_json(evidence / "ascii_result.json", ascii_result)

    # A single known pair may have multiple keys; keep adding distinct plaintexts.
    pairs = [(215, 140)]
    narrowing = []
    for plaintext in [215, 0, 1, 65, 85, 170, 255]:
        if plaintext != 215:
            pairs.append((plaintext, encrypt_block(plaintext, 642)))
        result = brute_force(pairs)
        narrowing.append({"pairs": [[f"{p:08b}", f"{c:08b}"] for p, c in pairs], **result.to_dict()})
        if result.keys == (642,):
            break
    assert result.keys == (642,)
    (evidence / "known_pairs.txt").write_text(
        "\n".join(f"{p:08b} {c:08b}" for p, c in pairs) + "\n", encoding="utf-8")
    core._subkeys.cache_clear()
    cold_result = brute_force(pairs).to_dict()
    warm = [brute_force(pairs).to_dict() for _ in range(30)]
    timings = [item["elapsed_ms"] for item in warm]
    attack = {"narrowing": narrowing, "cold_key_cache": cold_result, "warm_runs": warm,
              "benchmark": {"runs": 30, "min_ms": min(timings), "median_ms": statistics.median(timings),
                            "max_ms": max(timings)},
              "timing_scope": "perf_counter_ns around all 1024 key checks; excludes import, GUI rendering and process startup"}
    save_json(evidence / "brute_force.json", attack)

    random_source = random.Random(20261007)
    random_plaintext = random_source.randrange(256)
    random_key = random_source.randrange(1024)
    random_cipher = encrypt_block(random_plaintext, random_key)
    sample_keys = brute_force([(random_plaintext, random_cipher)]).keys
    collision_rows = []
    for plaintext in range(256):
        groups = collisions_for_plaintext(plaintext)
        sizes = [len(keys) for keys in groups.values()]
        collision_rows.append({"plaintext": f"{plaintext:08b}", "distinct_ciphertexts": len(groups),
                               "collision_groups": sum(size > 1 for size in sizes),
                               "singleton_groups": sizes.count(1), "max_keys_per_ciphertext": max(sizes),
                               "colliding_key_pairs": sum(size * (size - 1) // 2 for size in sizes)})
    with (evidence / "collision_all_plaintexts.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=collision_rows[0].keys())
        writer.writeheader()
        writer.writerows(collision_rows)
    signature_counts = Counter(actual[key * 256:(key + 1) * 256] for key in range(1024))
    collision = {"random_seed": 20261007, "random_plaintext": f"{random_plaintext:08b}",
                 "random_key": f"{random_key:010b}", "random_ciphertext": f"{random_cipher:08b}",
                 "random_pair_candidates": [f"{key:010b}" for key in sample_keys],
                 "plaintexts_checked": 256,
                 "all_plaintexts_have_collisions": all(row["collision_groups"] > 0 for row in collision_rows),
                 "min_distinct_ciphertexts": min(row["distinct_ciphertexts"] for row in collision_rows),
                 "max_distinct_ciphertexts": max(row["distinct_ciphertexts"] for row in collision_rows),
                 "max_keys_per_ciphertext": max(row["max_keys_per_ciphertext"] for row in collision_rows),
                 "unique_full_encryption_permutations": len(signature_counts),
                 "globally_equivalent_key_groups": sum(count > 1 for count in signature_counts.values()),
                 "plaintext_215": collision_rows[215]}
    save_json(evidence / "collisions.json", collision)
    summary = {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
               "environment": {"python": sys.version, "platform": platform.platform(),
                               "machine": platform.machine(), "processor": platform.processor(),
                               "cpp_compiler": compiler_version},
               "unit_tests": {"run": tests.testsRun, "failures": len(tests.failures), "errors": len(tests.errors)},
               "exhaustive_roundtrips": 262144, "fixed_key_permutations": 1024,
               "cross_language": {"cases": len(actual), "mismatches": mismatches, "cpp_reverse_cases": len(vectors),
                                  "table_sha256": hashlib.sha256(actual).hexdigest()},
               "ascii": ascii_result, "attack_benchmark": attack["benchmark"],
               "collision": collision, "elapsed_seconds": perf_counter() - started}
    save_json(evidence / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
