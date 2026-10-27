File Encryption Tool — Requirements v2
======================================

1. Overview
-----------

The project is a simple file encryption and decryption tool with a Tkinter GUI. The user picks an input file, chooses Encrypt or Decrypt, names an output file and presses Start. Encryption scrambles each byte with a fixed bit permutation and then XORs it with one byte from a 19-bit LFSR keystream. Decryption XORs with the same keystream byte and then applies the inverse permutation, which recovers the original file.

The bit ordering and register behaviour are defined strictly in Section 3 so that a file encrypted by one implementation can be decrypted by another. Where this overview and a numbered requirement differ, **the numbered requirement is the authority.**

> **Educational use only.** This cipher is a teaching exercise and is not secure. The keystream is fixed and independent of the data, so one known plaintext/ciphertext pair reveals it completely.

2. General and Technical
------------------------

1. The program shall be written in Python 3.10 or later, using only the standard library.
2. The user interface shall use Tkinter.
3. The target platform is Windows. The program shall run with `python app.py`. No executable packaging is required.
4. The cipher logic shall live in a separate module that does not import Tkinter, so it can be tested on its own.
5. The program shall work on any file type (text, images, binaries). The output file shall be exactly the same size as the input.
6. Files are expected to be small to medium (a few MB). Per-byte Python processing is acceptable, and keystream caching is not required.

3. Cipher Specification
-----------------------

**3.1 Parameters**

1. The key is the fixed 19-bit seed `0x67BD5`, defined as a constant in the code. There is no key entry field.
2. The LFSR polynomial is p(x) = 1 + x¹⁴ + x¹⁷ + x¹⁸ + x¹⁹, with taps at positions 14, 17, 18 and 19.
3. The byte permutation π, over the 8 bit positions within a byte, is: π(1)=2, π(2)=6, π(3)=3, π(4)=5, π(5)=1, π(6)=8, π(7)=4, π(8)=7.

**3.2 LFSR register**

1. The register is 19 bits wide. Bit 0 is the leftmost bit and the LSB, and it corresponds to x¹. Bit 18 is the rightmost bit and the MSB, and it corresponds to x¹⁹.
2. The seed is loaded directly, so the seed's LSB goes to bit 0 and its MSB goes to bit 18.
3. The tap positions x¹⁴, x¹⁷, x¹⁸ and x¹⁹ correspond to register bits 13, 16, 17 and 18.
4. The constant term "1" in the polynomial marks the feedback connection into the left end (bit 0) of the register. The feedback is not inverted.
5. Each clock step shall do the following, in this order:
   1. Output bit = bit 18 of the current state.
   2. Feedback `fb` = bit13 ⊕ bit16 ⊕ bit17 ⊕ bit18, read from the pre-shift state.
   3. New state = `((state << 1) | fb) & 0x7FFFF`.
6. The first bit output is therefore the MSB of the seed.

**3.3 Keystream byte**

1. One keystream byte is built from 8 consecutive clock steps.
2. The first output bit becomes the LSB (bit 0) of the keystream byte, and the eighth output bit becomes the MSB (bit 7).
3. The register is reset to the seed at the start of every encrypt or decrypt operation. It is clocked continuously (8 steps per input byte) across the whole file and is never re-seeded mid-file.

**3.4 Permutation**

1. Bit positions in a byte are numbered 1 to 8, where position 1 is the MSB and position 8 is the LSB.
2. For an input byte x = (x₁, x₂, …, x₈), the permuted byte is y = (x_π(1), x_π(2), …, x_π(8)). Output position i takes the input bit from position π(i).
   - Example: π(1)=2, so the output MSB is the input's bit at position 2.
3. The inverse permutation π⁻¹ satisfies π⁻¹(π(i)) = i. Applying it recovers x from y.
4. Both the permutation and its inverse shall be implemented as 256-entry lookup tables.

**3.5 Encrypt and decrypt**

1. **Encrypt:** for each input byte, permute it with π, then XOR with the next keystream byte.
2. **Decrypt:** for each input byte, XOR it with the next keystream byte, then apply π⁻¹.
3. The output carries no header, magic number, checksum or length field. Decrypting with the wrong mode, or decrypting a file that was never encrypted, therefore produces garbage without any error.

**3.6 Reference test vector**

Computed from the conventions above and to be confirmed against an independent implementation before the cipher is accepted.

| Item | Value (hex) |
|---|---|
| First 16 keystream bytes | `F3 5E 0D 66 C6 FD D7 1D 3A 25 02 7E 9D AB 43 4F` |
| Plaintext "CRYPTO" | `43 52 59 50 54 4F` |
| After permutation | `85 83 96 82 C2 D5` |
| Ciphertext (permuted ⊕ keystream) | `76 DD 9B E4 04 28` |

Sanity checks: the first keystream byte is `F3` = 11110011, with the first bit output in the LSB. This is consistent with the seed's leading bits 1, 1, 0, 0, … Also π maps `0x80` to `0x08` and `0x40` to `0x80`.

4. User Interface
-----------------

1. The UI shall let the user choose between Encrypt and Decrypt using radio buttons.
2. The UI shall let the user select an input file, via an editable path field and a Browse button.
3. The UI shall let the user specify an output file, via an editable path field and a Browse button that opens a Save As dialog.
4. Once an input file is chosen, the output path shall be pre-filled as `<input name>.enc` when encrypting or `<input name>.dec` when decrypting. The user may change it.
5. File dialogs shall use an "All files" filter only.
6. The UI shall have a button labelled "Start" that begins the operation.
7. The UI shall show a determinate progress bar, with a percentage label, that updates while the file is processed.
8. The UI shall display a short note that the output has no header, so the wrong mode or a non-encrypted file decrypts to garbage with no warning.
9. There is no Cancel button in this version.

5. Behaviour and Error Handling
-------------------------------

1. **Validation:** before starting, the program shall check that an input file and an output path are given, that the input is readable and that the output folder is writable. On failure it shall show a message box and not start.
2. **Same path:** if the input and output refer to the same file, the program shall refuse with an error message. The comparison shall use full resolution (`os.path.realpath`, then a case-insensitive comparison on Windows), so that `a.txt` vs `.\a.txt`, differing case, 8.3 short names, symlinks and junctions are all detected.
3. **Overwrite:** if the output file already exists, the program shall ask for confirmation before starting.
4. **Empty input:** a 0-byte input is allowed and produces a 0-byte output. The progress bar goes straight to 100%.
5. **Threading:** processing shall run in a worker thread, in 64 KB chunks. The UI shall poll for progress using `after()`.
6. **Controls while running:** Start and the other input controls shall be disabled until the operation finishes.
7. **Atomic writes:** the output shall be written to a temporary file in the destination folder and renamed to the final name only on success.
8. **Success:** the program shall show an "Operation complete" message box.
9. **Failure:** the program shall show the error and delete the temporary or partial output file, leaving no half-written result.
10. **Window closed during a run:** the program shall ask for confirmation. If the user confirms, it shall stop the worker, delete the temporary file and exit. If not, the run continues.
11. **Input changes during processing:** if the input file's size changes or a read fails while it is being processed, the operation shall fail with a clear message and be cleaned up as in item 9. It shall not complete normally on partial data.
12. **Start guard:** the worker shall refuse to start a second operation while one is running, in addition to the Start button being disabled.

**5.1 Error-handling table**

| Situation | Behaviour |
|---|---|
| Input or output field empty | Message box naming the missing field. Don't start. |
| Input missing, unreadable or a directory | Message box. Don't start. |
| Output folder missing or not writable | Message box. Don't start. |
| Output path is a folder | Message box. Don't start. |
| Input and output are the same file | Refuse with an error (see item 2). |
| Output file exists | Overwrite prompt. If the user answers No, return to idle with nothing changed. |
| Read error mid-file | Stop, show the error, delete the temporary file, reset the progress bar to 0, re-enable the controls. |
| Write error or disk full | Same as a read error. Say "disk full" when it can be detected. |
| Final rename fails (for example, target locked) | Show the error, delete the temporary file and leave any existing target file untouched. |
| Input size changes during the run | Fail with a clear message (item 11). |
| Start pressed while running | Ignored (item 12). |
| Window closed during a run | Confirmation, then clean shutdown (item 10). |
| Unexpected exception in the worker | Catch all exceptions, show a generic message with the exception text, clean up and re-enable the controls. The UI never stays stuck at partial progress. |
| Temporary file left over from a crash | The temporary file uses a recognisable name (`.<output name>.tmp`) in the destination folder. The real output name is never touched until the final rename. |

**5.2 Error-handling principles**

1. A failed run never leaves a partial or corrupt output file.
2. A failed run never destroys a pre-existing output file.
3. Every error produces visible feedback, and the UI always returns to a usable idle state.
4. The progress bar resets to 0 after an error.

6. Testing
----------

1. Unit tests shall check the keystream against the Section 3.6 test vector.
2. A test shall confirm that π and π⁻¹ are inverse permutations over all 256 byte values.
3. A test shall confirm that encrypting and then decrypting random data returns the original.
4. A test shall cover a file containing all 256 byte values.
5. A test shall cover an empty file.
6. A test shall confirm that the output length equals the input length.
7. Tests shall cover file sizes around the chunk boundary (64 KB − 1, 64 KB, 64 KB + 1, and three chunks plus 1 byte), to confirm the keystream is continuous across chunks.
8. A test shall confirm that two successive operations in the same session give identical output for the same input (no state carried between runs).
9. Tests shall cover the same-path check with different spellings of one path (relative vs absolute, differing case).
10. Tests shall cover failure cleanup: a failed run leaves no partial output and does not damage a pre-existing output file.