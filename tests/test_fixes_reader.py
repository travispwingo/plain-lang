"""Regression tests for the reader fixes: names, ties, elision, one-line forms, blocks and messages."""

import time
import unittest

from .support import run_source
from plainlang import nodes as N
from plainlang.parser import Reader
from plainlang.tidy import line_readings


def problems(source):
    return Reader().read(source).problems


def fixes(source):
    return [p.fix for p in problems(source)]


def output(source, answers=()):
    out, _, _ = run_source(source, answers=answers)
    return out


def reading(source, line):
    program = Reader().read(source)
    return [p.fix for p in program.problems], line_readings(program.statements).get(line)


class NameTies(unittest.TestCase):
    def test_a_name_that_is_also_a_check_word_is_a_rename_problem(self):   # reader-1, reader-8
        for word in ("text", "empty", "even", "odd"):
            with self.subTest(word=word):
                found = problems(f'set {word} to "z"\nset x to ""\nif x is {word}\n    show 1')
                self.assertEqual([f'Rename "{word}" so this line has only one meaning.'], [p.fix for p in found])
                self.assertEqual([f"if x is the same as {word}"], found[0].try_lines)
                self.assertEqual(found[0].try_lines, [i.strip() for i in found[0].ideas])

    def test_name_and_phrase_words_show_both_readings(self):   # reader-27
        p = problems("set hours to 3\nset time to 5\nset under time to 2\nif hours is under time\n    show 1")[0]
        self.assertEqual('Rename "under time" so this line has only one meaning.', p.fix)
        self.assertEqual(["if hours is less than time", "if hours is the same as under time"], p.try_lines)
        p = problems("set number to 3\nset x to 1\nif x is a number\n    show 1")[0]
        self.assertEqual('Rename "number" so this line has only one meaning.', p.fix)
        self.assertNotIn("if x is a number", p.try_lines)

    def test_the_same_as_wording_reads_as_your_name(self):
        self.assertEqual("1\n", output('set empty to "z"\nset x to "z"\nif x is the same as empty\n    show 1'))


class NamesYouSet(unittest.TestCase):
    def test_call_it_with_a_special_word(self):   # reader-2, reader-21
        found = fixes('ask "First number?" and call it one\nask "Second?" and call it two\n'
                      'show "The total is {one plus two}"')
        self.assertEqual(['Rename "one", for example to "first number".',
                          'Rename "two", for example to "second number".'], found)
        found = fixes('ask "Tip?" and call it tip percent\nshow tip percent')
        self.assertEqual(['Rename "tip percent", for example to "tip rate".'], found)
        found = fixes('ask "Your age?" and call it age in years\nshow age in years')
        self.assertEqual(1, len(found))
        self.assertTrue(found[0].startswith('Rename "age in years"'))

    def test_names_that_start_with_first_last_or_item(self):   # reader-6, reader-24
        self.assertEqual("Ann Lee\n", output('set first name to "Ann"\nset last name to "Lee"\n'
                                             'show "{first name} {last name}"'))
        self.assertEqual("3\n5\n", output("set item count to 3\nshow item count\nset last to 5\nshow last"))
        self.assertEqual("teal\n", output('set colors to a list of "red" and "blue"\n'
                                          'set item 2 of colors to "teal"\nshow item 2 of colors'))

    def test_a_field_set_with_of(self):
        self.assertEqual("age: 30\n", output("set p to a new record\nset the age of p to 30\nshow p"))

    def test_time_now_and_date_today_are_values_plain_has(self):   # reader-11, reader-43
        self.assertEqual(['Choose another name than "time now".'], fixes("set time now to 5\nshow time now"))
        self.assertEqual(['Choose another name than "date today".'], fixes("set date today to 5"))

    def test_bracket_names_in_a_how_to(self):   # reader-17
        found = fixes("combine 10 with 20 and call it total\nshow total\n"
                      "how to combine (one) with (two)\n    give back one plus two")
        self.assertEqual(['Rename "one", for example to "first number".',
                          'Rename "two", for example to "second number".'], found)

    def test_new_field_keeps_your_capitals(self):   # reader-18 (the reader's part)
        program = Reader().read("set body to a new record\nset body's userId to 1")
        target = program.statements[1].target
        self.assertEqual(("userid",), target.words)
        self.assertEqual(("userId",), target.raw)


class Elision(unittest.TestCase):
    def test_after_not_does_not_and_between(self):   # reader-4
        start = 'set x to 4\nset name to "abc"\n'
        for check, fixed in [
                ("x is not more than 3 or 5", "if x is at most 3 and x is at most 5"),
                ('name does not contain "z" or starts with "q"', 'if name does not contain "z" or name starts with "q"'),
                ("x is between 1 and 5 or more than 10", "if x is between 1 and 5 or x is more than 10"),
                ("x is not 3 or more than 10", "if x is not 3 or x is more than 10")]:
            with self.subTest(check=check):
                found = problems(start + f"if {check}\n    show 1")
                self.assertEqual(['Write the whole check again after "or", so it has only one meaning.'],
                                 [p.fix for p in found])
                self.assertEqual([fixed], found[0].try_lines)

    def test_positive_elision_still_works(self):
        self.assertEqual("yes\n", output('set x to 200\nif x is less than 1 or more than 100\n    show "yes"'))

    def test_negative_number_after_or(self):   # reader-10
        self.assertEqual(([], "if x is 5 or x is -6"), reading("set x to 5\nif x is 5 or -6\n    show 1", 2))
        self.assertEqual("1\n", output("set x to -6\nif x is 5 or -6\n    show 1"))


class Numbers(unittest.TestCase):
    def test_percent_written_as_a_word(self):   # reader-7, reader-30
        self.assertEqual("0.15\n30\n", output("set rate to 15 percent\nshow rate\nshow 15 percent of 200"))
        self.assertTrue(fixes("set tip to 200 plus 15 percent")[0].startswith("Write what the 15% is a part of"))

    def test_minus_sign_holds_tighter_than_rounded(self):   # reader-19, reader-25
        self.assertEqual("-3\n-3\n-3\n-2.5\n", output("show -2.5 rounded\nshow (-2.5 rounded)\n"
                                                      "show -2.5 rounded down\nshow -2.5 as text"))

    def test_text_joined_with_plus(self):   # reader-31
        p = problems('set score to 1\nshow "Score: " + score')[0]
        self.assertEqual("Put the value inside the text with { }.", p.fix)
        self.assertEqual(['show "Score: {score}"'], p.try_lines)
        self.assertEqual(['show "Score: {score}"'], p.ideas)


class Ties(unittest.TestCase):
    def test_tie_between_two_of_plains_phrases(self):   # reader-26
        p = problems('show a list of "x", "y" and "z" joined with "-"')[0]
        self.assertEqual("Add brackets, or reword this, so it has only one meaning.", p.fix)
        self.assertIn('show (a list of "x", "y" and "z") joined with "-"', p.try_lines)
        for line in p.try_lines:
            self.assertEqual([], fixes(line))
        self.assertEqual("x-y-z\n", output('show (a list of "x", "y" and "z") joined with "-"'))

    def test_tie_inside_braces_shows_both_readings(self):   # reader-44
        p = problems('set n to 2\nshow "{a random number from 1 to n plus 1}"')[0]
        self.assertEqual(['show "{(a random number from 1 to n) plus 1}"',
                          'show "{a random number from 1 to (n plus 1)}"'], p.try_lines)


class OneLineForms(unittest.TestCase):
    def test_otherwise_forms(self):   # reader-13, reader-34
        self.assertEqual("b\n", output('set score to 10\nif score is 11 then show "a"\n'
                                       'otherwise if score is 10 then show "b"'))
        self.assertEqual("b\n", output('set score to 10\nif score is 11 then show "a"\notherwise show "b"'))

    def test_comma_or_colon_where_then_belongs(self):   # reader-13
        for mark in (",", ":"):
            with self.subTest(mark=mark):
                found = problems(f'set score to 10\nif score is 10{mark} show "a"\nshow "after"')
                self.assertEqual([f'Write "then" in place of the "{mark}".'], [p.fix for p in found])
                self.assertEqual(['if score is 10 then show "a"'], found[0].try_lines)

    def test_otherwise_on_the_if_line(self):
        p = problems('set score to 10\nif score is 10 then show "a" otherwise show "b"')[0]
        self.assertEqual('Put "otherwise" and its step on the next line.', p.fix)
        self.assertEqual(['if score is 10 then show "a"', 'otherwise show "b"'], p.try_lines)

    def test_one_line_if_with_steps_under_it(self):
        p = problems('set score to 10\nif score is 10 then show "a"\n    show "b"')[0]
        self.assertEqual('Put the step after "then" on its own line, above the other steps.', p.fix)

    def test_then_instead_of_than_is_still_found(self):
        self.assertEqual(['Write "than" instead of "then".'], fixes("set x to 1\nif x is bigger then 3\n    show 1"))

    def test_otherwise_with_a_check(self):   # reader-23
        p = problems('set x to 5\nif x is 5\n    show "five"\notherwise x is 6\n    show "six"')[0]
        self.assertEqual('Write "otherwise if" to check something else.', p.fix)
        self.assertEqual(["otherwise if x is 6"], p.try_lines)
        self.assertIsNotNone(p.why)

    def test_steps_with_steps_of_their_own_after_then(self):   # reader-37
        found = fixes('set x to 1\nif x is 1 then repeat 3 times\nif x is 1 then try\nshow "after"')
        self.assertEqual(['Put this step on its own line under the "if".'] * 2, found)


class Blocks(unittest.TestCase):
    def test_colon_at_the_end_of_a_step(self):   # reader-5
        self.assertEqual("Here\n1 and 2\n", output('set xs to a list of 1 and 2\nshow "Here":\nshow xs'))
        found = problems('set xs to a list of 1 and 2\nshow "Here":\n    show xs\nshow "end"')
        self.assertEqual(["Move this line so it lines up with the steps above it."], [p.fix for p in found])
        self.assertEqual(3, found[0].line)

    def test_steps_under_a_step_are_still_checked(self):   # reader-5
        found = problems("set x to 1\nadd 1 to x:\n    this is nonsense blah")
        self.assertEqual([3, 3], [p.line for p in found])
        self.assertEqual("Move this line so it lines up with the steps above it.", found[0].fix)
        self.assertIn('"this"', found[1].why)

    def test_steps_under_a_line_with_a_problem_are_not_told_to_move(self):   # reader-22
        found = problems('set age to 20\nrepeet 3 times\n    show "yes"')
        self.assertEqual([2], [p.line for p in found])
        found = problems('function greet(name)\n    show "hi"')
        self.assertEqual([1], [p.line for p in found])

    def test_how_to_inside_other_steps(self):   # reader-9, reader-32
        found = problems('set x to 1\nif x is 1\n    how to greet (person)\n        this line is nonsense blah\n'
                         '    show "a"')
        self.assertEqual(['Move this "how to" to the left edge, outside other steps.'], [found[0].fix])
        self.assertEqual([3, 4], [p.line for p in found])

    def test_otherwise_after_an_if_with_a_problem(self):   # reader-29
        found = problems('set x to 1\nif x is bigger then 3\n    show "a"\notherwise\n    show "b"')
        self.assertEqual(['Write "than" instead of "then".'], [p.fix for p in found])
        found = problems('set x to 1\nif x is "abc\n    show 1\notherwise if x is 2\n    show 2\notherwise\n    show 3')
        self.assertEqual([2], [p.line for p in found])

    def test_otherwise_still_needs_an_if(self):
        found = fixes('set x to 1\nshow x\notherwise\n    show 2')
        self.assertEqual(['Put this "otherwise" right after an "if" and its steps.'], found)


class Recovery(unittest.TestCase):
    def test_names_from_lines_with_a_problem_are_kept(self):   # reader-15, reader-20
        found = problems('set greeting to "Hello\nshow greeting\nshow "{greeting}!"\nset count to 1,000\nadd 1 to count')
        self.assertEqual([1, 4], [p.line for p in found])

    def test_for_each_name_from_a_broken_header(self):   # reader-20, reader-29
        found = problems("set items to a list of 1\nrepeat for each thing on my list\n    show thing\n"
                         "for each other of items\n    show other")
        self.assertEqual([2, 4], [p.line for p in found])

    def test_name_with_a_special_word_is_kept(self):   # reader-20
        found = problems("set number of tries to 0\nadd 1 to number of tries")
        self.assertEqual(['Rename "number of tries", for example to "tries count".'], [p.fix for p in found])

    def test_each_unknown_name_once(self):   # reader-15, reader-20, reader-29
        found = problems("add 1 to tally\nadd 2 to tally\nshow tally plus 1")
        self.assertEqual(1, len(found))      # only the first line that uses it without a start
        self.assertEqual('Set "tally" to a starting value before this line, like: set tally to 0', found[0].fix)
        found = problems('set total to 1\nshow totl\nadd 1 to totl\nshow "{totl}"')
        self.assertEqual(['Write "total" instead of "totl".'], [p.fix for p in found])
        self.assertIn("lines 3 and 4", found[0].why)


class HowToClashes(unittest.TestCase):
    def test_how_to_that_a_line_could_read_as_a_built_in(self):   # reader-16, reader-28
        for header in ("remove a done task from (tasks)", "load (cart)", "show price"):
            with self.subTest(header=header):
                found = fixes(f"how to {header}\n    show 1")
                self.assertEqual(['Use different words for this "how to".'], found)

    def test_how_tos_that_dont_clash(self):
        for header in ("cross off a task in (tasks)", "work out the tip on (bill) at (rate)", "greet (person)",
                       "clear out (things)"):
            with self.subTest(header=header):
                self.assertEqual([], fixes(f"how to {header}\n    show 1"))

    def test_how_to_starting_with_a_bracket(self):   # reader-40, reader-45
        p = problems("how to (a) plus (b)\n    give back a")[0]
        self.assertNotIn("already starts", p.why)
        self.assertIn("word before the first bracket", p.why)


class Words(unittest.TestCase):
    def test_possessives_after_a_number_or_a_plural(self):   # reader-12
        self.assertEqual("5\n3\n", output("set player 1 to a new record\nset player 1's score to 5\n"
                                          "show player 1's score\nset players to a new record\n"
                                          "set players's score to 3\nshow players' score"))

    def test_commas_after_your_own_name(self):   # reader-14
        self.assertEqual("3, 2 and 1\n", output("set choices to a list of 3, 1 and 2\n"
                                                 "sort choices, largest first\nshow choices"))

    def test_leading_first(self):   # reader-33
        self.assertEqual("first\n", output('First show "first"'))

    def test_article_before_a_quoted_field(self):   # reader-36
        self.assertEqual("3\n", output('set project to a new record\nset project\'s "Price (USD)" to 3\n'
                                       'show the "Price (USD)" of project'))


class Limits(unittest.TestCase):
    def test_many_brackets(self):   # reader-35, reader-46
        line = "show " + "(" * 60 + "1" + ")" * 60
        self.assertEqual(["Split this line into shorter steps."], fixes(line))
        self.assertEqual(["Split this line into shorter steps."], fixes('show "{' + "(" * 60 + "1" + ")" * 60 + '}"'))

    def test_many_signs(self):   # reader-35
        start = time.perf_counter()
        self.assertEqual(["Split this line into shorter steps."], fixes("show " + "+".join(["1"] * 160)))
        self.assertLess(time.perf_counter() - start, 1)


class Messages(unittest.TestCase):
    def test_wording(self):   # reader-38, reader-39
        self.assertIn('An "if" line', problems("set x to 1\nif x is 1")[0].why)
        p = problems('how to greet (person)\nshow "hi"')[0]
        self.assertIn('belongs to the "how to" on line 1', p.fix)
        self.assertIn('An "if that fails" line', problems("try\n    show 1\nif that fails")[0].why)

    def test_explain_wording(self):   # reader-38
        self.assertEqual(([], "show (the number of guests) plus 1"),
                         reading("set guests to a list of 1\nshow the number of guests plus 1", 2))
        self.assertEqual(([], "show 7.25 rounded to 1 place"), reading("show 7.25 rounded to 1 place", 1))
        self.assertEqual(([], "wait 1 second"), reading("wait 1 second", 1))

    def test_placement_problems_mark_the_line(self):   # reader-41
        found = problems('how to greet (person)\n    show "Hi {person}"\ngreet "Ann" and call it result\n'
                         "give back 5\nstop repeating\nreturn 3")
        self.assertEqual([3, 4, 5, 6], [p.line for p in found])
        self.assertTrue(all(p.col is not None for p in found))
        self.assertEqual(12, found[0].col)
        self.assertIn('"return" is written "give back"', found[3].why)

    def test_else_is_recorded_for_tidy(self):   # reader-42
        program = Reader().read('set x to 1\nif x is 1\n    show "a"\nelse\n    show "b"')
        stmt = program.statements[1]
        self.assertIsInstance(stmt, N.If)
        self.assertEqual({4: [(0, 4, "otherwise")]}, stmt.branch_edits)


if __name__ == "__main__":
    unittest.main()
