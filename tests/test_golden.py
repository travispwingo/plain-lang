"""Every .plain file in examples/ and tests/golden/ runs and matches its .out transcript."""

import unittest
from pathlib import Path

from .support import ROOT, UPDATE, run_golden, sidecar

FOLDERS = [ROOT / "examples", ROOT / "tests" / "golden"]


def golden_files():
    for folder in FOLDERS:
        yield from sorted(folder.rglob("*.plain"))


class GoldenTests(unittest.TestCase):
    def test_golden_programs(self):
        for path in golden_files():
            with self.subTest(program=str(path.relative_to(ROOT))):
                out = run_golden(path)
                expected_file = sidecar(path, ".out")
                if UPDATE or not expected_file.exists():
                    expected_file.write_text(out, encoding="utf-8")
                    continue
                self.assertEqual(expected_file.read_text(encoding="utf-8"), out)


if __name__ == "__main__":
    unittest.main()
