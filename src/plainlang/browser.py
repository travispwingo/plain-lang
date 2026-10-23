"""BrowserHost: running Plain in the playground at plain-lang.dev, inside a Pyodide Web Worker.

`ask` and `wait` block the worker (never the page) on shared memory. The page wakes the
worker when you answer, or when you press Stop. Web requests use a synchronous request
inside the worker, so the browser's rules about other websites (CORS) apply.
"""

import json
import random
from datetime import datetime
from pathlib import Path

import js  # noqa: F401  (only exists under Pyodide)

from .interpreter import Run
from .parser import Reader
from .problems import Problem, layout, layout_all

FOLDER = Path("/home/pyodide/files")
FLUSH_EVERY = 0.05     # seconds between batches of shown lines
KEEP_LINES = 2000      # the page keeps at most this many lines anyway
WAITING, ANSWERED, STOPPED = 0, 1, 2


def post(kind, **payload):
    js.plainPost(kind, json.dumps(payload))


class BrowserHost:
    can_use_any_folder = False

    def __init__(self, run_id, seed=None):
        self.run_id = run_id
        self.folder = FOLDER
        self.random = random.Random(seed)
        self.buffer = []
        self.last_flush = self.clock()

    # Showing -------------------------------------------------------------------

    def show(self, text):
        self.buffer.append(text)
        if self.clock() - self.last_flush >= FLUSH_EVERY:
            self.flush()

    def flush(self):
        if self.buffer:
            lines = self.buffer
            if len(lines) > KEEP_LINES:
                lines = ["(earlier lines hidden)"] + lines[-KEEP_LINES:]
            post("show", text="\n".join(lines), run=self.run_id)
            self.buffer = []
        self.last_flush = self.clock()

    def clear(self):
        self.flush()
        post("clear", run=self.run_id)

    # Asking and waiting ----------------------------------------------------------

    def ask(self, question):
        self.flush()
        ctrl, data = js.plainCtrl, js.plainData
        js.Atomics.store(ctrl, 0, WAITING)
        post("ask", text=question, run=self.run_id)
        js.Atomics.wait(ctrl, 0, WAITING)
        state = js.Atomics.load(ctrl, 0)
        if state == STOPPED:
            stopped()
        length = js.Atomics.load(ctrl, 1)
        answer = bytes(data.subarray(0, length).to_py()).decode("utf-8", errors="replace")
        js.Atomics.store(ctrl, 0, WAITING)
        return answer

    def wait(self, seconds):
        self.flush()
        ctrl = js.plainCtrl
        js.Atomics.store(ctrl, 0, WAITING)
        js.Atomics.wait(ctrl, 0, WAITING, max(0, seconds) * 1000)
        if js.Atomics.load(ctrl, 0) == STOPPED:
            stopped()

    # Time ------------------------------------------------------------------------

    def clock(self):
        return js.performance.now() / 1000

    def now(self):
        d = js.Date.new()   # the browser's local time, not UTC
        return datetime(d.getFullYear(), d.getMonth() + 1, d.getDate(),
                        d.getHours(), d.getMinutes(), d.getSeconds())

    # The web ---------------------------------------------------------------------

    def web(self, method, url, body, kind):
        from .hosts import Reply
        if url.lower().startswith("http://"):
            raise Problem(f'Change "http://" to "https://" at the start of the address.',
                          "Pages in a browser can only read addresses that start with https://.")
        self.flush()
        request = js.XMLHttpRequest.new()
        try:
            request.open(method, url, False)
            request.responseType = "arraybuffer"
            if body is not None:
                request.setRequestHeader("Content-Type", kind or "text/plain")
                from pyodide.ffi import to_js
                request.send(to_js(body))
            else:
                request.send()
        except Exception:
            raise self.unreachable(url)
        if request.status == 0:
            raise self.unreachable(url)
        response = request.response
        content = bytes(js.Uint8Array.new(response).to_py()) if response else b""
        return Reply(request.status, request.getResponseHeader("Content-Type") or "", content)

    def unreachable(self, url):
        site = url.split("://", 1)[-1].split("/", 1)[0]
        return Problem(
            "Check your internet connection, then run your program again.",
            f"Plain couldn't read {site} from this page. Some websites don't let pages in a browser "
            "read them. If that's the case, run your program on your computer with plain run "
            "(see plain-lang.dev/install).")


def stopped():
    """Stop pressed. Clear Pyodide's interrupt flag too, so the stop happens only once."""
    js.Atomics.store(js.plainInterrupt, 0, 0)
    raise KeyboardInterrupt


def settle(action):
    """Do a last step after a stop, even if a second stop signal arrives meanwhile."""
    for _ in range(3):
        try:
            js.Atomics.store(js.plainInterrupt, 0, 0)
            action()
            return
        except KeyboardInterrupt:
            continue


# The worker calls these -------------------------------------------------------------

def reset_folder(files):
    FOLDER.mkdir(parents=True, exist_ok=True)
    for path in FOLDER.iterdir():
        if path.is_file():
            path.unlink()
    for name, text in json.loads(files).items():
        target = FOLDER / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


def folder_files():
    out = {}
    for path in sorted(FOLDER.rglob("*")):
        if path.is_file():
            try:
                out[str(path.relative_to(FOLDER))] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
    return out


def problem_json(problem, lines):
    return {"line": problem.line, "col": problem.col, "end": problem.end,
            "text": layout(problem, "your program", lines),
            "ideas": [idea for idea in problem.ideas][:3]}


def run_in_page(source, files, run_id, seed=None):
    """Check and run a program. Everything it shows goes to the page as messages."""
    reset_folder(files)
    program = Reader().read(source)
    if program.problems:
        post("problems", run=run_id,
             text=layout_all(program.problems, "your program", program.source_lines),
             problems=[problem_json(p, program.source_lines) for p in program.problems[:5]])
        post("done", run=run_id, files=folder_files())
        return
    host = BrowserHost(run_id, seed if isinstance(seed, int) else None)
    try:
        Run(program, host).run()
        host.flush()
    except KeyboardInterrupt:
        host.buffer.append("Stopped.")
        settle(host.flush)
    except Problem as problem:
        settle(host.flush)
        post("problems", run=run_id, text=layout(problem, "your program", program.source_lines),
             problems=[problem_json(problem, program.source_lines)])
    settle(lambda: post("done", run=run_id, files=folder_files()))


def check_in_page(source):
    """Problems for the editor, without running anything."""
    program = Reader().read(source)
    return json.dumps([problem_json(p, program.source_lines) for p in program.problems[:5]])
