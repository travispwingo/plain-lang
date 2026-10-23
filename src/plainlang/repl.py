"""Type Plain one line at a time. Names and your own steps last until you leave."""

import re
import sys
from pathlib import Path

from . import __version__
from .interpreter import Run
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


def howto_text(howto):
    return "how to " + howto.phrase.template.replace("{", "(").replace("}", ")")


class Session:
    def __init__(self, options, ask=input, show=None, host=None):
        from .hosts import TerminalHost
        from .parser import Program
        self.options = options
        self.ask = ask
        self.show = show or (lambda text: (sys.stdout.write(text + "\n"), sys.stdout.flush()))
        self.host = host or TerminalHost(seed=options.get("seed"))
        self.terminal = sys.stdin.isatty() and sys.stdout.isatty()   # Claude helps only in a terminal
        self.names, self.howtos, self.origins = set(), [], {}
        self.howto_lines = {}    # each of your how-tos -> the lines of the step that wrote it
        self.saved = []          # (text, how-tos it wrote) for every step that worked, for :save
        self.notes = set()
        self.explained_steps = False
        empty = Program([], [], [], set(), [], {}, [])
        self.run = SessionRun(empty, self.host)

    def loop(self):
        self.show(WELCOME)
        try:
            import readline  # noqa: F401  (gives the prompt a history)
        except ImportError:
            pass
        while True:
            try:
                line = self.ask("plain> ")
            except EOFError:
                self.show("")
                return 0
            except KeyboardInterrupt:
                self.show("")
                self.show("Type :quit to leave.")
                continue
            if not line.strip():
                continue
            if line.strip().lower() in ("quit", "exit", ":quit", ":q"):
                return 0
            if line.strip().startswith(":"):
                self.safely(self.command, line.strip())
                continue
            chunk = [line]
            if self.needs_steps(line):
                if not self.explained_steps:
                    self.show(STEPS_UNDER)
                    self.explained_steps = True
                while chunk:
                    try:
                        more = self.ask("  ...> ")
                    except EOFError:
                        break
                    except KeyboardInterrupt:
                        self.show("")
                        self.show("Cancelled. Those steps didn't run.")
                        chunk = []
                        break
                    if not more.strip():
                        break
                    chunk.append(more)
            if chunk:
                self.safely(self.enter, chunk)

    def safely(self, do, what):
        """Ctrl-C while Plain works on a line (waiting for Claude, say) stops that line only."""
        try:
            do(what)
        except KeyboardInterrupt:
            self.show("")
            self.show("Stopped.")

    def needs_steps(self, line):
        from .source import Line, looks_like_header, tokenize
        try:
            tokens, _, _ = tokenize(line)
        except Problem:
            return False
        return bool(tokens) and looks_like_header(Line(1, 0, line, tokens))

    def reader(self, leave_out=()):
        from .parser import Reader
        return Reader(known_names=self.names, known_howtos=[h for h in self.howtos if h not in leave_out],
                      known_origins=self.origins)

    def enter(self, chunk):
        text = "\n".join(chunk) + "\n"
        program = self.reader().read(text)
        # A how-to you write again replaces the one with the same wording from before.
        shapes = {h.phrase.shape for h in program.howtos if h not in self.howtos}
        replaced = [h for h in self.howtos if h.phrase.shape in shapes]
        if replaced:
            program = self.reader(leave_out=replaced).read(text)
        if program.problems:
            problem = program.problems[0]
            if len(chunk) == 1:
                if self.value_line(chunk[0]) is not None:
                    return
                problem = self.value_problem(chunk[0], problem) or problem
            self.show(self.message(problem, program.source_lines, len(chunk)))
            self.offer_ideas(chunk, program, problem)
            return
        if replaced:
            self.saved = [(saved, made) for saved, made in self.saved if not any(h in replaced for h in made)]
            for howto in replaced:
                self.show(f'Replaced your earlier "{howto_text(howto)}".')
        made = [h for h in program.howtos if h not in self.howtos]
        for howto in made:
            self.howto_lines[howto] = program.source_lines
        self.names |= program.names
        self.howtos = program.howtos
        self.origins.update(program.origins)
        self.run.program = program
        try:
            self.run.run()
            self.saved.append((text, made))
        except Problem as problem:
            self.show(self.running_message(problem, program, len(chunk)))
        except KeyboardInterrupt:
            self.show("Stopped.")

    def offer_ideas(self, chunk, program, problem):
        """Plain's own ideas, then Claude's in a terminal. Picking one runs it."""
        from .fixer import gather_ideas, idea_lines, indent_of
        options = dict(self.options, ai=self.options.get("ai") and self.terminal)
        ideas = gather_ideas(program, problem, Path("your step"), options, self.notes,
                             read=lambda text: self.reader().read(text), phrases=":phrases", tell=self.show)
        if not ideas:
            return
        for line in idea_lines(ideas, indent_of(chunk[problem.line - 1])):
            self.show(line)
        try:
            pick = self.ask("Type a number to use it, or press Enter to skip: ").strip()
        except (EOFError, KeyboardInterrupt):
            self.show("")
            return
        if pick.isdigit() and 1 <= int(pick) <= len(ideas):
            fixed = list(chunk)
            fixed[problem.line - 1:problem.line] = ideas[int(pick) - 1][0]
            self.enter(fixed)

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

    def value_problem(self, line, step_problem):
        """The problem with a line meant as a value, like "prise times 2": it starts with a
        number or with (nearly) one of your names, and its first word isn't a step."""
        from dataclasses import replace
        from .source import tokenize
        from .suggest import closest_name
        try:
            tokens, _, _ = tokenize(line)
        except Problem:
            return None
        first = tokens[0] if tokens else None
        if first is None or step_problem.col != first.col:
            return None
        known = [" ".join(name) for name in self.names]
        near_a_name = first.kind == "word" and (
            any(name.split()[0] == first.norm for name in known) or closest_name(first.norm, known))
        if first.kind != "number" and not near_a_name:
            return None
        shown = self.reader().read("show " + line + "\n").problems
        if not shown or shown[0].line != 1:
            return None
        problem, cut = shown[0], len("show ")
        return replace(problem,
                       col=None if problem.col is None else max(problem.col - cut, 0),
                       end=None if problem.end is None else max(problem.end - cut, 1),
                       ideas=[idea[cut:] for idea in problem.ideas if idea.startswith("show ")],
                       try_lines=[t[cut:] if t.startswith("show ") else t for t in problem.try_lines])

    def message(self, problem, lines, count, where="your step"):
        text = layout(problem, where, lines)
        if count == 1:
            text = text.replace("your step, line 1", "your step", 1)
        # The advice is about a file. Here, earlier names come from earlier steps.
        text = text.replace("Type plain phrases", "Type :phrases")
        text = text.replace("Nothing in your program", "Nothing in your steps")
        return re.sub(r'You set "([^"]+)" on line \d+\.',
                      lambda m: f'You set "{m.group(1)}" in an earlier step.'
                      if tuple(m.group(1).split()) in self.origins else m.group(0), text)

    def running_message(self, problem, program, count):
        """A problem while running. One inside a how-to shows that how-to's own line."""
        source, howto = self.run.problem_from or (None, None)
        if source is problem and howto in self.howto_lines:
            return self.message(problem, self.howto_lines[howto], 0, f'your "{howto_text(howto)}"')
        return self.message(problem, program.source_lines, count)

    def command(self, line):
        word, _, rest = line[1:].partition(" ")
        rest = rest.strip()
        if word == "help":
            self.show(HELP)
        elif word == "phrases":
            from .cli import phrases
            phrases(rest.split(), again=":phrases")
        elif word == "names":
            from .values import show_inline
            if not self.run.globals:
                self.show("You haven't set any names yet.")
            for name, value in self.run.globals.items():
                self.show(f"  {' '.join(name)}: {show_inline(value)}")
        elif word == "run":
            if not rest:
                self.show("Type a file name after :run, like this: :run hello.plain")
                return
            from .cli import open_and_run
            open_and_run("run", rest, self.options)
        elif word == "save":
            if not rest:
                self.show("Type a file name after :save, like this: :save my program.plain")
                return
            self.save(Path(rest if rest.endswith(".plain") else rest + ".plain"))
        else:
            self.show(f'Type :help to see what you can do. Plain has no command called ":{word}".')

    def save(self, path):
        if path.is_dir():
            self.show(f'Choose a different name after :save. "{path}" is a folder.')
            return
        if not path.parent.is_dir():
            self.show(f'Check the folder name "{path.parent}". There\'s no folder with that name here.')
            return
        try:
            path.write_text("".join(text for text, _ in self.saved), encoding="utf-8")
        except OSError:
            self.show(f'Check that you\'re allowed to change files in that folder. Plain couldn\'t save "{path.name}".')
            return
        self.show(f"Saved {len(self.saved)} steps to {path.name}.")


class SessionRun(Run):
    """Runs your steps, and remembers which of your how-tos the last problem came from."""

    def __init__(self, program, host):
        super().__init__(program, host)
        self.problem_from = None     # (problem, the how-to that was running, or None)

    def exec(self, stmt):
        try:
            super().exec(stmt)
        except Problem as problem:
            if self.problem_from is None or self.problem_from[0] is not problem:
                self.problem_from = (problem, self.frames[-1][1] if self.frames else None)
            raise


def repl(options):
    return Session(options).loop()
