"""CR-0015 U7: the interim --an-background guard (deleted with the guard
by CR-0015 deliverable 8).

    python -m unittest tests.test_cr0015_guard -v
"""
import os
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import train  # noqa: E402


class InterimGuard(unittest.TestCase):
    def run_main(self, *argv):
        with mock.patch.object(sys, "argv", ["train.py", *argv]), \
                mock.patch.object(train, "GrouseData",
                                  side_effect=AssertionError("reached data"),
                                  create=True):
            train.main()

    def test_an_background_blocked_before_data(self):
        with self.assertRaises(SystemExit) as cm:
            self.run_main("--an-background", "1")
        self.assertIn("CR-0015", str(cm.exception.code))

    def test_later_override_passes_guard(self):
        # argparse keeps the last value; the guard must let it through, and
        # the run then proceeds past the guard (here, to the patched data
        # load, which stops the test).
        with self.assertRaises(AssertionError) as cm:
            self.run_main("--an-background", "1", "--an-background", "0")
        self.assertIn("reached data", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
