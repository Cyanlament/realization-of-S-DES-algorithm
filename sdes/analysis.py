"""Exhaustive key search and key-collision experiments for the 10-bit space."""
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from time import perf_counter_ns
from typing import Callable, Iterable

from .core import encrypt_block, parse_bits, validate_integer


@dataclass(frozen=True)
class SearchResult:
    keys: tuple[int, ...]
    checked: int
    elapsed_ns: int
    started_at: str
    ended_at: str
    cancelled: bool

    def to_dict(self) -> dict:
        result = asdict(self)
        result["keys"] = [f"{key:010b}" for key in self.keys]
        result["elapsed_ms"] = self.elapsed_ns / 1_000_000
        return result


def parse_pairs(text: str) -> list[tuple[int, int]]:
    pairs = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.replace(",", " ").replace("，", " ").split()
        if len(parts) != 2:
            raise ValueError(f"第 {line_number} 行需要一个 8 位明文和一个 8 位密文，用空格分隔")
        pairs.append((parse_bits(parts[0], 8, "明文"), parse_bits(parts[1], 8, "密文")))
    if not pairs:
        raise ValueError("请至少输入一组已知明密文对")
    return pairs


def brute_force(pairs: Iterable[tuple[int, int]],
                progress: Callable[[int], None] | None = None,
                cancelled: Callable[[], bool] | None = None) -> SearchResult:
    known = tuple(pairs)
    if not known:
        raise ValueError("至少需要一组明密文对")
    for plaintext, ciphertext in known:
        validate_integer(plaintext, 8, "明文")
        validate_integer(ciphertext, 8, "密文")
    started_at = datetime.now(timezone.utc).isoformat()
    started = perf_counter_ns()
    matches = []
    checked = 0
    interrupted = False
    for key in range(1024):
        if cancelled and cancelled():
            interrupted = True
            break
        if all(encrypt_block(plaintext, key) == ciphertext for plaintext, ciphertext in known):
            matches.append(key)
        checked += 1
        if progress and (checked % 32 == 0 or checked == 1024):
            progress(checked)
    elapsed = perf_counter_ns() - started
    return SearchResult(tuple(matches), checked, elapsed, started_at,
                        datetime.now(timezone.utc).isoformat(), interrupted)


def collisions_for_plaintext(plaintext: int) -> dict[int, tuple[int, ...]]:
    validate_integer(plaintext, 8, "明文")
    groups: dict[int, list[int]] = defaultdict(list)
    for key in range(1024):
        groups[encrypt_block(plaintext, key)].append(key)
    return {ciphertext: tuple(keys) for ciphertext, keys in sorted(groups.items())}
