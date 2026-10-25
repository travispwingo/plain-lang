"""Fixes in the tools around the language: the fixer, the REPL and the CLI."""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .support import ROOT  # noqa: F401  (puts src on the path)

from plainlang import cli, fixer  # noqa: E402
from plainlang.hosts import TestHost  # noqa: E402
from plainlang.parser import Reader  # noqa: E402
from plainlang.repl import Session  # noqa: E402


def quietly(func, *args, **kwargs):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        result = func(*args, **kwargs)
    return result, out.getvalue()


def session(lines, options=None):
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
    s = Session(options or {"seed": None}, ask=ask, show=shown.append, host=host)
    s.loop()
    return shown, host, s


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

        (fixed, new_text), out = quietly(fixer.fix_file, path, text, Reader().read(text), ask=ask)
        return fixed, path, out

    def test_pick_an_idea_and_save(self):
        fixed, path, out = self.fix("show Hello there\n", ["1"])
        self.assertIsNotNone(fixed)
        self.assertEqual('show "Hello there"\n', path.read_text())
        self.assertEqual("show Hello there\n", (self.folder / "hello.plain.bak").read_text())
        self.assertIn('  1) show "Hello there"\n', out)

    # tools-15
    def test_indent_fix_is_offered(self):
        source = 'set x to 1\nif x is 1\nshow "one"\n'
        self.assertEqual(['    show "one"'], Reader().read(source).problems[0].ideas)

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

    def test_splice_keeps_notes_newlines_and_bom(self):
        text = "\ufeffset x to 1\r\n    show Hello  # say hi\r\nshow x\r\n"
        out = fixer.splice(text, 2, ['    show "Hello"'])
        self.assertEqual('\ufeffset x to 1\r\n    show "Hello"  # say hi\r\nshow x\r\n', out)

    # tools-24
    @unittest.skipIf(os.name == "nt" or os.geteuid() == 0, "needs a folder you can't change")
    def test_a_folder_you_cant_change(self):
        path = self.folder / "a.plain"
        path.write_text("show Hello there\n")
        os.chmod(self.folder, 0o555)
        try:
            (fixed, _), out = quietly(fixer.fix_file, path, path.read_text(), Reader().read(path.read_text()),
                                      ask=lambda prompt: "1")
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
        for word, phrase in (("display", "show VALUE"), ("load", "read FILE"), ("pause", "wait")):
            with self.subTest(word=word):
                code, out = quietly(cli.phrases, [word])
                self.assertEqual(0, code)
                self.assertIn(phrase, out)

    def test_output_into_a_reader_that_stops_ends_quietly(self):
        # plain phrases | head: once head stops reading, Plain stops too, with no traceback.
        read_end, write_end = os.pipe()

        class Stopped(io.StringIO):
            def write(self, text):
                raise BrokenPipeError

            def fileno(self):
                return write_end

        try:
            with mock.patch("sys.stdout", Stopped()), self.assertRaises(SystemExit) as stop:
                cli.phrases([])
            self.assertEqual(0, stop.exception.code)
        finally:
            os.close(read_end)
            os.close(write_end)

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
            session([f":run {folder / 'dice.plain'}"], options={"seed": 7})
        self.assertEqual([{"seed": 7}], seen)

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

    # tools-17
    def test_ctrl_c_throws_away_the_steps_being_typed(self):
        shown, host, _ = session(["repeat 2 times", '    show "cancelled"', KeyboardInterrupt, 'show "next"'])
        self.assertEqual(["next"], host.transcript)
        self.assertIn("Cancelled. Those steps didn't run.", shown)

    def test_ctrl_c_while_plain_works_on_a_line_keeps_the_session(self):
        with mock.patch.object(Session, "offer_ideas", side_effect=KeyboardInterrupt):
            shown, host, _ = session(["set total to 41", "count up the totals", "show total plus 1"])
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
        self.assertIn("your step: Start this line with a step Plain knows.\n", text)
        self.assertIn("Find a phrase that fits at plain-lang.dev/phrases/, or type :phrases", text)
        self.assertNotIn("plain phrases", text)

    def test_the_docs_pointer_in_the_repl(self):
        shown, _, _ = session(['set names to a list of "b" and "a"', "sort names by by"])
        message = next(s for s in shown if s.startswith("your step: "))
        self.assertTrue(message.endswith("\nFind a phrase that fits at plain-lang.dev/phrases/#lists-and-tables, "
                                         "or type :phrases sort"), message)

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
