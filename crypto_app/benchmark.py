"""Round-trip a random file through the cipher and report timings.

Usage: python benchmark.py [size_in_MB]   (default 5)
"""
import os
import sys
import tempfile
import time

import cipher


def run(src_path, dst_path, decrypt):
    total = os.path.getsize(src_path)
    start = time.perf_counter()
    with open(src_path, "rb") as src, open(dst_path, "wb") as dst:
        cipher.process_stream(src, dst, decrypt, total)
    return time.perf_counter() - start


def main():
    megabytes = float(sys.argv[1]) if len(sys.argv) > 1 else 5
    size = int(megabytes * 1024 * 1024)
    with tempfile.TemporaryDirectory() as tmp:
        original = os.path.join(tmp, "original.bin")
        encrypted = os.path.join(tmp, "encrypted.bin")
        decrypted = os.path.join(tmp, "decrypted.bin")
        with open(original, "wb") as fh:
            fh.write(os.urandom(size))

        t_enc = run(original, encrypted, decrypt=False)
        t_dec = run(encrypted, decrypted, decrypt=True)

        with open(original, "rb") as a, open(encrypted, "rb") as b, open(decrypted, "rb") as c:
            orig, enc, dec = a.read(), b.read(), c.read()

        print(f"file size            : {size} bytes ({megabytes:g} MB)")
        print(f"encrypted size       : {len(enc)} bytes (same as input: {len(enc) == size})")
        print(f"encrypt time         : {t_enc:.2f} s ({megabytes / t_enc:.2f} MB/s)")
        print(f"decrypt time         : {t_dec:.2f} s ({megabytes / t_dec:.2f} MB/s)")
        print(f"total (enc + dec)    : {t_enc + t_dec:.2f} s")
        print(f"ciphertext != input  : {enc != orig}")
        print(f"round trip identical : {dec == orig} (byte for byte, {len(dec)} bytes)")
        return 0 if dec == orig and len(enc) == size else 1


if __name__ == "__main__":
    sys.exit(main())
