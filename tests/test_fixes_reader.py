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
    def test_a_name_that_is_also_a_check_word_is_a_rename_problem(self):   # reader-1, reader-8, change 15
        for word in ("text", "empty", "even", "odd"):
            with self.subTest(word=word):
                found = problems(f'set {word} to "z"\nset x to ""\nif x is {word}\n    show 1')
                self.assertEqual([f'Rename "{word}" so this line has only one meaning, for example to "my {word}".'],
                                 [p.fix for p in found])
                # Once the name is renamed, the line reads with Plain's words as it is.
                self.assertEqual([], found[0].try_lines)
                self.assertEqual([], found[0].ideas)

    def test_name_and_phrase_words_show_both_readings(self):   # reader-27
        p = problems("set hours to 3\nset time to 5\nset under time to 2\nif hours is under time\n    show 1")[0]
        self.assertEqual('Rename "under time" so this line has only one meaning, for example to "my under time".',
                         p.fix)
        self.assertEqual([], p.try_lines)
        p = problems("set number to 3\nset x to 1\nif x is a number\n    show 1")[0]
        self.assertEqual('Rename "number" so this line has only one meaning, for example to "my number".', p.fix)
        self.assertEqual([], p.try_lines)

    def test_a_clash_offers_only_a_rename(self):   # change 15: never "is the same as", which changes the meaning
        p = problems('ask "Which person?" and call it number\nif number is a number\n    show 1')[0]
        self.assertEqual('Rename "number" so this line has only one meaning, for example to "my number".', p.fix)
        self.assertEqual(["if my number is a number"], p.try_lines)
        self.assertEqual([], p.ideas)   # a rename changes more than this one line
        self.assertEqual("1\n", output('set my number to 3\nif my number is a number\n    show 1'))
        p = problems('set my number to 3\nset number to 3\nif number is a number\n    show 1')[0]
        self.assertEqual(["if new number is a number"], p.try_lines)

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
        self.assertEqual(['Rename "number of tries", for example to "how many tries".'], [p.fix for p in found])

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
        self.assertEqual(([], "show 7.25 rounded to 1 decimal place"), reading("show 7.25 rounded to 1 place", 1))
        self.assertEqual(([], "wait 1 second"), reading("wait 1 second", 1))

    def test_placement_problems_mark_the_line(self):   # reader-41
        found = problems('how to greet (person)\n    show "Hi {person}"\ngreet "Ann" and call it result\n'
                         "give back 5\nstop repeating\nreturn 3")
        self.assertEqual([3, 4, 5, 6], [p.line for p in found])
        self.assertTrue(all(p.col is not None for p in found))
        self.assertEqual(12, found[0].col)
        self.assertEqual('Write "give back 3" instead.', found[3].fix)

    def test_else_offers_otherwise(self):   # change 8: "else" isn't English on its own
        found = problems('set x to 1\nif x is 1\n    show "a"\nelse\n    show "b"')
        self.assertEqual([(4, 'Write "otherwise" instead.', ["otherwise"])],
                         [(p.line, p.fix, p.try_lines) for p in found])


def offered(source):
    """(fix, try lines) of the first problem, after checking that each try line reads in its place."""
    found = problems(source)
    assert found, "no problem"
    p = found[0]
    lines = source.split("\n")
    for text in p.try_lines:
        fixed = "\n".join(lines[:p.line - 1] + [text] + lines[p.line:])
        assert not [q for q in problems(fixed) if q.line == p.line], (text, [q.fix for q in problems(fixed)])
    return p.fix, p.try_lines


class AgreeingWords(unittest.TestCase):   # change 6
    def test_plural_words_read_and_explain_keeps_them(self):
        source = ('set results to an empty list\nset letters to "abc"\n'
                  'if results are empty\n    show 1\nif letters contain "e"\n    show 2\n'
                  'if results aren\'t empty\n    show 3\nif letters do not start with "x"\n    show 4')
        program = Reader().read(source)
        self.assertEqual([], program.problems)
        readings = line_readings(program.statements)
        self.assertEqual(["if results are empty", 'if letters contain "e"', "if results are not empty",
                          'if letters do not start with "x"'], [readings[n] for n in (3, 5, 7, 9)])
        self.assertEqual("1\n4\n", output(source))

    def test_are_and_contain_end_names(self):
        self.assertEqual(['Rename "we are done", for example to "we done".'], fixes("set we are done to yes"))
        self.assertIn('"contain" is one of Plain\'s special words', problems("set boxes contain to 1")[0].why)

    def test_bare_start_with_is_not_added(self):
        self.assertTrue(problems('set names to an empty list\nif names start with "a"\n    show 1'))
        self.assertEqual([], problems("set start time to 3\nset end date to 4\nshow start time plus end date"))

    def test_cant_is_not_a_contraction(self):
        from plainlang.words import CONTRACTIONS
        self.assertNotIn("can't", CONTRACTIONS)
        self.assertEqual(("are", "not"), CONTRACTIONS["aren't"])


class OfferedFixes(unittest.TestCase):   # changes 8, 19 and 25: offered, never read
    def test_code_words_are_no_longer_read(self):
        from plainlang.words import CORE_STARTS, SPECIAL_WORDS, SYNONYMS
        for word in ("else", "fetch", "mean", "return"):
            self.assertNotIn(word, SYNONYMS)
        self.assertNotIn("return", CORE_STARTS)
        self.assertFalse({"true", "false"} & SPECIAL_WORDS)

    def test_equals_signs(self):
        self.assertEqual(('Write "is" instead of "==".', ["if x is 3"]), offered("set x to 3\nif x == 3\n    show 1"))
        self.assertEqual(('Write "is not" instead of "!=".', ["if x is not 3"]),
                         offered("set x to 3\nif x != 3\n    show 1"))
        self.assertEqual([], problems("set x to 3\nif x = 3 or x ≠ 4\n    show 1"))

    def test_else(self):
        source = 'set x to 3\nif x is 3\n    show "a"\nelse if x != 4\n    show "b"\nelse:\n    show "c"'
        found = problems(source)
        self.assertEqual([(4, ["otherwise if x is not 4"]), (6, ["otherwise"])], [(p.line, p.try_lines) for p in found])

    def test_return_fetch_true_false(self):
        self.assertEqual(('Write "give back n times 2" instead.', ["    give back n times 2"]),
                         offered("how to double (n)\n    return n times 2\ndouble 3 and call it six\nshow six"))
        self.assertEqual(["    give back yes"], offered("how to check (n)\n    return true")[1])
        self.assertEqual(['read "notes.txt" and call it notes'], offered('fetch "notes.txt" and call it notes')[1])
        self.assertEqual(["set done to yes"], offered("set done to TRUE")[1])
        self.assertEqual(["if done is no"], offered("set done to yes\nif done is False\n    show 1")[1])
        self.assertEqual(['if done is "true" or done is yes'],
                         offered('set done to yes\nif done is "true" or done is true\n    show 1')[1])
        self.assertEqual([], problems('show "true or false"'))
        self.assertEqual("5\n", output("set true to 5\nshow true"))   # no longer a special word

    def test_mean(self):
        fix, lines = offered("set scores to a list of 1 and 2\nshow the mean of scores")
        self.assertEqual('Write "average" instead of "mean", or use \'s for a field called "mean".', fix)
        self.assertEqual(["show the average of scores", "show scores' mean"], lines)
        self.assertEqual([], problems("set scores to a list of 1 and 2\nshow the average of scores"))

    def test_call_it_wordings(self):
        for said in ("and name it person", "and keep it as person", "and save it as person",
                     "and store it as person", "and call the answer person"):
            with self.subTest(said=said):
                self.assertEqual(['ask "Your name?" and call it person'],
                                 offered(f'ask "Your name?" {said}\nshow person')[1])
                self.assertEqual(1, len(problems(f'ask "Your name?" {said}\nshow person')))

    def test_next_round_and_fails_wordings(self):
        for said in ("go to the next round", "go on to the next round", "move on to the next round"):
            with self.subTest(said=said):
                self.assertEqual(["    skip to the next round"], offered(f"repeat 2 times\n    {said}")[1])
        for said in ("if that doesn't work", "if that goes wrong", "if there's a problem", "if it does not work"):
            with self.subTest(said=said):
                self.assertEqual(["if that fails"], offered(f'try\n    show 1\n{said}\n    show 2')[1])

    def test_to_starts_a_howto(self):
        self.assertEqual(["how to work out the tip on (bill)"],
                         offered("to work out the tip on (bill)\n    give back bill times 15%")[1])

    def test_where_wordings(self):
        sales = 'set sales to an empty list\n'
        self.assertEqual(["show sales where amount is more than 100"],
                         offered(sales + "show sales whose amount is more than 100")[1])
        self.assertEqual(('Write "it" instead of "each".', ["show sales where it is more than 100"]),
                         offered(sales + "show sales where each is more than 100"))
        self.assertEqual(["show sales where it is more than 100", "show sales where its item is more than 100"],
                         offered(sales + "show sales where the item is more than 100")[1])
        self.assertEqual([], problems(sales + "show sales where amount is more than 100"))

    def test_ordinal_items(self):
        colors = 'set colors to a list of "red" and "blue"\n'
        for word, n in (("second", 2), ("third", 3), ("twelfth", 12)):
            with self.subTest(word=word):
                self.assertEqual([f"show item {n} of colors", f"show colors' {word} item"],
                                 offered(colors + f"show the {word} item of colors")[1])
        self.assertEqual([], problems(colors + "show the first item of colors"))

    def test_wait_for_enter(self):
        self.assertEqual(["wait for Enter"], offered("wait for the Enter key")[1])
        self.assertEqual([], problems("wait for Enter\nwait for enter"))


class RenameSuggestions(unittest.TestCase):   # change 21: a suggested name keeps the meaning
    def test_suggestions(self):
        for name, new in (("lap times", "lap results"), ("best times", "best results"),
                          ("number of players", "player count"), ("number of boxes", "box count"),
                          ("number of tries", "how many tries"), ("price rounded", "price"),
                          ("date joined", "join date"), ("tip percent", "tip rate"),
                          ("total minus tax", "total without tax"), ("count of apples", "apple count"),
                          ("my list of things", "my things list"), ("has ticket", "got ticket")):
            with self.subTest(name=name):
                self.assertEqual([f'Rename "{name}", for example to "{new}".'], fixes(f"set {name} to 1"))

    def test_never_a_fixed_word(self):
        from plainlang.parser import RENAMES
        from plainlang.suggest import phrase_words
        from plainlang.words import CORE_STARTS, SPECIAL_WORDS
        fixed = phrase_words() | CORE_STARTS | SPECIAL_WORDS
        for word, new in RENAMES.items():
            with self.subTest(word=word):
                self.assertFalse(set(new.split()) & fixed, new)

    def test_a_field_with_a_special_word_goes_in_quotes(self):
        source = 'read "people.csv" and call it members\nrepeat for each member in members\n    show member\'s date joined'
        fix, lines = offered(source)
        self.assertEqual('Put the field name "date joined" in double quotes.', fix)
        self.assertEqual(['    show member\'s "date joined"'], lines)



# Stage 2 of the plain-language review: reading ---------------------------------------------

def each_choice_reads(test, source):
    """The first problem, after checking that every choice it offers reads in place of its line."""
    p = problems(source)[0]
    lines = source.split("\n")
    for choice in p.choices or [p.try_lines]:
        fixed = "\n".join(lines[:p.line - 1] + choice + lines[p.line:])
        test.assertEqual([], [q.fix for q in problems(fixed)], fixed)
    return p


def tidied(source):
    from plainlang.tidy import tidy
    return tidy(source, Reader().read(source))


def explained(source):
    from plainlang.tidy import explain
    return explain(Reader().read(source))


class EndLines(unittest.TestCase):   # change 0
    def test_known_end_lines_are_left_out(self):
        source = ('repeat 2 times\n    if 1 is 1\n        show "a"\n    end if\nend repeat\n'
                  'try\n    show "b"\nEnd Try.\nhow to greet (p)\n    show p\nend\ngreet "c"')
        self.assertEqual([], fixes(source))
        self.assertEqual("a\na\nb\nc\n", output(source))

    def test_any_other_end_line_is_a_problem(self):
        # These were left out without a word, so the game never ended.
        source = 'repeat 3 times\n    if 1 is 1\n        show "You win!"\n    end the game\n    show "round"'
        p = each_choice_reads(self, source)
        self.assertEqual((4, 'Write "stop the program" instead.', ["    stop the program"]),
                         (p.line, p.fix, p.try_lines))
        for line, fix in (("end it", 'Write "stop the program" instead.'),
                          ("end the program", 'Write "stop the program" instead.'),
                          ("end repeating", 'Write "stop repeating" instead.'),
                          ("end the repeat", 'Write "stop repeating" instead.'),
                          ("end the program now and then", 'Start this line with a different word, '
                                                           'or write "stop the program" to finish the program.')):
            with self.subTest(line=line):
                self.assertEqual([fix], fixes(f"repeat 2 times\n    show 1\n    {line}"))

    def test_end_words_from_other_languages(self):
        p = problems("for each n from 1 to 2\n    show n\nend for")[0]
        self.assertEqual(('Delete this line, or write "end repeat" instead.', ["end repeat"]), (p.fix, p.try_lines))
        self.assertEqual([], fixes("for each n from 1 to 2\n    show n\nend repeat"))
        p = problems("how to greet (p)\n    show p\nend function")[0]
        self.assertEqual(["end"], p.try_lines)
        self.assertEqual(["Delete this line."], fixes("repeat 2 times\n    show 1\n    end while"))

    def test_after_then(self):
        p = each_choice_reads(self, "if 1 is 2 then end the game")
        self.assertEqual(["if 1 is 2 then stop the program"], p.try_lines)
        self.assertEqual([], fixes("set end to 3\nset start to 1\nif start is less than end\n    show 1"))

    def test_explain_and_tidy(self):
        source = 'if 1 is 1\n    show "a"\nend if  # done\nrepeat 2 times\n    show "b"\nend repeat\nshow "c"\n'
        self.assertIn("end if  # done", explained(source).split("\n")[2])
        self.assertTrue(explained(source).split("\n")[2].endswith("(Plain leaves this line out)"))
        text, changes = tidied(source)
        self.assertEqual('if 1 is 1\n    show "a"\n# done\nrepeat 2 times\n    show "b"\nshow "c"\n', text)
        self.assertEqual(["line 3   deleted end if", "line 6   deleted end repeat"], changes)


class PostfixBrackets(unittest.TestCase):   # change 1
    def test_a_word_after_a_where_check_is_a_tie(self):
        source = ("set amounts to a list of 120.555, 80 and 300.111\n"
                  "show the total of amounts where it is more than 100 rounded to 2 places")
        p = each_choice_reads(self, source)
        self.assertEqual('Add brackets to show what "rounded to 2 places" goes with.', p.fix)
        self.assertEqual([["show (the total of amounts where it is more than 100) rounded to 2 places"],
                          ["show the total of amounts where it is more than (100 rounded to 2 places)"]],
                         p.choices)
        first, second = (source.split("\n")[0] + "\n" + c[0] for c in p.choices)
        self.assertEqual(("420.67\n", "420.666\n"), (output(first), output(second)))

    def test_explain_shows_what_it_covers(self):
        source = "set bill to 10.4\nset rate to 0.4\nshow bill plus rate rounded\nrepeat 2 times 3 times\n    show 1"
        self.assertEqual(([], "show (bill plus rate) rounded"), reading(source, 3))
        self.assertEqual(([], "repeat (2 times 3) times"), reading(source, 4))
        self.assertEqual(([], "show bill rounded"), reading("set bill to 1\nshow bill rounded", 2))
        self.assertEqual(([], "set x to the total of scores rounded to 2 decimal places"),
                         reading("set scores to a list of 1\nset x to the total of scores rounded to 2 places", 2))

    def test_tidy_adds_the_brackets(self):
        source = ("set bill to 10.4\nset rate to 0.4\nshow the bill plus rate rounded\nrepeat 2 times 3 times\n"
                  "    show 1\nset scores to a list of 1 and 2\nshow sum of scores plus 1 rounded\n")
        text, changes = tidied(source)
        self.assertEqual("show (the bill plus rate) rounded", text.split("\n")[2])
        self.assertEqual("repeat (2 times 3) times", text.split("\n")[3])
        self.assertEqual("show (total of scores plus 1) rounded", text.split("\n")[6])
        self.assertIn("line 3   the bill plus rate → (the bill plus rate)", changes)
        self.assertEqual(output(source), output(text))
        self.assertEqual([], tidied(text)[1])


class PhraseWordsAfterThe(unittest.TestCase):   # change 4
    def test_phrase_words_are_a_problem(self):
        orders = "set o to a new record\nset o's total to 10\nset orders to a list of o\n"
        p = each_choice_reads(self, orders + "show the totals of orders")
        self.assertEqual('Write "the total of" instead of "the totals of", or use \'s for a field called "totals".',
                         p.fix)
        self.assertEqual([["show the total of orders"], ["show orders' totals"]], p.choices)
        p = each_choice_reads(self, orders + "show the items of orders")
        self.assertEqual(["show orders' items"], p.try_lines)
        for said, phrase in (("numbers", "the number of"), ("averages", "the average of"),
                             ("lengths", "the length of"), ("first", "the first item of"),
                             ("last", "the last item of"), ("copies", "a copy of")):
            with self.subTest(said=said):
                p = problems(orders + f"show the {said} of orders")[0]
                self.assertEqual(f'show {phrase} orders', p.try_lines[0])

    def test_everyday_words_for_phrases(self):
        for line, fixed in (('show the letters of "abc"', 'show the characters of "abc"'),
                            ("show the max of scores", "show the largest of scores"),
                            ("show the minimum of scores", "show the smallest of scores"),
                            ("show the count of scores", "show the number of scores"),
                            ('show the size of "abc"', 'show the length of "abc"'),
                            ("show the unique items of scores", "show the different items of scores"),
                            ("show a random item of scores", "show a random item from scores")):
            with self.subTest(line=line):
                p = each_choice_reads(self, "set scores to a list of 1 and 2\n" + line)
                self.assertEqual(fixed, p.try_lines[0])

    def test_ordinary_words_keep_working(self):
        source = ("set p to a new record\nset p's first name to \"Ann\"\nset p's amount to 3\n"
                  "show the first name of p\nshow the amount of p\nshow the \"items\" of p\nshow p's items")
        self.assertEqual([], fixes(source))

    def test_while_running(self):
        out = output('set t to "abc"\nshow t\'s letters')
        self.assertIn('Write "the characters of t" instead.', out)

    def test_the_table_covers_every_phrase_word(self):
        # Each word before "of" in Plain's own value phrases, and each noun's plural, is a phrase
        # or gets a problem, so it never quietly reads as a field.
        from plainlang.registry import REGISTRY, Slot
        from plainlang.suggest import PHRASE_WORD_EXAMPLES, PHRASE_WORDS
        reader = Reader()
        nouns = {"number", "total", "average", "length", "item", "text", "copy", "list"}
        for phrase in REGISTRY:
            if phrase.kind != "value" or "of" not in phrase.template.split():
                continue
            for element in phrase.elements:
                if isinstance(element, Slot):
                    break
                for word in [w for w in element.alts if w != "of"]:
                    plural = word[:-1] + "ies" if word.endswith("y") else word + "s"
                    forms = {word, plural} if word in nouns else {word}
                    for form in forms:
                        with self.subTest(word=form):
                            self.assertTrue((form,) in reader.property_prefixes or form in PHRASE_WORDS
                                            or form in PHRASE_WORD_EXAMPLES, form)


class CountingDown(unittest.TestCase):   # change 12
    def test_written_numbers(self):
        p = each_choice_reads(self, "repeat for each n from 5 to 1\n    show n")
        self.assertEqual('Write "repeat for each n from 5 down to 1" to count down.', p.fix)
        self.assertEqual("5\n4\n", output("repeat for each n from 5 down to 4\n    show n"))

    def test_worked_out_ends_take_no_rounds(self):
        self.assertEqual("done\n", output("set todos to an empty list\n"
                                          "repeat for each n from 1 to the number of todos\n"
                                          '    show n\nshow "done"'))
        self.assertEqual("5\n", output("repeat for each n from 5 to 5\n    show n"))


class NotFolds(unittest.TestCase):   # change 13
    def test_two_nots_are_a_problem(self):
        source = "set done to an empty list\nif not done is not empty\n    show 1"
        p = each_choice_reads(self, source)
        self.assertEqual(('Write "if done is empty" instead.', ["if done is empty"]), (p.fix, p.try_lines))
        p = each_choice_reads(self, "set scores to a list of 1\nif not (the number of scores is not more than 3)\n"
                                    "    show 1")
        self.assertEqual(["if the number of scores is more than 3"], p.try_lines)

    def test_explain_and_tidy_fold_a_not(self):
        source = ("set scores to a list of 1 and 5\nset done to an empty list\n"
                  "if not (the number of scores is at most 3)\n    show 1\nif not done is empty\n    show 2\n"
                  "if not (done is empty or scores is empty)\n    show 3\nshow scores where not it > 1\n")
        self.assertEqual(([], "if the number of scores is more than 3"), reading(source, 3))
        self.assertEqual(([], "if done is not empty"), reading(source, 5))
        self.assertEqual(([], "if not (done is empty or scores is empty)"), reading(source, 7))
        text, changes = tidied(source)
        self.assertEqual(["if the number of scores is more than 3", "if done is not empty",
                          "if not (done is empty or scores is empty)", "show scores where it is at most 1"],
                         [text.split("\n")[n] for n in (2, 4, 6, 8)])
        self.assertEqual(output(source), output(text))


class ItTwice(unittest.TestCase):   # change 14
    def test_where_it_and_call_it(self):
        source = ('set scores to a list of 50, 72 and 95\n'
                  'ask "Pick one" with choices scores where it is more than 60 and call it pick\nshow pick')
        p = problems(source)[0]
        self.assertEqual('Split this line into two steps, so "it" has only one meaning.', p.fix)
        self.assertEqual(['set matching scores to scores where it is more than 60',
                          'ask "Pick one" with choices matching scores and call it pick'], p.try_lines)
        lines = source.split("\n")
        self.assertEqual([], fixes("\n".join(lines[:1] + p.try_lines + lines[2:])))

    def test_one_meaning_reads(self):
        self.assertEqual([], fixes('set scores to a list of 50 and 72\nset high to scores where it is more than 60\n'
                                   'ask "Pick one" with choices high and call it pick'))


class TextSplits(unittest.TestCase):   # changes 16 and 17
    def test_where_after_the_words_of_a_text(self):
        source = 'set story to "a big brown cat"\nshow the words of story where it starts with "b"'
        p = problems(source)[0]
        self.assertEqual([['show (the words of story) where it starts with "b"'],
                          ["set story words to the words of story", 'show story words where it starts with "b"']],
                         p.choices)
        for choice in p.choices:
            self.assertEqual("big and brown\n", output(source.split("\n")[0] + "\n" + "\n".join(choice)))

    def test_the_lines_of_a_file_name(self):
        source = 'set todos to the lines of "todos.txt"\nshow the number of todos'
        p = problems(source)[0]
        self.assertEqual([['read the lines of "todos.txt" and call it todos'],
                          ['set my text to "todos.txt"', 'set todos to the lines of my text']], p.choices)
        for choice in p.choices:
            self.assertEqual([], fixes("\n".join(choice + source.split("\n")[1:])))
        self.assertEqual([], fixes('set x to "a.txt"\nshow the lines of x\nshow the words of "hi there.txt now"'))


class ReviewFixes(unittest.TestCase):   # the review of changes 0-33
    def test_where_after_written_text(self):   # change 16
        source = 'show the words of "a bb c" where it starts with "b"'
        p = problems(source)[0]
        self.assertEqual([['show (the words of "a bb c") where it starts with "b"'],
                          ['set words to the words of "a bb c"', 'show words where it starts with "b"']], p.choices)
        for choice in p.choices:
            self.assertEqual("bb\n", output("\n".join(choice)))
        source = 'set story to "a,b"\nset parts to story split by "," where it is "b"\nshow parts'
        p = problems(source)[0]
        self.assertEqual(['set parts to (story split by ",") where it is "b"'], p.choices[0])
        self.assertEqual("b\n", output(source.replace('story split by ","', '(story split by ",")')))
        self.assertEqual(['Use "where" after a list or a table.'], fixes('show "abc" where it is "b"'))

    def test_a_tie_offers_both_bracketings_as_choices(self):   # change 1
        p = problems("show the total of a list of 1.25 and 2.5 rounded")[0]
        self.assertEqual([["show the total of a list of 1.25 and (2.5 rounded)"],
                          ["show (the total of a list of 1.25 and 2.5) rounded"]], p.choices)
        self.assertEqual("4\n", output("show (the total of a list of 1.25 and 2.5) rounded"))
        self.assertEqual("show (the total of a list of 1.25 and 2.5) rounded",
                         reading("show (the total of a list of 1.25 and 2.5) rounded", 1)[1])

    def test_rounded_after_a_check_in_brackets(self):   # change 1
        source = "set amounts to a list of 120.5, 80 and 300.25\nshow the total of amounts where (it is more than 100) rounded"
        fix, lines = offered(source)
        self.assertEqual(["show (the total of amounts where it is more than 100) rounded"], lines)
        self.assertEqual("421\n", output(source.split("\n")[0] + "\n" + lines[0]))

    def test_stop_repeating_only_where_it_works(self):   # change 0
        self.assertEqual(["Delete this line."], fixes('show "a"\nend the repeat'))
        self.assertEqual(["Delete this line."], fixes('show "a"\nend repeating now'))
        self.assertEqual([("Delete this line, or write \"end repeat\" instead.", ["end repeat"])],
                         [(p.fix, p.try_lines) for p in problems('repeat 2 times\n    show "a"\nend the repeat')])
        self.assertEqual(["    stop repeating"], problems('repeat 2 times\n    end repeating now')[0].try_lines)
        nested = 'repeat 2 times\n    repeat 2 times\n        show "a"\n    end the loop\n    show "b"'
        p = problems(nested)[0]
        self.assertEqual([["    end repeat"], ["    stop repeating"]], p.choices)
        for choice in p.choices:
            lines = nested.split("\n")
            self.assertEqual([], fixes("\n".join(lines[:3] + choice + lines[4:])))

    def test_no_apostrophe_s_on_a_written_list(self):   # change 4
        self.assertEqual(["show the largest of a list of 1 and 2"], offered("show the max of a list of 1 and 2")[1])
        self.assertEqual(["show the number of a list of 1 and 2"], offered("show the count of a list of 1 and 2")[1])
        self.assertEqual(["show the different items of a list of 1 and 1"],
                         offered("show the unique items of a list of 1 and 1")[1])

    def test_a_csv_file_name_offers_only_the_text(self):   # change 17
        p = problems('show the words of "notes.csv"')[0]
        self.assertEqual(['set my text to "notes.csv"', "show the words of my text"], p.try_lines)
        self.assertIn("gives a .csv file as a table", p.why)
        self.assertIn("records and lists", problems('show the characters of "data.json"')[0].why)


class PoliteHowTo(unittest.TestCase):   # change 24
    def test_a_how_to_that_starts_with_a_polite_word(self):
        source = 'how to first greet (person)\n    show "Hello, {person}!"\nfirst greet "Ann"'
        p = problems(source)
        self.assertEqual([(1, "Start your own step with a different word.", ["how to greet (person)"])],
                         [(q.line, q.fix, q.try_lines) for q in p])
        self.assertIn('leaves out "first"', p[0].why)
        self.assertEqual("Hello, Ann!\n", output(source.replace("how to first greet", "how to greet")))

if __name__ == "__main__":
    unittest.main()
