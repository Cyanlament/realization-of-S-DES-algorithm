"""Pure S-DES functions. Bit positions in the assignment are one-based, MSB first.

The second key shift is cumulative: LS-1, then LS-2 (three positions total).
SBOX2 is the assignment's modified table, not a table copied from a textbook.
"""
from functools import lru_cache

P10 = (3, 5, 2, 7, 4, 10, 1, 9, 8, 6)
P8 = (6, 3, 7, 4, 8, 5, 10, 9)
IP = (2, 6, 3, 1, 4, 8, 5, 7)
IP_INVERSE = (4, 1, 3, 5, 7, 2, 8, 6)
EP = (4, 1, 2, 3, 2, 3, 4, 1)
P4 = (2, 4, 3, 1)
SBOX1 = ((1, 0, 3, 2), (3, 2, 1, 0), (0, 2, 1, 3), (3, 1, 0, 2))
SBOX2 = ((0, 1, 2, 3), (2, 3, 1, 0), (3, 0, 1, 2), (2, 1, 0, 3))


def validate_integer(value: int, width: int, name: str) -> int:
    if type(value) is not int or not 0 <= value < (1 << width):
        raise ValueError(f"{name}必须是 0 到 {(1 << width) - 1} 之间的整数")
    return value


def parse_bits(text: str, width: int, name: str = "输入") -> int:
    """Validate an exact-width binary string; trim surrounding whitespace only."""
    if not isinstance(text, str):
        raise ValueError(f"{name}必须为二进制文本")
    text = text.strip()
    if len(text) != width or any(bit not in "01" for bit in text):
        raise ValueError(f"{name}必须恰好为 {width} 位，只能包含 0 和 1")
    return int(text, 2)


def permute(value: int, input_width: int, table: tuple[int, ...]) -> int:
    output = 0
    for position in table:
        output = (output << 1) | ((value >> (input_width - position)) & 1)
    return output


def rotate_five(value: int, amount: int) -> int:
    return ((value << amount) | (value >> (5 - amount))) & 0b11111


@lru_cache(maxsize=1024)
def _subkeys(key: int) -> tuple[int, int]:
    permuted = permute(key, 10, P10)
    left, right = permuted >> 5, permuted & 31
    left, right = rotate_five(left, 1), rotate_five(right, 1)
    first = permute((left << 5) | right, 10, P8)
    left, right = rotate_five(left, 2), rotate_five(right, 2)
    second = permute((left << 5) | right, 10, P8)
    return first, second


def generate_subkeys(key: int) -> tuple[int, int]:
    return _subkeys(validate_integer(key, 10, "密钥"))


def substitute(nibble: int, box: tuple[tuple[int, ...], ...]) -> int:
    # Outer bits select the row; inner bits select the column.
    row = ((nibble & 8) >> 2) | (nibble & 1)
    column = (nibble >> 1) & 3
    return box[row][column]


def round_function(right: int, subkey: int) -> int:
    mixed = permute(right, 4, EP) ^ subkey
    substitution = (substitute(mixed >> 4, SBOX1) << 2) | substitute(mixed & 15, SBOX2)
    return permute(substitution, 4, P4)


# Small immutable lookup tables accelerate exhaustive experiments. The actual
# permutation and substitution definitions above remain the source of truth.
_INITIAL = tuple(permute(value, 8, IP) for value in range(256))
_FINAL = tuple(permute(value, 8, IP_INVERSE) for value in range(256))
_ROUND = tuple(tuple(round_function(right, key) for right in range(16)) for key in range(256))


def _transform(block: int, first: int, second: int) -> int:
    initial = _INITIAL[block]
    left, right = initial >> 4, initial & 15
    # f_k followed by SW: only the left half is XORed before swapping.
    left, right = right, left ^ _ROUND[first][right]
    left ^= _ROUND[second][right]
    return _FINAL[(left << 4) | right]


def encrypt_block(plaintext: int, key: int) -> int:
    validate_integer(plaintext, 8, "明文")
    return _transform(plaintext, *generate_subkeys(key))


def decrypt_block(ciphertext: int, key: int) -> int:
    validate_integer(ciphertext, 8, "密文")
    first, second = generate_subkeys(key)
    return _transform(ciphertext, second, first)


def transform_bytes(data: bytes, key: int, decrypt: bool = False) -> bytes:
    """Process each byte independently; preserve length and all byte values."""
    if not isinstance(data, bytes):
        raise ValueError("数据必须是 bytes")
    first, second = generate_subkeys(key)
    if decrypt:
        first, second = second, first
    return bytes(_transform(value, first, second) for value in data)


def trace_block(block: int, key: int, decrypt: bool = False) -> dict:
    """Return JSON-serializable intermediate values for teaching and auditing."""
    validate_integer(block, 8, "分组")
    first, second = generate_subkeys(key)
    scheduled = [f"{first:08b}", f"{second:08b}"]
    if decrypt:
        first, second = second, first
    state = permute(block, 8, IP)
    initial = f"{state:08b}"
    rounds = []
    for index, subkey in enumerate((first, second)):
        left, right = state >> 4, state & 15
        expanded = permute(right, 4, EP)
        mixed = expanded ^ subkey
        s1 = substitute(mixed >> 4, SBOX1)
        s2 = substitute(mixed & 15, SBOX2)
        function = permute((s1 << 2) | s2, 4, P4)
        state = ((left ^ function) << 4) | right
        record = {"round": index + 1, "subkey": f"{subkey:08b}",
                  "left": f"{left:04b}", "right": f"{right:04b}",
                  "ep": f"{expanded:08b}", "xor": f"{mixed:08b}",
                  "s1": f"{s1:02b}", "s2": f"{s2:02b}",
                  "p4": f"{function:04b}", "fk": f"{state:08b}"}
        if index == 0:
            state = ((state & 15) << 4) | (state >> 4)
            record["sw"] = f"{state:08b}"
        rounds.append(record)
    return {"operation": "decrypt" if decrypt else "encrypt", "input": f"{block:08b}",
            "key": f"{key:010b}", "subkeys": scheduled, "ip": initial,
            "rounds": rounds, "output": f"{permute(state, 8, IP_INVERSE):08b}"}
