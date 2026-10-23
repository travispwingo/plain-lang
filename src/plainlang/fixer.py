"""The pick-a-fix-and-save screen, shared by plain run, plain fix and the REPL."""

import os
import sys

from .problems import layout


def say(text=""):
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def gather_ideas(program, problem, path, options, notes):
    """Plain's own checked ideas first, then Claude's to fill the list up to 3."""
    ideas = [([idea], "", [], "Plain") for idea in problem.ideas]
    if len(ideas) >= 3 or not options.get("ai") or problem.running or problem.line is None:
        return ideas[:3]
    from . import ai
    first_line = problem.line
    try:
        say(f"Asking Claude for ideas. This sends {path.name} to Anthropic, "
            "which charges your account a small amount for each request.")
        answer, (first, last) = ai.ask_claude(program, problem, path.name)
    except ai.Unavailable as reason:
        if str(reason) not in notes:
            notes.add(str(reason))
            say(str(reason))
        return ideas[:3]
    if answer.get("unsupported") and not answer.get("rewrites"):
        say(f"Claude says Plain can't do this yet: {answer['unsupported']}. "
            "To see what Plain can do, type: plain phrases")
    for new, why, effects in ai.checked_ideas(program, problem, answer, path.parent):
        if len(ideas) >= 3:
            break
        if any(new == idea[0] for idea in ideas):
            continue
        ideas.append((new, why, effects, "Claude"))
    return ideas


def splice(text, number, new_lines):
    """Replace one line of the file, keeping its newline style, BOM and any # note on it."""
    bom = text.startswith("﻿")
    body = text[1:] if bom else text
    newline = "\r\n" if "\r\n" in body else "\n"
    lines = body.replace("\r\n", "\n").split("\n")
    old = lines[number - 1]
    note = note_of(old)
    new = list(new_lines)
    if note and not note_of(new[0]):
        new[0] = new[0].rstrip() + "  # " + note
    lines[number - 1:number] = new
    return ("﻿" if bom else "") + newline.join(lines)


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
    with open(temp, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    os.replace(temp, path)


def fix_file(path, text, program, options, interactive=True, ask=input):
    """Go through each problem, offer checked ideas, save the ones you pick.

    Returns (program, text) when the file is clean, or (None, text) when lines are left."""
    from .parser import Reader
    from .problems import layout_all
    if not interactive:
        say(layout_all(program.problems, path.name, program.source_lines))
        return None, text
    backup_made = False
    notes = set()
    skipped = set()
    while True:
        waiting = [p for p in program.problems if (p.line, p.fix) not in skipped]
        if not waiting:
            break
        problem = waiting[0]
        say(layout(problem, path.name, program.source_lines))
        say()
        ideas = gather_ideas(program, problem, path, options, notes)
        if not ideas:
            say("Plain has no ideas for this one. Press Enter to skip it.")
            answer = ask("")
            skipped.add((problem.line, problem.fix))
            continue
        for number, (lines, why, effects, source) in enumerate(ideas, start=1):
            label = f"(from {source})" if source == "Claude" else ""
            extra = "".join(f" ({e})" for e in effects)
            first = lines[0].strip()
            say(f"  {number}) {first}    {label}{extra}".rstrip())
            for more in lines[1:]:
                say(f"     {more.rstrip()}")
            if why:
                say(f"     {why}")
        choices = "1" if len(ideas) == 1 else ", ".join(str(n) for n in range(1, len(ideas))) + f" or {len(ideas)}"
        answer = ask(f"\nType {choices} to use it, or press Enter to skip: ").strip()
        if not answer.isdigit() or not 1 <= int(answer) <= len(ideas):
            skipped.add((problem.line, problem.fix))
            continue
        chosen = ideas[int(answer) - 1][0]
        old = program.source_lines[problem.line - 1].strip()
        if not backup_made:
            backup = path.with_name(path.name + ".bak")
            backup.write_text(text, encoding="utf-8")
            backup_made = True
        text = splice(text, problem.line, chosen)
        write_atomic(path, text)
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
