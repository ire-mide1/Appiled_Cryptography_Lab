"""Tkinter front end. Only this thread touches widgets; the worker talks via a queue."""
import os
import queue
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import jobs

TITLE = "File Encryption Tool"
POLL_MS = 50
NOTE = ("Note: the output has no header. Decrypting with the wrong mode, or a file "
        "that was never encrypted, gives garbage with no warning.")
ALL_FILES = [("All files", "*.*")]


class App:
    def __init__(self, root):
        self.root = root
        self.job = None
        self._setting_output = False
        self._output_edited = False

        root.title(TITLE)
        root.minsize(560, 0)
        root.resizable(True, False)

        self.mode_var = tk.StringVar(value="encrypt")
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.progress_var = tk.DoubleVar(value=0)
        self.percent_var = tk.StringVar(value="0%")

        self._build()

        self.mode_var.trace_add("write", lambda *_: self._refill_output())
        self.input_var.trace_add("write", lambda *_: self._refill_output())
        self.output_var.trace_add("write", lambda *_: self._on_output_changed())
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build(self):
        frame = ttk.Frame(self.root, padding=14)
        frame.grid(sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Mode:").grid(row=0, column=0, sticky="w", pady=(0, 10))
        modes = ttk.Frame(frame)
        modes.grid(row=0, column=1, columnspan=2, sticky="w", pady=(0, 10))
        self.radio_encrypt = ttk.Radiobutton(
            modes, text="Encrypt", value="encrypt", variable=self.mode_var)
        self.radio_decrypt = ttk.Radiobutton(
            modes, text="Decrypt", value="decrypt", variable=self.mode_var)
        self.radio_encrypt.grid(row=0, column=0, padx=(0, 18))
        self.radio_decrypt.grid(row=0, column=1)

        ttk.Label(frame, text="Input file:").grid(row=1, column=0, sticky="w", pady=4)
        self.input_entry = ttk.Entry(frame, textvariable=self.input_var)
        self.input_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        self.input_button = ttk.Button(frame, text="Browse…", command=self._browse_input)
        self.input_button.grid(row=1, column=2, pady=4)

        ttk.Label(frame, text="Output file:").grid(row=2, column=0, sticky="w", pady=4)
        self.output_entry = ttk.Entry(frame, textvariable=self.output_var)
        self.output_entry.grid(row=2, column=1, sticky="ew", padx=8, pady=4)
        self.output_button = ttk.Button(frame, text="Browse…", command=self._browse_output)
        self.output_button.grid(row=2, column=2, pady=4)

        self.start_button = ttk.Button(frame, text="Start", command=self.start)
        self.start_button.grid(row=3, column=0, columnspan=3, sticky="w", pady=(12, 8))

        bar = ttk.Frame(frame)
        bar.grid(row=4, column=0, columnspan=3, sticky="ew")
        bar.columnconfigure(0, weight=1)
        self.progressbar = ttk.Progressbar(
            bar, orient="horizontal", mode="determinate", maximum=100,
            variable=self.progress_var)
        self.progressbar.grid(row=0, column=0, sticky="ew")
        ttk.Label(bar, textvariable=self.percent_var, width=5, anchor="e").grid(
            row=0, column=1, padx=(8, 0))

        ttk.Label(frame, text=NOTE, wraplength=520, justify="left").grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(12, 0))

        self._controls = [
            self.radio_encrypt, self.radio_decrypt, self.input_entry, self.input_button,
            self.output_entry, self.output_button, self.start_button,
        ]

    # --- output-name pre-fill -------------------------------------------------

    def _decrypt(self):
        return self.mode_var.get() == "decrypt"

    def _set_output(self, text):
        self._setting_output = True
        try:
            self.output_var.set(text)
        finally:
            self._setting_output = False

    def _on_output_changed(self):
        if not self._setting_output:
            # An emptied field counts as "not edited", so auto-fill resumes.
            self._output_edited = bool(self.output_var.get().strip())

    def _refill_output(self):
        if self._output_edited or self._running():
            return
        input_path = jobs.clean_path(self.input_var.get())
        if input_path:
            self._set_output(jobs.default_output_name(input_path, self._decrypt()))

    # --- browse buttons -------------------------------------------------------

    def _browse_input(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="Select input file", filetypes=ALL_FILES)
        if path:
            self.input_var.set(os.path.normpath(path))

    def _browse_output(self):
        current = jobs.clean_path(self.output_var.get())
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Select output file", filetypes=ALL_FILES,
            initialdir=os.path.dirname(current) or None,
            initialfile=os.path.basename(current) or None,
            confirmoverwrite=False)  # overwrite is confirmed once, in start()
        if path:
            self.output_var.set(os.path.normpath(path))

    # --- running a job --------------------------------------------------------

    def _running(self):
        return self.job is not None

    def _set_controls(self, enabled):
        state = "normal" if enabled else "disabled"
        for widget in self._controls:
            widget.configure(state=state)

    def _show_progress(self, done, total):
        percent = 100 if total == 0 else done * 100 // total
        self.progress_var.set(percent)
        self.percent_var.set(f"{percent}%")

    def start(self):
        if self._running():
            return
        input_path = jobs.clean_path(self.input_var.get())
        output_path = jobs.clean_path(self.output_var.get())
        error = jobs.validate(input_path, output_path)
        if error:
            messagebox.showerror(TITLE, error, parent=self.root)
            return
        if os.path.exists(output_path) and not messagebox.askyesno(
                TITLE, f"The output file already exists:\n{output_path}\n\nOverwrite it?",
                parent=self.root):
            return
        self.job = jobs.Job(input_path, output_path, self._decrypt())
        self._set_controls(False)
        self._show_progress(0, 1)
        self.job.start()
        self.root.after(POLL_MS, self._poll)

    def _poll(self):
        job = self.job
        if job is None:
            return
        latest = final = None
        while True:
            try:
                message = job.messages.get_nowait()
            except queue.Empty:
                break
            if message[0] == "progress":
                latest = message
            else:
                final = message
        if latest is not None:
            self._show_progress(latest[1], latest[2])
        if final is None:
            self.root.after(POLL_MS, self._poll)
        else:
            self._finish(final)

    def _finish(self, message):
        job, self.job = self.job, None
        job.join(1.0)
        self._set_controls(True)
        kind = message[0]
        if kind == "done":
            self._show_progress(1, 1)
            messagebox.showinfo(TITLE, "Operation complete.", parent=self.root)
        else:
            self._show_progress(0, 1)
            if kind == "error":
                messagebox.showerror(TITLE, message[1], parent=self.root)

    # --- closing --------------------------------------------------------------

    def _on_close(self):
        if self._running():
            if not messagebox.askyesno(
                    TITLE, "An operation is in progress.\n\nStop it and close the window?",
                    parent=self.root):
                return
            self.job.request_stop()
            self.job.join(2.0)
        self.root.destroy()
