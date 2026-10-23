"""Problems: what Plain tells you when it can't go on, laid out the same way every time.

1. file, line and the fix (starting with a verb)
2. your line with ^ marks under the part that's wrong
3. "Try this:" and the fixed lines, when there are any
4. "Why:" in one or two sentences
"""

from dataclasses import dataclass, field

MAX_SHOWN = 5
HELP_ADDRESS = "plain-lang.dev/help"


@dataclass(eq=False)
class Problem(Exception):
    fix: str
    why: str | None = None
    line: int | None = None
    col: int | None = None
    end: int | None = None
    try_lines: list[str] = field(default_factory=list)
    running: bool = False
    # Ideas are whole replacement lines that Plain checked work. The fixer offers them.
    ideas: list[str] = field(default_factory=list)
    focus: str | None = None      # text to underline, when the problem doesn't know its column
    guard: str | None = None      # a name to check is a number first (for "Try this")
    ask_claude: bool = False      # design section 7: Claude may offer ideas for this problem

    def __str__(self):
        return self.fix

    def at(self, line, col=None, end=None):
        """Fill in where the problem is, unless it already says."""
        if self.line is None:
            self.line = line
            if self.col is None:
                self.col, self.end = col, end
        return self


def layout(problem, file_name, source_lines):
    where = f"{file_name}, line {problem.line}" if problem.line else file_name
    if problem.running:
        where += ", while running"
    out = [f"{where}: {problem.fix}"]
    if problem.line and 0 < problem.line <= len(source_lines):
        raw = source_lines[problem.line - 1].rstrip("\n")
        out += ["", "    " + widen(raw)]
        if problem.col is not None:
            end = problem.end if problem.end and problem.end > problem.col else problem.col + 1
            start, stop = column(raw, problem.col), column(raw, end)
            out.append("    " + " " * start + "^" * (stop - start))
    if problem.try_lines:
        out.append("Try this:")
        out += ["    " + line for line in problem.try_lines]
    if problem.why:
        out.append(f"Why: {problem.why}")
    return "\n".join(out)


def widen(text):
    """A Tab counts as 4 spaces."""
    return text.replace("\t", "    ")


def column(raw, col):
    """Where a column of the line as written lands once Tabs are shown as 4 spaces."""
    return len(widen(raw[:col])) + max(0, col - len(raw))


def layout_all(problems, file_name, source_lines):
    """All problems found before running, at most MAX_SHOWN of them, with the footer."""
    shown = problems[:MAX_SHOWN]
    parts = [layout(p, file_name, source_lines) for p in shown]
    count = len(problems)
    things = "1 thing" if count == 1 else f"{count} things"
    footer = f"Plain found {things} to fix, so it hasn't run your program yet."
    if count > MAX_SHOWN:
        footer += f" Here are the first {MAX_SHOWN}."
    return "\n\n".join(parts) + "\n\n" + footer


PLAIN_WENT_WRONG = (
    f"Please tell us about this at {HELP_ADDRESS}, and include your program and this message.\n"
    "Why: Plain itself went wrong. This is a mistake in Plain, not in your program."
)


def things(count, word):
    return f"1 {word}" if count == 1 else f"{count} {word}s"
