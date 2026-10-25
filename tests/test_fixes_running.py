"""Regression tests for problems found while running programs: files, numbers, the web and messages."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .support import ROOT, run_source
from plainlang.hosts import TerminalHost
from plainlang.interpreter import Run
from plainlang.parser import Reader
from plainlang.problems import Problem
from plainlang.words import BANNED_WORDS


def in_folder(source, files, answers=()):
    """Run source in a temp folder holding files (name -> text). Returns (output, the folder's files)."""
    with tempfile.TemporaryDirectory() as tmp:
        data = []
        for name, text in files.items():
            path = Path(tmp) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            data.append(Path(tmp) / Path(name).parts[0])
        out, host, _ = run_source(source, answers=answers, data=sorted(set(data)))
        return out, host


def run_saving(source, files=()):
    """Run source in a temp folder and give back the output and every file there, folders included."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for name, text in dict(files).items():
            (tmp / name).parent.mkdir(parents=True, exist_ok=True)
            (tmp / name).write_text(text, encoding="utf-8")
        from plainlang.hosts import TestHost
        from plainlang.problems import layout
        host = TestHost(tmp)
        program = Reader().read(source)
        assert not program.problems, [p.fix for p in program.problems]
        try:
            Run(program, host).run()
            out = host.output()
        except Problem as problem:
            out = host.output() + layout(problem, "program.plain", program.source_lines) + "\n"
        saved = {p.relative_to(tmp).as_posix(): p.read_text(encoding="utf-8")
                 for p in tmp.rglob("*") if p.is_file()}
        return out, saved


PEOPLE = "name,age\nAnn,30\nBo,25\n"


class Saving(unittest.TestCase):
    def test_a_saved_table_keeps_every_row(self):                       # running-1
        big = "n,sq\n" + "".join(f"{i},{i * i}\n" for i in range(1, 26))
        out, saved = run_saving('read "big.csv" and call it t\nsave t to "big.txt"\n'
                                'add t to the file "biglog.txt"\n', {"big.csv": big})
        self.assertEqual("", out)
        for name in ("big.txt", "biglog.txt"):
            lines = saved[name].splitlines()
            self.assertEqual(26, len(lines), name)
            self.assertEqual(["25", "625"], lines[-1].split())
            self.assertNotIn("more", saved[name])

    def test_json_keeps_exact_numbers(self):                             # running-4, running-15
        out, saved = run_saving(
            'set nums to a list of 1.50, 10 divided by 3, 12345678901234567.89 and -0.0\n'
            'save nums to "nums.json"\n'
            "set r to a new record\nset r's amount to 12345678901234567.89\nset r's price to 19.90\n"
            "set r's t to \"a \"\"q\"\" é\"\nset r's ok to yes\nset r's none to nothing\n"
            "set r's list to an empty list\n"
            'save r to "money.json"\nread "money.json" and call it back\nshow back\n')
        self.assertEqual("[\n  1.50,\n  3.3333333333,\n  12345678901234567.89,\n  0.0\n]\n", saved["nums.json"])
        self.assertIn('"amount": 12345678901234567.89,\n  "price": 19.90,', saved["money.json"])
        self.assertEqual({"amount", "price", "t", "ok", "none", "list"}, set(json.loads(saved["money.json"])))
        self.assertEqual('amount: 12345678901234567.89, price: 19.90, t: a "q" é, ok: yes, none: nothing, '
                         "list: (empty list)\n", out)

    def test_add_to_the_file_makes_the_folder(self):                    # running-10
        out, saved = run_saving('add "x" to the file "newdir/log.txt"\n')
        self.assertEqual("", out)
        self.assertEqual("x\n", saved["newdir/log.txt"])

    def test_rename_into_a_missing_folder_names_the_folder(self):       # running-10
        out, saved = run_saving('rename "out.txt" to "nofolder/out.txt"\n', {"out.txt": "hi\n"})
        self.assertIn('Check the folder name "nofolder".', out)
        self.assertNotIn(os.sep + "private", out)
        self.assertIn("out.txt", saved)

    def test_rename_inside_a_folder(self):                               # running-14
        out, saved = run_saving('rename "sub/one.txt" to "sub/uno.txt"\nshow the files in "sub"\n',
                                {"sub/one.txt": "1\n", "sub/two.txt": "2\n"})
        self.assertEqual("two.txt and uno.txt\n", out)

    def test_missing_file_message_never_shows_a_full_path(self):        # running-10
        from plainlang.interpreter import data_problem
        problem = data_problem(FileNotFoundError(2, "gone", "/somewhere/deep/folder/sub/x.txt"),
                               Path("/somewhere/deep/folder"))
        self.assertEqual('Check the file name "sub/x.txt".', problem.fix)


class ReadingCsv(unittest.TestCase):
    def test_a_quoted_comma_in_the_header_isnt_a_delimiter(self):       # running-7
        out, _ = in_folder('read "q.csv" and call it q\nshow item 1 of q\n',
                           {"q.csv": '"Price, USD";Name\n5;Ann\n6;Bob\n'})
        self.assertEqual("Price, USD: 5, Name: Ann\n", out)

    def test_blank_lines_before_the_header(self):                        # running-8
        out, _ = in_folder('read "lead.csv" and call it t\nshow the number of t\n'
                           'show the total of the amounts of t\n',
                           {"lead.csv": "\nname,amount\nAnn,5\nBob,6\n"})
        self.assertEqual("2\n11\n", out)

    def test_repeated_column_names_keep_every_value(self):              # running-19
        out, _ = in_folder('read "dup.csv" and call it dup\nshow dup\n', {"dup.csv": "a,a,B\n1,2,3\n"})
        self.assertEqual("a  a 2  B\n1  2    3\n", out)


class Numbers(unittest.TestCase):
    def test_too_big_a_number_is_a_message_try_can_handle(self):        # running-5
        out, _, _ = run_source('set x to 99999999999\ntry\n    repeat 20 times\n        set x to x times x\n'
                               'if that fails\n    show "caught"\n')
        self.assertEqual("caught\n", out)
        out, _, _ = run_source('set x to 99999999999\nrepeat 20 times\n    set x to x times x\n')
        self.assertIn("line 3, while running: Use smaller numbers here.", out)

    def test_numbers_are_never_normalized(self):                         # running-16 (partly)
        out, _ = in_folder('read "v.json" and call it d\nshow d\'s v\nshow 10 divided by 3\n'
                           'show 10 divided by 3 times 3\nshow 1 divided by 8\n',
                           {"v.json": '{"v": 2.500000000000}'})
        self.assertEqual("2.5000000000\n3.3333333333\n10\n0.125\n", out)

    def test_long_decimals_from_data_can_be_shown(self):                 # running-17
        out, _ = in_folder('read "big.json" and call it d\nshow d\'s v\nshow "v is {d\'s v}"\n',
                           {"big.json": '{"v": 12345678901234567890.123456789012}'})
        self.assertEqual("12345678901234567890.1234567890\nv is 12345678901234567890.1234567890\n", out)

    def test_the_stopwatch_rounds_halves_up_without_float_noise(self):  # running-20
        out, _, _ = run_source('wait 0.25 seconds\nshow the stopwatch\nwait 0.1 seconds\nwait 0.3 seconds\n'
                               'show the stopwatch\n')
        self.assertEqual("0.3\n0.7\n", out)

    def test_waiting_too_long_is_a_message(self):                        # running-25
        program = Reader().read("wait 100000000000000000000 seconds\n")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(Problem) as caught:
                Run(program, TerminalHost(folder=tmp)).run()
        self.assertEqual("Use a smaller number here.", caught.exception.fix)

    def test_dividing_by_a_written_0(self):                              # running-24, running-27
        for source in ("show 1 divided by 0\n", "set x to 10\nshow x / 0\n"):
            out, _, _ = run_source(source)
            self.assertIn("while running: Divide by a number other than 0.", out)
        out, _, _ = run_source("set count to 0\nshow 10 divided by count\n")
        self.assertIn('Check that "count" is not 0 before you divide by it.', out)


class Messages(unittest.TestCase):
    def assertWhy(self, source, why, fix=None, answers=()):
        out, _, _ = run_source(source, answers=answers)
        self.assertIn(f"Why: {why}\n", out)
        if fix:
            self.assertIn(f"while running: {fix}\n", out)
        for word in BANNED_WORDS:
            self.assertNotRegex(out.lower(), rf"\b{word}\b")
        return out

    def test_kind_checks_name_the_phrase(self):                          # running-3, running-9, running-26
        self.assertWhy('set name to "ann"\nshow the words of name in uppercase\n',
                       '"in uppercase" needs text for this part, and this is a list of 1 item.',
                       'Use text here, in double quotes, like "hello".')
        self.assertWhy('set colors to a list of "red" and "blue"\nshow colors in uppercase\n',
                       '"in uppercase" needs text for this part, and "colors" is a list.')
        self.assertWhy('set word to "hello"\nshow word joined with ", "\n',
                       '"joined with" needs a list, and "hello" is text.')
        self.assertWhy('show "abc" rounded\n', '"rounded" needs a number for this part, and "abc" is text.')
        self.assertWhy('show 5 rounded to "two" places\n',
                       '"rounded to" needs a number for this part, and "two" is text.')
        self.assertWhy('show a random number from "x" to 5\n',
                       '"a random number from" needs a number for this part, and "x" is text.')
        self.assertWhy('show the words of a list of 1 and 2\n',
                       '"the words of" needs text for this part, and this is a list of 2 items.')

    def test_text_where_a_list_is_needed_gets_a_hint_that_fits(self):    # running-9
        self.assertWhy('show item 2 of "abc"\n', '"item" needs a list, and "abc" is text. To pick from the '
                       'characters of text, write: item 2 of the characters of "abc"')
        self.assertWhy('set w to "abc"\nshow the number of w\n',
                       '"the number of" needs a list, and "abc" is text. To count the characters in text, '
                       'write "the length of".')
        out, _, _ = run_source('show item 2 of the characters of "abc"\n')
        self.assertEqual("b\n", out)

    def test_fixes_use_your_names(self):                                 # running-26
        self.assertWhy('set scores to an empty list\nshow the average of scores\n',
                       "The list is empty, so there's no average.",
                       "Check that the list is not empty first, with: if scores is not empty")
        self.assertWhy('set shopping to a list of "milk"\nremove "bread" from shopping\n',
                       'There\'s no "bread" in the list.',
                       'Check that the list contains "bread" first, with: if shopping contains "bread"')
        self.assertWhy('set v to "x"\nshow v as a number\n', '"x" is text, and it doesn\'t read as a number.',
                       'Check that "v" is a number first, with: if v is a number')
        self.assertWhy('show "x" as a number\n', '"x" is text, and it doesn\'t read as a number.',
                       'Use text that reads as a number here, like "42".')
        self.assertWhy("show the largest of an empty list\n", "The list is empty, so there's no largest.",
                       "Check that the list is not empty first.")

    def test_text_joined_with_plus_offers_one_text(self):                # running-11
        # Written text joined with + is caught before running (spec 3.3), with a checked fix.
        out, _, _ = run_source('set score to 5\nshow "Score: " + score\n')
        self.assertIn("hasn't run your program yet", out)
        self.assertIn('Try this:\n    show "Score: {score}"\n', out)
        out = self.assertWhy('set a to "x"\nset b to "y"\nset c to "z"\nshow a + b + c\n',
                             "Adding only works with numbers. To put text together, write it all inside one "
                             "pair of quotes, with each value in { }.")
        self.assertIn('Try this:\n    show "{a}{b}{c}"\n', out)
        out, _, _ = run_source('set a to "x"\nset b to "y"\nshow "{a + b}!"\n')
        self.assertIn('Try this:\n    show "{a}{b}!"\n', out)
        out, _, _ = run_source('set n to 2\nshow "Total: " + (n plus 1)\n')
        self.assertIn('Try this:\n    show "Total: {n plus 1}"\n', out)
        out, _, _ = run_source('set score to 5\nshow "Score: {score}"\nset n to 2\nshow "Total: {n plus 1}"\n')
        self.assertEqual("Score: 5\nTotal: 3\n", out)

    def test_a_typed_answer_still_gets_the_type_a_number_check(self):    # running-11 keeps section 8 message 5
        out = self.assertWhy('set total to 12\nask "How many more?" and call it answer\n'
                             'set total to total plus answer\n',
                             'You can\'t add "lots" to 12, because "lots" is text, not a number. "answer" got '
                             'its value on line 2, from what was typed.',
                             'Check that "answer" is a number before you add it.', answers=["lots"])
        self.assertIn('    otherwise\n        show "Please type a number."\n', out)

    def test_lists_and_tables_are_described_not_shown(self):            # running-12
        out, _ = in_folder('read "people.csv" and call it people\nshow people plus 1\n', {"people.csv": PEOPLE})
        self.assertIn('while running: Use a number here instead of "people".\n', out)
        self.assertIn('Why: You can\'t add 1 to "people", because "people" is a table, not a number.', out)
        self.assertNotIn("Try this", out)
        self.assertNotIn("Ann", out.split("\n", 1)[1].replace("read", ""))
        self.assertWhy('set nums to a list of 1, 2 and 3\nif nums is more than 2\n    show 1\n',
                       'You can\'t compare "nums" with 2, because "nums" is a list, not a number. "nums" got '
                       'its value on line 1, from a set step.', 'Use a number here instead of "nums".')

    def test_a_typed_answer_in_a_comparison_names_the_name(self):       # running-12
        out = self.assertWhy('ask "Age?" and call it age\nif age is more than 18\n    show 1\n',
                             'You can\'t compare "twenty" with 18, because "twenty" is text, not a number. '
                             '"age" got its value on line 1, from what was typed.',
                             'Check that "age" is a number before you compare it.', answers=["twenty"])
        self.assertNotIn("Try this", out)     # an "if" line can't go inside another "if" with no steps

    def test_a_website_reply_isnt_called_typed(self):                   # running-22
        web = {"https://e.com/post": {"status": 200, "kind": "text/plain", "body": "hello"}}
        out, _, _ = run_source('send "x" to "https://e.com/post" and call it r\nshow r plus 1\n', web=web)
        self.assertIn('"r" got its value on line 1, from the website\'s reply.', out)
        self.assertNotIn("Please type a number", out)

    def test_sorting_by_field(self):                                      # running-2, running-13
        out, _ = in_folder('read "people.csv" and call it people\nsort people by age, smallest first\n'
                           'show people\nset ages to a list of 3, 1 and 2\nsort ages smallest first\nshow ages\n',
                           {"people.csv": PEOPLE})
        self.assertEqual("name  age\nBo    25\nAnn   30\n1, 2 and 3\n", out)
        out, _ = in_folder('read "people.csv" and call it people\nsort people by height\n', {"people.csv": PEOPLE})
        self.assertIn("while running: Use one of the columns this table has: name, age.\n", out)   # change 5
        self.assertIn('Why: There\'s no column "height" in this table.', out)
        out, _, _ = run_source('set xs to a list of 1, "b" and 2\nsort xs\n')
        self.assertIn("Check that the items are all numbers, or all text, before you sort them.", out)

    def test_small_wording_fixes(self):                                   # running-24
        self.assertWhy('set colors to a list of "r"\nset item 5 of colors to "x"\n',
                       "The list has 1 item, so there is no item 5.")
        self.assertWhy('show the total of a list of 1, "x" and 3\n', '"x" is text, not a number.',
                       "Check that every item is a number before you add them up.")

    def test_the_problem_means_nothing_after_if_that_fails(self):        # running-24
        out, _, _ = run_source('try\n    show 1 divided by 0\nif that fails\n    show "x"\ntry\n    show "ok"\n'
                               'if that fails\n    show "never"\nshow "after: {the problem}"\n')
        self.assertEqual("x\nok\nafter: nothing\n", out)

    def test_adding_to_text_offers_one_text(self):                       # running-28
        out = self.assertWhy('set t to "abc"\nset x to "def"\nadd x to t\n',
                             '"t" is the text "abc", and "add" only adds numbers or puts items on a list.')
        self.assertIn('    set t to "{t}{x}"\n', out)
        out, _, _ = run_source('set t to "abc"\nadd "d" to t\n')
        self.assertIn('    set t to "{t}d"\n', out)
        out, _ = in_folder('read "todos.txt" and call it todos\nadd "walk" to todos\n',
                           {"todos.txt": "buy milk\nfeed cat\n"})
        self.assertIn('write "read the lines of" on line 1.', out)
        self.assertNotIn("a list of", out)    # text with several lines can't be written in quotes
        out, _, _ = run_source('set t to "abc"\nset x to "def"\nset t to "{t}{x}"\nshow t\n')
        self.assertEqual("abcdef\n", out)


class Pages(unittest.TestCase):
    def test_page_text_keeps_words_apart(self):                          # running-18
        out, _, _ = run_source('set page to "<table><tr><td>Ann</td><td>5</td></tr></table><p>Hello</p>World'
                               '<ul><li>one</li><li>two</li></ul><span>a</span>"\nshow the text of page\n')
        self.assertEqual("Ann 5\nHello\nWorld\none\ntwo\na\n", out)

    def test_nested_json_errors_show_the_message(self):                  # running-23
        web = {"https://api.example.com/x": {"status": 400,
                                             "body": {"error": {"code": 400, "message": "API key not valid"}}}}
        out, _, _ = run_source('read "https://api.example.com/x" and call it x\n', web=web)
        self.assertIn("Why: It said: API key not valid\n", out)


class Handler(BaseHTTPRequestHandler):
    sent = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == "/short":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "100")
            self.end_headers()
            self.wfile.write(b"hello")
            self.wfile.flush()
            self.close_connection = True
        elif self.path == "/hangup":
            self.close_connection = True

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        Handler.sent.append(body)
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class RealWeb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def run_plain(self, source):
        import contextlib
        import io
        program = Reader().read(source)
        self.assertEqual([], [p.fix for p in program.problems])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            Run(program, TerminalHost()).run()
        return out.getvalue()

    def test_a_dropped_connection_is_a_web_message(self):                # running-6
        for page in ("short", "hangup"):
            with self.subTest(page=page):
                with self.assertRaises(Problem) as caught:
                    self.run_plain(f'read "{self.base}/{page}" and call it x\n')
                self.assertEqual("Check your internet connection and the address, then run this again.",
                                 caught.exception.fix)
                out = self.run_plain(f'try\n    read "{self.base}/{page}" and call it x\nif that fails\n'
                                     f'    show "caught"\n')
                self.assertEqual("caught\n", out)

    def test_sending_keeps_exact_numbers(self):                           # running-4
        self.run_plain(f"set msg to a new record\nset msg's ratio to 10 divided by 3\n"
                       f"set msg's big to 12345678901234567.89\n"
                       f'send msg to "{self.base}/post" and call it reply\n')
        self.assertEqual(b'{"ratio": 3.3333333333, "big": 12345678901234567.89}', Handler.sent[-1])


class Pipes(unittest.TestCase):
    def test_output_cut_short_by_head_stops_quietly(self):               # running-21
        with tempfile.TemporaryDirectory() as tmp:
            program = Path(tmp) / "p.plain"
            program.write_text("repeat for each i from 1 to 100000\n    show i\n")
            env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
            run = subprocess.Popen([sys.executable, "-m", "plainlang", "run", str(program)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            self.assertEqual(b"1", run.stdout.readline().rstrip())   # Windows ends lines with \r\n
            run.stdout.close()
            err = run.stderr.read()
            run.stderr.close()
            self.assertEqual(0, run.wait(timeout=30))
            self.assertEqual(b"", err)


if __name__ == "__main__":
    unittest.main()
