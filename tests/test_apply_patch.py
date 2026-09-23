"""Tests for patch/apply_patch.py.

Two kinds of test:

* Fake-EXE tests always run. They build a 494,910-byte file of zeros with the
  expected bytes at the patch site, and override the md5 constants so the
  patcher accepts it. No game code is needed.
* Real-EXE tests run only when COL1_PRISTINE_EXE points at an unmodified
  VICEROY.EXE (md5 0f5d5b0063721fbc6aca314e5a43ddaf). They check the real
  md5 values end to end.

Run:  python3 -m unittest discover -s tests -v
"""
import hashlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "patch"))
import apply_patch as ap  # noqa: E402


def fake_exe(site: bytes) -> bytes:
    data = bytearray(ap.EXPECTED_SIZE)
    data[ap.OFFSET:ap.OFFSET + 2] = site
    return bytes(data)


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.exe = self.tmp / "VICEROY.EXE"

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["apply_patch.py", *map(str, argv)]), \
                redirect_stdout(out), redirect_stderr(err):
            rc = ap.main()
        return rc, out.getvalue(), err.getvalue()


class FakeExeTests(Base):
    def setUp(self):
        super().setUp()
        self.orig = fake_exe(ap.ORIGINAL_BYTES)
        self.patched = fake_exe(ap.PATCHED_BYTES)
        for name, val in (("MD5_ORIGINAL", md5(self.orig)),
                          ("MD5_PATCHED", md5(self.patched))):
            p = mock.patch.object(ap, name, val)
            p.start()
            self.addCleanup(p.stop)

    def test_apply_writes_only_the_two_bytes(self):
        self.exe.write_bytes(self.orig)
        rc, _, _ = self.run_main(self.exe)
        self.assertEqual(rc, 0)
        self.assertEqual(self.exe.read_bytes(), self.patched)

    def test_apply_makes_backup_of_input(self):
        self.exe.write_bytes(self.orig)
        self.run_main(self.exe)
        self.assertEqual((self.tmp / "VICEROY.EXE.bak").read_bytes(), self.orig)

    def test_apply_twice_is_noop(self):
        self.exe.write_bytes(self.patched)
        rc, out, _ = self.run_main(self.exe)
        self.assertEqual(rc, 0)
        self.assertIn("already patched", out)
        self.assertEqual(self.exe.read_bytes(), self.patched)

    def test_revert_restores_original(self):
        self.exe.write_bytes(self.patched)
        rc, _, _ = self.run_main(self.exe, "--revert")
        self.assertEqual(rc, 0)
        self.assertEqual(self.exe.read_bytes(), self.orig)

    def test_check_changes_nothing(self):
        self.exe.write_bytes(self.orig)
        rc, out, _ = self.run_main(self.exe, "--check")
        self.assertEqual(rc, 0)
        self.assertIn("status  : original", out)
        self.assertEqual(self.exe.read_bytes(), self.orig)
        self.assertFalse((self.tmp / "VICEROY.EXE.bak").exists())

    def test_unknown_md5_refused(self):
        other = bytearray(self.orig)
        other[0] = 0x4D  # some unrelated byte
        self.exe.write_bytes(bytes(other))
        rc, _, err = self.run_main(self.exe)
        self.assertEqual(rc, 2)
        self.assertIn("unrecognised", err)
        self.assertEqual(self.exe.read_bytes(), bytes(other))

    def test_force_still_checks_site_bytes(self):
        other = bytearray(self.orig)
        other[0] = 0x4D
        other[ap.OFFSET] = 0x11  # wrong byte at the patch site
        self.exe.write_bytes(bytes(other))
        rc, _, err = self.run_main(self.exe, "--force")
        self.assertEqual(rc, 2)
        self.assertIn("Refusing to write", err)
        self.assertEqual(self.exe.read_bytes(), bytes(other))

    def test_missing_file(self):
        rc, _, err = self.run_main(self.tmp / "nope.exe")
        self.assertEqual(rc, 1)
        self.assertIn("no such file", err)


PRISTINE = os.environ.get("COL1_PRISTINE_EXE")


@unittest.skipUnless(PRISTINE and Path(PRISTINE).is_file(),
                     "set COL1_PRISTINE_EXE to an unmodified VICEROY.EXE")
class RealExeTests(Base):
    def test_real_md5_round_trip(self):
        shutil.copy(PRISTINE, self.exe)
        self.assertEqual(md5(self.exe.read_bytes()), ap.MD5_ORIGINAL)
        self.assertEqual(self.run_main(self.exe)[0], 0)
        self.assertEqual(md5(self.exe.read_bytes()), ap.MD5_PATCHED)
        self.assertEqual(self.run_main(self.exe, "--revert")[0], 0)
        self.assertEqual(md5(self.exe.read_bytes()), ap.MD5_ORIGINAL)


if __name__ == "__main__":
    unittest.main()
