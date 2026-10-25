"""The pick-a-fix-and-save screen, shared by plain run, plain fix and the REPL."""

import os
import re
import shutil
import sys

from .problems import layout


def say(text=""):
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def ideas_for(problem):
    """Plain's own checked ideas for a problem, at most 3, each as its lines (an idea can be a
    step plus its use)."""
    return [idea.split("\n") for idea in problem.ideas[:3]]


def idea_lines(ideas, indent=""):
    """The numbered ideas, ready to show, moved left by the indent of the line they replace
    (so an idea that moves a line right shows that)."""
    out = []
    for number, lines in enumerate(ideas, start=1):
        first, *more = [line[len(indent):] if line.startswith(indent) else line.lstrip() for line in lines]
        out.append(f"  {number}) {first.rstrip()}")
        out += [f"     {line.rstrip()}" for line in more]
    return out


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


def splice(text, number, new_lines):
    """Replace one line of the file, keeping each line's own newline, the BOM and any # note on it.

    A line ends at CR LF, a lone CR or LF, the same way Plain reads it."""
    bom = text.startswith("\ufeff")
    body = text[1:] if bom else text
    parts = re.split(r"(\r\n|\r|\n)", body)
    lines, ends = parts[0::2], parts[1::2] + [""]
    old, end = lines[number - 1], ends[number - 1]
    note = note_of(old)
    new = list(new_lines)
    if note and not note_of(new[0]):
        new[0] = new[0].rstrip() + "  # " + note
    between = end or next((e for e in reversed(ends[:number - 1]) if e), "\n")
    lines[number - 1:number] = new
    ends[number - 1:number] = [between] * (len(new) - 1) + [end]
    return ("\ufeff" if bom else "") + "".join(line + e for line, e in zip(lines, ends))


def note_of(line):
    from .source import tokenize
    from .problems import Problem
    try:
        _, note, _ = tokenize(line)
    except Problem:
        return None
    return note


def write_atomic(path, text):
    temp = path.with_name(path.name + ".tmp")
    try:
        with open(temp, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(temp, path)
    except OSError:
        temp.unlink(missing_ok=True)
        raise


def cant_save(path):
    return f'Check that you\'re allowed to change "{path.name}" and its folder. Plain couldn\'t save it.'


def fix_file(path, text, program, interactive=True, ask=input):
    """Go through each problem, offer checked ideas, save the ones you pick.

    Returns (program, text) when the file is clean, or (None, text) when lines are left."""
    from .parser import Reader
    from .problems import layout_all

    def answer(prompt):
        try:
            return ask(prompt).strip()
        except EOFError:      # Ctrl-D, or the end of what was typed: skip
            say()
            return ""

    if not interactive:
        say(layout_all(program.problems, path.name, program.source_lines))
        return None, text
    backup_made = False
    skipped = set()
    while True:
        waiting = [p for p in program.problems if (p.line, p.fix) not in skipped]
        if not waiting:
            break
        problem = waiting[0]
        say(layout(problem, path.name, program.source_lines))
        say()
        ideas = ideas_for(problem)
        if not ideas:
            say("Plain has no ideas for this one. Press Enter to skip it.")
            answer("")
            skipped.add((problem.line, problem.fix))
            continue
        for line in idea_lines(ideas, indent_of(program.source_lines[problem.line - 1])):
            say(line)
        choices = "1" if len(ideas) == 1 else ", ".join(str(n) for n in range(1, len(ideas))) + f" or {len(ideas)}"
        picked = answer(f"\nType {choices} to use it, or press Enter to skip: ")
        if not picked.isdigit() or not 1 <= int(picked) <= len(ideas):
            skipped.add((problem.line, problem.fix))
            continue
        chosen = ideas[int(picked) - 1]
        old = program.source_lines[problem.line - 1].strip()
        new_text = splice(text, problem.line, chosen)
        try:
            if not backup_made:
                shutil.copyfile(path, path.with_name(path.name + ".bak"))   # the file exactly as it was
                backup_made = True
            write_atomic(path, new_text)
        except OSError:
            say(cant_save(path))
            return None, text
        text = new_text
        say(f"Saved line {problem.line}. Your old line was: {old}")
        program = Reader().read(text)
    if backup_made:
        say(f"Your file from before is in {path.name}.bak.")
    if program.problems:
        left = len(program.problems)
        lines = "1 line" if left == 1 else f"{left} lines"
        say(f"{path.name} still has {lines} Plain can't follow, so it won't run yet. "
            f"When you're ready, run: plain fix {path.name}")
        return None, text
    return program, text
