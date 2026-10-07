import unittest

from sdes.analysis import brute_force, collisions_for_plaintext, parse_pairs
from sdes.core import (IP, IP_INVERSE, SBOX2, decrypt_block, encrypt_block,
                       generate_subkeys, parse_bits, permute, trace_block, transform_bytes)
from sdes.encoding import decode_plaintext, encode_plaintext, parse_ciphertext, render_ciphertext


class CoreTests(unittest.TestCase):
    def test_assignment_modified_sbox(self):
        self.assertEqual(SBOX2, ((0,1,2,3), (2,3,1,0), (3,0,1,2), (2,1,0,3)))

    def test_hand_worked_vector(self):
        self.assertEqual(generate_subkeys(0b1010000010), (0b10100100, 0b10010010))
        self.assertEqual(encrypt_block(0b11010111, 0b1010000010), 0b11101000)
        self.assertEqual(decrypt_block(0b11101000, 0b1010000010), 0b11010111)
        trace = trace_block(0b11010111, 0b1010000010)
        self.assertEqual(trace["rounds"][0]["sw"], "11010010")
        self.assertEqual(trace["rounds"][1]["fk"], "10110010")

    def test_subkeys_from_independent_pdf_shifts(self):
        def select(value, positions):
            return ''.join(value[position - 1] for position in positions)
        for key in range(1024):
            source = select(f'{key:010b}', (3,5,2,7,4,10,1,9,8,6))
            expected = []
            for shift in ((2,3,4,5,1), (3,4,5,1,2)):
                shifted = select(source[:5], shift) + select(source[5:], shift)
                expected.append(int(select(shifted, (6,3,7,4,8,5,10,9)), 2))
            self.assertEqual(generate_subkeys(key), tuple(expected), f'{key:010b}')

    def test_inverse_permutation_all_blocks(self):
        for block in range(256):
            self.assertEqual(permute(permute(block, 8, IP), 8, IP_INVERSE), block)

    def test_all_keys_all_blocks_round_trip_and_permutation(self):
        for key in range(1024):
            ciphertexts = set()
            for plaintext in range(256):
                cipher = encrypt_block(plaintext, key)
                ciphertexts.add(cipher)
                self.assertEqual(decrypt_block(cipher, key), plaintext)
            self.assertEqual(len(ciphertexts), 256)

    def test_trace_matches_fast_path(self):
        for key in (0, 1, 642, 1023):
            for block in range(256):
                self.assertEqual(int(trace_block(block, key)["output"], 2), encrypt_block(block, key))
                self.assertEqual(int(trace_block(block, key, True)["output"], 2), decrypt_block(block, key))

    def test_strict_binary_validation(self):
        self.assertEqual(parse_bits(" 00000000\n", 8), 0)
        for value in ("", "101", "000000000", "00000002", "0000 000", "０１０１０１０１", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_bits(value, 8)

    def test_integer_range_validation(self):
        for value in (-1, 256, 1.0, True, "1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                encrypt_block(value, 0)
        for key in (-1, 1024, False, "0"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                generate_subkeys(key)


class EncodingTests(unittest.TestCase):
    def test_all_ascii_bytes_round_trip(self):
        text = "".join(chr(value) for value in range(128))
        data = encode_plaintext(text)
        self.assertEqual(decode_plaintext(transform_bytes(transform_bytes(data, 642), 642, True)), text)

    def test_all_bytes_all_formats_round_trip(self):
        data = bytes(range(256))
        for mode in ("Hex", "Base64", "转义字节"):
            cipher = transform_bytes(data, 642)
            self.assertEqual(parse_ciphertext(render_ciphertext(cipher, mode), mode), cipher)
            self.assertEqual(transform_bytes(cipher, 642, True), data)

    def test_unicode_and_whitespace_round_trip(self):
        text = "  信息安全\nS-DES 🔐\t "
        data = encode_plaintext(text, "UTF-8")
        self.assertEqual(decode_plaintext(transform_bytes(transform_bytes(data, 0), 0, True), "UTF-8"), text)

    def test_empty_input(self):
        for mode in ("Hex", "Base64", "转义字节"):
            self.assertEqual(render_ciphertext(b"", mode), "")
            self.assertEqual(parse_ciphertext("", mode), b"")
        self.assertEqual(transform_bytes(b"", 0), b"")

    def test_reject_non_ascii(self):
        with self.assertRaises(ValueError):
            encode_plaintext("中文")
        with self.assertRaises(ValueError):
            decode_plaintext(b"\xff")

    def test_reject_malformed_ciphertext(self):
        for mode, text in (("Hex", "0"), ("Hex", "GG"), ("Base64", "?"),
                           ("Base64", "Y Q=="), ("转义字节", "abc"), ("转义字节", r"\x0G")):
            with self.subTest(mode=mode, text=text), self.assertRaises(ValueError):
                parse_ciphertext(text, mode)

    def test_reject_unknown_modes_and_wrong_type(self):
        for function, argument in ((encode_plaintext, "a"), (decode_plaintext, b"a"),
                                    (render_ciphertext, b"a"), (parse_ciphertext, "a")):
            with self.assertRaises(ValueError):
                function(argument, "unknown")
        with self.assertRaises(ValueError):
            transform_bytes("text", 0)


class AnalysisTests(unittest.TestCase):
    def test_search_returns_all_matches(self):
        result = brute_force([(215, 232)])
        self.assertIn(642, result.keys)
        self.assertEqual(result.checked, 1024)
        expected = tuple(key for key in range(1024) if encrypt_block(215, key) == 232)
        self.assertEqual(result.keys, expected)
        self.assertGreater(len(result.keys), 1)
        self.assertGreater(result.elapsed_ns, 0)
        self.assertFalse(result.cancelled)

    def test_multiple_pairs_return_equivalent_keys(self):
        pairs = [(value, encrypt_block(value, 642)) for value in range(256)]
        self.assertEqual(brute_force(pairs).keys, (642, 898))

    def test_inconsistent_pairs(self):
        self.assertEqual(brute_force([(0, 0), (0, 1)]).keys, ())

    def test_no_pairs_and_bad_pairs(self):
        for pairs in ([], [(256, 0)], [(0, -1)]):
            with self.assertRaises(ValueError):
                brute_force(pairs)
        for text in ("", "0 0", "00000000 00000000 extra"):
            with self.assertRaises(ValueError):
                parse_pairs(text)
        self.assertEqual(parse_pairs("\n00000000,11111111\n"), [(0, 255)])

    def test_progress_and_cancellation(self):
        seen = []
        result = brute_force([(0, 0)], progress=seen.append, cancelled=lambda: bool(seen))
        self.assertTrue(result.cancelled)
        self.assertEqual(result.checked, 32)
        self.assertEqual(seen, [32])

    def test_collision_groups_partition_key_space(self):
        groups = collisions_for_plaintext(215)
        self.assertEqual(sorted(key for keys in groups.values() for key in keys), list(range(1024)))
        self.assertTrue(any(len(keys) > 1 for keys in groups.values()))
        for cipher, keys in groups.items():
            self.assertTrue(all(encrypt_block(215, key) == cipher for key in keys))


if __name__ == "__main__":
    unittest.main()
