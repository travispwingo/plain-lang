"""Type Plain one line at a time. Names and your own steps last until you leave."""

import sys
from pathlib import Path

from . import __version__
from .problems import Problem, layout

WELCOME = (f"Plain {__version__}. Type a step, like show \"Hello\", and press Enter. "
           "Type :help for help, or :quit to leave.")
STEPS_UNDER = "(Type the steps that go under it. Press Enter on an empty line when you're done.)"
HELP = """Type a step and press Enter, like: show "Hello"
Type a value on its own to see it, like: 2 plus 3
A line like "repeat 3 times" needs steps under it. Type them, then press Enter on an empty line.

  :help            Show this help
  :phrases WORDS   Find Plain's phrases about WORDS
  :names           Show each name and its value
  :run FILE        Run a .plain file
  :save FILE       Save every step that worked as a .plain file
  :quit            Leave (quit, exit and Ctrl-D work too)"""


class Session:
    def __init__(self, options, ask=input, show=None, host=None):
        from .hosts import TerminalHost
        from .interpreter import Run
        from .parser import Program
        self.options = options
        self.ask = ask
        self.show = show or (lambda text: (sys.stdout.write(text + "\n"), sys.stdout.flush()))
        self.host = host or TerminalHost(seed=options.get("seed"))
        self.names, self.howtos, self.origins = set(), [], {}
        self.saved = []          # every chunk that worked, for :save
        self.explained_steps = False
        empty = Program([], [], [], set(), [], {}, [])
        self.run = Run(empty, self.host)

    def loop(self):
        self.show(WELCOME)
        try:
            import readline  # noqa: F401  (gives the prompt a history)
        except ImportError:
            pass
        while True:
            try:
                line = self.ask("plain> ")
            except (EOFError, KeyboardInterrupt):
                self.show("")
                return 0
            if not line.strip():
                continue
            if line.strip().lower() in ("quit", "exit", ":quit", ":q"):
                return 0
            if line.strip().startswith(":"):
                self.command(line.strip())
                continue
            chunk = [line]
            if self.needs_steps(line):
                if not self.explained_steps:
                    self.show(STEPS_UNDER)
                    self.explained_steps = True
                while True:
                    try:
                        more = self.ask("  ...> ")
                    except (EOFError, KeyboardInterrupt):
                        break
                    if not more.strip():
                        break
                    chunk.append(more)
            self.enter(chunk)

    def needs_steps(self, line):
        from .source import Line, looks_like_header, tokenize
        try:
            tokens, _, _ = tokenize(line)
        except Problem:
            return False
        return bool(tokens) and looks_like_header(Line(1, 0, line, tokens))

    def reader(self):
        from .parser import Reader
        return Reader(known_names=self.names, known_howtos=self.howtos, known_origins=self.origins)

    def enter(self, chunk):
        from .interpreter import StopProgramSignal
        text = "\n".join(chunk) + "\n"
        program = self.reader().read(text)
        if program.problems and len(chunk) == 1:
            value = self.value_line(chunk[0])
            if value is not None:
                return
        if program.problems:
            problem = program.problems[0]
            self.show(self.message(problem, program.source_lines, len(chunk)))
            if problem.ideas:
                for number, idea in enumerate(problem.ideas[:3], start=1):
                    self.show(f"  {number}) {idea.strip()}")
                pick = self.ask("Type a number to use it, or press Enter to skip: ").strip()
                if pick.isdigit() and 1 <= int(pick) <= len(problem.ideas[:3]):
                    fixed = list(chunk)
                    fixed[problem.line - 1] = problem.ideas[int(pick) - 1]
                    self.enter(fixed)
            return
        self.names |= program.names
        self.howtos = program.howtos
        self.origins.update(program.origins)
        self.run.program = program
        try:
            self.run.exec_body(program.statements)
            self.saved.append(text)
        except StopProgramSignal:
            self.saved.append(text)
        except Problem as problem:
            self.show(self.message(problem, program.source_lines, len(chunk)))
        except KeyboardInterrupt:
            self.show("Stopped.")

    def value_line(self, line):
        """A line that is only a value shows that value, like 2 plus 3."""
        from .parser import LineReader, make_view
        from .source import tokenize
        from .values import show_value
        try:
            tokens, _, _ = tokenize(line)
        except Problem:
            return None
        view = make_view(tokens)
        if not view:
            return None
        reader = self.reader()
        reader.main_names = set(self.names)
        reader.howtos, reader.howto_index = list(self.howtos), {}
        lr = LineReader(reader, view, self.names, set())
        readings = lr.check(0, len(view))
        if len(readings) != 1 or type(readings[0]).__name__ == "Bad":
            return None
        try:
            value = self.run.eval(readings[0])
        except Problem as problem:
            problem.line = problem.line or 1
            self.show(self.message(problem, [line], 1))
            return True
        self.show(show_value(value))
        return True

    def message(self, problem, lines, count):
        text = layout(problem, "your step", lines)
        if count == 1:
            text = text.replace("your step, line 1", "your step", 1)
        return text

    def command(self, line):
        word, _, rest = line[1:].partition(" ")
        rest = rest.strip()
        if word == "help":
            self.show(HELP)
        elif word == "phrases":
            from .cli import phrases
            phrases(rest.split())
        elif word == "names":
            from .values import show_inline
            if not self.run.globals:
                self.show("You haven't set any names yet.")
            for name, value in self.run.globals.items():
                self.show(f"  {' '.join(name)}: {show_inline(value)}")
        elif word == "run":
            from .cli import main
            main(["run", rest] if rest else ["run"])
        elif word == "save":
            if not rest:
                self.show("Type a file name after :save, like this: :save my program.plain")
                return
            path = Path(rest if rest.endswith(".plain") else rest + ".plain")
            path.write_text("".join(self.saved), encoding="utf-8")
            self.show(f"Saved {len(self.saved)} steps to {path.name}.")
        else:
            self.show(f'Type :help to see what you can do. Plain has no command called ":{word}".')


def repl(options):
    return Session(options).loop()
