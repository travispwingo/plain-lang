"""TerminalHost's real web code, against a local server. No internet needed."""

import json
import os
import ssl
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from .support import ROOT, run_source
from plainlang import hosts
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


class Certificates(unittest.TestCase):
    """Every web request checks certificates, with the system's own list when Python has none."""

    def setUp(self):
        hosts.web_context.cache_clear()
        self.addCleanup(hosts.web_context.cache_clear)

    def context_with(self, count, files, loads=()):
        fake = mock.Mock(**{"cert_store_stats.return_value": {"x509_ca": count},
                            "load_verify_locations.side_effect": list(loads)})
        with mock.patch.object(hosts.ssl, "create_default_context", lambda: fake), \
                mock.patch.object(hosts, "CERTIFICATE_FILES", files):
            self.assertIs(fake, hosts.web_context())
        return fake

    def test_it_checks_and_is_made_once(self):
        context = hosts.web_context()
        self.assertIs(context, hosts.web_context())
        self.assertEqual(ssl.CERT_REQUIRED, context.verify_mode)
        self.assertTrue(context.check_hostname)

    def test_pythons_own_certificates_come_first(self):
        fake = self.context_with(140, ("/a.pem",))
        fake.load_verify_locations.assert_not_called()

    def test_with_none_the_first_list_that_loads_is_used(self):
        fake = self.context_with(0, ("/missing.pem", "/damaged.pem", "/good.pem", "/later.pem"),
                                 loads=[FileNotFoundError(), ssl.SSLError(), None])
        self.assertEqual([mock.call(cafile=path) for path in ("/missing.pem", "/damaged.pem", "/good.pem")],
                         fake.load_verify_locations.call_args_list)

    @unittest.skipUnless(any(os.path.isfile(path) for path in hosts.CERTIFICATE_FILES),
                         "this computer keeps none of the lists")
    def test_the_systems_own_list_really_loads(self):
        with mock.patch.object(hosts.ssl, "create_default_context", lambda: ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)):
            context = hosts.web_context()
        self.assertGreater(context.cert_store_stats()["x509_ca"], 0)
        self.assertEqual(ssl.CERT_REQUIRED, context.verify_mode)

    def failing_check(self, homebrew, code=20):
        seen = {}

        def urlopen(request, timeout, context):
            seen["context"] = context
            error = ssl.SSLCertVerificationError(1, "certificate verify failed")
            error.verify_code = code
            raise urllib.error.URLError(error)
        with mock.patch.object(hosts.urllib.request, "urlopen", urlopen), \
                mock.patch.object(hosts, "homebrew_python", lambda: homebrew), self.assertRaises(Problem) as caught:
            TerminalHost().web("GET", "https://example.com/", None, None)
        self.assertIs(hosts.web_context(), seen["context"])
        self.assertNotIn("Install Certificates", caught.exception.fix + caught.exception.why)
        return caught.exception.fix, caught.exception.why

    def test_the_fix_comes_first(self):
        why = "Plain couldn't check that the website is who it says it is."
        self.assertEqual(("Update your computer's web certificates, then run this again. "
                          "To update them, type: brew postinstall ca-certificates", why), self.failing_check(True))
        self.assertEqual(("Update your computer's web certificates, then run this again. "
                          "To see how, go to plain-lang.dev/help#certificates", why), self.failing_check(False))
        self.assertEqual(why, self.failing_check(False, code=19)[1])      # a work network's own certificate

    def test_a_bad_certificate_on_the_website_is_the_websites_problem(self):
        for code in (10, 18, 62):                  # run out, signed by itself, for another website
            with self.subTest(code=code):
                fix, why = self.failing_check(False, code=code)
                self.assertEqual("Check the address. If it's right, the website has to fix its certificate.", fix)
                self.assertIn("different website", why)

    def test_homebrews_python(self):
        for prefix, homebrew in (("/opt/homebrew/Cellar/python@3.15/3.15.0/Frameworks/Python.framework/Versions/3.15",
                                  True),
                                 ("/home/linuxbrew/.linuxbrew/Cellar/plain/0.1.0/libexec", True),
                                 ("/Library/Frameworks/Python.framework/Versions/3.13", False)):
            with self.subTest(prefix=prefix), mock.patch.object(hosts.sys, "base_prefix", prefix):
                self.assertEqual(homebrew, hosts.homebrew_python())


if __name__ == "__main__":
    unittest.main()
