"""The REPL, with scripted typing."""

import tempfile
import unittest
from pathlib import Path

from .support import ROOT
from plainlang.hosts import TestHost
from plainlang.repl import Session


def session(lines, answers=()):
    typed = list(lines)
    shown = []

    def ask(prompt):
        if not typed:
            raise EOFError
        return typed.pop(0)

    host = TestHost(tempfile.mkdtemp(), answers=answers)
    s = Session({"seed": None}, ask=ask, show=shown.append, host=host)
    s.loop()
    return shown, host, s


class Repl(unittest.TestCase):
    def test_names_last_between_lines(self):
        shown, host, _ = session(["set price to 42.50", "price times 2", "show price"])
        self.assertIn("85.00", shown)
        self.assertEqual(["42.50"], host.transcript)

    def test_steps_under_a_line(self):
        shown, host, _ = session(["repeat 2 times", '    show "hi"', ""])
        self.assertEqual(["hi", "hi"], host.transcript)
        self.assertIn("(Type the steps that go under it. Press Enter on an empty line when you're done.)", shown)

    def test_problem_with_an_idea(self):
        shown, host, _ = session(["show Hello there", "1"])
        self.assertTrue(any("Put the text in double quotes." in s for s in shown))
        self.assertEqual(["Hello there"], host.transcript)

    def test_your_own_steps_last(self):
        shown, host, _ = session(["how to greet (person)", '    show "Hi, {person}!"', "", 'greet "Ann"'])
        self.assertEqual(["Hi, Ann!"], host.transcript)

    def test_save(self):
        folder = Path(tempfile.mkdtemp())
        target = folder / "mine.plain"
        shown, host, _ = session(["set x to 3", "show x", f":save {target}"])
        self.assertEqual("set x to 3\nshow x\n", target.read_text())


if __name__ == "__main__":
    unittest.main()
