"""Hosts: where a program's showing, asking, waiting and web requests actually happen.

Only this module (and browser.py) talks to the outside world, so the same core runs in a
terminal, in tests and in the browser.
"""

import http.client
import os
import random
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .problems import Problem

USER_AGENT = "Plain/0.1 (+https://plain-lang.dev)"
WEB_TIMEOUT = 15


@dataclass(frozen=True, slots=True)
class Reply:
    status: int
    kind: str        # the content type
    body: bytes


class TerminalHost:
    can_use_any_folder = True

    def __init__(self, folder=None, seed=None):
        self.folder = Path(folder or Path.cwd())
        self.random = random.Random(seed)
        self.started = time.monotonic()

    def show(self, text):
        try:
            print(text, flush=True)
        except BrokenPipeError:
            # Whatever was reading the output (like "head") has stopped, so stop quietly.
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
            from .interpreter import StopProgramSignal
            raise StopProgramSignal() from None

    def ask(self, question):
        try:
            return input(question.rstrip() + " ")
        except EOFError:
            raise Problem("Run this program where you can type answers.",
                          "It asked a question, but nothing was typed.")

    def wait(self, seconds):
        time.sleep(seconds)

    def clear(self):
        if sys.stdout.isatty():
            print("\033[2J\033[H", end="", flush=True)

    def clock(self):
        return time.monotonic()

    def now(self):
        return datetime.now()

    def web(self, method, url, body, kind):
        request = urllib.request.Request(url, data=body, method=method,
                                         headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
        if kind:
            request.add_header("Content-Type", kind)
        try:
            with urllib.request.urlopen(request, timeout=WEB_TIMEOUT) as response:
                return Reply(response.status, response.headers.get("Content-Type", ""), response.read())
        except urllib.error.HTTPError as error:
            return Reply(error.code, error.headers.get("Content-Type", "") if error.headers else "",
                         error.read() if error.fp else b"")
        except urllib.error.URLError as error:
            reason = error.reason
            if isinstance(reason, ssl.SSLCertVerificationError):
                raise Problem(
                    "Install your computer's web certificates, then run this again.",
                    "Plain couldn't check that the website is who it says it is. On a Mac, run "
                    "\"Install Certificates.command\" in your Python folder.")
            if isinstance(reason, TimeoutError):
                raise Problem("Check your internet connection, then run this again.",
                              f"The website didn't answer within {WEB_TIMEOUT} seconds.")
            raise Problem("Check your internet connection and the address, then run this again.",
                          "Plain couldn't reach the website.")
        except TimeoutError:
            raise Problem("Check your internet connection, then run this again.",
                          f"The website didn't answer within {WEB_TIMEOUT} seconds.")
        except (http.client.HTTPException, OSError):
            raise Problem("Check your internet connection and the address, then run this again.",
                          "The website stopped answering before it finished.")
        except ValueError:
            raise Problem("Check the web address.", "Plain couldn't use it as an address.")


class TestHost:
    """A host for tests: scripted answers, a transcript, a fake clock and web fixtures."""

    can_use_any_folder = False

    def __init__(self, folder, answers=(), seed=0, web=None, now=None):
        self.folder = Path(folder)
        self.answers = list(answers)
        self.random = random.Random(seed)
        self.fixtures = dict(web or {})
        self.transcript = []
        self.time = 0.0
        self.fixed_now = now or datetime(2026, 10, 23, 14, 5)
        self.requests = []

    def show(self, text):
        self.transcript.append(text)

    def ask(self, question):
        if not self.answers:
            raise Problem("Add more answers to the test.",
                          "The program asked a question but the test ran out of answers.")
        answer = self.answers.pop(0)
        self.transcript.append(f"{question.rstrip()} {answer}")
        return answer

    def wait(self, seconds):
        self.time += seconds

    def clear(self):
        self.transcript.append("(the screen was cleared)")

    def clock(self):
        return self.time

    def now(self):
        return self.fixed_now

    def web(self, method, url, body, kind):
        self.requests.append((method, url, body))
        fixture = self.fixtures.get(f"{method} {url}") or self.fixtures.get(url)
        if fixture is None:
            raise Problem("Check your internet connection and the address, then run this again.",
                          "Plain couldn't reach the website.")
        body = fixture.get("body", "")
        if not isinstance(body, (str, bytes)):
            import json
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode()
        return Reply(fixture.get("status", 200), fixture.get("kind", "application/json"), body)

    def output(self):
        return "\n".join(self.transcript) + ("\n" if self.transcript else "")
