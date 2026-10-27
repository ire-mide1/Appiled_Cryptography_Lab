import io
import random
import unittest

import cipher

CHUNK = cipher.CHUNK_SIZE


def run_stream(data, decrypt=False, chunk_size=CHUNK, **kw):
    src, dst = io.BytesIO(data), io.BytesIO()
    cipher.process_stream(src, dst, decrypt, len(data), chunk_size=chunk_size, **kw)
    return dst.getvalue()


def rand_bytes(n, seed=1):
    return random.Random(seed).randbytes(n)


class Tables(unittest.TestCase):
    def test_bijection(self):
        self.assertEqual(sorted(cipher.PERM), list(range(256)))
        self.assertEqual(sorted(cipher.INV_PERM), list(range(256)))
        for x in range(256):
            self.assertEqual(cipher.INV_PERM[cipher.PERM[x]], x)
            self.assertEqual(cipher.PERM[cipher.INV_PERM[x]], x)

    def test_inverse_row(self):
        # pi^-1 = 5,1,3,7,4,2,8,6: input position j lands at output position pi^-1(j).
        inv_pi = (5, 1, 3, 7, 4, 2, 8, 6)
        for j in range(1, 9):
            value_in = 1 << (8 - j)
            value_out = 1 << (8 - inv_pi[j - 1])
            self.assertEqual(cipher.PERM[value_in], value_out)
            self.assertEqual(cipher.INV_PERM[value_out], value_in)

    def test_pi_inverse_composes_to_identity(self):
        pi = cipher.PI
        inv_pi = [0] * 8
        for i, p in enumerate(pi, 1):
            inv_pi[p - 1] = i
        self.assertEqual(tuple(inv_pi), (5, 1, 3, 7, 4, 2, 8, 6))
        for i in range(1, 9):
            self.assertEqual(inv_pi[pi[i - 1] - 1], i)


class Register(unittest.TestCase):
    def test_state_stays_19_bits_and_non_zero(self):
        ks = cipher.Keystream()
        for _ in range(2000):
            ks.next_bytes(50)
            self.assertTrue(0 < ks.state <= cipher.MASK)

    def test_zero_seed_rejected(self):
        with self.assertRaises(ValueError):
            cipher.Keystream(0)

    def test_instances_are_independent(self):
        a, b = cipher.Keystream(), cipher.Keystream()
        a.next_bytes(1000)
        self.assertEqual(b.next_bytes(32), cipher.Keystream().next_bytes(32))

    def test_register_period_is_maximal(self):
        # Informational: x^19+x^18+x^17+x^14+1 should give period 2^19 - 1 clocks.
        ks = cipher.Keystream()
        # 2^19 - 1 = 524287 clocks; step 8 clocks at a time then finish bit by bit.
        full, rest = divmod((1 << 19) - 1, 8)
        for _ in range(full):
            ks.next_bytes(1)
        state = ks.state
        for _ in range(rest):
            fb = ((state >> 13) ^ (state >> 16) ^ (state >> 17) ^ (state >> 18)) & 1
            state = ((state << 1) | fb) & cipher.MASK
        self.assertEqual(state, cipher.SEED)


class RoundTrip(unittest.TestCase):
    def test_random_sizes(self):
        for n in (1, 2, 7, 8, 255, 256, 1000, 4097, 100000):
            data = rand_bytes(n, seed=n)
            enc = run_stream(data)
            self.assertEqual(len(enc), n)
            self.assertEqual(run_stream(enc, decrypt=True), data)

    def test_all_byte_values(self):
        data = bytes(range(256)) * 3
        self.assertEqual(run_stream(run_stream(data), decrypt=True), data)

    def test_runs_of_zero_and_ff(self):
        for fill in (0x00, 0xFF):
            data = bytes([fill]) * 5000
            self.assertEqual(run_stream(run_stream(data), decrypt=True), data)

    def test_encryption_changes_data(self):
        data = rand_bytes(1000)
        self.assertNotEqual(run_stream(data), data)

    def test_empty_input(self):
        self.assertEqual(run_stream(b""), b"")
        self.assertEqual(run_stream(b"", decrypt=True), b"")

    def test_length_preserved(self):
        for n in (0, 1, 63, 64, 65, CHUNK - 1, CHUNK, CHUNK + 1):
            self.assertEqual(len(run_stream(rand_bytes(n, seed=3))), n)

    def test_wrong_mode_does_not_recover_plaintext(self):
        data = rand_bytes(500)
        self.assertNotEqual(run_stream(run_stream(data), decrypt=False), data)


class Chunking(unittest.TestCase):
    def one_piece(self, data, decrypt=False):
        return cipher.transform(data, cipher.Keystream(), decrypt)

    def test_chunk_boundaries_match_single_piece(self):
        for n in (CHUNK - 1, CHUNK, CHUNK + 1, 3 * CHUNK + 1):
            data = rand_bytes(n, seed=n)
            self.assertEqual(run_stream(data), self.one_piece(data), n)
            self.assertEqual(run_stream(data, decrypt=True),
                             self.one_piece(data, decrypt=True), n)

    def test_chunk_size_does_not_change_output(self):
        data = rand_bytes(3000, seed=9)
        expected = self.one_piece(data)
        for size in (1, 7, 64, 1000, CHUNK):
            self.assertEqual(run_stream(data, chunk_size=size), expected, size)

    def test_two_runs_give_identical_output(self):
        data = rand_bytes(CHUNK + 5, seed=4)
        self.assertEqual(run_stream(data), run_stream(data))


class StreamBehaviour(unittest.TestCase):
    def test_progress_is_monotonic_and_ends_at_total(self):
        data = rand_bytes(3 * CHUNK + 10)
        calls = []
        run_stream(data, on_progress=lambda d, t: calls.append((d, t)))
        dones = [d for d, _ in calls]
        self.assertEqual(dones, sorted(dones))
        self.assertEqual(len(set(dones)), len(dones))
        self.assertEqual(calls[-1], (len(data), len(data)))
        self.assertEqual(len(calls), 4)

    def test_empty_input_reports_zero_of_zero(self):
        calls = []
        run_stream(b"", on_progress=lambda d, t: calls.append((d, t)))
        self.assertEqual(calls, [(0, 0)])

    def test_input_shorter_than_total(self):
        with self.assertRaises(cipher.InputChangedError):
            cipher.process_stream(io.BytesIO(b"abc"), io.BytesIO(), False, 10)

    def test_input_longer_than_total(self):
        with self.assertRaises(cipher.InputChangedError):
            cipher.process_stream(io.BytesIO(b"abcdef"), io.BytesIO(), False, 3)

    def test_stop_request(self):
        data = rand_bytes(3 * CHUNK)
        calls = {"n": 0}

        def stop():
            calls["n"] += 1
            return calls["n"] > 1  # allow the first chunk, stop before the second

        dst = io.BytesIO()
        with self.assertRaises(cipher.StopRequested):
            cipher.process_stream(io.BytesIO(data), dst, False, len(data), should_stop=stop)
        self.assertEqual(len(dst.getvalue()), CHUNK)


if __name__ == "__main__":
    unittest.main()
