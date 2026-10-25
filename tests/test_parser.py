"""How Plain reads lines: precedence, ties, elision, limits, and a fuzz test."""

import random
import unittest

from .support import ROOT
from plainlang.parser import Reader
from plainlang.tidy import line_readings


def reading(source, line=None):
    program = Reader().read(source)
    lines = line_readings(program.statements)
    number = line or max(lines) if lines else None
    return program, lines.get(number) if number else None


class Precedence(unittest.TestCase):
    def check(self, source, expected):
        program, got = reading(source)
        self.assertEqual([], [p.fix for p in program.problems])
        self.assertEqual(expected, got)

    def test_school_order(self):
        self.check("set a to 1\nset b to 2\nset c to 3\nset x to a plus b times c",
                   "set x to a plus b times c")
        self.check("set a to 1\nset b to 2\nset c to 3\nset x to (a plus b) times c",
                   "set x to (a plus b) times c")

    def test_rounded_applies_to_everything_on_its_left(self):
        self.check("set a to 1\nset b to 2\nset x to a times b rounded to 2 places plus 1",
                   "set x to ((a times b) rounded to 2 decimal places) plus 1")

    def test_of_slot_takes_one_value(self):
        self.check("set guests to an empty list\nset x to the number of guests plus 1",
                   "set x to (the number of guests) plus 1")

    def test_where_belongs_to_the_list_before_it(self):
        self.check('set sales to an empty list\nshow the number of sales where amount is more than 100',
                   "show the number of sales where its amount is more than 100")


class Ties(unittest.TestCase):
    def problem(self, source):
        program = Reader().read(source)
        self.assertTrue(program.problems, "expected a problem")
        return program.problems[0]

    def test_open_last_slot_needs_brackets(self):
        p = self.problem("set roll to a random number from 1 to 6 plus a random number from 1 to 6")
        self.assertIn("brackets", p.fix)
        self.assertEqual(2, len(p.try_lines))

    def test_mixing_and_or(self):
        p = self.problem("set a to yes\nset b to no\nset c to yes\nif a and b or c\n    show 1")
        self.assertEqual({"if a and (b or c)", "if (a and b) or c"}, set(p.try_lines))

    def test_names_are_never_split(self):
        p = self.problem("set count to 0\nset file count to 0\nadd 1 to file count")
        self.assertIn('Rename "file count"', p.fix)

    def test_howto_and_builtin(self):
        p = self.problem('set board to a list of 1\nshow board\nhow to show the board\n    show 2')
        self.assertIn('Use different words for this "how to".', p.fix)   # the line using it is a follow-on

    def test_same_shape_as_builtin(self):
        p = self.problem("how to add (amount) to (account)\n    show amount")
        self.assertIn('different words for this "how to"', p.fix)


class Limits(unittest.TestCase):
    def test_forty_words(self):
        line = "show " + " plus ".join(["1"] * 45)
        program = Reader().read(line)
        self.assertIn("shorter steps", program.problems[0].fix)


class Fuzz(unittest.TestCase):
    WORDS = ("show set to is not and or of the a plus times score sales where it its "
             '"hi" 3 ( ) , if repeat for each in list item number total "x" yes nothing '
             "rounded places from by add remove sort read save ask call").split()

    def test_random_lines_never_crash(self):
        rng = random.Random(1234)
        for _ in range(3000):
            n = rng.randint(1, 9)
            line = " ".join(rng.choice(self.WORDS) for _ in range(n))
            source = "set score to 1\nset sales to an empty list\n" + line + "\n"
            try:
                Reader().read(source)
            except Exception as error:  # noqa: BLE001
                self.fail(f"{line!r} crashed Plain: {error!r}")


if __name__ == "__main__":
    unittest.main()
