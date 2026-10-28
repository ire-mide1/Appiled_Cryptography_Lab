# File Encryption Tool (Applied Cryptography Lab 1)

An app, written in Python with Tkinter, that encrypts and decrypts any file.

> **Educational use only. This cipher is NOT secure.** The key is fixed and built into the code, and the scrambling pattern never depends on the file. Anyone who has one original/encrypted pair of a file can work out the whole keystream. Do not use it to protect real data.

---

## 1. Quick start

You need Python 3.10 or newer. Nothing else is needed, because the app uses only the standard library.


To use the app
In your terminal, type:
```
cd crypto_app
python app.py
```
The cipher app will open, Follow this guidelines:

1. Choose **Encrypt** or **Decrypt**.
2. Click **Browse…** and pick your desired input file.
3. The output name is automatically filled in for you. However, you can change it.
4. Click **Start**. A progress bar shows how far along it is, and you can stop it part way through.

Output naming:

| You do this | Suggested output |
|---|---|
| Encrypt `notes.txt` | `notes.txt.enc` |
| Decrypt `notes.txt.enc` | `notes.txt` |
| Decrypt a file that doesn't end in `.enc` | `<name>.dec` |

The output is always exactly the same size as the input. There is no header, so if you decrypt with the wrong mode, or decrypt a file that was never encrypted, you get garbage and no warning.

To run the tests and the benchmark, in your terminal, type these:

```
cd crypto_app
python -m unittest discover -s tests -t .
python benchmark.py 5        # round-trips a 5 MB random file and prints timings
```

## 2. How the repo is organised

```
.
├── README.md               this file
├── Requirements_V1.md      the original self written requirements
├── Requirements_V2.md      the iterative requirements written with claude
├── Design_v1.md            shows the app design
├── interrogation.md        step-by-step worked example of the LFSR and permutation
├── project_chat.md         log of the conversation with claude
└── crypto_app/
    ├── app.py              entry point: opens the window
    ├── ui.py               the Tkinter window (buttons, fields, progress bar)
    ├── jobs.py             file handling: checks, temp files, background thread
    ├── cipher.py           the cipher itself: LFSR, permutation, stream processing
    ├── benchmark.py        timing and round-trip check on a random file
    ├── requirements.txt    no packages needed (stdlib only)
    └── tests/
        ├── test_cipher.py  cipher behaviour and edge cases
        ├── test_jobs.py    file handling, errors, cancel, cleanup
        └── test_vector.py  fixed reference values (hard-coded, never recomputed)
```



---

## 3. Limits

- Windows is the target platform. The code is mostly portable, but only Windows was considered.
- It is meant for small to medium files, and `benchmark.py` shows the real speed on your machine.
- No password, no header, and no integrity check. See the warning at the top.
