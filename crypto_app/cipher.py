"""Cipher core: a 19-bit LFSR keystream and an 8-bit bit permutation.

No Tkinter and no file paths here. See Requirements_V2.md Section 3 and
Design_v1.md Section 2 for the exact conventions.

Register bit 0 is x^1 (the left end, LSB); bit 18 is x^19 (the right end, MSB
and the output bit). Byte bit positions are numbered 1..8 with 1 = MSB.
"""

SEED = 0x67BD5
REG_BITS = 19
MASK = (1 << REG_BITS) - 1
TAP_BITS = (13, 16, 17, 18)  # x^14, x^17, x^18, x^19
OUT_BIT = 18
PI = (2, 6, 3, 5, 1, 8, 4, 7)  # 1-based; output position i takes input bit PI[i-1]
CHUNK_SIZE = 64 * 1024


class StopRequested(Exception):
    """Raised by process_stream when should_stop() returns True."""


class InputChangedError(Exception):
    """Raised when the input is shorter or longer than the size announced."""


def build_permutation_tables(pi=PI):
    """Return (PERM, INV_PERM) as 256-byte tables.

    PERM[x] has output bit y_i = x_pi(i). INV_PERM is built by inverting the
    finished forward table, so the two can never disagree.
    """
    perm = bytearray(256)
    for x in range(256):
        bits = [(x >> (8 - i)) & 1 for i in range(1, 9)]  # bits[i-1] = x_i
        y = 0
        for i in range(8):
            y = (y << 1) | bits[pi[i] - 1]
        perm[x] = y
    inv = bytearray(256)
    for x in range(256):
        inv[perm[x]] = x
    return bytes(perm), bytes(inv)


PERM, INV_PERM = build_permutation_tables()


class Keystream:
    """LFSR keystream. A new instance starts at the seed; there is no shared state."""

    def __init__(self, seed=SEED):
        seed &= MASK
        if seed == 0:
            raise ValueError("LFSR seed must be non-zero")
        self._state = seed

    @property
    def state(self):
        return self._state

    def next_bytes(self, n):
        """Clock 8 times per byte and return n keystream bytes.

        The first output bit of each byte is its LSB.
        """
        state = self._state
        out = bytearray(n)
        for j in range(n):
            byte = 0
            for k in range(8):
                feedback = ((state >> 13) ^ (state >> 16) ^ (state >> 17) ^ (state >> 18)) & 1
                byte |= ((state >> 18) & 1) << k
                state = ((state << 1) | feedback) & MASK
            out[j] = byte
        self._state = state
        return bytes(out)

    def next_byte(self):
        return self.next_bytes(1)[0]


def transform(data, keystream, decrypt=False):
    """Encrypt (permute, then XOR) or decrypt (XOR, then inverse permute) one chunk."""
    ks = keystream.next_bytes(len(data))
    if decrypt:
        table = INV_PERM
        return bytes([table[b ^ k] for b, k in zip(data, ks)])
    table = PERM
    return bytes([table[b] ^ k for b, k in zip(data, ks)])


def process_stream(src, dst, decrypt, total, on_progress=None, should_stop=None,
                   chunk_size=CHUNK_SIZE):
    """Transform `total` bytes from src to dst in chunks.

    A fresh Keystream is used, so every call starts from the seed and runs
    continuously across chunks. on_progress(done, total) is called after each
    chunk (once, as (0, 0), for an empty input). should_stop() is checked before
    each chunk. Raises InputChangedError if src has fewer or more than `total`
    bytes, and StopRequested if asked to stop.
    """
    keystream = Keystream()
    done = 0
    while done < total:
        if should_stop is not None and should_stop():
            raise StopRequested()
        chunk = src.read(min(chunk_size, total - done))
        if not chunk:
            raise InputChangedError("input is shorter than expected")
        dst.write(transform(chunk, keystream, decrypt))
        done += len(chunk)
        if on_progress is not None:
            on_progress(done, total)
    if src.read(1):
        raise InputChangedError("input is longer than expected")
    if total == 0 and on_progress is not None:
        on_progress(0, 0)
    return done
