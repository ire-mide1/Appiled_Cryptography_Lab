import errno
import os
import queue
import random
import tempfile
import threading
import unittest
from unittest import mock

import cipher
import jobs


def drain(job):
    messages = []
    while True:
        try:
            messages.append(job.messages.get_nowait())
        except queue.Empty:
            return messages


class JobTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = self._tmp.name

    def path(self, name):
        return os.path.join(self.dir, name)

    def write(self, name, data):
        with open(self.path(name), "wb") as fh:
            fh.write(data)
        return self.path(name)

    def read(self, name):
        with open(self.path(name), "rb") as fh:
            return fh.read()

    def run_job(self, inp, out, decrypt=False, **kw):
        job = jobs.Job(inp, out, decrypt, **kw)
        job.run()
        return job, drain(job)

    def leftover_temps(self):
        return [n for n in os.listdir(self.dir) if n.endswith(".tmp")]


class DefaultOutputName(unittest.TestCase):
    def test_encrypt_appends_enc(self):
        self.assertEqual(jobs.default_output_name("notes.txt", False), "notes.txt.enc")

    def test_decrypt_strips_enc(self):
        self.assertEqual(jobs.default_output_name("notes.txt.enc", True), "notes.txt.dec")
        self.assertEqual(jobs.default_output_name("NOTES.ENC", True), "NOTES.dec")

    def test_decrypt_without_enc_appends_dec(self):
        self.assertEqual(jobs.default_output_name("notes.txt", True), "notes.txt.dec")
        self.assertEqual(jobs.default_output_name("a.enc.txt", True), "a.enc.txt.dec")

    def test_name_that_is_only_enc_is_not_stripped(self):
        self.assertEqual(jobs.default_output_name(os.path.join("d", ".enc"), True),
                         os.path.join("d", ".enc") + ".dec")


class CleanPath(unittest.TestCase):
    def test_strips_quotes_and_whitespace(self):
        self.assertEqual(jobs.clean_path('  "C:\\a b\\c.txt"  '), "C:\\a b\\c.txt")
        self.assertEqual(jobs.clean_path("'x.txt'"), "x.txt")
        self.assertEqual(jobs.clean_path("  plain.txt "), "plain.txt")


class Validate(JobTestCase):
    def test_empty_fields(self):
        inp = self.write("in.bin", b"x")
        self.assertIn("input file", jobs.validate("", self.path("out")))
        self.assertIn("input file", jobs.validate("   ", self.path("out")))
        self.assertIn("output file", jobs.validate(inp, ""))

    def test_input_missing_or_directory(self):
        self.assertIn("does not exist", jobs.validate(self.path("nope"), self.path("o")))
        self.assertIn("not a file", jobs.validate(self.dir, self.path("o")))

    def test_output_is_folder(self):
        inp = self.write("in.bin", b"x")
        self.assertIn("folder", jobs.validate(inp, self.dir))

    def test_output_folder_missing(self):
        inp = self.write("in.bin", b"x")
        self.assertIn("does not exist", jobs.validate(inp, os.path.join(self.dir, "nodir", "o")))

    def test_valid_request_and_no_probe_left_behind(self):
        inp = self.write("in.bin", b"x")
        self.assertIsNone(jobs.validate(inp, self.path("out.enc")))
        self.assertEqual(self.leftover_temps(), [])

    def test_quoted_paths_accepted(self):
        inp = self.write("in.bin", b"x")
        self.assertIsNone(jobs.validate(f'"{inp}"', f'"{self.path("out.enc")}"'))

    def test_same_path_spellings(self):
        inp = self.write("in.bin", b"x")
        msg = "same file"
        self.assertIn(msg, jobs.validate(inp, inp))
        rel = os.path.relpath(inp)
        if os.path.splitdrive(rel)[0] == os.path.splitdrive(inp)[0]:
            self.assertIn(msg, jobs.validate(inp, rel))
        self.assertIn(msg, jobs.validate(inp, os.path.join(self.dir, ".", "in.bin")))
        self.assertIn(msg, jobs.validate(inp, os.path.join(self.dir, "x", "..", "in.bin")))
        if os.name == "nt":
            self.assertIn(msg, jobs.validate(inp, inp.upper()))

    def test_same_file_through_symlink(self):
        inp = self.write("in.bin", b"x")
        link = self.path("link.bin")
        try:
            os.symlink(inp, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks cannot be created here")
        self.assertIn("same file", jobs.validate(inp, link))

    def test_same_file_for_nonexistent_output_is_false(self):
        inp = self.write("in.bin", b"x")
        self.assertFalse(jobs.same_file(inp, self.path("other.bin")))


class RunSuccess(JobTestCase):
    def test_encrypt_then_decrypt_files(self):
        data = random.Random(5).randbytes(200_000)
        inp = self.write("in.bin", data)
        enc = self.path("in.bin.enc")
        _, msgs = self.run_job(inp, enc)
        self.assertEqual(msgs[-1], ("done",))
        self.assertEqual(len(self.read("in.bin.enc")), len(data))
        self.assertNotEqual(self.read("in.bin.enc"), data)
        self.assertEqual(self.leftover_temps(), [])
        _, msgs = self.run_job(enc, self.path("back.bin"), decrypt=True)
        self.assertEqual(msgs[-1], ("done",))
        self.assertEqual(self.read("back.bin"), data)

    def test_known_vector_through_files(self):
        inp = self.write("c.txt", b"CRYPTO")
        self.run_job(inp, self.path("c.enc"))
        self.assertEqual(self.read("c.enc"), bytes.fromhex("76DD9BE40428"))

    def test_empty_file(self):
        inp = self.write("empty.bin", b"")
        _, msgs = self.run_job(inp, self.path("empty.enc"))
        self.assertEqual(self.read("empty.enc"), b"")
        self.assertEqual(msgs, [("progress", 0, 0), ("done",)])

    def test_progress_messages_increase_and_end_with_done(self):
        inp = self.write("in.bin", random.Random(1).randbytes(10_000))
        _, msgs = self.run_job(inp, self.path("o.enc"), chunk_size=1000)
        progress = [m for m in msgs if m[0] == "progress"]
        self.assertEqual(len(progress), 10)
        dones = [m[1] for m in progress]
        self.assertEqual(dones, sorted(dones))
        self.assertEqual(progress[-1], ("progress", 10_000, 10_000))
        self.assertEqual(msgs[-1], ("done",))

    def test_two_runs_in_one_session_are_identical(self):
        inp = self.write("in.bin", random.Random(2).randbytes(70_000))
        self.run_job(inp, self.path("a.enc"))
        self.run_job(inp, self.path("b.enc"))
        self.assertEqual(self.read("a.enc"), self.read("b.enc"))

    def test_overwrites_existing_output_on_success(self):
        inp = self.write("in.bin", b"hello")
        self.write("out.enc", b"old contents that are longer")
        self.run_job(inp, self.path("out.enc"))
        self.assertEqual(len(self.read("out.enc")), 5)

    def test_leftover_temp_from_a_crash_is_overwritten(self):
        inp = self.write("in.bin", b"hello")
        self.write(".out.enc.tmp", b"stale")
        _, msgs = self.run_job(inp, self.path("out.enc"))
        self.assertEqual(msgs[-1], ("done",))
        self.assertEqual(self.leftover_temps(), [])


class RunFailure(JobTestCase):
    def partial_then_raise(self, exc):
        real = cipher.process_stream

        def fake(src, dst, decrypt, total, **kw):
            dst.write(b"partial")
            raise exc
        return mock.patch.object(jobs.cipher, "process_stream", side_effect=fake), real

    def test_failure_leaves_no_output_and_no_temp(self):
        inp = self.write("in.bin", b"x" * 100)
        patcher, _ = self.partial_then_raise(OSError(errno.EIO, "boom"))
        with patcher:
            _, msgs = self.run_job(inp, self.path("out.enc"))
        self.assertEqual(msgs[-1][0], "error")
        self.assertFalse(os.path.exists(self.path("out.enc")))
        self.assertEqual(self.leftover_temps(), [])

    def test_failure_does_not_damage_existing_output(self):
        inp = self.write("in.bin", b"x" * 100)
        self.write("out.enc", b"precious")
        patcher, _ = self.partial_then_raise(OSError(errno.EIO, "boom"))
        with patcher:
            self.run_job(inp, self.path("out.enc"))
        self.assertEqual(self.read("out.enc"), b"precious")
        self.assertEqual(self.leftover_temps(), [])

    def test_disk_full_message(self):
        inp = self.write("in.bin", b"x" * 100)
        patcher, _ = self.partial_then_raise(OSError(errno.ENOSPC, "No space left"))
        with patcher:
            _, msgs = self.run_job(inp, self.path("out.enc"))
        self.assertEqual(msgs[-1][0], "error")
        self.assertIn("disk is full", msgs[-1][1])

    def test_unexpected_exception_is_reported(self):
        inp = self.write("in.bin", b"x" * 100)
        patcher, _ = self.partial_then_raise(RuntimeError("weird"))
        with patcher:
            _, msgs = self.run_job(inp, self.path("out.enc"))
        self.assertEqual(msgs[-1][0], "error")
        self.assertIn("weird", msgs[-1][1])
        self.assertEqual(self.leftover_temps(), [])

    def test_input_size_change_detected_by_stream(self):
        inp = self.write("in.bin", b"x" * 100)
        patcher, _ = self.partial_then_raise(cipher.InputChangedError("short"))
        with patcher:
            _, msgs = self.run_job(inp, self.path("out.enc"))
        self.assertEqual(msgs[-1][0], "error")
        self.assertIn("changed", msgs[-1][1])
        self.assertFalse(os.path.exists(self.path("out.enc")))

    def test_input_grows_after_processing_is_detected(self):
        inp = self.write("in.bin", b"x" * 100)
        real = cipher.process_stream

        def grow(src, dst, decrypt, total, **kw):
            result = real(src, dst, decrypt, total, **kw)
            with open(inp, "ab") as fh:
                fh.write(b"more")
            return result

        with mock.patch.object(jobs.cipher, "process_stream", side_effect=grow):
            _, msgs = self.run_job(inp, self.path("out.enc"))
        self.assertEqual(msgs[-1][0], "error")
        self.assertIn("changed", msgs[-1][1])
        self.assertFalse(os.path.exists(self.path("out.enc")))
        self.assertEqual(self.leftover_temps(), [])

    def test_failed_rename_keeps_existing_target(self):
        inp = self.write("in.bin", b"x" * 100)
        self.write("out.enc", b"precious")
        with mock.patch.object(jobs.os, "replace", side_effect=PermissionError(13, "locked")):
            _, msgs = self.run_job(inp, self.path("out.enc"))
        self.assertEqual(msgs[-1][0], "error")
        self.assertEqual(self.read("out.enc"), b"precious")
        self.assertEqual(self.leftover_temps(), [])

    def test_missing_input_at_run_time(self):
        _, msgs = self.run_job(self.path("gone.bin"), self.path("out.enc"))
        self.assertEqual(msgs[-1][0], "error")
        self.assertFalse(os.path.exists(self.path("out.enc")))
        self.assertEqual(self.leftover_temps(), [])


class StopAndThreading(JobTestCase):
    def test_stop_request_mid_run_cleans_up(self):
        inp = self.write("in.bin", random.Random(3).randbytes(10_000))
        job = jobs.Job(inp, self.path("out.enc"), False, chunk_size=1000)
        real = cipher.process_stream

        def stop_after_first(src, dst, decrypt, total, on_progress=None, **kw):
            def wrapped(done, tot):
                on_progress(done, tot)
                job.request_stop()
            return real(src, dst, decrypt, total, on_progress=wrapped, **kw)

        with mock.patch.object(jobs.cipher, "process_stream", side_effect=stop_after_first):
            job.run()
        msgs = drain(job)
        self.assertEqual(msgs[-1], ("stopped",))
        self.assertEqual([m for m in msgs if m[0] == "progress"], [("progress", 1000, 10_000)])
        self.assertFalse(os.path.exists(self.path("out.enc")))
        self.assertEqual(self.leftover_temps(), [])

    def test_stop_before_start_leaves_nothing(self):
        inp = self.write("in.bin", b"x" * 100)
        job = jobs.Job(inp, self.path("out.enc"), False)
        job.request_stop()
        job.run()
        self.assertEqual(drain(job), [("stopped",)])
        self.assertFalse(os.path.exists(self.path("out.enc")))

    def test_second_start_while_running_is_ignored(self):
        inp = self.write("in.bin", b"x" * 100)
        job = jobs.Job(inp, self.path("out.enc"), False)
        gate = threading.Event()
        real = cipher.process_stream

        def blocking(*a, **kw):
            gate.wait(5)
            return real(*a, **kw)

        with mock.patch.object(jobs.cipher, "process_stream", side_effect=blocking):
            self.assertTrue(job.start())
            self.assertTrue(job.is_running())
            self.assertFalse(job.start())
            gate.set()
            job.join(5)
        self.assertFalse(job.is_running())
        self.assertEqual(drain(job)[-1], ("done",))
        self.assertEqual(self.read("out.enc") != b"", True)

    def test_threaded_run_produces_same_result(self):
        data = random.Random(8).randbytes(150_000)
        inp = self.write("in.bin", data)
        job = jobs.Job(inp, self.path("out.enc"), False)
        job.start()
        job.join(30)
        msgs = drain(job)
        self.assertEqual(msgs[-1], ("done",))
        expected = cipher.transform(data, cipher.Keystream())
        self.assertEqual(self.read("out.enc"), expected)


if __name__ == "__main__":
    unittest.main()
