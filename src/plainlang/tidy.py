"""plain explain (how Plain reads each line) and plain tidy (main words, 4-space steps,
your own steps at the end)."""

import re

from . import nodes as N
from .parser import start_of
from .source import normalize

EXPLAIN_WIDTH = 44


def line_readings(statements, out=None):
    """{line number: how Plain reads that line, in main words}"""
    out = {} if out is None else out
    for stmt in statements:
        if isinstance(stmt, N.If):
            for index, (check, body) in enumerate(stmt.branches):
                number = stmt.branch_lines[index] if index < len(stmt.branch_lines) else stmt.line
                if index == 0:
                    out[number] = "if " + check.canonical()
                    if body and body[0].line == number:   # one-line form
                        out[number] += " then " + body[0].canonical()
                        continue
                else:
                    out[number] = "otherwise" if check is None else "otherwise if " + check.canonical()
                    if body and body[0].line == number:   # one-line form: otherwise show "lose"
                        joiner = " " if check is None else " then "
                        out[number] += joiner + body[0].canonical()
                        continue
                line_readings(body, out)
            continue
        if isinstance(stmt, N.ErrorBlock):
            line_readings(stmt.body, out)
            continue
        out[stmt.line] = stmt.canonical()
        for attr in ("body", "fallback"):
            if hasattr(stmt, attr):
                line_readings(getattr(stmt, attr), out)
    return out


LEFT_OUT = "(Plain leaves this line out)"


def explain(program):
    readings = line_readings(program.statements)
    for number in getattr(program, "left_out", []):
        readings[number] = LEFT_OUT    # "end", "end if", "end repeat" and "end try"
    lines = []
    for number in sorted(readings):
        raw = program.source_lines[number - 1].rstrip().expandtabs(4)   # keep the indent: it shows what belongs where
        left = f"{number:>3}  {raw}"
        if len(left) <= EXPLAIN_WIDTH - 2:
            lines.append(left.ljust(EXPLAIN_WIDTH) + readings[number])
        else:
            lines.append(left)
            lines.append(" " * EXPLAIN_WIDTH + readings[number])
    return "\n".join(lines)


def collect_edits(statements, edits=None):
    """{line number: [(col, end, new words)]} for every synonym Plain replaced with its main word."""
    edits = {} if edits is None else edits
    for stmt in statements:
        for edit in stmt.synonym_edits:
            edits.setdefault(stmt.line, []).append(edit)
        if isinstance(stmt, N.If):
            # Each "otherwise" line keeps its own edits.
            for number, extra in getattr(stmt, "branch_edits", {}).items():
                edits.setdefault(number, []).extend(extra)
            for index, (check, body) in enumerate(stmt.branches):
                number = stmt.branch_lines[index] if index < len(stmt.branch_lines) else stmt.line
                for node in nodes_of(check):
                    for edit in getattr(node, "syn", []) + rewrite(node):
                        edits.setdefault(number, []).append(edit)
                collect_edits(body, edits)
            continue
        for node in nodes_of(stmt):
            for edit in getattr(node, "syn", []) + rewrite(node):
                edits.setdefault(stmt.line, []).append(edit)
        if isinstance(stmt, N.Repeat):
            edits.setdefault(stmt.line, [])
            if stmt.kind == "times" and N.covers_arithmetic(stmt.count):
                edits[stmt.line].append(Rewrite(stmt.count, "brackets"))   # repeat (2 times 3) times
        children = []
        if isinstance(stmt, N.If):
            children = [body for _, body in stmt.branches]
        elif isinstance(stmt, (N.Repeat, N.HowTo, N.ErrorBlock)):
            children = [stmt.body]
        elif isinstance(stmt, N.Try):
            children = [stmt.body, stmt.fallback]
        for body in children:
            collect_edits(body, edits)
    return edits


class Rewrite:
    """A change to a whole part of a line, worked out from the words as you wrote them: brackets
    around what "rounded" covers (change 1), or a "not" folded into its check (change 13)."""

    def __init__(self, node, kind):
        self.node, self.kind = node, kind
        self.col, self.end = node.col, node.end


def rewrite(node):
    if isinstance(node, N.Not) and N.flipped(node.value) is not None and not N.is_negative(node.value):
        return [Rewrite(node, "fold")]
    if isinstance(node, N.Postfix) and N.covers_arithmetic(node.value):
        return [Rewrite(node.value, "brackets")]
    return []


def resolve(raw, edits):
    """Turn each Rewrite into an ordinary (col, end, new words) edit. Edits inside a rewritten part
    are done as part of it, smallest parts first."""
    plain = [e for e in edits if not isinstance(e, Rewrite)]
    for r in sorted((e for e in edits if isinstance(e, Rewrite)), key=lambda r: r.end - r.col):
        col = start_of(raw, r.col)
        inner = [e for e in plain if col <= e[0] and e[1] <= r.end]
        plain = [e for e in plain if e not in inner]
        if r.kind == "brackets":
            parts = [(col, col, "("), (r.end, r.end, ")")]
        else:
            parts = fold_parts(raw, r.node)
        text = raw[col:r.end]
        for a, b, words in sorted(inner + parts, reverse=True):
            text = text[:a - col] + words + text[b - col:]
        plain.append((col, r.end, text))
    return plain


def fold_parts(raw, node):
    """The changes that fold "not" into its check: not score is 5 becomes score is not 5."""
    after_not = re.match(r"not\s*", raw[node.col:], flags=re.IGNORECASE).end()
    parts = [(node.col, node.col + after_not, "")]
    check = node.value
    if isinstance(check, N.Paren):
        opening = re.match(r"\(\s*", raw[check.col:]).end()
        closing = len(raw[:check.end - 1]) - len(raw[:check.end - 1].rstrip())
        parts = [(node.col, check.col + opening, ""), (check.end - 1 - closing, check.end, "")]
        check = check.inner
    opposite = N.flipped(check)
    match check:
        case N.Compare():
            parts.append((check.left.end, check.right.col,
                          " " + N.comparison_words(opposite.op, opposite.plural) + " "))
        case N.TypeCheck():
            stop = check.arg.col if check.arg is not None else check.end
            words = opposite.canonical()[len(opposite.value.canonical()):]
            if check.arg is not None:
                words = words[:len(words) - len(check.arg.canonical())]
            parts.append((check.value.end, stop, words))
        case N.Between():
            verb = ("are" if check.plural else "is") + (" not" if opposite.negated else "")
            parts.append((check.value.end, check.low.col, f" {verb} between "))
    return parts


def nodes_of(thing):
    if isinstance(thing, N.Node):
        yield thing
        for value in vars(thing).values():
            yield from nodes_of(value)
    elif isinstance(thing, N.Statement):
        for key, value in vars(thing).items():
            if key not in ("body", "fallback", "branches"):
                yield from nodes_of(value)
        if isinstance(thing, N.If):
            for check, _ in thing.branches:
                yield from nodes_of(check)
    elif isinstance(thing, (list, tuple)):
        for item in thing:
            yield from nodes_of(item)
    elif isinstance(thing, dict):
        for item in thing.values():
            yield from nodes_of(item)


def tidy(text, program):
    """Returns (new text, list of changes in words). The file keeps its BOM and line endings."""
    bom, crlf = text.startswith("\ufeff"), "\r\n" in text
    lines = normalize(text).split("\n")
    edits = collect_edits(program.statements)
    changes = []
    depth = {}
    bare_loops = set()

    def walk(code_lines, level):
        for line in code_lines:
            depth[line.number] = level
            walk(line.body, level + 1)

    walk(program.lines, 0)
    for stmt in all_statements(program.statements):
        if isinstance(stmt, N.Repeat):
            raw = lines[stmt.line - 1].lstrip().lower()
            if raw.startswith(("for ", "while ", "until ")):
                bare_loops.add(stmt.line)

    out = list(lines)
    deleted = []
    for number in getattr(program, "left_out", []):
        # An "end" line goes, but a note on it stays, on a line of its own.
        raw = lines[number - 1]
        note = raw.find("#")
        out[number - 1] = raw[:len(raw) - len(raw.lstrip())] + raw[note:] if note >= 0 else DELETED
        deleted.append((number, f"line {number}   deleted {raw[:note if note >= 0 else len(raw)].strip()}"))
    for number, level in depth.items():
        raw = lines[number - 1]
        new = raw
        said = []
        for col, end, word in sorted(resolve(raw, edits.get(number, [])), reverse=True):
            old = new[col:end]
            if old.lower() != word:
                # "sort names smallest first" becomes "sort names": those words go.
                said.append(f"line {number}   {old} → {word}" if word else
                            f"line {number}   deleted {old.strip(' ,')}")
                new = new[:col] + word + new[end:]
        changes += reversed(said)
        body = new.lstrip(" \t")
        if number in bare_loops:
            first = body.split()[0]
            changes.append(f"line {number}   {first} → repeat {first}")
            body = "repeat " + body
        out[number - 1] = "    " * level + body
    if deleted:
        changes = [text for _, text in sorted(
            [(int(c.split()[1]), c) for c in changes] + deleted, key=lambda pair: pair[0])]

    # Move your own steps (and the notes right above them) after the main steps.
    howtos = [line for line in program.lines if is_howto(out[line.number - 1])]
    moving = set()
    blocks = []
    for line in howtos:
        start = line.number - 1
        while start - 1 >= 0 and out[start - 1].strip().startswith("#"):
            start -= 1
        end = last_number(line)
        block = list(range(start, end))
        if any(index >= start for index in moving):
            pass
        blocks.append(block)
        moving.update(block)
    last_main = max((i for i, text in enumerate(out) if i not in moving and text.strip()), default=-1)
    if blocks and any(index < last_main for block in blocks for index in block):
        main = [text for i, text in enumerate(out) if i not in moving]
        while main and not main[-1].strip():
            main.pop()
        for block in blocks:
            main.append("")
            main.extend(out[i] for i in block)
            header = out[block[-1]] if False else next(out[i] for i in block if is_howto(out[i]))
            changes.append(f'moved "{header.strip()}" after the main steps')
        out = main + [""]
    result = "\n".join(text for text in out if text is not DELETED)
    if not result.endswith("\n"):
        result += "\n"
    if crlf:
        result = result.replace("\n", "\r\n")
    return ("\ufeff" if bom else "") + result, changes


DELETED = "\0"    # stands in for a deleted line until the end, so line numbers still match


def is_howto(text):
    words = text.strip().lower().split()
    return len(words) > 1 and words[0] == "how" and words[1] == "to"


def last_number(line):
    last = line.number
    for child in line.body:
        last = max(last, last_number(child))
    return last


def all_statements(statements):
    for stmt in statements:
        yield stmt
        if isinstance(stmt, N.If):
            for _, body in stmt.branches:
                yield from all_statements(body)
        for attr in ("body", "fallback"):
            if hasattr(stmt, attr) and not isinstance(stmt, N.If):
                yield from all_statements(getattr(stmt, attr))
