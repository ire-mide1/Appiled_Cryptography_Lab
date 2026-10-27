File Encryption Tool — Design v1
================================

Implements [Requirements_V2.md](Requirements_V2.md). Where this document and the requirements differ, the requirements are the authority. No code exists yet; this describes how it will be built.

**Known difference from the requirements:** Requirements 4.4 says the decrypt output is pre-filled as `<input name>.dec`. This design strips a trailing `.enc` first (decision D3, Section 9), so `notes.txt.enc` suggests `notes.txt.dec`. Requirements_V2.md has not been changed to match, so the two currently disagree.

1. Module layout
----------------

```
Applied Crpytography/
├── app.py            entry point: creates the Tk root and the UI
├── ui.py             Tkinter widgets, event handlers, queue polling (no cipher maths)
├── jobs.py           validation, atomic output, worker thread, cleanup (no Tkinter)
├── cipher.py         LFSR, permutation tables, byte/stream transforms (no Tkinter, no file paths)
├── README.md         how to run, Python version, "teaching cipher, not secure"
└── tests/
    ├── test_cipher.py
    ├── test_jobs.py
    └── test_vector.py
```

| Module | Responsibility | Imports |
|---|---|---|
| `cipher.py` | Constants (seed, taps, π). Builds the permutation and inverse tables. Provides a keystream generator and a stream transformer that works on file-like objects. | stdlib only; no `tkinter`, no `os.path` logic |
| `jobs.py` | Path validation, same-path check, temp-file naming, running the transform on a worker thread, cleanup, posting progress and result messages to a `queue.Queue`. | `cipher`, `os`, `threading`, `queue` |
| `ui.py` | Builds the window, reads field values, shows message boxes, polls the queue with `after()`, enables and disables controls. | `tkinter`, `jobs` |
| `app.py` | `python app.py` starts the program. | `ui` |

The dependency direction is `app → ui → jobs → cipher`. Nothing lower imports anything higher, so `cipher.py` and `jobs.py` can be tested without a display.

**1.1 Public interface (names and intent only)**

| Function / class | Purpose |
|---|---|
| `cipher.Keystream()` | New instance starts at the seed. `next_byte()` clocks 8 times. `next_bytes(n)` returns `n` bytes. No module-level state, so two runs can never share a register. |
| `cipher.PERM`, `cipher.INV_PERM` | 256-entry tables (`bytes` objects), built once at import from π. |
| `cipher.transform(data, keystream, decrypt)` | Transforms one chunk of `bytes` and returns `bytes` of the same length. |
| `cipher.process_stream(src, dst, decrypt, total, on_progress, should_stop)` | Reads `src` in 64 KB chunks, writes to `dst`, and calls `on_progress(done, total)` after each chunk. Raises on short read or size mismatch. Checks `should_stop()` before each chunk. |
| `jobs.validate(input_path, output_path)` | Returns an error string, or `None` if the request is acceptable. Does not show any UI. |
| `jobs.same_file(a, b)` | Full-resolution same-file check (see 5.2). |
| `jobs.default_output_name(input_path, decrypt)` | Suggested output path. Encrypt: append `.enc`. Decrypt: if the name ends in `.enc` (case-insensitive), strip it and append `.dec`; otherwise append `.dec`. Kept in `jobs.py` so it can be tested without a display. |
| `jobs.Job(...)` | Holds input, output, mode, the message queue and the stop event. `start()` launches the worker thread. `request_stop()` sets the stop event. |

2. Cipher design
----------------

**2.1 Constants**

| Name | Value |
|---|---|
| `SEED` | `0x67BD5` |
| `MASK` | `0x7FFFF` (19 bits) |
| `TAP_BITS` | `(13, 16, 17, 18)`, which are x¹⁴, x¹⁷, x¹⁸ and x¹⁹ |
| `PI` | `(2, 6, 3, 5, 1, 8, 4, 7)`, 1-based positions, position 1 = MSB |

**2.2 Exact LFSR clocking**

Register: 19 bits. Bit 0 is the leftmost bit and LSB (x¹). Bit 18 is the rightmost bit and MSB (x¹⁹).

One clock step, in this order:

1. `out` = bit 18 of `state`.
2. `fb` = bit 13 ⊕ bit 16 ⊕ bit 17 ⊕ bit 18, all read from the **pre-shift** `state`.
3. `state = ((state << 1) | fb) & 0x7FFFF`.
4. The step emits `out`.

Keystream byte: do 8 steps. The first `out` goes to bit 0 of the byte, the second to bit 1, and so on. The eighth goes to bit 7.

The register is created at `SEED` for each `Keystream()` instance and runs on across chunks. It is never re-seeded within a file.

**Worked clock example (first step).**
- `SEED` = `0x67BD5`. The relevant bits are bit 18 = 1, bit 17 = 1, bit 16 = 0, bit 13 = 1.
- `out` = 1.
- `fb` = 1 ⊕ 0 ⊕ 1 ⊕ 1 = 1.
- Shift: `0x67BD5 << 1` = `0xCF7AA`. OR in `fb`: `0xCF7AB`. Mask to 19 bits: `0x4F7AB`.
- New state = `0x4F7AB`. Its bit 18 is 1, so the second `out` is 1.

The first 8 outputs, in order, are 1, 1, 0, 0, 1, 1, 1, 1. Packed with the first as the LSB, the byte is `11110011` = `0xF3`, which matches the first byte of the test vector.

**2.3 Permutation and inverse tables**

Forward rule: `y_i = x_π(i)`, where output position `i` takes the input bit from position `π(i)`.

| Output position i | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| π(i), the input position it takes | 2 | 6 | 3 | 5 | 1 | 8 | 4 | 7 |
| π⁻¹(i), for the inverse | 5 | 1 | 3 | 7 | 4 | 2 | 8 | 6 |

Inverse check: π⁻¹(π(i)) = i. For example π(1) = 2 and π⁻¹(2) = 1.

**Build method.** For each `x` in 0 to 255:
1. Split `x` into bits x₁…x₈, with x₁ = MSB (`(x >> (8 − i)) & 1`).
2. Form the output bits `y_i = x_π(i)`.
3. Pack y₁…y₈ back into a byte, y₁ as the MSB. That gives `PERM[x]`.
4. Set `INV_PERM[PERM[x]] = x`.

Building `INV_PERM` by inverting the finished forward table (rather than applying π⁻¹ separately) guarantees the two tables are inverses of each other. A test also checks it directly against the π⁻¹ row above.

Spot values: `PERM[0x80] = 0x08` (input MSB is x₁, used where π(i) = 1, which is i = 5, the bit with value `0x08`). `PERM[0x40] = 0x80` (x₂ is used at i = 1, the MSB).

**2.4 Worked example on one byte: the letter "C" (`0x43`)**

First keystream byte = `0xF3`.

**Encrypt.**
1. `0x43` = `01000011`, so x₁…x₈ = 0, 1, 0, 0, 0, 0, 1, 1.
2. Output bits `y_i = x_π(i)` with π = 2, 6, 3, 5, 1, 8, 4, 7:
   y₁ = x₂ = 1, y₂ = x₆ = 0, y₃ = x₃ = 0, y₄ = x₅ = 0, y₅ = x₁ = 0, y₆ = x₈ = 1, y₇ = x₄ = 0, y₈ = x₇ = 1.
3. y = `10000101` = `0x85` (so `PERM[0x43] = 0x85`).
4. XOR with the keystream byte: `0x85 ⊕ 0xF3` = `0x76`. Ciphertext byte = `0x76`.

**Decrypt.**
1. `0x76 ⊕ 0xF3` = `0x85`.
2. Apply the inverse: `INV_PERM[0x85]`. Using `x_π(i) = y_i`: x₂ = 1, x₆ = 0, x₃ = 0, x₅ = 0, x₁ = 0, x₈ = 1, x₄ = 0, x₇ = 1.
3. So x = (0, 1, 0, 0, 0, 0, 1, 1) = `01000011` = `0x43` = "C". Round trip complete.

These values match the requirements' test vector (`0x43 → 0x85 → 0x76`).

3. Worker thread and progress bar
---------------------------------

Tkinter is not thread-safe, so **only the main thread touches widgets.** The worker never imports or calls Tkinter.

**3.1 Flow**

1. The user clicks Start. `ui.py` runs `jobs.validate`, handles the overwrite prompt, then creates a `Job`.
2. The UI disables the controls, sets the progress bar to 0 and starts the job.
3. The worker thread (a daemon thread):
   1. Opens the input and a temporary file `.<output name>.tmp` in the destination folder.
   2. Records the input size `total` (from `fstat` on the open handle).
   3. Calls `process_stream`. After each 64 KB chunk it puts `("progress", done, total)` on the queue.
   4. On success: flush and close, then `os.replace(temp, output)`. Posts `("done",)`.
   5. On any failure: closes the files, deletes the temp file, posts `("error", message)`.
4. The UI polls the queue every 50 ms with `root.after(50, poll)`. It drains all pending messages per tick, applies only the **latest** progress value, and updates the bar and "NN%" label.
5. On `done`: set the bar to 100%, show "Operation complete", re-enable the controls.
6. On `error`: show the message, reset the bar to 0, re-enable the controls.

**3.2 Message protocol**

| Message | Meaning | UI action |
|---|---|---|
| `("progress", done, total)` | Bytes processed so far | Update bar and percentage |
| `("done",)` | Output renamed into place | Show success, return to idle |
| `("error", text)` | Run failed and was cleaned up | Show error, reset bar, return to idle |
| `("stopped",)` | Worker honoured a stop request | Return to idle (used on window close) |

**3.3 Progress detail**

- Percentage = `done * 100 // total`.
- If `total` is 0 (empty file), no chunks are read and the UI jumps straight to 100%.
- Progress is posted per chunk, not per byte, so a few MB produces only dozens of messages.

**3.4 Stop and window close**

- Closing the window during a run asks for confirmation. If confirmed, `request_stop()` sets a `threading.Event`. `process_stream` checks it before each chunk and raises a stop signal. The worker cleans up and posts `("stopped",)`.
- The UI waits briefly for that message (short join with timeout, so the window can't hang) and then destroys the window.
- If the user declines, nothing changes.

4. UI layout
------------

```
┌─ File Encryption Tool ───────────────────────────────┐
│  Mode:   (•) Encrypt     ( ) Decrypt                 │
│                                                      │
│  Input file:   [ C:\path\to\input.txt        ] [Browse…] │
│  Output file:  [ C:\path\to\input.txt.enc    ] [Browse…] │
│                                                      │
│  [ Start ]                                           │
│                                                      │
│  [██████████░░░░░░░░░░░░░░░░░░░░]  42%               │
│                                                      │
│  Note: output has no header. Decrypting with the     │
│  wrong mode, or a file that was never encrypted,     │
│  gives garbage with no warning.                      │
└──────────────────────────────────────────────────────┘
```

| Widget | Type | Notes |
|---|---|---|
| Mode | Two `ttk.Radiobutton`s sharing one `StringVar` | Default: Encrypt |
| Input path | `ttk.Entry` + Browse (`askopenfilename`) | Editable; "All files" filter only |
| Output path | `ttk.Entry` + Browse (`asksaveasfilename`) | Editable; pre-filled via `default_output_name` after an input is chosen or the mode changes. Auto-fill stops once the user has edited or browsed the field |
| Start | `ttk.Button` | Disabled while a job runs |
| Progress | `ttk.Progressbar` (determinate, 0–100) + percentage `Label` | Resets to 0 on error |
| Note | Static `Label` | Required by req. 4.8 |

Layout uses `grid` with the path columns stretching. Validation reads the **current text** of the entry fields, not the last Browse result.

5. Error handling
-----------------

All errors surface as message boxes; the UI always returns to idle. These implement Requirements Section 5.

**5.1 Before starting (no files touched)**

| Check | Message / action |
|---|---|
| Input or output field empty (after stripping whitespace and surrounding quotes) | Name the missing field |
| Input missing, not a file, or unreadable | Say so; do not start |
| Output folder missing or not writable (tested by creating then deleting the temp file) | Say so; do not start |
| Output path is a directory | Say so; do not start |
| Same file (5.2) | Refuse |
| Output exists | `askyesno` overwrite prompt. No leaves everything unchanged |

**5.2 Same-file check**

1. If both paths exist, use `os.path.samefile` (handles symlinks, junctions, 8.3 names, case).
2. Otherwise compare `os.path.normcase(os.path.realpath(path))` for both.

**5.3 During the run (worker)**

| Failure | Behaviour |
|---|---|
| Read error, write error, disk full | Close the files, delete the temp file, post `("error", text)` |
| Read returns fewer bytes than expected, or input size at the end differs from `total` | Treated as "input changed": fail with a clear message |
| `os.replace` fails (target locked) | Delete the temp file, leave any existing target untouched, report the error |
| Any other exception | Caught by a top-level `try/except` in the worker and reported with the exception text |
| Stop requested | Clean up and post `("stopped",)` |

Guarantees (Requirements 5.2): the real output name is touched only by the final `os.replace`, so a failure cannot leave a partial file or destroy a pre-existing one. A leftover temp file from a hard crash is recognisable by its `.<name>.tmp` pattern and is overwritten on the next run to the same output.

A second Start while a job is active is ignored both by the disabled button and by a guard in `Job.start()`.

6. Unit tests
-------------

Run with `python -m unittest` (standard library, no extra dependencies).

**6.1 `test_vector.py` — reference vector**

These are fixed expected values, hard-coded in the test file. They have been independently verified by the user and are not recomputed by the tests from the code under test. The "CRYPTO" result is also to be compared with classmates; if that comparison turns up a difference, these tests are the first thing to revisit.

| Test | Check |
|---|---|
| Single-byte "C" example | `0x43` permutes to `0x85`, and XOR with the first keystream byte `0xF3` gives `0x76`. Decrypting `0x76` with `0xF3` gives `0x85`, which the inverse table maps back to `0x43` |
| Keystream | First 16 bytes from a fresh `Keystream()` equal `F3 5E 0D 66 C6 FD D7 1D 3A 25 02 7E 9D AB 43 4F` |
| Permutation step | `PERM` applied to `43 52 59 50 54 4F` gives `85 83 96 82 C2 D5` |
| Encrypt "CRYPTO" | Output equals `76 DD 9B E4 04 28` |
| Decrypt | Decrypting `76 DD 9B E4 04 28` gives `CRYPTO` |
| Spot values | `PERM[0x80] = 0x08`, `PERM[0x40] = 0x80`, `PERM[0x43] = 0x85` |

**6.2 `test_cipher.py`**

| Test | Check |
|---|---|
| Table bijection | `PERM` has all 256 distinct values, `INV_PERM[PERM[x]] == x` and `PERM[INV_PERM[x]] == x` for all `x` |
| Inverse row | `INV_PERM` agrees with the π⁻¹ row (5, 1, 3, 7, 4, 2, 8, 6) |
| Round trip | Random data of several sizes encrypts then decrypts to the original |
| All byte values | A file containing 0–255 round trips, and runs of `00` and `FF` do too |
| Empty input | 0 bytes in, 0 bytes out |
| Length preserved | Output length equals input length for many sizes |
| Chunk boundaries | Sizes 64 KB − 1, 64 KB, 64 KB + 1 and 3 chunks + 1 give output identical to processing in one piece (keystream continuous across chunks) |
| No shared state | Two `Keystream()` instances produce identical output. Two successive runs give identical output for the same input |
| Register width | State never exceeds `0x7FFFF`; state never becomes 0 over a full test run |
| Mode independence | Chunk size does not change the output (try 1, 7 and 64 KB) |

**6.3 `test_jobs.py` (temporary directories)**

| Test | Check |
|---|---|
| Same-path spellings | Relative vs absolute, differing case, and a symlink or junction where creatable are all rejected |
| Default output name | Encrypt: `notes.txt` → `notes.txt.enc`. Decrypt: `notes.txt.enc` → `notes.txt.dec`; `notes.txt` → `notes.txt.dec`; `NOTES.ENC` → `NOTES.dec`; a name that is only `.enc` or has `.enc` in the middle (`a.enc.txt`) gets `.dec` appended, not stripped |
| Missing or empty fields | `validate` returns the expected message |
| Output is a folder | Rejected |
| Success path | Output equals the expected bytes; no temp file left |
| Failure cleanup | Injecting a failing source or sink mid-run leaves no output file |
| Pre-existing output | After an injected failure, the old output is unchanged |
| Input size change | A source whose size differs from `total` fails and cleans up |
| Stop request | Setting the stop event mid-run cleans up and posts `stopped` |
| Two runs in one session | Same input gives identical output both times |
| Messages | A normal run posts monotonically increasing progress and ends with `done` |

**6.4 Manual UI checklist**

The UI is checked by hand, since Tkinter needs a display. Steps: run an encrypt then decrypt through the UI and compare with the original (`fc /b` on Windows); try the empty file; double-click Start; close the window mid-run on a larger file; switch mode after choosing an input; paste a path wrapped in quotes; choose a read-only destination.

7. Build order
--------------

Each step ends with its tests passing before moving on.

1. **`cipher.py` tables and LFSR**, with `test_vector.py` (fixed, verified values) and the bijection tests. This is the correctness core. The simple bit-by-bit LFSR comes first, with no keystream caching.
2. **`cipher.transform` and `process_stream`**, with the round-trip, empty, length and chunk-boundary tests.
3. **Benchmark checkpoint**: time a 5 MB file (see risk R1). Optimise only if it takes longer than about 5 seconds; otherwise leave it. Any optimisation must not use precomputed keystream caching, and the fixed test vector protects the rewrite.
4. **`jobs.py`**: validation, same-file check, temp file and atomic replace, cleanup, worker thread and queue, with `test_jobs.py`.
5. **`ui.py` skeleton**: layout only, no wiring. Look at it, adjust.
6. **Wire up the UI**: Browse buttons, output name pre-fill, validation message boxes, overwrite prompt.
7. **Worker integration**: queue polling, progress bar, control disable and enable.
8. **Error and close paths**: error boxes, bar reset, window-close confirmation and clean stop.
9. **Manual checklist** (6.4) and fixes.
10. **README**: how to run, Python version, teaching-cipher note.

8. Risks
--------

| # | Risk | Why it matters | Mitigation |
|---|---|---|---|
| R1 | **Speed.** A straightforward bit-by-bit LFSR does 8 clock steps per byte in pure Python. I have not measured it. My rough expectation is around a few MB per 10–30 seconds on a typical laptop, which may feel slow for "a few MB". | The progress bar helps, but a long wait is poor UX. | **Decided (D2):** build the simple version first and measure (build step 3). Optimise only if 5 MB takes longer than about 5 seconds, without changing the output and without precomputed keystream caching (for example, byte-at-a-time table lookups for the 8-step transition). The fixed test vector guards any rewrite. |
| R2 | ~~The test vector has not been confirmed independently.~~ **Resolved (D1):** the user verified the first 16 keystream bytes, the "CRYPTO" ciphertext and the "C" example independently. | Interoperability is the main point of the spec. | Residual item: the user will also compare the "CRYPTO" result with classmates. The tests treat the values as fixed. |
| R3 | **Windows file locking.** `os.replace` can fail if the target is open elsewhere. Antivirus can briefly lock the temp file. | Spurious failures. | Failure path leaves the old target intact. No retry loop in v1. |
| R4 | **Windows path quirks.** Long paths over 260 characters, UNC paths, and quotes pasted into the field. | Validation false negatives. | Strip quotes, use `realpath`/`samefile`. Long-path handling relies on Python's own support. I'd call it best effort. |
| R5 | **Closing the window while a worker runs.** A daemon thread could be killed mid-write, leaving a temp file. | Leftover files. | Stop event plus a short join. A leftover `.tmp` is never confused with real output. |
| R6 | **Tkinter thread safety.** Any widget call from the worker could crash intermittently. | Hard-to-reproduce bugs. | Only the queue crosses the thread boundary. |
| R7 | **Wrong-mode use gives garbage silently.** | Users may think the tool is broken. | The UI note, which is required by the spec. |

9. Decisions
------------

All nine items from the first draft are now settled. Items 1–3 were answered by the user; items 4–9 use the defaults proposed.

| # | Topic | Decision |
|---|---|---|
| D1 | Test vector (R2) | Independently verified by the user: the first 16 keystream bytes (`F3 5E 0D 66 C6 FD D7 1D 3A 25 02 7E 9D AB 43 4F`), "CRYPTO" → `76 DD 9B E4 04 28`, and the "C" example (`0x43 → 0x85 → 0x76`). All are added as fixed unit tests (Section 6.1). The user will also compare "CRYPTO" with classmates. |
| D2 | Speed (R1) | Build the simple bit-by-bit version, benchmark 5 MB at build step 3, and optimise only if it takes longer than about 5 seconds. No precomputed keystream caching. |
| D3 | Decrypt output name | Strip a trailing `.enc` (case-insensitive) when present and append `.dec`: `notes.txt.enc` → `notes.txt.dec`. If the name doesn't end in `.enc`, just append `.dec`. Encrypt appends `.enc`. Implemented by `jobs.default_output_name` and tested. |
| D4 | Pre-fill after manual edit | Auto-fill only while the user has not edited or browsed the output field. |
| D5 | Window close | Ask for confirmation only while a job is running. Close immediately when idle. |
| D6 | Temp file location | In the destination folder, named `.<output name>.tmp`, so the final rename stays on one drive. |
| D7 | Wording and title | Window title "File Encryption Tool". Plain, short message-box text as in the tables above. |
| D8 | Folder name | The project folder name "Crpytography" is left as is. |
| D9 | Test discovery | Tests live in `tests/` and run with `python -m unittest discover -s tests`, documented in the README. |

No open decisions remain in this design.
