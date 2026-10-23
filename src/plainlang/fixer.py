"""The pick-a-fix-and-save screen, shared by plain run, plain fix and the REPL."""

import os
import re
import sys

from .problems import layout


def say(text=""):
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def gather_ideas(program, problem, path, options, notes, read=None, phrases="plain phrases", tell=say):
    """Plain's own checked ideas first, then Claude's to fill the list up to 3.

    The REPL passes its own way to read a whole candidate program, to list Plain's phrases
    and to show a line."""
    ideas = [([idea], "", [], "Plain") for idea in problem.ideas]
    if len(ideas) >= 3 or not options.get("ai") or problem.running or problem.line is None \
            or not problem.ask_claude or about_layout(program, problem):
        return ideas[:3]
    from . import ai
    try:
        answer, _ = ai.ask_claude(program, problem, path.name, tell=tell)
    except ai.Unavailable as reason:
        if str(reason) not in notes:
            notes.add(str(reason))
            tell(str(reason))
        return ideas[:3]
    note = ai.unsupported_note(answer, program.source_lines[problem.line - 1])
    if note:
        tell(f"Claude says Plain can't do this yet: {note}. To see what Plain can do, type: {phrases}")
    for new, why, effects in ai.checked_ideas(program, problem, answer, path.parent, own_ideas=problem.ideas,
                                              own_file=path, read=read):
        if len(ideas) >= 3:
            break
        ideas.append((new, why, effects, "Claude"))
    return ideas


def about_layout(program, problem):
    """A problem with how far lines are moved to the right, which Claude isn't asked about."""
    from .source import build_blocks, read_lines
    _, found = build_blocks(read_lines("\n".join(program.source_lines)))
    return any((p.line, p.fix) == (problem.line, problem.fix) for p in found)


def idea_lines(ideas, indent=""):
    """The numbered ideas, ready to show, moved left by the indent of the line they replace
    (so an idea that moves a line right shows that)."""
    out = []
    for number, (lines, why, effects, source) in enumerate(ideas, start=1):
        label = f"(from {source})" if source == "Claude" else ""
        extra = "".join(f" ({e})" for e in effects)
        first, *more = [line[len(indent):] if line.startswith(indent) else line.lstrip() for line in lines]
        out.append(f"  {number}) {first.rstrip()}    {label}{extra}".rstrip())
        out += [f"     {line.rstrip()}" for line in more]
        if why:
            out.append(f"     {why}")
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


def fix_file(path, text, program, options, interactive=True, ask=input):
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
        chosen = ideas[int(picked) - 1][0]
        old = program.source_lines[problem.line - 1].strip()
        new_text = splice(text, problem.line, chosen)
        try:
            if not backup_made:
                path.with_name(path.name + ".bak").write_text(text, encoding="utf-8")
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
