"""The phrasing corpus: how beginners write lines, and how Plain must read them.

Each line in phrasings.txt is either
    a line as someone wrote it  =>  how Plain reads it, in main words
or
    ! a line Plain must NOT read (it gives a problem instead)
Lines starting with "names:" set the names that exist for the cases after them.
"""

import unittest

from .support import ROOT
from plainlang.parser import Reader
from plainlang.tidy import line_readings

CORPUS = ROOT / "tests" / "phrasings.txt"


def cases():
    names = []
    for number, raw in enumerate(CORPUS.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("names:"):
            names = [n.strip() for n in line[len("names:"):].split(",") if n.strip()]
            continue
        if line.startswith("!"):
            yield number, names, line[1:].strip(), None
        else:
            written, _, reading = line.partition("=>")
            yield number, names, written.strip(), reading.strip()


def read_in_context(names, line):
    preamble = "".join(f"set {name} to nothing\n" for name in names)
    source = preamble + line + "\n"
    if line.split()[0].lower() in ("if", "repeat", "for", "while", "until", "otherwise", "else"):
        source += "    show 1\n"
    program = Reader().read(source)
    number = len(names) + 1
    return program, line_readings(program.statements).get(number)


class Phrasings(unittest.TestCase):
    def test_corpus(self):
        for number, names, written, reading in cases():
            with self.subTest(line=number, written=written):
                program, got = read_in_context(names, written)
                if reading is None:
                    self.assertTrue(program.problems, f"Plain read it as: {got}")
                else:
                    self.assertEqual([], [p.fix for p in program.problems])
                    self.assertEqual(reading, got)


if __name__ == "__main__":
    unittest.main()
