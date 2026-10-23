"""Reading a program: from lines of tokens to a tree of steps, or to problems.

Every line is read into exactly one meaning before anything runs. Reading is a memoized
search over spans of words. If a line can be read two different ways, that is a problem
that shows both. Plain never guesses.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal

from . import nodes as N
from .problems import Problem
from .registry import REGISTRY, Phrase, Slot, Word, word_matches
from .suggest import reads_cleanly
from .source import (Piece, build_blocks, indent_problem, inline_break, read_lines, step_words,
                     tokenize)
from .values import Quoted
from .words import (ADD_OPS, ARTICLES, COMPARISONS, CORE_STARTS, ELIDED_COMPARISONS,
                    LINE_ALIASES, MUL_OPS, MUL_TWO_WORD_OPS, NEGATIVE_COMPARISONS,
                    NUMBER_WORDS, POLITE_STARTS, SPECIAL_WORDS, SYNONYMS, TYPE_CHECKS)

MAX_WORDS = 40
MAX_PARTS = 100     # words, numbers, texts and signs in one line (commas between items don't count)
MAX_DEPTH = 20      # brackets inside brackets
MAX_READINGS = 16
RESERVED_NAMES = {("problem",): "the problem", ("timer",): "the timer",
                  ("time", "now"): "the time now", ("date", "today"): "the date today"}


class TooMany(Exception):
    pass


# Views ----------------------------------------------------------------------------

def make_view(tokens, line_start=True):
    """The tokens Plain reads: articles before ordinary words, polite words at the start,
    final punctuation and commas outside lists are dropped."""
    toks = list(tokens)
    while toks and toks[-1].kind == "symbol" and toks[-1].norm in ".!;:":
        toks.pop()
    if line_start:
        while len(toks) > 1 and toks[0].kind == "word" and toks[0].norm in POLITE_STARTS \
                and not (toks[0].norm == "first" and (toks[1].kind == "number" or toks[1].norm in ("item", "items"))):
            toks.pop(0)   # but "first item of colors" is a value
    # Commas separate items only after "a list of" and "with choices", never in your names.
    norms = [t.norm for t in toks]
    items_from = next((k for k in range(1, len(norms)) if (norms[k - 1], norms[k]) in
                       (("list", "of"), ("with", "choices"), ("with", "options"))), len(norms))
    out = []
    for index, tok in enumerate(toks):
        if tok.kind == "symbol" and tok.norm == "," and index < items_from:
            continue
        if tok.kind == "word" and tok.norm in ARTICLES:
            nxt = toks[index + 1] if index + 1 < len(toks) else None
            if nxt is not None and nxt.kind == "word" and nxt.norm not in SPECIAL_WORDS \
                    and nxt.norm not in ARTICLES:
                continue
            after = toks[index + 2] if index + 2 < len(toks) else None
            if nxt is not None and nxt.kind == "text" and after is not None and \
                    (after.kind == "poss" or is_word(after, "of")):
                continue   # the "Price (USD)" of project: a quoted field name
        out.append(tok)
    return out


def bracket_depth(tokens):
    depth = deepest = 0
    for tok in tokens:
        if tok.kind == "symbol" and tok.norm == "(":
            depth += 1
            deepest = max(deepest, depth)
        elif tok.kind == "symbol" and tok.norm == ")":
            depth -= 1
    return deepest


def is_word(tok, *words):
    return tok.kind == "word" and (not words or tok.norm in words)


def is_ordinary(tok):
    return tok.kind == "word" and tok.norm not in SPECIAL_WORDS


def name_word(tok):
    if tok.kind == "word":
        return tok.norm
    if tok.kind == "number" and not tok.percent and tok.raw.isdigit():
        return tok.raw
    return None


def is_percent(toks):
    """15 percent, which means the same as 15%."""
    return len(toks) == 2 and toks[0].kind == "number" and not toks[0].percent and is_word(toks[1], "percent")


def percent_lit(toks):
    return N.Lit(toks[0].value / 100, raw=toks[0].raw + "%", percent=True, col=toks[0].col, end=toks[1].end)


def span_cols(tokens, i, j):
    if i >= j:
        return None, None
    return tokens[i].col, tokens[j - 1].end


# Program --------------------------------------------------------------------------

@dataclass(eq=False)
class HowToDef:
    phrase: Phrase
    params: list
    line: object
    own_names: set = field(default_factory=set)
    gives: bool = False
    body: list = field(default_factory=list)


@dataclass
class Program:
    statements: list
    problems: list
    source_lines: list
    names: set
    howtos: list
    origins: dict
    lines: list


class Reader:
    """Reads a whole program. Names and how-tos from earlier REPL lines can be passed in."""

    def __init__(self, known_names=(), known_howtos=(), known_origins=None):
        import plainlang.phrases  # noqa: F401  (registers the built-in phrases)
        self.quiet = False      # True while checking a suggested fix: no suggestions inside suggestions
        self.known_names = set(known_names)
        self.known_howtos = list(known_howtos)
        self.origins = dict(known_origins or {})
        self.step_index = {}
        self.value_index = {}
        self.postfix = []
        for phrase in REGISTRY:
            if phrase.kind == "step":
                for w in phrase.first_words:
                    self.step_index.setdefault(w, []).append(phrase)
            elif phrase.kind == "value":
                for w in phrase.first_words:
                    self.value_index.setdefault(w, []).append(phrase)
            else:
                self.postfix.append(phrase)
        self.step_words = step_words()
        self.property_prefixes = set()
        for phrase in REGISTRY:
            if phrase.kind != "value":
                continue
            words = []
            for e in phrase.elements:
                if isinstance(e, Slot):
                    break
                words.append(e)
            if words and words[-1].main == "of":
                self.property_prefixes.add(tuple(w.main for w in words[:-1]))

    # Whole program ---------------------------------------------------------------

    def read(self, text):
        lines = read_lines(text)
        source_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if source_lines and source_lines[0].startswith("﻿"):
            source_lines[0] = source_lines[0][1:]
        top, problems = build_blocks(lines)
        for line in walk(top):
            if line.problem is not None:
                problems.append(line.problem)
        self.howtos = list(self.known_howtos)
        howto_lines = []
        for line in walk(top):   # one inside other steps gets a problem when it's read
            if line.problem is None and self.first(line) == "how":
                howto = self.read_howto_header(line, problems)
                if howto is not None:
                    self.howtos.append(howto)
                    howto_lines.append((line, howto))
        self.howto_index = {}
        for howto in self.howtos:
            for w in howto.phrase.first_words:
                self.howto_index.setdefault(w, []).append(howto)
        self.check_shapes(howto_lines, problems)

        # Declare names: shared names come from the main steps, own names from each how-to.
        self.main_names = set(self.known_names)
        for line in self.walk_main(top):
            self.declare(line, self.main_names, problems)
        for line, howto in howto_lines:
            params = set(howto.params)
            names = self.main_names | params
            for inner in self.walk_main(line.body):
                self.declare(inner, names, problems)
            howto.own_names = {p for p in params if keeps_name(p)} | (names - self.main_names - params)

        statements = self.read_body(top, problems, scope=None)
        self.check_placement(statements, problems, in_repeat=False, in_howto=False)
        problems.sort(key=lambda p: (p.line or 0, p.col or 0))
        problems = group_unknown_names(dedupe_problems(problems), source_lines)
        return Program(statements, problems, source_lines, self.main_names,
                       self.howtos, self.origins, top)

    def walk_main(self, lines):
        """Every line, leaving out "how to" lines and the steps under them."""
        for line in lines:
            if line.problem is None and self.first(line) == "how":
                continue
            yield line
            yield from self.walk_main(line.body)

    def first(self, line):
        view = make_view(line.tokens)
        return view[0].norm if view and view[0].kind == "word" else ""

    # How-to headers ----------------------------------------------------------------

    def read_howto_header(self, line, problems):
        view = make_view(line.tokens)
        if len(view) < 3 or not is_word(view[1], "to"):
            problems.append(Problem(
                'Start your own step with "how to", then the words for it.',
                'A line that starts with "how" makes a new step of your own, like: how to greet (person)',
                line=line.number, col=view[0].col, end=view[-1].end,
                try_lines=["how to greet (person)", '    show "Hello, {person}!"']))
            return None
        parts, params, bracketed, k = [], [], [], 2
        while k < len(view):
            tok = view[k]
            if tok.kind == "symbol" and tok.norm == "(":
                close = next((m for m in range(k + 1, len(view)) if view[m].norm == ")"), None)
                inner = view[k + 1:close] if close is not None else []
                words = [name_word(t) for t in inner]
                if close is None or not inner or None in words or inner[0].kind != "word":
                    problems.append(Problem(
                        "Put one name inside each pair of brackets, like (bill).",
                        "Words in brackets are the values you hand to your step when you use it.",
                        line=line.number, col=tok.col, end=view[-1].end))
                    return None
                name = tuple(words)
                bracketed.append((name, inner[0].col, inner[-1].end))
                if parts and isinstance(parts[-1], Slot):
                    problems.append(Problem(
                        "Put a word between the two bracketed parts.",
                        "Plain needs a word between them to tell where one value ends and the next begins.",
                        line=line.number, col=tok.col, end=view[close].end))
                    return None
                parts.append(Slot(" ".join(name), "value"))
                params.append(name)
                k = close + 1
            elif tok.kind == "word":
                parts.append(Word((tok.norm,)))
                k += 1
            else:
                problems.append(Problem(
                    "Use only words and (bracketed names) in a how-to's wording.",
                    f'Plain found "{tok.raw}" in the wording of your step.',
                    line=line.number, col=tok.col, end=tok.end))
                return None
        if not parts or not isinstance(parts[0], Word) or parts[0].main in CORE_STARTS:
            why = (f'"{parts[0].main}" already starts one of Plain\'s own lines, so it can\'t start yours.'
                   if parts and isinstance(parts[0], Word) else
                   "Your own step needs a word before the first bracket, so Plain can tell when a line uses it.")
            problems.append(Problem(
                "Start your own step with a word that says what it does, like: how to greet (person)",
                why, line=line.number, col=view[2].col, end=view[-1].end))
            return None
        for name, col, end in bracketed:
            problem = name_problem(name, line.number, col, end)
            if problem is not None:
                problems.append(problem)
        template = howto_template(line, view)
        phrase = Phrase(template, tuple(parts), "step", None, origin=f"line {line.number}")
        phrase.main = phrase
        howto = HowToDef(phrase, params, line)
        phrase.run = howto
        howto.gives = any(self.first(inner) in ("give", "return") for inner in walk(line.body))
        phrase.gives = howto.gives
        return howto

    def check_shapes(self, howto_lines, problems):
        builtin_shapes = {p.shape: p for p in REGISTRY if p.kind == "step"}
        seen = {}
        for line, howto in howto_lines:
            shape = howto.phrase.shape
            other = builtin_shapes.get(shape)
            if other is None and shape in seen:
                other = seen[shape]
            if other is not None:
                example = other.example if isinstance(other, Phrase) and other.example else ""
                theirs = " ".join("..." if s == "_" else s for s in shape)
                whose = "Plain's own phrase" if other.run is not None and not isinstance(other.run, HowToDef) \
                    else "another how-to"
                problems.append(Problem(
                    'Use different words for this "how to".',
                    f'It uses the same words in the same places as {whose} "{theirs}"'
                    + (f", as in {example}" if example else "") + ", so Plain couldn't tell them apart.",
                    line=line.number, col=line.indent, end=len(line.raw.rstrip())))
            elif (other := builtin_overlap(howto.phrase)) is not None:
                theirs = " ".join("..." if s == "_" else s for s in other.shape)
                problems.append(Problem(
                    'Use different words for this "how to".',
                    f'A line that uses it could also be read as Plain\'s own phrase "{theirs}", as in '
                    f"{other.example}, so Plain couldn't tell them apart.",
                    line=line.number, col=line.indent, end=len(line.raw.rstrip())))
            seen[shape] = howto.phrase

    # Declaring names ---------------------------------------------------------------

    def declare(self, line, names, problems):
        tokens, quiet = line.tokens, False
        if line.problem is not None:
            # Keep the names a broken line meant to set, from the words before its problem.
            tokens, quiet = tokens_before_problem(line), True
        view = make_view(tokens)
        if not view:
            return
        first = view[0].norm
        norms = [t.norm for t in view]
        if first == "set" and "to" in norms:
            k = norms.index("to")
            target = view[1:k]
            if target and not self.is_place(target, names):
                self.add_name(target, names, line, problems, quiet)
        if first == "for" or (first == "repeat" and norms[1:2] == ["for"]):
            start = 1 if first == "for" else 2
            if len(view) > start + 1 and norms[start] in ("each", "every"):
                rest = norms[start + 1:]
                stop = next((m for m, w in enumerate(rest) if w in ("in", "from")), None)
                if stop:
                    self.add_name(view[start + 1:start + 1 + stop], names, line, problems, quiet)
                elif stop is None:
                    # A broken header, like "for each thing on my list": keep "thing".
                    self.add_name(view[start + 1:start + 2], names, line, problems, quiet=True)
        k = find_call_it(view)
        if k is not None:
            self.add_name(view[k + 3:], names, line, problems, quiet)
        # Names a broken line probably meant to set, so later lines don't pile up problems.
        if len(view) >= 3 and first not in CORE_STARTS:
            for m, tok in enumerate(view):
                if tok.norm in ("is", "=", "+", "-") and m > 0 and all(name_word(t) for t in view[:m]):
                    if tok.norm in ("is", "=") or (m + 1 < len(view) and view[m + 1].norm == "="):
                        self.add_name(view[:m], names, line, problems, quiet=True)
                    break

    @staticmethod
    def is_place(target, names):
        """True for a field or an item of a list (sale's amount, the age of person, item 2 of
        colors), which "set" changes instead of making a new name."""
        norms = [t.norm for t in target]
        if any(t.kind == "poss" for t in target):
            return True
        if "of" not in norms:
            return False
        last_of = len(norms) - 1 - norms[::-1].index("of")
        after = tuple(name_word(t) for t in target[last_of + 1:])
        return norms[0] in ("item", "first", "last") or after in names

    def add_name(self, toks, names, line, problems, quiet=False):
        words = tuple(name_word(t) for t in toks)
        if not toks or None in words or toks[0].kind != "word":
            return
        problem = name_problem(words, line.number, toks[0].col, toks[-1].end)
        if problem is not None and not quiet:
            problems.append(problem)
        # A name with a special word is still kept, so the lines that use it don't pile up problems.
        if keeps_name(words):
            names.add(words)
            self.origins.setdefault(words, line.number)

    # Bodies ------------------------------------------------------------------------

    def read_body(self, lines, problems, scope):
        statements = []
        failed = None   # the first word of the line just before, when it had a problem
        for line in lines:
            if line.problem is not None:
                statements.append(N.ErrorBlock(self.read_body(line.body, problems, scope), line=line.number))
                failed = next((t.norm for t in tokens_before_problem(line) if t.kind == "word"), "")
                continue
            try:
                stmt = self.read_line(line, scope, problems)
            except RecursionError:
                problems.append(Problem("Split this line into shorter steps.",
                                        "It has more brackets inside brackets than Plain can follow.",
                                        line=line.number, col=line.indent, end=len(line.raw.rstrip())))
                statements.append(N.ErrorBlock([], line=line.number))
                failed = self.first(line)
                continue
            except Problem as problem:
                problems.append(problem.at(line.number))
                statements.append(N.ErrorBlock(self.read_body(line.body, problems, scope), line=line.number))
                failed = self.first(line)
                continue
            after_failed, failed = failed, None
            if line.body and not line.is_header:
                # Steps moved to the right under a step that has no steps of its own.
                problems.append(indent_problem(line.body[0], line))
                self.read_body(line.body, problems, scope)
            if stmt is None:
                continue
            if isinstance(stmt, tuple):   # otherwise / if that fails attach to what came before
                kind, payload = stmt
                prev = statements[-1] if statements else None
                if kind == "otherwise" and isinstance(prev, N.If):
                    if prev.branches[-1][0] is None:
                        problems.append(Problem(
                            'Move this "otherwise" up, or change the plain "otherwise" above it to "otherwise if".',
                            'A plain "otherwise" has to be the last part of an "if".',
                            line=line.number, col=line.indent, end=len(line.raw.rstrip())))
                    prev.branches.append(payload[:2])
                    prev.branch_lines.append(payload[2])
                    if len(payload) > 3:
                        prev.branch_edits[payload[2]] = payload[3]
                elif kind == "fails" and isinstance(prev, N.Try) and not prev.fallback:
                    prev.fallback = payload
                elif isinstance(prev, N.ErrorBlock) and after_failed in (
                        ("if", "otherwise", "else") if kind == "otherwise" else ("try",)):
                    prev.body += payload[1] if kind == "otherwise" else payload   # follows from that problem
                    failed = after_failed if kind == "otherwise" else None
                elif kind == "otherwise":
                    problems.append(Problem(
                        'Put this "otherwise" right after an "if" and its steps.',
                        '"otherwise" gives the steps to take when the "if" above it isn\'t true.',
                        line=line.number, col=line.indent, end=len(line.raw.rstrip())))
                else:
                    problems.append(Problem(
                        'Put "if that fails" right after a "try" and its steps.',
                        '"if that fails" gives the steps to take when a step under "try" has a problem.',
                        line=line.number, col=line.indent, end=len(line.raw.rstrip())))
                continue
            statements.append(stmt)
        return statements

    def scope_for(self, scope):
        if scope is None:
            return self.main_names, set()
        return self.main_names | scope.own_names, scope.own_names

    def line_reader(self, tokens, scope):
        names, own = self.scope_for(scope)
        reader = LineReader(self, tokens, names, own)
        reader.scope = scope
        return reader

    def read_line(self, line, scope, problems):
        view = make_view(line.tokens)
        if not view:
            return None
        if len([t for t in view if t.kind == "word"]) > MAX_WORDS:
            raise Problem("Split this line into shorter steps.",
                          f"Plain reads lines of up to {MAX_WORDS} words, so each step stays easy to follow.",
                          line=line.number, col=view[0].col, end=view[-1].end)
        if len([t for t in view if t.norm != ","]) > MAX_PARTS:
            raise Problem("Split this line into shorter steps.",
                          f"Plain reads up to {MAX_PARTS} numbers, words and signs in one line, "
                          "so each step stays easy to follow.",
                          line=line.number, col=view[0].col, end=view[-1].end)
        if bracket_depth(view) > MAX_DEPTH:
            raise Problem("Split this line into shorter steps.",
                          f"Plain reads up to {MAX_DEPTH} brackets inside each other in one line.",
                          line=line.number, col=view[0].col, end=view[-1].end)
        norms = tuple(t.norm for t in view)
        if norms in LINE_ALIASES:
            return N.StopProgram(line=line.number)
        first = view[0].norm if view[0].kind == "word" else ""
        reader = self.line_reader(view, scope)
        reader.line = line
        edits = []
        if first == "else":
            edits.append((view[0].col, view[0].end, "otherwise"))
            first = "otherwise"
        if first == "return":
            edits.append((view[0].col, view[0].end, "give back"))
        stmt = self.read_core(first, view, line, scope, problems, reader)
        if stmt is NotCore:
            if first == "how":
                return self.read_howto(line, problems)
            stmt = reader.read_step_line(0, len(view), line)
        if isinstance(stmt, N.Statement):
            stmt.synonym_edits = edits + reader.synonym_edits
            if stmt.col is None:
                stmt.col, stmt.end = view[0].col, view[-1].end
        elif isinstance(stmt, tuple) and stmt[0] == "otherwise":
            stmt = ("otherwise", stmt[1] + (edits + reader.synonym_edits,))   # for plain tidy
        return stmt

    def read_howto(self, line, problems):
        howto = next((h for h in self.howtos if h.line is line), None)
        if howto is None:
            return None
        if line.indent > 0:
            problems.append(Problem(
                'Move this "how to" to the left edge, outside other steps.',
                'Your own steps are written on their own, not inside other steps.',
                line=line.number, col=0, end=line.indent))
        body = self.read_body(line.body, problems, howto)
        howto.body = body
        return N.HowTo(howto.phrase, howto.params, body, frozenset(howto.own_names), line=line.number)

    def read_core(self, first, view, line, scope, problems, reader):
        n = len(view)
        norms = [t.norm for t in view]
        L = line.number

        def body():
            return self.read_body(line.body, problems, scope)

        if first == "set":
            if "to" not in norms[1:]:
                raise Problem('Write "to" between the name and its value, like: set score to 0',
                              '"set" keeps a value under a name: set NAME to VALUE.',
                              line=L, col=view[0].col, end=view[-1].end)
            k = norms.index("to", 1)
            if k == 1:
                raise Problem('Write a name between "set" and "to", like: set score to 0',
                              '"set" keeps a value under a name: set NAME to VALUE.',
                              line=L, col=view[0].col, end=view[1].end)
            target = reader.read_place(1, k, declaring=True)
            value = reader.one(reader.check(k + 1, n), k + 1, n, line)
            return N.SetStep(target, value, line=L)

        if first in ("if", "while", "until") and n == 1 or first == "otherwise" and norms[1:] == ["if"]:
            raise Problem(f'Write a check after "{view[-1].raw}", like: {view[-1].raw} score is 10',
                          f'"{view[-1].raw}" needs a check with a yes or no answer.',
                          line=L, col=view[0].col, end=view[-1].end)
        if first == "if":
            if norms[1:3] in (["that", "fails"],):
                if n > 3:
                    raise Problem('Put the steps for "if that fails" on the lines below it.',
                                  '"if that fails" goes on a line of its own, with its steps below it.',
                                  line=L, col=view[3].col, end=view[-1].end)
                return ("fails", body())
            if norms[1:3] == ["it", "fails"]:
                raise Problem('Write "if that fails" instead of "if it fails".',
                              'In Plain, "it" means the item being checked inside "where".',
                              line=L, col=view[0].col, end=view[2].end, try_lines=["if that fails"],
                              ideas=[line.raw.replace(view[1].raw, "that", 1)])
            then = self.find_then(view, reader, 1)
            if then is not None and then < n - 1:
                self.check_one_line(view, then, line, reader)
                check = reader.one(reader.check(1, then), 1, then, line, check=True)
                inner = self.read_inline_step(view[then + 1:], line, scope, problems)
                return N.If([(check, [inner])], branch_lines=[L], line=L)
            stop = then if then is not None and then == n - 1 else n
            readings = reader.check(1, stop)
            if not line.body and (len(readings) != 1 or isinstance(readings[0], N.Bad)):
                self.check_then_missing(line, reader)
            check = reader.one(readings, 1, stop, line, check=True)
            return N.If([(check, body())], branch_lines=[L], line=L)

        if first == "otherwise":
            if n > 1 and norms[1] == "if":
                then = self.find_then(view, reader, 2)
                if then is not None and then < n - 1:
                    self.check_one_line(view, then, line, reader)
                    check = reader.one(reader.check(2, then), 2, then, line, check=True)
                    inner = self.read_inline_step(view[then + 1:], line, scope, problems, "otherwise if")
                    return ("otherwise", (check, [inner], L))
                stop = then if then is not None else n
                check = reader.one(reader.check(2, stop), 2, stop, line, check=True)
                return ("otherwise", (check, body(), L))
            if n > 1:
                checks = reader.check(1, n)
                if len(checks) == 1 and isinstance(checks[0], (N.Compare, N.Between, N.TypeCheck, N.Logic, N.Not)):
                    fixed = line.raw[:view[0].end] + " if" + line.raw[view[0].end:]
                    raise Problem('Write "otherwise if" to check something else.',
                                  '"otherwise" on its own takes the steps for when nothing above was true. '
                                  '"otherwise if" checks something new first.',
                                  line=L, col=view[0].col, end=view[0].end, try_lines=[fixed.strip()],
                                  ideas=[fixed] if not self.quiet and reads_cleanly(reader, line, fixed) else [])
                if line.body:
                    raise Problem('Put the step after "otherwise" on its own line, above the other steps.',
                                  'Steps that belong to "otherwise" go on the lines below it, all lined up.',
                                  line=L, col=view[1].col, end=view[-1].end,
                                  try_lines=[view[0].raw, "    " + line.raw[view[1].col:view[-1].end]])
                inner = self.read_inline_step(view[1:], line, scope, problems, "otherwise")
                return ("otherwise", (None, [inner], L))
            return ("otherwise", (None, body(), L))

        if first in ("repeat", "for", "while", "until"):
            return self.read_repeat(view, line, reader, body, problems)

        if first in ("give", "return"):
            start = 2 if first == "give" and n > 1 and norms[1] == "back" else 1
            if first == "give" and start == 1:
                return NotCore
            if start >= n:
                raise Problem("Write the value to give back, like: give back total",
                              '"give back" ends your step and hands a value back to the line that used it.',
                              line=L, col=view[0].col, end=view[-1].end)
            value = reader.one(reader.check(start, n), start, n, line)
            return N.GiveBack(value, line=L)

        if first == "try":
            if n > 1:
                raise Problem('Put the steps to try on the lines below "try", moved 4 spaces to the right.',
                              '"try" goes on a line of its own, with the steps to try below it.',
                              line=L, col=view[1].col, end=view[-1].end)
            return N.Try(body(), line=L)

        if first == "stop":
            rest = norms[1:]
            if rest == ["repeating"]:
                return N.StopRepeating(line=L)
            if rest == ["program"]:
                return N.StopProgram(line=L)
            raise Problem('Write "stop repeating" to leave the repeat, or "stop the program" to end it.',
                          'Plain has two kinds of stop, so it asks you to say which one you mean.',
                          line=L, col=view[0].col, end=view[-1].end,
                          ideas=[line.raw.rstrip() + " repeating", line.raw.rstrip() + " the program"]
                          if not rest else [])

        if first == "skip":
            if norms[1:] in (["to", "next", "round"], ["this", "round"], ["round"]):
                return N.Skip(line=L)
            raise Problem('Write "skip to the next round".',
                          'It goes straight to the next round of the repeat.',
                          line=L, col=view[0].col, end=view[-1].end)

        if first == "end":
            return None
        return NotCore

    def read_inline_step(self, tokens, line, scope, problems, word="if"):
        sub = Line_(line, tokens)
        stmt = self.read_core(tokens[0].norm if tokens[0].kind == "word" else "", tokens, sub, scope,
                              problems, self.line_reader(tokens, scope))
        if stmt is NotCore:
            stmt = self.line_reader(tokens, scope).read_step_line(0, len(tokens), sub)
        if isinstance(stmt, (tuple, N.If, N.Repeat, N.Try)) or stmt is None:
            raise Problem(f'Put this step on its own line under the "{word}".',
                          "It has steps of its own, so it needs a line of its own.",
                          line=line.number, col=tokens[0].col, end=tokens[-1].end)
        if stmt.col is None:
            stmt.col, stmt.end = tokens[0].col, tokens[-1].end
        return stmt

    def find_then(self, view, reader, start):
        """The "then" before the step in: if CHECK then STEP. In "is bigger then 3" it isn't one."""
        then = reader.find_then(start)
        if then is None or then == len(view) - 1:
            return then
        nxt = view[then + 1]
        if nxt.kind == "word" and (nxt.norm in self.step_words or nxt.norm in self.howto_index):
            return then
        return None

    def check_one_line(self, view, then, line, reader):
        """if CHECK then STEP: the step has to be the only one."""
        raw = line.raw
        if line.body:
            step = raw[view[then + 1].col:view[-1].end]
            raise Problem('Put the step after "then" on its own line, above the other steps.',
                          'Steps that belong to the "if" go on the lines below it, all lined up.',
                          line=line.number, col=view[then].col, end=view[-1].end,
                          try_lines=[raw[:view[then].col].strip(), "    " + step])
        other = next((m for m in range(then + 1, len(view))
                      if is_word(view[m], "otherwise") and reader.depth[m] == 0), None)
        if other is not None:
            raise Problem('Put "otherwise" and its step on the next line.',
                          'Each line has one step, so "otherwise" starts a line of its own.',
                          line=line.number, col=view[other].col, end=view[-1].end,
                          try_lines=[raw[:view[other].col].strip(), raw[view[other].col:].strip()])

    def check_then_missing(self, line, reader):
        """if score is 10, show "Yes": a comma or colon where "then" belongs."""
        mark = inline_break(line)
        if mark is None:
            return
        fixed = line.raw[:mark.col].rstrip() + " then " + line.raw[mark.end:].lstrip()
        ok = not self.quiet and reads_cleanly(reader, line, fixed)
        raise Problem(f'Write "then" in place of the "{mark.raw}".',
                      '"then" shows where the check ends and the step begins.',
                      line=line.number, col=mark.col, end=mark.end, try_lines=[fixed.strip()],
                      ideas=[fixed] if ok else [])

    def read_repeat(self, view, line, reader, body, problems):
        L = line.number
        norms = [t.norm for t in view]
        n = len(view)
        k = 1 if norms[0] == "repeat" else 0
        if k >= n:
            raise Problem('Say how to repeat, like: repeat 3 times, repeat forever or repeat until done is yes',
                          '"repeat" needs to know how many times, or until when.',
                          line=L, col=view[0].col, end=view[-1].end)
        word = norms[k]
        if k == 1 and n == 2 and word in ("once", "twice", "forever"):
            if word == "forever":
                return N.Repeat("forever", body(), line=L)
            count = N.Lit(Decimal(1 if word == "once" else 2), col=view[1].col, end=view[1].end)
            return N.Repeat("times", body(), count=count, line=L)
        if word in ("until", "while"):
            check = reader.one(reader.check(k + 1, n), k + 1, n, line, check=True)
            return N.Repeat(word, body(), check=check, line=L)
        if word == "for" and k + 1 < n and norms[k + 1] in ("each", "every"):
            start = k + 2
            stop = next((m for m in range(start, n) if norms[m] in ("in", "from")), None)
            if stop is None or stop == start:
                raise Problem('Write it like this: repeat for each item in my list',
                              '"repeat for each" goes through a list one item at a time.',
                              line=L, col=view[0].col, end=view[-1].end)
            name = reader.read_place(start, stop, declaring=True)
            if norms[stop] == "in":
                items = reader.one(reader.check(stop + 1, n), stop + 1, n, line)
                return N.Repeat("each", body(), name=name, items=items, line=L)
            to = next((m for m in range(stop + 1, n) if norms[m] == "to"), None)
            if to is None:
                raise Problem('Write it like this: repeat for each n from 1 to 10',
                              '"from" counts with a name, so it needs both ends: from 1 to 10.',
                              line=L, col=view[0].col, end=view[-1].end)
            down = norms[to - 1] == "down"
            low_end = to - 1 if down else to
            start_value = reader.one(reader.arith(stop + 1, low_end), stop + 1, low_end, line)
            stop_value = reader.one(reader.arith(to + 1, n), to + 1, n, line)
            return N.Repeat("count", body(), name=name, start=start_value, stop=stop_value, down=down, line=L)
        if k == 1 and norms[-1] in ("times", "time") and n > 2:
            count = reader.one(reader.arith(1, n - 1), 1, n - 1, line)
            return N.Repeat("times", body(), count=count, line=L)
        raise Problem('Say how to repeat, like: repeat 3 times, repeat forever, repeat until done is yes, '
                      'or repeat for each item in my list',
                      '"repeat" needs to know how many times, or until when.',
                      line=L, col=view[0].col, end=view[-1].end)

    # Placement checks --------------------------------------------------------------

    def check_placement(self, statements, problems, in_repeat, in_howto):
        for stmt in statements:
            if isinstance(stmt, (N.StopRepeating, N.Skip)) and not in_repeat:
                word = "stop repeating" if isinstance(stmt, N.StopRepeating) else "skip to the next round"
                problems.append(Problem(
                    f'Move "{word}" inside a "repeat", or delete it.',
                    f'"{word}" only has a meaning while steps are repeating.',
                    line=stmt.line, col=stmt.col, end=stmt.end))
            elif isinstance(stmt, N.GiveBack) and not in_howto:
                said_return = any(edit[2] == "give back" for edit in stmt.synonym_edits)
                problems.append(Problem(
                    'Move "give back" inside a "how to", or delete it.',
                    ('In Plain, "return" is written "give back". It hands' if said_return else '"give back" hands')
                    + " a value back from one of your own steps.",
                    line=stmt.line, col=stmt.col, end=stmt.end))
            elif isinstance(stmt, N.Step) and stmt.call_it and not stmt.phrase.gives:
                what = "your step" if isinstance(stmt.phrase.run, HowToDef) else f'"{stmt.phrase.main.template.split()[0]}"'
                col, end = stmt.call_span or (stmt.col, stmt.end)
                problems.append(Problem(
                    f'Remove "and call it {" ".join(stmt.call_it)}", or add "give back" to {what}.',
                    f'{what[0].upper() + what[1:]} gives nothing back, so there is no value to keep.',
                    line=stmt.line, col=col, end=end))
            for child, repeat, howto in children(stmt):
                self.check_placement(child, problems, in_repeat or repeat,
                                     in_howto or howto)


def builtin_overlap(howto):
    """One of Plain's own step phrases that a line using this how-to could also be read as,
    when the how-to's words fit into that phrase's slots: how to remove a done task from (tasks)
    against remove VALUE from LIST. A slot can hold any run of your words, since any of them
    could be one of your names."""
    parts = [("slot",) if isinstance(e, Slot) else e.main for e in howto.elements]
    first = parts[0]

    def fits(elements, k):
        if not elements:
            return k == len(parts)
        el, rest = elements[0], elements[1:]
        if isinstance(el, Word):
            here = k < len(parts) and isinstance(parts[k], str) and \
                (parts[k] in el.alts or SYNONYMS.get(parts[k]) in el.alts) and fits(rest, k + 1)
            return here or (el.optional and fits(rest, k))
        for end in range(k + 1, len(parts) + 1):
            if not all(p == ("slot",) or p not in SPECIAL_WORDS for p in parts[k:end]):
                break
            if fits(rest, end):
                return True
        return False

    for phrase in REGISTRY:
        if phrase.kind == "step" and phrase.main is phrase and \
                {first, SYNONYMS.get(first)} & set(phrase.first_words) and fits(phrase.elements, 0):
            return phrase
    return None


class NotCoreType:
    pass


NotCore = NotCoreType()


class Line_:
    """A part of a line read on its own, like the step after "then"."""

    def __init__(self, line, tokens):
        self.number = line.number
        self.raw = line.raw
        self.tokens = tokens
        self.body = []
        self.indent = line.indent


def children(stmt):
    if isinstance(stmt, N.If):
        for _, body in stmt.branches:
            yield body, False, False
    elif isinstance(stmt, N.Repeat):
        yield stmt.body, True, False
    elif isinstance(stmt, N.HowTo):
        yield stmt.body, False, True
    elif isinstance(stmt, N.Try):
        yield stmt.body, False, False
        yield stmt.fallback, False, False
    elif isinstance(stmt, N.ErrorBlock):
        yield stmt.body, True, True


def walk(lines):
    for line in lines:
        yield line
        yield from walk(line.body)


def tokens_before_problem(line):
    """The tokens of a line up to the place where it has a problem, like an unclosed quote."""
    if line.problem.col is None:
        return []
    try:
        tokens, _, _ = tokenize(line.raw[:line.problem.col], line_no=line.number)
    except Problem:
        return []
    return tokens


def find_call_it(view):
    for k in range(len(view) - 3, 0, -1):
        if is_word(view[k], "and") and is_word(view[k + 1], "call") and is_word(view[k + 2], "it", "them"):
            return k
    return None


def dedupe_problems(problems):
    seen, out = set(), []
    for p in problems:
        key = (p.line, p.fix)
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth",
            "tenth", "eleventh", "twelfth")


def name_problem(words, line=None, col=None, end=None):
    """Why these words can't be one of your names, or None when they can."""
    if words in RESERVED_NAMES:
        return Problem(f'Choose another name than "{" ".join(words)}".',
                       f'"{RESERVED_NAMES[words]}" is a value Plain already has.', line=line, col=col, end=end)
    special = [w for k, w in enumerate(words) if w in SPECIAL_WORDS and not (k > 0 and w in NUMBER_WORDS)]
    if special:
        return Problem(f'Rename "{" ".join(words)}", for example to "{suggest_rename(words)}".',
                       f'"{special[0]}" is one of Plain\'s special words, so it can\'t be part of a name.',
                       line=line, col=col, end=end)
    return None


def keeps_name(words):
    """Plain keeps a name it reported, so later lines don't pile up problems, unless the name
    has no ordinary word (one) or is a value Plain already has (timer)."""
    return words not in RESERVED_NAMES and any(w not in SPECIAL_WORDS for w in words)


def group_unknown_names(problems, source_lines):
    """Each unknown name is reported once, with all the lines that use it."""
    def words_of(p):
        if not (p.line and p.col is not None and p.why and 0 < p.line <= len(source_lines)):
            return None
        return " ".join(source_lines[p.line - 1][p.col:p.end].lower().split())

    groups = {}
    for p in problems:   # "Set score before …" and "Write total instead of totl."
        if words_of(p) and "Nothing in your program sets" in p.why:
            groups.setdefault(words_of(p), []).append(p)
    for p in problems:   # "Put the text in double quotes" for: show score
        words = words_of(p)
        if words and "Plain looks for a name" in p.why:
            name = next((n for n in groups if words == n or words.startswith(n + " ")), None)
            if name is not None:
                groups[name].append(p)
    drop = set()
    for words, group in groups.items():
        keep = group[0]
        others = sorted({p.line for p in group if p.line != keep.line})
        if not others:
            continue
        lines = f"line {others[0]}" if len(others) == 1 else \
            "lines " + ", ".join(str(n) for n in others[:-1]) + f" and {others[-1]}"
        keep.why += f' You also use "{words}" on {lines}.'
        drop.update(id(p) for p in group if p is not keep)
    return [p for p in problems if id(p) not in drop]


def suggest_rename(words):
    words = list(words)
    if len(words) >= 3 and words[1] == "of" and words[0] == "number":
        return " ".join(words[2:]) + " count"
    if len(words) == 1 and NUMBER_WORDS.get(words[0], 0) >= 1:
        return ORDINALS[NUMBER_WORDS[words[0]] - 1] + " number"
    if "of" in words:   # the age of person: person age
        k = words.index("of")
        words = words[k + 1:] + words[:k]
    swaps = {"percent": "rate", "times": "count", "split": "share", "rounded": "round",
             "joined": "joint", "plus": "extra", "minus": "less"}
    out = [swaps.get(w, w) for w in words if w in swaps or w not in SPECIAL_WORDS]
    return " ".join(out) if out else "my value"


# Reading one line -----------------------------------------------------------------

class LineReader:
    def __init__(self, reader, tokens, names, own):
        self.scope = None
        self.line = None
        self.r = reader
        self.t = tokens
        self.names = names
        self.own = own
        self.memo = {}
        self.synonym_edits = []
        self.max_name = max((len(n) for n in names), default=0)
        self.boundaries = {len(tokens)} | {k for k, t in enumerate(tokens) if t.norm == ")"}
        depth, self.depth = 0, []
        for tok in tokens:
            if tok.kind == "symbol" and tok.norm == ")":
                depth -= 1
            self.depth.append(depth)
            if tok.kind == "symbol" and tok.norm == "(":
                depth += 1

    # Choosing one reading ------------------------------------------------------------

    def one(self, readings, i, j, line, check=False):
        """Exactly one reading, or a problem."""
        bad = [r for r in readings if isinstance(r, N.Bad)]
        if bad:
            raise self.bad_problem(bad[0], line)
        if len(readings) == 1:
            return readings[0]
        if not readings:
            raise self.explain_failure(i, j, line, check=check)
        col, end = span_cols(self.t, i, j)
        raise self.tie_problem(readings[0], readings[1], col, end, line)

    def tie_problem(self, a, b, col, end, line):
        """Two readings of the same words. When one of them uses your name and the other
        reads those words as Plain's own, the fix is to rename."""
        indent = line.raw[:len(line.raw) - len(line.raw.lstrip())]
        splits = [x for x in (split_name(a, b), split_name(b, a)) if x is not None]
        split = max(splits, key=lambda x: x[0].end - x[0].col) if splits else None
        if split is None:
            try_lines = [replace_span(line.raw, col, end, r.canonical()) for r in (a, b)]
            return Problem(
                "Add brackets, or reword this, so it has only one meaning.",
                "Plain can read it two ways, and it never guesses which one you mean.",
                line=line.number, col=col, end=end, try_lines=try_lines,
                ideas=[indent + t for t in try_lines])
        name, with_name, with_words = split
        try_lines = [replace_span(line.raw, col, end, with_words.canonical()),
                     replace_span(line.raw, col, end, same_as_text(with_name, name))]
        try_lines = [t for t in try_lines if t != line.raw.strip()]
        ideas = [] if self.r.quiet else [indent + t for t in try_lines if reads_cleanly(self, line, indent + t)]
        words = name.canonical()
        return Problem(
            f'Rename "{words}" so this line has only one meaning.',
            f'Plain can read this line two ways: with your name "{words}", or with Plain\'s own words. '
            "Plain never guesses, so you choose.",
            line=line.number, col=name.col, end=name.end, try_lines=try_lines, ideas=ideas)

    def bad_problem(self, bad, line):
        problem = bad.problem
        problem.line = line.number
        if problem.col is None and bad.col is not None:
            problem.col, problem.end = bad.col, bad.end
        if bad.alts and bad.col is not None:
            problem.try_lines = [replace_span(line.raw, bad.col, bad.end, alt) for alt in bad.alts]
            indent = line.raw[:len(line.raw) - len(line.raw.lstrip())]
            problem.ideas = [indent + t for t in problem.try_lines]
        return problem

    def explain_failure(self, i, j, line, check=False):
        if self.r.quiet:
            return Problem("Plain couldn't follow this line.", line=getattr(line, "number", None))
        from .suggest import explain_unreadable
        return explain_unreadable(self, i, j, line, check=check)

    def find_then(self, start):
        for k in range(start, len(self.t)):
            if is_word(self.t[k], "then") and self.depth[k] == 0:
                return k
        return None

    # Steps ---------------------------------------------------------------------------

    def read_step_line(self, i, j, line):
        call_it = call_span = None
        k = find_call_it(self.t[i:j])
        if k is not None:
            k += i
            name_toks = self.t[k + 3:j]
            words = tuple(name_word(t) for t in name_toks)
            if not name_toks or None in words:
                raise Problem("Write a name after \"and call it\", like: and call it answer",
                              '"and call it" keeps what the step gives back under the name after it.',
                              line=line.number, col=self.t[k].col, end=self.t[j - 1].end)
            call_it = words
            call_span = (self.t[k].col, self.t[j - 1].end)
            j = k
            self.boundaries.add(k)
        self.mark_step_boundaries(i, j)
        readings = self.step_readings(i, j)
        stmt = self.choose_step(readings, i, j, line)
        stmt.call_it = call_it
        stmt.call_span = call_span if call_it else None
        return stmt

    def mark_step_boundaries(self, i, j):
        """A "where" check can end right before one of a step's own words, like "to" in save … to."""
        first = self.t[i]
        if first.kind != "word":
            return
        phrases = []
        for w in {first.norm, SYNONYMS.get(first.norm)}:
            phrases += self.r.step_index.get(w, [])
        phrases += [h.phrase for h in self.r.howto_index.get(first.norm, [])]
        for phrase in phrases:
            for element in phrase.elements[1:]:
                if isinstance(element, Word):
                    for k in range(i + 1, j):
                        if word_matches(self.t[k], element.alts):
                            self.boundaries.add(k)

    def step_readings(self, i, j):
        first = self.t[i]
        candidates = []
        if first.kind == "word":
            for w in {first.norm, SYNONYMS.get(first.norm)}:
                candidates += self.r.step_index.get(w, [])
            candidates += [h.phrase for h in self.r.howto_index.get(first.norm, [])]
        readings = []
        seen = set()
        for phrase in candidates:
            if id(phrase) in seen:
                continue
            seen.add(id(phrase))
            for args, fixed, syn in self.align(phrase.elements, i, j, "step"):
                readings.append((phrase, args, fixed, syn))
        return readings

    def choose_step(self, readings, i, j, line):
        good = [r for r in readings if not any(isinstance(v, N.Bad) for v in r[1].values())]
        bad = [v for r in readings for v in r[1].values() if isinstance(v, N.Bad)]
        if not good:
            if bad:
                raise self.bad_problem(bad[0], line)
            raise self.explain_failure(i, j, line)
        unique = {}
        for r in good:
            key = (id(r[0].main), tuple(sorted((k, N.arg_text(v)) for k, v in r[1].items())))
            unique.setdefault(key, r)
        good = list(unique.values())
        if len(good) > 1:
            howto = [r for r in good if isinstance(r[0].run, HowToDef)]
            builtin = [r for r in good if not isinstance(r[0].run, HowToDef)]
            if howto and builtin:
                raise self.step_tie(howto[0], builtin[0], line,
                                    "It reads as your own step and also as one of Plain's own phrases.")
            if len(howto) > 1:
                raise self.step_tie(howto[0], howto[1], line, "It reads as two of your own steps.")
            # Between built-ins, the reading that uses more of Plain's words wins,
            # unless that means splitting one of your names.
            good.sort(key=lambda r: -len(r[2]))
            best = good[0]
            for other in good[1:]:
                for v in other[1].values():
                    for name in names_in(v):
                        if name.col is not None and any(
                                name.col <= self.t[k].col < name.end for k in best[2]):
                            raise Problem(
                                f'Rename "{name.canonical()}" so this line has only one meaning.',
                                f'Plain can read this line two ways, because "{name.canonical()}" '
                                f'also contains words of one of its phrases. Plain never guesses, so you choose.',
                                line=line.number, col=name.col, end=name.end)
            if len(good[1][2]) == len(best[2]):
                raise self.step_tie(best, good[1], line, "Plain can read it two ways.")
            readings = [best]
        else:
            readings = good
        phrase, args, fixed, syn = readings[0]
        self.synonym_edits += [(self.t[k].col, self.t[k].end, main) for k, main in syn]
        return N.Step(phrase, args, line=line.number)

    def step_tie(self, a, b, line, why):
        texts = []
        same = a[0].main is b[0].main
        howto = any(isinstance(r[0].run, HowToDef) for r in (a, b))
        for phrase, args, _, _ in (a, b):
            text = phrase.main.render({k: N.arg_text(v, wrap_math=False) for k, v in args.items()})
            origin = "your step" if isinstance(phrase.run, HowToDef) else "Plain's phrase"
            texts.append(text if same else f"{text}    ({origin} \"{phrase.main.template}\")")
        fix = "Reword this line, or rename your step, so the line has only one meaning." if howto else \
            "Add brackets, or reword this, so it has only one meaning."
        indent = line.raw[:len(line.raw) - len(line.raw.lstrip())]
        ideas = [] if not same or self.r.quiet else \
            [indent + t for t in texts if reads_cleanly(self, line, indent + t)]
        return Problem(fix, why + " Plain never guesses, so you choose.",
                       line=line.number, col=self.t[0].col, end=self.t[-1].end, try_lines=texts, ideas=ideas)

    # Matching a phrase's words and slots ----------------------------------------------

    def align(self, elements, i, j, mode, w=False):
        """All ways the phrase's words and slots can cover tokens i..j exactly."""
        results = []
        count = len(elements)
        last_slot = max((e for e in range(count) if isinstance(elements[e], Slot)), default=-1)

        def rec(e, k, args, fixed, syn):
            if len(results) > MAX_READINGS:
                raise TooMany
            if e == count:
                if k == j:
                    results.append((dict(args), fixed, syn))
                return
            el = elements[e]
            if isinstance(el, Word):
                if k < j and word_matches(self.t[k], el.alts):
                    hit = syn
                    if self.t[k].norm not in el.alts:
                        hit = syn + [(k, el.main)]
                    rec(e + 1, k + 1, args, fixed | {k}, hit)
                if el.optional:
                    rec(e + 1, k, args, fixed, syn)
                return
            if e == count - 1:
                ends = [j]
            else:
                nxt = elements[e + 1]
                if isinstance(nxt, Word):
                    stops = {nxt}
                    m = e + 1
                    while isinstance(elements[m], Word) and elements[m].optional and m + 1 < count:
                        m += 1
                        if isinstance(elements[m], Word):
                            stops.add(elements[m])
                    ends = [end for end in range(k + 1, j)
                            if any(word_matches(self.t[end], s.alts) for s in stops)]
                else:
                    ends = range(k + 1, j)
            prev = elements[e - 1] if e > 0 else None
            after_of = isinstance(prev, Word) and prev.main == "of"
            for end in ends:
                for value in self.read_slot(el, k, end, mode, e == last_slot and e == count - 1, after_of, w):
                    args[el.name] = value
                    rec(e + 1, end, args, fixed, syn)
                    del args[el.name]

        try:
            rec(0, i, {}, frozenset(), [])
        except TooMany:
            pass
        return results

    def read_slot(self, slot, s, e, mode, last, after_of, w):
        if s >= e:
            return []
        kind = slot.kind
        if kind == "field":
            words = self.field_words(s, e)
            return [words] if words is not None else []
        if kind == "place":
            return [p for p in self.places(s, e)]
        if kind == "items":
            return self.items(s, e, w)
        if mode == "step":
            return self.check(s, e, w)
        if last:
            return self.ofv(s, e, w)
        return self.arith(s, e, w)

    def field_words(self, s, e):
        toks = self.t[s:e]
        if len(toks) == 1 and toks[0].kind == "text" and all(isinstance(p, str) for p in toks[0].value):
            return (Quoted("".join(toks[0].value)),)
        if toks and all(is_ordinary(t) or (k > 0 and t.kind == "number" and name_word(t))
                        for k, t in enumerate(toks)):
            return tuple(name_word(t) for t in toks)
        return None

    def items(self, s, e, w):
        """Values separated by commas and a final "and": a list of nodes."""
        splits = [k for k in range(s, e) if self.depth[k] == self.depth[s] and
                  (self.t[k].norm == "," or is_word(self.t[k], "and"))]
        if not splits:
            return [[v] for v in self.arith(s, e, w)]
        bounds = [s] + [k for k in splits] + [e]
        parts = []
        for a, b in zip(bounds, bounds[1:]):
            start = a if a == s else a + 1
            readings = [r for r in self.arith(start, b, w)]
            if len(readings) != 1:
                return []
            parts.append(readings[0])
        return [parts]

    # Places ----------------------------------------------------------------------------

    def read_place(self, i, j, declaring=False):
        """The NAME in "set NAME to" or "for each NAME in"."""
        toks = self.t[i:j]
        words = tuple(name_word(t) for t in toks)
        if declaring and None not in words and toks[0].kind == "word" and \
                not any(t.kind == "poss" for t in toks) and words in self.names:
            return N.Name(words, words in self.own, col=toks[0].col, end=toks[-1].end)
        places = self.places(i, j)
        if len(places) == 1:
            return places[0]
        col, end = span_cols(self.t, i, j)
        if declaring and None not in words and toks and toks[0].kind == "word":
            problem = name_problem(words, col=col, end=end)
            if problem is not None:
                raise problem
        raise Problem(
            "Write a name here, like score, or a field, like sale's amount.",
            "This is where Plain keeps the value, so it needs a name, a field or an item of a list.",
            col=col, end=end)

    def places(self, i, j):
        out = []
        for node in self.ofv(i, j, False):
            if isinstance(node, (N.Name, N.Field)) or (
                    isinstance(node, N.Value) and node.phrase.main.template.split()[0] in
                    ("item", "the") and "item" in node.phrase.main.template):
                out.append(node)
        return out

    # Checks: or / and / not -----------------------------------------------------------

    def remember(self, key, compute):
        if key in self.memo:
            return self.memo[key]
        self.memo[key] = []
        result = dedupe(compute())
        if len(result) > MAX_READINGS:
            result = result[:MAX_READINGS]
        self.memo[key] = result
        return result

    def check(self, i, j, w=False):
        if i >= j:
            return []
        return self.remember(("check", i, j, w), lambda: self._check(i, j, w))

    def _check(self, i, j, w):
        out = list(self.notlevel(i, j, w))
        for k in range(i + 1, j - 1):
            tok = self.t[k]
            if not is_word(tok, "and", "or") or self.depth[k] != self.depth[i]:
                continue
            op = tok.norm
            for left in self.check(i, k, w):
                if isinstance(left, N.Bad):
                    out.append(left)
                    continue
                if ends_with_list(left):
                    continue
                out += self.elided(left, op, k + 1, j, w)
                for right in self.check(k + 1, j, w):
                    if isinstance(right, N.Bad):
                        out.append(right)
                        continue
                    if starts_with_literal(right) or starts_with_comparison(self.t[k + 1]):
                        continue
                    out.append(N.make_logic(op, [left, right], col=self.t[i].col, end=self.t[j - 1].end))
        return out

    def elided(self, left, op, s, j, w):
        """'answer is "y" or "yes"': the right side reuses the left side's subject."""
        if isinstance(left, N.Logic):
            if not left.group:
                return []
            comp = left.items[-1]
        else:
            comp = left
        if not isinstance(comp, (N.Compare, N.Between, N.TypeCheck)):
            return []
        subject = comp.value if isinstance(comp, (N.Between, N.TypeCheck)) else comp.left
        negative = isinstance(comp, N.Between) or (isinstance(comp, N.TypeCheck) and comp.negated) or (
            isinstance(comp, N.Compare) and (comp.op in NEGATIVE_COMPARISONS or comp.said_not))
        news = []
        lits = self.literal(s, j)
        for lit in lits:
            if negative:
                news.append(self.negative_elision(left, comp, op, lit, s, j))
                continue
            if isinstance(comp, N.TypeCheck):
                continue
            if op == "and" and comp.op in ("is", "exact"):
                news.append(N.Bad(Problem(
                    'Use "or" here, or write the whole check again after "and".',
                    "A value can't be two things at once. Did you mean \"or\"?"),
                    col=self.t[s].col, end=self.t[j - 1].end))
                continue
            news.append(N.Compare(subject, comp.op, lit, col=lit.col, end=lit.end))
        # A comparison without its subject: "or more than 100".
        for words, cop in COMPARISONS + ELIDED_COMPARISONS:
            n = len(words)
            if s + n <= j and all(self.t[s + m].norm == words[m] for m in range(n)):
                for right in self.arith(s + n, j, w):
                    new = N.Compare(subject, cop, right, said_not="not" in words,
                                    col=self.t[s].col, end=self.t[j - 1].end)
                    news.append(self.written_out(left, comp, op, new, s, j) if negative else new)
        if s < j and is_word(self.t[s], "is"):
            for tc in self.type_checks(None, s, j, w, subject=subject):
                news.append(self.written_out(left, comp, op, tc, s, j) if negative else tc)
        out = []
        for new in news:
            if isinstance(new, N.Bad):
                out.append(new)
            else:
                out.append(N.make_logic(op, [left, new], group=True, col=left.col, end=self.t[j - 1].end))
        return out

    def negative_elision(self, left, comp, op, lit, s, j):
        subject = comp.value if isinstance(comp, (N.Between, N.TypeCheck)) else comp.left
        col = left.col if left.col is not None else self.t[s].col
        end = self.t[j - 1].end
        s_text = subject.canonical()
        alts = []
        if isinstance(comp, N.Compare):
            first = comp.canonical()
            alts.append(f"{first} and {s_text} {N.COMPARISON_WORDS[comp.op]} {lit.canonical()}")
            if comp.op == "is not":
                alts.append(f"{s_text} is not in a list of {comp.right.canonical()} and {lit.canonical()}")
        elif isinstance(comp, N.Between):
            alts.append(f"{comp.canonical()} {op} {s_text} is {lit.canonical()}")
        return N.Bad(elision_problem(comp, op), alts, col=col, end=end)

    def written_out(self, left, comp, op, new, s, j):
        """After a negative check or "between", the second check needs its first part too."""
        col = left.col if left.col is not None else self.t[s].col
        return N.Bad(elision_problem(comp, op), [f"{left.canonical()} {op} {new.canonical()}"],
                     col=col, end=self.t[j - 1].end)

    def literal(self, s, j):
        toks = self.t[s:j]
        if len(toks) == 1:
            tok = toks[0]
            if tok.kind == "number":
                return [N.Lit(tok.value, raw=tok.raw, percent=tok.percent, col=tok.col, end=tok.end)]
            if tok.kind == "text":
                return [self.text_node(tok)]
            if tok.kind == "word" and tok.norm in ("yes", "true", "no", "false", "nothing"):
                value = {"yes": True, "true": True, "no": False, "false": False, "nothing": None}[tok.norm]
                return [N.Lit(value, col=tok.col, end=tok.end)]
            if tok.kind == "word" and tok.norm in NUMBER_WORDS:
                return [N.Lit(Decimal(NUMBER_WORDS[tok.norm]), col=tok.col, end=tok.end)]
        if len(toks) == 2 and toks[0].norm == "-" and toks[1].kind == "number":
            return [N.Lit(-toks[1].value, raw="-" + toks[1].raw, col=toks[0].col, end=toks[1].end)]
        if is_percent(toks):
            return [percent_lit(toks)]
        return []

    def notlevel(self, i, j, w):
        if i >= j:
            return []
        out = []
        if is_word(self.t[i], "not") and i + 1 < j:
            out += [N.Not(x, col=self.t[i].col, end=self.t[j - 1].end) if not isinstance(x, N.Bad) else x
                    for x in self.notlevel(i + 1, j, w)]
        out += self.compare(i, j, w)
        return out

    def compare(self, i, j, w):
        out = list(self.arith(i, j, w))
        for k in range(i + 1, j):
            if self.depth[k] != self.depth[i]:
                continue
            tok = self.t[k]
            if tok.kind not in ("word", "symbol") or tok.norm not in COMPARISON_FIRST:
                continue
            lefts = None
            for words, op in COMPARISONS:
                n = len(words)
                if k + n < j + 1 and all(self.t[k + m].norm == words[m] for m in range(n)) and k + n < j:
                    if lefts is None:
                        lefts = self.cmp_left(i, k, w)
                    if not lefts:
                        break
                    for right in self.arith(k + n, j, w):
                        for left in lefts:
                            if isinstance(left, N.Bad):
                                out.append(left)
                            elif isinstance(right, N.Bad):
                                out.append(right)
                            else:
                                out.append(N.Compare(left, op, right, said_not="not" in words,
                                                     col=self.t[i].col, end=self.t[j - 1].end))
            if is_word(tok, "is"):
                if lefts is None:
                    lefts = self.cmp_left(i, k, w)
                for left in lefts:
                    out += self.type_checks(left, k, j, w)
        return out

    def type_checks(self, left, k, j, w, subject=None):
        """is [not] empty / a number / even / divisible by N / between A and B."""
        subject = subject if subject is not None else left
        out = []
        n = k + 1
        negated = n < j and is_word(self.t[n], "not")
        if negated:
            n += 1
        words = tuple(t.norm for t in self.t[n:j])
        col, end = self.t[k].col if left is None else subject.col, self.t[j - 1].end
        if words in TYPE_CHECKS:
            out.append(N.TypeCheck(subject, TYPE_CHECKS[words], negated, col=col, end=end))
        if words[:2] == ("divisible", "by") and n + 2 < j:
            for arg in self.arith(n + 2, j, w):
                out.append(N.TypeCheck(subject, "divisible", negated, arg, col=col, end=end))
        if words[:1] == ("between",):
            for m in range(n + 2, j - 1):
                if is_word(self.t[m], "and") and self.depth[m] == self.depth[n]:
                    for low in self.arith(n + 1, m, w):
                        for high in self.arith(m + 1, j, w):
                            out.append(N.Between(subject, low, high, negated, col=col, end=end))
        return out

    def cmp_left(self, i, k, w):
        if w and all(is_ordinary(t) for t in self.t[i:k]):
            words = tuple(t.norm for t in self.t[i:k])
            return [N.RowField(words, col=self.t[i].col, end=self.t[k - 1].end)]
        return self.arith(i, k, w)

    # Arithmetic -----------------------------------------------------------------------

    def arith(self, i, j, w=False):
        if i >= j:
            return []
        return self.remember(("sum", i, j, w), lambda: self._sum(i, j, w))

    def _sum(self, i, j, w):
        out = list(self.product(i, j, w))
        for k in range(i + 1, j - 1):
            tok = self.t[k]
            if self.depth[k] != self.depth[i] or tok.kind not in ("word", "symbol") or tok.norm not in ADD_OPS:
                continue
            op = ADD_OPS[tok.norm]
            for left in self.arith(i, k, w):
                for right in self.product(k + 1, j, w):
                    out.append(self.combine(op, left, right, i, j))
        return [x for x in out if x is not None]

    def product(self, i, j, w):
        return self.remember(("product", i, j, w), lambda: self._product(i, j, w))

    def _product(self, i, j, w):
        out = list(self.unary(i, j, w))
        for k in range(i + 1, j - 1):
            tok = self.t[k]
            if self.depth[k] != self.depth[i] or tok.kind not in ("word", "symbol"):
                continue
            size, op = 0, None
            if tok.norm in MUL_OPS:
                size, op = 1, MUL_OPS[tok.norm]
            elif k + 1 < j and (tok.norm, self.t[k + 1].norm) in MUL_TWO_WORD_OPS:
                size, op = 2, MUL_TWO_WORD_OPS[(tok.norm, self.t[k + 1].norm)]
            if not op or k + size >= j:
                continue
            for left in self.product(i, k, w):
                for right in self.unary(k + size, j, w):
                    out.append(self.combine(op, left, right, i, j))
        return [x for x in out if x is not None]

    def combine(self, op, left, right, i, j):
        if isinstance(left, N.Bad):
            return left
        if isinstance(right, N.Bad):
            return right
        if starts_with_postfix(right):
            return None   # a postfix word applies to all the arithmetic on its left
        col, end = self.t[i].col, self.t[j - 1].end
        tail = open_tail(left)
        if tail is not None:
            phrase_text = tail.canonical()
            slot_node = tail.args[tail.phrase.slots[-1].name]
            right_text = right.canonical()
            whole_left = left.canonical()
            a = f"({whole_left}) {op} {right_text}" if tail is left else None
            slot_text = slot_node.canonical()
            b_inner = phrase_text[: len(phrase_text) - len(slot_text)] + f"({slot_text} {op} {right_text})"
            alts = [a or f"({phrase_text}) {op} {right_text}", b_inner]
            return N.Bad(Problem(
                "Add brackets to show which numbers go together.",
                f'Plain can read this two ways: the {op} could belong to the last number of '
                f'"{tail.phrase.main.template.split("{")[0].strip()} …", or come after it.'),
                alts, col=col, end=end)
        if op == "plus" and (isinstance(left, N.TextLit) or isinstance(right, N.TextLit)):
            joined = '"' + text_inside(left) + text_inside(right) + '"'
            both = isinstance(left, N.TextLit) and isinstance(right, N.TextLit)
            return N.Bad(Problem(
                "Write the two texts as one text." if both else "Put the value inside the text with { }.",
                'In Plain, "plus" and "+" only add numbers. To join text, write the value in { } inside the text.'),
                [joined], col=col, end=end)
        if op in ("plus", "minus") and isinstance(right, N.Lit) and right.percent:
            lt = left.canonical()
            pct = right.canonical()
            frac = N.number_text(right.value)
            return N.Bad(Problem(
                f"Write what the {pct} is a part of.",
                f'"{lt} {op} {pct}" could mean {op} {pct} of {lt}, or {op} {frac}.'),
                [f"{lt} {op} {pct} of {lt}", f"{lt} {op} {frac}"], col=col, end=end)
        return N.Math(op, left, right, col=col, end=end)

    def unary(self, i, j, w):
        if i >= j:
            return []
        out = []
        tok = self.t[i]
        if tok.kind == "symbol" and tok.norm == "-" and i + 1 < j:
            # The minus sign holds tighter than "rounded": -2.5 rounded is (-2.5) rounded.
            for x in self.unary(i + 1, j, w):
                if not isinstance(x, N.Postfix):
                    out.append(x if isinstance(x, N.Bad) else N.Neg(x, col=tok.col, end=self.t[j - 1].end))
        out += self.ofv(i, j, w)
        out += self.postfixed(i, j, w)
        return out

    def postfixed(self, i, j, w):
        return self.remember(("postfix", i, j, w), lambda: self._postfixed(i, j, w))

    def _postfixed(self, i, j, w):
        out = []
        for phrase in self.r.postfix:
            starter = phrase.elements[1]
            for k in range(i + 1, j):
                if not word_matches(self.t[k], starter.alts) or self.depth[k] != self.depth[i]:
                    continue
                matches = self.align(phrase.elements[1:], k, j, "value", w)
                if not matches:
                    continue
                for operand in self.arith(i, k, w):
                    for args, fixed, syn in matches:
                        if isinstance(operand, N.Bad):
                            out.append(operand)
                            continue
                        bad = [v for v in args.values() if isinstance(v, N.Bad)]
                        if bad:
                            out.append(bad[0])
                            continue
                        node = N.Postfix(phrase, operand, args, col=self.t[i].col, end=self.t[j - 1].end)
                        node.syn = [(self.t[k].col, self.t[k].end, main) for k, main in syn]
                        out.append(node)
        return out

    # Values: atoms, fields, phrases, where -----------------------------------------------

    def ofv(self, i, j, w=False):
        if i >= j:
            return []
        return self.remember(("ofv", i, j, w), lambda: self._ofv(i, j, w))

    def _ofv(self, i, j, w):
        out = list(self.atoms(i, j, w))
        t = self.t
        col, end = t[i].col, t[j - 1].end
        # sale's amount
        for k in range(i + 1, j - 1):
            if t[k].kind == "poss" and self.depth[k] == self.depth[i]:
                words = self.field_words(k + 1, j)
                if words is None:
                    continue
                for base in self.ofv(i, k, w):
                    if isinstance(base, N.Value) and isinstance(base.phrase.elements[-1], Slot):
                        continue   # "the first item of places's results": 's belongs to places
                    if isinstance(base, (N.Name, N.Field, N.Paren, N.It, N.Value, N.RowField)) and \
                            not (isinstance(base, N.Field) and base.of_form):
                        out.append(self.field_node(base, words, col, end, self.raw_words(k + 1, j)))
        # 15% of bill
        if t[i].kind == "number" and t[i].percent and i + 2 < j + 1 and i + 1 < j and is_word(t[i + 1], "of"):
            pct = N.Lit(t[i].value, raw=t[i].raw, percent=True, col=t[i].col, end=t[i].end)
            for v in self.ofv(i + 2, j, w):
                out.append(v if isinstance(v, N.Bad) else N.PercentOf(pct, v, col=col, end=end))
        if i + 2 < j and is_percent(t[i:i + 2]) and is_word(t[i + 2], "of"):
            pct = percent_lit(t[i:i + 2])
            for v in self.ofv(i + 3, j, w):
                out.append(v if isinstance(v, N.Bad) else N.PercentOf(pct, v, col=col, end=end))
        # Built-in value phrases
        first = t[i]
        if first.kind == "word":
            seen = set()
            for word in {first.norm, SYNONYMS.get(first.norm)}:
                for phrase in self.r.value_index.get(word, []):
                    if id(phrase) in seen:
                        continue
                    seen.add(id(phrase))
                    for args, fixed, syn in self.align(phrase.elements, i, j, "value", w):
                        bad = [v for v in args.values() if isinstance(v, N.Bad)]
                        if bad:
                            out.append(bad[0])
                            continue
                        node = self.value_node(phrase, args, col, end)
                        node.syn = [(self.t[k].col, self.t[k].end, main) for k, main in syn]
                        out.append(node)
        # the amounts of sales (a field of a record, or a column of a table).
        # A phrase covering the same words wins over this reading.
        phrase_found = any(isinstance(x, N.Value) for x in out)
        for k in range(i + 1, j - 1):
            if phrase_found:
                break
            if is_word(t[k], "of") and self.depth[k] == self.depth[i]:
                words = self.field_words(i, k)
                if words is None or self.is_property(i, k):
                    continue
                for target in self.ofv(k + 1, j, w):
                    if isinstance(target, N.Bad):
                        out.append(target)
                    else:
                        out.append(N.Field(target, words, quoted=isinstance(words[0], Quoted), of_form=True,
                                           raw=self.raw_words(i, k), col=col, end=end))
        # sales where amount is more than 100. The check runs to the end of the line, a closing
        # bracket, or the next word of the step.
        for k in range(i + 1, j - 1):
            if j not in self.boundaries:
                break
            if is_word(t[k], "where") and self.depth[k] == self.depth[i]:
                bases = [b for b in self.ofv(i, k, w)
                         if isinstance(b, (N.Name, N.Paren)) or (isinstance(b, N.Field) and not b.of_form)]
                if not bases:
                    continue
                for c in self.check(k + 1, j, True):
                    for base in bases:
                        out.append(c if isinstance(c, N.Bad) else N.Where(base, c, col=col, end=end))
        return out

    def is_property(self, i, k):
        words = tuple(SYNONYMS.get(t.norm, t.norm) for t in self.t[i:k])
        return words in self.r.property_prefixes

    def field_node(self, base, words, col, end, raw=None):
        return N.Field(base, words, quoted=isinstance(words[0], Quoted), raw=raw, col=col, end=end)

    def raw_words(self, s, e):
        return tuple(t.raw for t in self.t[s:e])

    def value_node(self, phrase, args, col, end):
        last = phrase.elements[-1]
        open_end = isinstance(last, Slot) and last.kind not in ("items", "field") and not (
            len(phrase.elements) > 1 and isinstance(phrase.elements[-2], Word)
            and phrase.elements[-2].main == "of")
        return N.Value(phrase, args, open_end, col=col, end=end)

    def atoms(self, i, j, w):
        t = self.t
        out = []
        if j == i + 2 and is_percent(t[i:j]):   # 15 percent
            out.append(percent_lit(t[i:j]))
        if j == i + 1:
            out += self.literal(i, j)
            tok = t[i]
            if w and is_word(tok, "it"):
                out.append(N.It(col=tok.col, end=tok.end))
        if j - i <= self.max_name:
            words = tuple(name_word(tok) for tok in t[i:j])
            if None not in words and t[i].kind == "word" and words in self.names:
                out.append(N.Name(words, words in self.own, col=t[i].col, end=t[j - 1].end))
        if t[i].norm == "(" and t[j - 1].norm == ")" and j - i > 2 and self.matching(i, j - 1):
            for inner in self.check(i + 1, j - 1, w):
                out.append(inner if isinstance(inner, N.Bad) else N.Paren(inner, col=t[i].col, end=t[j - 1].end))
        if w and is_word(t[i], "its") and j > i + 1:
            words = self.field_words(i + 1, j)
            if words is not None:
                out.append(N.RowField(words, quoted=isinstance(words[0], Quoted), col=t[i].col, end=t[j - 1].end))
        return out

    def matching(self, open_index, close_index):
        depth = 0
        for k in range(open_index, close_index + 1):
            if self.t[k].norm == "(":
                depth += 1
            elif self.t[k].norm == ")":
                depth -= 1
                if depth == 0 and k != close_index:
                    return False
        return depth == 0

    def text_node(self, tok):
        pieces = []
        for piece in tok.value:
            if isinstance(piece, str):
                pieces.append(piece)
                continue
            view = make_view(piece.tokens, line_start=False)
            sub = LineReader(self.r, view, self.names, self.own)
            sub.scope = self.scope
            sub.line = self.line
            readings = sub.check(0, len(view)) if view else []
            bad = [r for r in readings if isinstance(r, N.Bad)]
            if bad:
                if self.line is not None:
                    raise sub.bad_problem(bad[0], self.line)
                raise bad[0].problem.at(None, piece.col, piece.end)
            if len(readings) != 1:
                if not readings:
                    problem = sub.explain_failure(0, len(view), PieceLine(piece, self.line), check=False)
                    raise problem
                if self.line is not None:
                    raise sub.tie_problem(readings[0], readings[1], view[0].col, view[-1].end, self.line)
                raise Problem("Add brackets inside the { } so it has only one meaning.",
                              "Plain can read it two ways, and it never guesses which one you mean.",
                              col=piece.col, end=piece.end)
            self.synonym_edits += sub.synonym_edits
            pieces.append(readings[0])
        url = bool(pieces) and isinstance(pieces[0], str) and pieces[0].lower().startswith(("http://", "https://"))
        return N.TextLit(pieces, url, col=tok.col, end=tok.end)


class PieceLine:
    """A {…} piece of a text, read as part of its line."""

    def __init__(self, piece, line):
        self.number = line.number if line is not None else None
        self.raw = line.raw if line is not None else ""
        self.indent = line.indent if line is not None else 0
        self.body = getattr(line, "body", [])
        self.tokens = piece.tokens
        self.piece = piece
        self.whole = line


COMPARISON_FIRST = {words[0] for words, _ in COMPARISONS}


def dedupe(readings):
    seen, out = set(), []
    for r in readings:
        if r is None:
            continue
        # "x is empty" prints the same whether "empty" is your name or Plain's check, so the
        # kind of node is part of the key.
        key = (type(r).__name__, r.canonical()) if not isinstance(r, N.Bad) else ("bad", r.problem.fix, r.col)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def elision_problem(comp, op):
    said = 'After "is not" or "between"'
    if isinstance(comp, N.Compare) and comp.op in ("not contains", "not starts", "not ends"):
        said = 'After "does not"'
    return Problem(f'Write the whole check again after "{op}", so it has only one meaning.',
                   f"{said}, leaving out the first part could mean two different things.")


def ends_with_list(node):
    """True when the last thing in this check is "a list of …" without brackets."""
    while True:
        if isinstance(node, N.Value) and node.phrase.main.template.startswith("a list of"):
            return True
        if isinstance(node, N.Compare):
            node = node.right
        elif isinstance(node, N.Logic):
            node = node.items[-1]
        else:
            return False


def starts_with_literal(node):
    while isinstance(node, N.Logic):
        node = node.items[0]
    if isinstance(node, N.Neg):   # -6 is a written number too
        node = node.value
    return isinstance(node, (N.Lit, N.TextLit))


def starts_with_comparison(tok):
    return tok.kind in ("word", "symbol") and tok.norm in COMPARISON_FIRST and tok.norm != "not"


def starts_with_postfix(node):
    while True:
        if isinstance(node, N.Postfix):
            return True
        if isinstance(node, N.Math):
            node = node.left
        else:
            return False


def text_inside(node):
    """How a value is written inside text: the words of a text, or {value}."""
    if isinstance(node, N.TextLit):
        return node.canonical()[1:-1]
    return "{" + node.canonical() + "}"


def open_tail(node):
    """The value phrase at the right end of this arithmetic whose last slot is open."""
    while True:
        if isinstance(node, N.Value):
            return node if node.open_end else None
        if isinstance(node, N.Math):
            node = node.right
        elif isinstance(node, N.Neg):
            node = node.value
        else:
            return None


def nodes_in(node):
    if isinstance(node, N.Node):
        yield node
        for value in vars(node).values():
            yield from nodes_in(value)
    elif isinstance(node, (list, tuple)):
        for item in node:
            yield from nodes_in(item)
    elif isinstance(node, dict):
        for item in node.values():
            yield from nodes_in(item)


def names_in(node):
    return (n for n in nodes_in(node) if isinstance(n, N.Name))


def split_name(a, b):
    """(name, a, b) when reading a uses one of your names on words that reading b doesn't
    read as that name, like "under time" in: if hours is under time. The longest such name."""
    spans = {(n.col, n.end) for n in names_in(b)}
    split = [n for n in names_in(a) if n.col is not None and (n.col, n.end) not in spans]
    if not split:
        return None
    return max(split, key=lambda n: n.end - n.col), a, b


def same_as_text(reading, name):
    """The reading that uses your name, written with "is the same as" so it differs from the
    reading that uses Plain's words: if hours is the same as under time."""
    for node in nodes_in(reading):
        if isinstance(node, N.Compare) and node.op == "is" and node.right is name:
            node.right = N.Name(("the same as",) + name.words)
            try:
                return reading.canonical()
            finally:
                node.right = name
    return reading.canonical()


def replace_span(raw, col, end, text):
    if col is None:
        return text
    before = raw[:col]
    m = re.match(r"^\(?(a|an|the) ", text, flags=re.IGNORECASE)
    if m:
        article = m.group(1).lower()
        tail = before.rstrip()
        if re.search(r"(^|[\s{(])" + article + "$", tail, flags=re.IGNORECASE):
            before = tail[:-len(article)]
    return (before + text + raw[end:]).strip()


def howto_template(line, view):
    """The wording of your step as you wrote it, with {name} for each bracketed part."""
    raw = line.raw
    start = view[2].col
    text = raw[start:view[-1].end]
    out, k = [], 0
    while k < len(text):
        if text[k] == "(":
            close = text.find(")", k)
            out.append("{" + " ".join(text[k + 1:close].lower().split()) + "}")
            k = close + 1
        else:
            out.append(text[k].lower())
            k += 1
    return " ".join("".join(out).split())


def read_program(text, **kwargs):
    return Reader(**kwargs).read(text)
