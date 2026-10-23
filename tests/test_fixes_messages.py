"""Messages for lines Plain can't follow: each fix is in your own words and has been checked."""

import unittest

from .support import run_source
from plainlang.parser import Reader
from plainlang.problems import layout


def problem_on(source, number):
    program = Reader().read(source)
    found = [p for p in program.problems if p.line == number]
    assert found, f"no problem on line {number}: {[p.fix for p in program.problems]}"
    return found[0]


def with_line(source, number, new):
    lines = source.split("\n")
    lines[number - 1:number] = new.split("\n")
    return "\n".join(lines)


class OfferedFixesWork(unittest.TestCase):
    """Every one-keypress idea makes its line read, so the fixer never saves a broken line."""

    PROGRAMS = [
        "set x to 1\nif x is 1\n    show 1\nelif x is 2\n    show 2\n",
        "set age to 20\niff age is 20\n    show 1\n",
        "show The answer is 42\n",
        "set age to 20\nif age is bigger 18\n    show 1\n",
        'set total to 0\nshow "Total is " total\n',
        "set scores to a list of 1, 2 and 3\nif the number of scores where it is morethan 10\n    show 1\n",
        "set age to 20\nif age is 18 or more\n    show 1\n",
        "set age to 20\nif age is even or odd\n    show 1\n",
        'set shopping to a list of "milk"\nadd "tea" and "rice" to shopping\n',
        "// greet\n",
        'show "hi" // greet\n',
        'set fruits to a list of "a" and "b"\nfruits.append("kiwi")\n',
        "set name to Bob\n",
        "read people.csv and call it people\n",
        'show "She said "hi" to me"\n',
        "how to double (n)\n    give back n times 2\nset x to double 4\n",
    ]

    def test_ideas_read_cleanly(self):
        for source in self.PROGRAMS:
            program = Reader().read(source)
            with self.subTest(source=source):
                self.assertTrue(program.problems)
                problem = program.problems[0]
                self.assertTrue(problem.ideas, problem.fix)
                for idea in problem.ideas:
                    fixed = Reader().read(with_line(source, problem.line, idea))
                    self.assertEqual([], [p.fix for p in fixed.problems if p.line == problem.line], idea)


class Habits(unittest.TestCase):
    def test_elif_becomes_otherwise_if(self):  # messages-1, messages-17
        p = problem_on("set x to 1\nif x is 1\n    show 1\nelif x is 2\n    show 2\n", 4)
        self.assertEqual('Write "otherwise if x is 2" instead.', p.fix)
        self.assertEqual(["otherwise if x is 2"], p.try_lines)

    def test_show_line_with_is_is_text_not_a_name(self):  # messages-1
        p = problem_on("show The answer is 42\n", 1)
        self.assertEqual("Put the text in double quotes.", p.fix)
        self.assertEqual(['show "The answer is 42"'], p.try_lines)

    def test_slip_on_if(self):  # messages-1
        p = problem_on('set age to 20\niff age is 20\n    show "yes"\n', 2)
        self.assertEqual('Write "if" instead of "iff".', p.fix)
        self.assertEqual(["if age is 20"], p.ideas)

    def test_is_still_offers_set(self):
        p = problem_on("score is 0\nshow score\n", 1)
        self.assertEqual('Write "set score to 0" instead.', p.fix)

    def test_notes(self):  # messages-13, messages-17
        p = problem_on('// greet\nshow "hi"\n', 1)
        self.assertEqual(["# greet"], p.try_lines)
        p = problem_on('show "hi" // greet\n', 1)
        self.assertEqual(['show "hi"  # greet'], p.try_lines)

    def test_dividing_with_two_slashes_is_not_a_note(self):
        p = problem_on("set x to 5\nset y to x // 2\n", 2)
        self.assertNotIn("#", " ".join(p.try_lines))

    def test_append_len_and_brackets(self):  # messages-14, messages-17
        start = 'set fruits to a list of "a" and "b"\n'
        self.assertEqual(['add "kiwi" to fruits'], problem_on(start + 'fruits.append("kiwi")\n', 2).try_lines)
        p = problem_on(start + "show len(fruits)\n", 2)
        self.assertEqual('Write "the number of fruits" instead of "len(fruits)".', p.fix)
        self.assertEqual("show the number of fruits", p.try_lines[0])
        self.assertEqual(["set more to a list of 1, 2 and 3"],
                         problem_on(start + "set more to [1, 2, 3]\n", 2).try_lines)
        p = problem_on(start + "show fruits[1]\n", 2)
        self.assertEqual(["show item 2 of fruits"], p.try_lines)
        self.assertEqual([], p.ideas)


class Repairs(unittest.TestCase):
    def test_missing_than(self):  # messages-2
        p = problem_on('set age to 20\nif age is bigger 18\n    show "adult"\n', 2)
        self.assertEqual('Write "bigger than" instead of "bigger".', p.fix)
        self.assertEqual(["if age is bigger than 18"], p.try_lines)

    def test_value_after_text_goes_inside_it(self):  # messages-2
        p = problem_on('set total to 0\nshow "Total is " total\n', 2)
        self.assertEqual(['show "Total is {total}"'], p.try_lines)
        p = problem_on('set name to "Ann"\nshow "Hello" name\n', 2)
        self.assertEqual(['show "Hello {name}"'], p.try_lines)
        out, _, _ = run_source(with_line('set name to "Ann"\nshow "Hello" name\n', 2, p.ideas[0]))
        self.assertEqual("Hello Ann\n", out)

    def test_meaningful_words_are_never_dropped(self):  # messages-2
        for source in ('set age to 20\nif age is bigger 18\n    show 1\n', 'set total to 0\nshow "Total is " total\n'):
            program = Reader().read(source)
            self.assertFalse(any(p.fix.startswith("Remove the word") for p in program.problems))

    def test_words_run_together(self):  # messages-4
        p = problem_on("set scores to a list of 1, 2 and 3\nif the number of scores where it is morethan 10\n"
                       "    show 1\n", 2)
        self.assertEqual('Write "more than" instead of "morethan".', p.fix)


class TextWithoutQuotes(unittest.TestCase):
    def test_unknown_name_in_arithmetic_is_not_quoted(self):  # messages-3
        p = problem_on("add 1 to tally\nshow tally plus 1\n", 2)
        self.assertEqual('Set "tally" before this line uses it, or check the spelling.', p.fix)
        self.assertEqual([], p.try_lines)

    def test_field_inside_where_needs_its(self):  # messages-3
        p = problem_on('read "people.csv" and call it people\n'
                       "show the names of people where the length of name is more than 2\n", 2)
        self.assertEqual('Write "its name" instead of "name".', p.fix)

    def test_ask_question_is_quoted_whole(self):  # messages-8
        p = problem_on("ask What is your name? and call it name\n", 1)
        self.assertEqual(['ask "What is your name?" and call it name'], p.try_lines)

    def test_show_sentence_is_quoted_whole(self):  # messages-8
        self.assertEqual(['show "my name is Ann"'], problem_on("show my name is Ann\n", 1).try_lines)

    def test_unset_name_after_plus_sign(self):  # messages-8
        p = problem_on('show "Hello" + name\n', 1)
        self.assertEqual('Set "name" before this line uses it, or check the spelling.', p.fix)

    def test_possessive_with_no_field(self):  # messages-8
        p = problem_on('set x to "a"\nshow x\'s\n', 2)
        self.assertEqual([], p.try_lines)
        self.assertIn("field", p.fix)

    def test_set_and_file_names(self):  # messages-15
        p = problem_on("set name to Bob\nshow name\n", 1)
        self.assertEqual(['set name to "Bob"'], p.try_lines)
        self.assertIn('"Bob"', p.why)
        p = problem_on("read people.csv and call it people\n", 1)
        self.assertEqual("Put the file name in double quotes.", p.fix)
        self.assertEqual(['read "people.csv" and call it people'], p.try_lines)

    def test_messages_quote_your_words(self):  # messages-15
        p = problem_on("set lunch to 4\nset t to work out the tip on lunch\n", 2)
        self.assertEqual('Set "work out the tip on lunch" before this line uses it, or check the spelling.', p.fix)

    def test_quote_marks_inside_text(self):  # messages-19
        p = problem_on('show "She said "hi" to me"\n', 1)
        self.assertEqual('Write "" for each quote mark inside text.', p.fix)
        self.assertEqual(['show "She said ""hi"" to me"'], p.try_lines)


class StepsInsideLines(unittest.TestCase):
    TIP = "how to work out the tip on (bill) at (rate)\n    give back bill times rate\n"

    def test_how_to_inside_show(self):  # messages-5
        source = "set lunch to 40\nshow work out the tip on lunch at 15%\n" + self.TIP
        p = problem_on(source, 2)
        self.assertEqual(["work out the tip on lunch at 15% and call it tip", "show tip"], p.try_lines)
        out, _, _ = run_source(with_line(source, 2, "\n".join(p.try_lines)))
        self.assertEqual("6.00\n", out)

    def test_how_to_inside_set(self):  # messages-5, messages-11
        p = problem_on("set lunch to 40\nset t to work out the tip on lunch at 15%\n" + self.TIP, 2)
        self.assertEqual(["work out the tip on lunch at 15% and call it t"], p.try_lines)
        p = problem_on("how to double (n)\n    give back n times 2\nset x to double 4\n", 3)
        self.assertEqual(["double 4 and call it x"], p.try_lines)

    def test_read_inside_set(self):  # messages-11
        p = problem_on('set people to read "people.csv"\n', 1)
        self.assertEqual(['read "people.csv" and call it people'], p.try_lines)

    def test_how_to_inside_arithmetic(self):  # messages-18
        p = problem_on("set price to 3\nshow price plus double it 2\nhow to double it (n)\n    give back n times 2\n", 2)
        self.assertEqual(["double it 2 and call it result", "show price plus result"], p.try_lines)

    def test_ask_inside_if_keeps_the_check(self):
        p = problem_on('if ask "Yes?" is "y"\n    show 1\n', 1)
        self.assertEqual(['ask "Yes?" and call it result', 'if result is "y"'], p.try_lines)


class WhereInsideChecks(unittest.TestCase):
    def test_brackets_in_your_own_words(self):  # messages-9, messages-16
        source = 'set scores to a list of 5, 12 and 30\nif the number of scores where it is more than 10 is at least 2\n    show "lots"\n'
        p = problem_on(source, 2)
        self.assertEqual("if the number of (scores where it is more than 10) is at least 2", p.try_lines[-1])
        self.assertNotIn("sales", " ".join(p.try_lines))
        out, _, _ = run_source(with_line(source, 2, p.ideas[0]))
        self.assertEqual("lots\n", out)

    def test_repeat_until_stays_repeat_until(self):  # messages-16
        p = problem_on("set scores to a list of 5, 12 and 30\n"
                       "repeat until the number of scores where it is more than 10 is 3\n    add 20 to scores\n", 2)
        self.assertTrue(all(line.startswith(("set ", "repeat until")) for line in p.try_lines))

    def test_only_when_a_comparison_follows(self):  # messages-4
        p = problem_on("set scores to a list of 1, 2 and 3\nif the number of scores where it is morethan 10\n"
                       "    show 1\n", 2)
        self.assertNotIn("brackets", p.fix)


class EverydayWordings(unittest.TestCase):  # messages-6
    def test_or_more(self):
        p = problem_on("set age to 20\nif age is 18 or more\n    show 1\n", 2)
        self.assertEqual(["if age is at least 18"], p.try_lines)

    def test_or_odd(self):
        p = problem_on("set age to 20\nif age is even or odd\n    show 1\n", 2)
        self.assertEqual(["if age is even or is odd"], p.try_lines)

    def test_it_outside_where(self):
        p = problem_on("set xs to a list of 1 and 2\nrepeat for each x in xs\n    show it\n", 3)
        self.assertIn('"it"', p.fix)
        self.assertEqual([], p.try_lines)
        p = problem_on("show its amount\n", 1)
        self.assertIn('"its"', p.fix)
        self.assertEqual([], p.try_lines)

    def test_add_several_items(self):
        source = 'set shopping to a list of "milk"\nadd "tea" and "rice" to shopping\nshow shopping\n'
        p = problem_on(source, 2)
        self.assertEqual(['add a list of "tea" and "rice" to shopping'], p.try_lines)
        out, _, _ = run_source(with_line(source, 2, p.ideas[0]))
        self.assertEqual("milk, tea and rice\n", out)

    def test_list_then_or(self):
        p = problem_on('set age to 3\nif age is in a list of 1, 5 and 6 or age is 3\n    show "y"\n', 2)
        self.assertEqual(["if age is in (a list of 1, 5 and 6) or age is 3"], p.try_lines)


class YourOwnSteps(unittest.TestCase):
    def test_name_set_only_inside_a_how_to(self):  # messages-7
        p = problem_on('bump the count\nshow "label {label}"\n\nhow to bump the count\n    set label to "set inside"\n', 2)
        self.assertIn("give back label", p.fix)
        self.assertIn('only inside your step "bump the count" (line 5)', p.why)

    def test_step_used_without_its_value(self):  # messages-12
        for call in ("greet", 'greet "Ann" "Bo"'):
            p = problem_on('how to greet (person)\n    show "hi {person}"\n' + call + "\n", 3)
            self.assertEqual("Write this line the way your step on line 1 is worded: greet (person)", p.fix)

    def test_wording_without_brackets(self):  # messages-12
        source = 'how to greet person\n    show "hi {person}"\ngreet "Bo"\n'
        for number in (2, 3):
            p = problem_on(source, number)
            self.assertTrue(p.fix.startswith('Put brackets around "person" on line 1'), p.fix)
            self.assertEqual(["how to greet (person)"], p.try_lines)


class Carets(unittest.TestCase):
    def test_tab_counts_as_four_spaces(self):  # messages-10
        for indent in ("\t", "  \t"):
            source = f"set x to 1\nif x is 1\n{indent}show agee\n"
            program = Reader().read(source)
            text = layout(program.problems[0], "t.plain", program.source_lines).split("\n")
            shown, carets = text[2], text[3]
            self.assertEqual("agee", shown[carets.index("^"):len(carets)])


if __name__ == "__main__":
    unittest.main()
