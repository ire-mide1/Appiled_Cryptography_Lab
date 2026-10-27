"""Fixed reference values, hard-coded and independently verified by the user.

These are never recomputed from the code under test.
"""
import unittest

import cipher

KEYSTREAM_16 = bytes.fromhex("F35E0D66C6FDD71D3A25027E9DAB434F")
PLAINTEXT = b"CRYPTO"
PERMUTED = bytes.fromhex("85839682C2D5")
CIPHERTEXT = bytes.fromhex("76DD9BE40428")


class ReferenceVector(unittest.TestCase):
    def test_single_byte_c_example(self):
        self.assertEqual(cipher.PERM[0x43], 0x85)
        self.assertEqual(0x85 ^ 0xF3, 0x76)
        self.assertEqual(0x76 ^ 0xF3, 0x85)
        self.assertEqual(cipher.INV_PERM[0x85], 0x43)

    def test_first_16_keystream_bytes(self):
        self.assertEqual(cipher.Keystream().next_bytes(16), KEYSTREAM_16)

    def test_keystream_one_byte_at_a_time_matches(self):
        ks = cipher.Keystream()
        self.assertEqual(bytes(ks.next_byte() for _ in range(16)), KEYSTREAM_16)

    def test_permutation_step(self):
        self.assertEqual(bytes(cipher.PERM[b] for b in PLAINTEXT), PERMUTED)

    def test_encrypt_crypto(self):
        self.assertEqual(cipher.transform(PLAINTEXT, cipher.Keystream()), CIPHERTEXT)

    def test_decrypt_crypto(self):
        self.assertEqual(
            cipher.transform(CIPHERTEXT, cipher.Keystream(), decrypt=True), PLAINTEXT)

    def test_spot_values(self):
        self.assertEqual(cipher.PERM[0x80], 0x08)
        self.assertEqual(cipher.PERM[0x40], 0x80)
        self.assertEqual(cipher.PERM[0x43], 0x85)

    def test_first_two_register_states(self):
        ks = cipher.Keystream()
        self.assertEqual(ks.state, 0x67BD5)
        ks.next_bytes(1)
        self.assertEqual(ks.state, 0x3D583)  # after 8 clocks (interrogation.md 1.5)
        ks.next_bytes(1)
        self.assertEqual(ks.state, 0x58333)  # after 16 clocks (interrogation.md 1.6)


if __name__ == "__main__":
    unittest.main()
