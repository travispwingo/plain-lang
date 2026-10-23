"""Every tests/problems/*.plain file gives exactly the message in its .err file, carets included."""

import unittest

from .support import ROOT, UPDATE, run_golden, sidecar

FOLDER = ROOT / "tests" / "problems"


class ProblemMessages(unittest.TestCase):
    def test_messages(self):
        for path in sorted(FOLDER.glob("*.plain")):
            with self.subTest(program=path.name):
                out = run_golden(path)
                expected = sidecar(path, ".err")
                if UPDATE or not expected.exists():
                    expected.write_text(out, encoding="utf-8")
                    continue
                self.assertEqual(expected.read_text(encoding="utf-8"), out)


if __name__ == "__main__":
    unittest.main()
