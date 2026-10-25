"""Regression tests for the phrase changes from the plain-language review: has (3), largest and
A to Z (7), the stopwatch (10), an empty record (11), capital and small letters (27), adding a list
to a file (30), and accepted older wordings shown in main words."""

import tempfile
import unittest
from pathlib import Path

from .support import run_source
from plainlang.hosts import TestHost
from plainlang.interpreter import Run
from plainlang.parser import Reader
from plainlang.problems import Problem
from plainlang.tidy import explain, line_readings, tidy


def output(source, answers=(), files=None):
    with tempfile.TemporaryDirectory() as tmp:
        data = []
        for name, text in (files or {}).items():
            (Path(tmp) / name).write_text(text, encoding="utf-8")
            data.append(Path(tmp) / name)
        out, _, _ = run_source(source, answers=answers, data=data)
        return out


def problem_while_running(source, files=None):
    """The problem a program has while running, after reading cleanly."""
    with tempfile.TemporaryDirectory() as tmp:
        for name, text in (files or {}).items():
            (Path(tmp) / name).write_text(text, encoding="utf-8")
        program = Reader().read(source)
        assert not program.problems, [p.fix for p in program.problems]
        try:
            Run(program, TestHost(Path(tmp))).run()
        except Problem as problem:
            return problem
    raise AssertionError("no problem")


def fixes(source):
    return [p.fix for p in Reader().read(source).problems]


def tidied(source):
    return tidy(source, Reader().read(source))


def reading(source, line):
    return line_readings(Reader().read(source).statements).get(line)


RECORD = 'set person to an empty record\nset person\'s name to "Ann"\n'
SALES = "date,customer,amount\n2026-10-01,Ann,120.50\n2026-10-02,Bo,80\n2026-10-03,Cy,300\n"


class Has(unittest.TestCase):   # change 3
    def test_has_checks_for_a_field(self):
        source = RECORD + ('if person has "name"\n    show 1\nif person has "age"\n    show 2\n'
                           'if person does not have "age"\n    show 3\nif person doesn\'t have "name"\n    show 4\n'
                           'set people to a list of person\nshow the number of people where it has "NAME"\n'
                           'if person has "name" and "age"\n    show 5\n')
        self.assertEqual("1\n3\n1\n", output(source))

    def test_have_after_a_plural_name_reads_as_has(self):
        self.assertEqual("if rows have \"x\"", reading('set rows to nothing\nif rows have "x"\n    show 1', 2))
        self.assertEqual("if rows do not have \"x\"",
                         reading('set rows to nothing\nif rows don\'t have "x"\n    show 1', 2))

    def test_has_and_have_are_special_words(self):
        self.assertEqual(['Rename "has ticket", for example to "got ticket".'], fixes("set has ticket to 1"))
        self.assertTrue(fixes("set have to 1"))

    def test_contains_still_looks_inside_text_and_lists(self):
        self.assertEqual("1\n2\n", output('set n to "Ann"\nif n contains "nn"\n    show 1\n'
                                          'set l to a list of "a" and "b"\nif "b" is in l\n    show 2\n'))

    def test_contains_on_a_record_offers_has(self):
        p = problem_while_running('set reply to an empty record\nset reply\'s results to 3\n'
                                  'if the reply contains "results"\n    show 1\n')
        self.assertEqual('Write "has" to check whether a record has a field.', p.fix)
        self.assertEqual(['if the reply has "results"'], p.try_lines)
        p = problem_while_running('set reply to an empty record\nif "results" is not in reply\n    show 1\n')
        self.assertEqual(['if reply does not have "results"'], p.try_lines)

    def test_a_value_of_the_record_offers_that_fields_check_first(self):
        p = problem_while_running(RECORD + 'if person does not contain "ann"\n    show 1\n')
        self.assertEqual([['if person\'s name is not "ann"'], ['if person does not have "ann"']], p.choices)
        self.assertIn('It\'s the value of its field "name".', p.why)
        for choice in p.choices:
            self.assertEqual([], fixes(RECORD + choice[0] + "\n    show 1\n"))

    def test_has_on_text_or_a_list_offers_contains(self):
        p = problem_while_running('set todos to a list of "milk"\nif todos have "milk"\n    show 1\n')
        self.assertEqual('Write "contain" to look inside a list.', p.fix)
        self.assertEqual(['if todos contain "milk"'], p.try_lines)
        p = problem_while_running('set n to "Ann"\nif n does not have "A"\n    show 1\n')
        self.assertEqual(['if n does not contain "A"'], p.try_lines)

    def test_has_on_a_table_offers_one_row(self):
        p = problem_while_running('read "sales.csv" and call it sales\nif sales has "amount"\n    show 1\n',
                                  {"sales.csv": SALES})
        self.assertEqual(['if the first item of sales has "amount"'], p.try_lines)

    def test_has_on_a_number(self):
        p = problem_while_running('set n to 3\nif n has "x"\n    show 1\n')
        self.assertEqual('Use "has" with a record, to check whether it has a field.', p.fix)

    def test_an_otherwise_if_check_names_its_own_line(self):
        p = problem_while_running('set r to an empty record\nif 1 is 2\n    show 1\notherwise if r contains "x"\n'
                                  '    show 2\n')
        self.assertEqual(4, p.line)
        self.assertEqual(['otherwise if r has "x"'], p.try_lines)


class LargestAndAToZ(unittest.TestCase):   # change 7
    def test_sorting_text_from_z_to_a(self):
        source = ('set names to a list of "bo", "Ann" and "cy"\nsort names from Z to A\nshow names\n'
                  'sort names from a to z\nshow names\nread "sales.csv" and call it sales\n'
                  'sort sales by customer, from Z to A\nshow sales\'s customer\n'
                  'sort sales by customer from A to Z\nshow sales\'s customer\n')
        self.assertEqual("cy, bo and Ann\nAnn, bo and cy\nCy, Bo and Ann\nAnn, Bo and Cy\n",
                         output(source, files={"sales.csv": SALES}))

    def test_numbers_keep_largest_and_smallest(self):
        self.assertEqual("9\n3\n9, 4 and 3\n", output('set s to a list of 3, 9 and 4\nshow the largest of s\n'
                                                     'show the smallest of s\nsort s largest first\nshow s\n'))

    def test_largest_of_text_offers_sorting(self):
        source = 'set words to the words of "zoo elephant ant"\nshow the largest of words\n'
        p = problem_while_running(source)
        self.assertEqual("Sort the text first, then take its last item.", p.fix)
        self.assertEqual([["sort words", "show the last item of words"],
                          ["sort words from Z to A", "show the first item of words"]], p.choices)
        for choice in p.choices:
            self.assertEqual("zoo\n", output(source.split("\n")[0] + "\n" + "\n".join(choice) + "\n"))
        p = problem_while_running(source.replace("largest", "smallest"))
        self.assertEqual([["sort words", "show the first item of words"],
                          ["sort words from Z to A", "show the last item of words"]], p.choices)

    def test_largest_of_a_column_or_a_worked_out_list(self):
        p = problem_while_running('read "sales.csv" and call it sales\nshow the largest of sales\'s customer\n',
                                  {"sales.csv": SALES})
        self.assertEqual(["sort sales by customer", "show the last item of sales's customer"], p.choices[0])
        p = problem_while_running('show the smallest of the words of "b a c"\n')
        self.assertEqual([['set my list to the words of "b a c"', "sort my list", "show the first item of my list"]],
                         p.choices)
        self.assertEqual("a\n", output("\n".join(p.choices[0]) + "\n"))

    def test_a_mixed_list_keeps_its_own_message(self):
        p = problem_while_running('set m to a list of 3 and "a"\nshow the largest of m\n')
        self.assertEqual('Check that "a" is a number before you compare it.', p.fix)

    def test_number_words_on_text_and_letters_on_numbers(self):
        cases = [
            ('set n to a list of "b" and "a"\nsort n largest first\n', 'Write "from Z to A" instead of "largest first".',
             ["sort n from Z to A"]),
            ('set n to a list of "b" and "a"\nsort n lowest first\n', 'Leave out "lowest first" to sort text from A to Z.',
             ["sort n"]),
            ("set n to a list of 2 and 1\nsort n from Z to A\n", 'Write "largest first" instead of "from Z to A".',
             ["sort n largest first"]),
            ("set n to a list of 2 and 1\nsort n from a to z\n", 'Leave out "from a to z" to sort numbers smallest first.',
             ["sort n"]),
        ]
        for source, fix, lines in cases:
            with self.subTest(source=source):
                p = problem_while_running(source)
                self.assertEqual((fix, lines), (p.fix, p.try_lines))
        p = problem_while_running('read "sales.csv" and call it sales\nsort sales by customer, biggest first\n',
                                  {"sales.csv": SALES})
        self.assertEqual(('Write "from Z to A" instead of "biggest first".', ["sort sales by customer from Z to A"]),
                         (p.fix, p.try_lines))

    def test_from_z_to_a_keeps_its_letters(self):
        self.assertEqual("sort names from Z to A", reading("set names to nothing\nsort names from Z to A", 2))
        self.assertTrue(fixes("set names to nothing\nsort names from Z"))
        self.assertEqual('Put the text in double quotes.', fixes("show z")[0])


class Stopwatch(unittest.TestCase):   # change 10
    def test_the_stopwatch_counts_up_from_its_start(self):
        out, _, _ = run_source("wait 2 seconds\nstart the stopwatch\nwait 1 second\nshow the stopwatch\n")
        self.assertEqual("1.0\n", out)

    def test_timer_is_an_offered_fix(self):
        found = Reader().read('start the timer\nshow "Took {the timer} seconds."\nstart timer\n').problems
        self.assertEqual([["start the stopwatch"], ['show "Took {the stopwatch} seconds."'], ["start the stopwatch"]],
                         [p.try_lines for p in found])
        self.assertEqual('Write "the stopwatch" instead of "timer".', found[2].fix)

    def test_timer_can_be_your_name_and_stopwatch_cant(self):
        self.assertEqual("10\n", output("set timer to 10\nshow the timer\n"))
        self.assertEqual(['Choose another name than "stopwatch".'], fixes("set stopwatch to 3"))


class OlderWordings(unittest.TestCase):   # changes 11 and 27
    SOURCE = ('set r to a new record\nshow "hi" in capitals\nshow "hi" in uppercase\nshow "Hi" in lowercase\n'
              'show 2.555 rounded to 2 decimals\nset n to a list of 3, 1 and 2\nsort n, smallest first\n'
              'show a random number between 1 and 1\nset w to a list of "b" and "a"\nsort w from A to Z\nshow w\n')

    def test_they_still_run(self):
        self.assertEqual("HI\nHI\nhi\n2.56\n1\na and b\n", output(self.SOURCE))
        self.assertEqual("(empty record)\nHELLO\nhello\n",
                         output('set r to an empty record\nshow r\nshow "hello" in capital letters\n'
                                'show "HELLO" in small letters\n'))

    def test_explain_shows_the_main_wording(self):
        readings = line_readings(Reader().read(self.SOURCE).statements)
        self.assertEqual(["set r to an empty record", 'show "hi" in capital letters', 'show "hi" in capital letters',
                          'show "Hi" in small letters', "show 2.555 rounded to 2 decimal places", "sort n",
                          "show a random number from 1 to 1", "sort w"],
                         [readings[n] for n in (1, 2, 3, 4, 5, 7, 8, 10)])
        self.assertIn("an empty record", explain(Reader().read(self.SOURCE)))

    def test_tidy_writes_the_main_wording(self):
        text, changes = tidied(self.SOURCE)
        self.assertEqual(["set r to an empty record", 'show "hi" in capital letters', 'show "hi" in capital letters',
                          'show "Hi" in small letters', "show 2.555 rounded to 2 decimal places",
                          "set n to a list of 3, 1 and 2", "sort n", "show a random number from 1 to 1",
                          'set w to a list of "b" and "a"', "sort w", "show w"], text.split("\n")[:-1])
        self.assertIn("line 1   a new record → an empty record", changes)
        self.assertIn("line 7   deleted smallest first", changes)
        self.assertIn("line 10   deleted from A to Z", changes)
        self.assertEqual(["line 8   a random number between → a random number from", "line 8   and → to"],
                         [c for c in changes if c.startswith("line 8 ")])
        self.assertEqual(output(self.SOURCE), output(text))
        self.assertEqual([], tidied(text)[1])

    def test_messages_quote_the_words_you_wrote(self):
        p = problem_while_running('set c to a list of "a"\nshow c in capital letters\n')
        self.assertEqual('"in capital letters" needs text for this part, and "c" is a list.', p.why)
        p = problem_while_running('set c to a list of "a"\nshow c in lowercase\n')
        self.assertEqual('"in lowercase" needs text for this part, and "c" is a list.', p.why)


class AddToFile(unittest.TestCase):   # change 30
    def test_a_list_adds_one_line_for_each_item(self):
        source = ('add a list of "milk" and "eggs" to the file "shop.txt"\nadd "jam" to the file "shop.txt"\n'
                  'add an empty list to the file "shop.txt"\nadd a list of 1 and 2.50 to the file "shop.txt"\n'
                  'read "shop.txt" and call it shop\nshow shop\n')
        self.assertEqual("milk\neggs\njam\n1\n2.50\n", output(source))

    def test_a_table_still_adds_its_rows(self):
        source = ('read "sales.csv" and call it sales\nadd sales where amount is more than 100 to the file "big.txt"\n'
                  'read "big.txt" and call it big\nshow big\n')
        self.assertEqual("date        customer  amount\n2026-10-01  Ann       120.50\n2026-10-03  Cy        300\n",
                         output(source, files={"sales.csv": SALES}))

    def test_a_written_file_name_needs_the_file(self):
        for line in ('add "milk" to "shopping.txt"', 'add "milk" to the "shopping.txt"'):
            with self.subTest(line=line):
                p = Reader().read(line).problems[0]
                self.assertEqual(['add "milk" to the file "shopping.txt"'], p.try_lines)
                self.assertEqual('Write "the file" before "shopping.txt" to add to that file.', p.fix)
        self.assertNotIn('the file', " ".join(fixes('set x to 1\nadd 1 to "x"')))


if __name__ == "__main__":
    unittest.main()
