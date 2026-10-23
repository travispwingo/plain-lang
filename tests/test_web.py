"""TerminalHost's real web code, against a local server. No internet needed."""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .support import ROOT, run_source
from plainlang.hosts import TerminalHost
from plainlang.interpreter import Run
from plainlang.parser import Reader
from plainlang.problems import Problem


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.startswith("/json"):
            self.reply(200, "application/json", json.dumps({"name": "cpython", "stars": 7}).encode())
        elif self.path.startswith("/echo"):
            self.reply(200, "text/plain", self.path.encode())
        elif self.path == "/page":
            self.reply(200, "text/html", b"<p>Hello <a href='/x'>you</a></p>")
        else:
            self.reply(404, "text/plain", b"nope")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        self.reply(200, "application/json", json.dumps({"got": json.loads(body)}).encode())

    def reply(self, status, kind, body):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def run_plain(self, source):
        import io
        import contextlib
        program = Reader().read(source)
        self.assertEqual([], [p.fix for p in program.problems])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            Run(program, TerminalHost()).run()
        return out.getvalue()

    def test_json(self):
        out = self.run_plain(f'read "{self.base}/json" and call it repo\nshow repo\'s name\nshow repo\'s stars')
        self.assertEqual("cpython\n7\n", out)

    def test_missing_page(self):
        with self.assertRaises(Problem) as caught:
            self.run_plain(f'read "{self.base}/nothing-here" and call it page')
        self.assertIn("code 404", caught.exception.fix)

    def test_address_pieces_are_encoded(self):
        out = self.run_plain(f'set city to "New York & Co"\nread "{self.base}/echo?q={{city}}" and call it reply\nshow reply')
        self.assertEqual("/echo?q=New%20York%20%26%20Co\n", out)

    def test_send(self):
        out = self.run_plain(f'set message to a new record\nset message\'s n to 3\n'
                             f'send message to "{self.base}/post" and call it reply\nshow reply\'s got\'s n')
        self.assertEqual("3\n", out)

    def test_page_text_and_links(self):
        out = self.run_plain(f'read "{self.base}/page" and call it page\nshow the text of page\nshow the links of page')
        self.assertEqual("Hello you\n/x\n", out)

    def test_try_catches_web_problems(self):
        out = self.run_plain(f'try\n    read "{self.base}/nothing" and call it page\nif that fails\n    show "failed"')
        self.assertEqual("failed\n", out)


if __name__ == "__main__":
    unittest.main()
