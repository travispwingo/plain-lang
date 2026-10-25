"""Problems: what Plain tells you when it can't go on, laid out the same way every time.

1. file, line and the fix (starting with a verb)
2. your line with ^ marks under the part that's wrong
3. "Try this:" and the fixed lines, when there are any
4. "Why:" in one or two sentences
5. where to look in the docs, when Plain has no fix of its own
"""

from dataclasses import dataclass, field

MAX_SHOWN = 5
SITE = "plain-lang.dev"
HELP_ADDRESS = f"{SITE}/help"


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
    choices: list = field(default_factory=list)   # different fixes to choose from, each a list of lines
    examples: list = field(default_factory=list)  # phrases that might fit; not checked against your line
    # Where to look when Plain has no fix of its own: a sentence with a plain-lang.dev link, and the
    # words for `plain phrases` that list the same phrase ("" lists them all, None adds no command).
    docs: str | None = None
    look_up: str | None = None

    def __str__(self):
        return self.fix

    def at(self, line, col=None, end=None):
        """Fill in where the problem is, unless it already says."""
        if self.line is None:
            self.line = line
            if self.col is None:
                self.col, self.end = col, end
        return self


def layout(problem, file_name, source_lines, phrases="plain phrases"):
    """The message. `phrases` is how to list Plain's phrases where you are, or None in the
    playground, which has no command to type."""
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
    if len(problem.choices) > 1:
        out.append("Try one of these:")
        for k, choice in enumerate(problem.choices):
            if k:
                out.append("  or")
            out += ["    " + line for line in choice]
    elif problem.try_lines:
        out.append("Try this:")
        out += ["    " + line for line in problem.try_lines]
    if problem.examples:
        out.append("For example:")
        out += ["    " + line for line in problem.examples]
    if problem.why:
        why = problem.why
        out.append(f"Why: {why[:1].upper() + why[1:]}")
    if problem.docs:
        command = phrases is not None and problem.look_up is not None
        out.append(problem.docs + (f", or type: {phrases} {problem.look_up}".rstrip() if command else ""))
    return "\n".join(out)


def widen(text):
    """A Tab counts as 4 spaces."""
    return text.replace("\t", "    ")


def column(raw, col):
    """Where a column of the line as written lands once Tabs are shown as 4 spaces."""
    return len(widen(raw[:col])) + max(0, col - len(raw))


def layout_all(problems, file_name, source_lines, phrases="plain phrases"):
    """All problems found before running, at most MAX_SHOWN of them, with the footer."""
    shown = problems[:MAX_SHOWN]
    parts = [layout(p, file_name, source_lines, phrases) for p in shown]
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
