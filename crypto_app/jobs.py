"""File-level work: validation, atomic output, worker thread and progress messages.

No Tkinter here. The worker never touches widgets; it only puts tuples on a
queue that the UI polls (see Design_v1.md Section 3):

    ("progress", done, total)   bytes processed so far
    ("done",)                   output renamed into place
    ("error", text)             run failed and was cleaned up
    ("stopped",)                worker honoured a stop request
"""
import errno
import os
import queue
import threading

import cipher


def clean_path(text):
    """Strip whitespace and one pair of surrounding quotes from a typed path."""
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        text = text[1:-1].strip()
    return text


def default_output_name(input_path, decrypt):
    """Suggested output path: encrypt appends .enc; decrypt strips a trailing .enc to restore the original name.

    If the input doesn't end in .enc, .dec is appended so the output never equals the input.
    """
    if not decrypt:
        return input_path + ".enc"
    if input_path.lower().endswith(".enc") and len(os.path.basename(input_path)) > len(".enc"):
        return input_path[:-len(".enc")]
    return input_path + ".dec"


def temp_path_for(output_path):
    """Temporary file in the destination folder: .<output name>.tmp"""
    folder, name = os.path.split(os.path.abspath(output_path))
    return os.path.join(folder, "." + name + ".tmp")


def same_file(a, b):
    """True if a and b refer to the same file (symlinks, junctions, 8.3 names, case)."""
    if os.path.exists(a) and os.path.exists(b):
        return os.path.samefile(a, b)
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def validate(input_path, output_path):
    """Return an error message, or None if the request is acceptable."""
    input_path = clean_path(input_path)
    output_path = clean_path(output_path)
    if not input_path:
        return "Please choose an input file."
    if not output_path:
        return "Please choose an output file."
    if not os.path.exists(input_path):
        return f"The input file does not exist:\n{input_path}"
    if not os.path.isfile(input_path):
        return f"The input path is not a file:\n{input_path}"
    try:
        with open(input_path, "rb"):
            pass
    except OSError as exc:
        return f"The input file cannot be read:\n{exc.strerror or exc}"
    if os.path.isdir(output_path):
        return "The output path is a folder. Please give a file name."
    if same_file(input_path, output_path):
        return "The input and output are the same file. Please choose a different output file."
    folder = os.path.dirname(os.path.abspath(output_path))
    if not os.path.isdir(folder):
        return f"The output folder does not exist:\n{folder}"
    probe = temp_path_for(output_path)
    try:
        with open(probe, "wb"):
            pass
        os.remove(probe)
    except OSError as exc:
        return f"The output folder is not writable:\n{exc.strerror or exc}"
    return None


def _describe(exc):
    if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
        return "The disk is full. The output file was not created."
    if isinstance(exc, OSError):
        return f"File error: {exc.strerror or exc}"
    return f"Unexpected error: {exc}"


class Job:
    """One encrypt or decrypt run. start() runs it on a daemon worker thread."""

    def __init__(self, input_path, output_path, decrypt, chunk_size=cipher.CHUNK_SIZE):
        self.input_path = clean_path(input_path)
        self.output_path = clean_path(output_path)
        self.decrypt = decrypt
        self.chunk_size = chunk_size
        self.messages = queue.Queue()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        """Start the worker. Returns False (and does nothing) if a run is already active."""
        if self.is_running():
            return False
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()
        return True

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def request_stop(self):
        self._stop.set()

    def join(self, timeout=None):
        if self._thread is not None:
            self._thread.join(timeout)

    def _post(self, message):
        self.messages.put(message)

    def run(self):
        """The worker body; also callable directly (synchronously) in tests."""
        temp = temp_path_for(self.output_path)
        src = dst = None
        result = ("error", "Unexpected error.")
        try:
            src = open(self.input_path, "rb")
            total = os.fstat(src.fileno()).st_size
            dst = open(temp, "wb")
            cipher.process_stream(
                src, dst, self.decrypt, total,
                on_progress=lambda done, tot: self._post(("progress", done, tot)),
                should_stop=self._stop.is_set,
                chunk_size=self.chunk_size)
            if os.fstat(src.fileno()).st_size != total:
                raise cipher.InputChangedError("input size changed")
            dst.close()
            src.close()
            os.replace(temp, self.output_path)
            result = ("done",)
        except cipher.StopRequested:
            result = ("stopped",)
        except cipher.InputChangedError:
            result = ("error", "The input file changed while it was being processed.")
        except Exception as exc:  # report everything; the UI must never get stuck
            result = ("error", _describe(exc))
        finally:
            for handle in (dst, src):
                try:
                    if handle is not None:
                        handle.close()
                except OSError:
                    pass
            if result[0] != "done":
                try:
                    os.remove(temp)
                except OSError:
                    pass
        self._post(result)
