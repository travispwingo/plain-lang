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
from .source import Piece, build_blocks, read_lines
from .values import Quoted
from .words import (ADD_OPS, ARTICLES, COMPARISONS, CORE_STARTS, ELIDED_COMPARISONS,
                    LINE_ALIASES, MUL_OPS, MUL_TWO_WORD_OPS, NEGATIVE_COMPARISONS,
                    NUMBER_WORDS, POLITE_STARTS, SPECIAL_WORDS, SYNONYMS, TYPE_CHECKS)

MAX_WORDS = 40
MAX_READINGS = 16
RESERVED_NAMES = {("problem",): "the problem", ("timer",): "the timer"}


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
        while len(toks) > 1 and toks[0].kind == "word" and toks[0].norm in POLITE_STARTS:
            toks.pop(0)
    norms = [t.norm for t in toks]
    keep_commas = any(norms[k] == "list" and k + 1 < len(norms) and norms[k + 1] == "of"
                      for k in range(len(norms))) or "choices" in norms or "options" in norms
    out = []
    for index, tok in enumerate(toks):
        if tok.kind == "symbol" and tok.norm == "," and not keep_commas:
            continue
        if tok.kind == "word" and tok.norm in ARTICLES:
            nxt = toks[index + 1] if index + 1 < len(toks) else None
            if nxt is not None and nxt.kind == "word" and nxt.norm not in SPECIAL_WORDS \
                    and nxt.norm not in ARTICLES:
                continue
        out.append(tok)
    return out


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


def span_cols(tokens, i, j):
    if i >= j:
        return None, None
    return tokens[i].col, tokens[j - 1].end


# Program --------------------------------------------------------------------------

@dataclass
class HowToDef:
    phrase: Phrase
    params: list
    line: object
    own_names: set = field(default_factory=set)
    gives: bool = False


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
        for line in top:
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
        main_lines = [line for line in top if not (self.first(line) == "how" and line.problem is None)]
        self.main_names = set(self.known_names)
        for line in walk(main_lines):
            self.declare(line, self.main_names, problems)
        for line, howto in howto_lines:
            names = set()
            for inner in walk(line.body):
                self.declare(inner, names, problems)
            howto.own_names = set(howto.params) | (names - self.main_names)

        statements = self.read_body(top, problems, scope=None)
        self.check_placement(statements, problems, in_repeat=False, in_howto=False)
        problems.sort(key=lambda p: (p.line or 0, p.col or 0))
        return Program(statements, dedupe_problems(problems), source_lines, self.main_names,
                       self.howtos, self.origins, top)

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
        parts, params, k = [], [], 2
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
            word = parts[0].main if parts and isinstance(parts[0], Word) else "("
            problems.append(Problem(
                "Start your own step with a word that says what it does, like: how to greet (person)",
                f'"{word}" already starts one of Plain\'s own lines, so it can\'t start yours.',
                line=line.number, col=view[2].col, end=view[-1].end))
            return None
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
            seen[shape] = howto.phrase

    # Declaring names ---------------------------------------------------------------

    def declare(self, line, names, problems):
        if line.problem is not None:
            return
        view = make_view(line.tokens)
        if not view:
            return
        first = view[0].norm
        norms = [t.norm for t in view]
        if first == "set" and "to" in norms:
            k = norms.index("to")
            target = view[1:k]
            if target and not any(t.kind == "poss" for t in target) and \
                    not (target[0].kind == "word" and target[0].norm in ("item", "first", "last")):
                self.add_name(target, names, line, problems)
        if first in ("repeat", "for") or (first == "repeat" and len(view) > 1):
            start = 1 if first == "for" else 2
            if len(view) > start and view[start - 1].norm == "for" if first == "repeat" else True:
                if len(view) > start and view[start].norm in ("each", "every"):
                    rest = norms[start + 1:]
                    stop = next((m for m, w in enumerate(rest) if w in ("in", "from")), None)
                    if stop:
                        self.add_name(view[start + 1:start + 1 + stop], names, line, problems)
        k = find_call_it(view)
        if k is not None:
            self.add_name(view[k + 3:], names, line, problems, quiet=True)
        # Names a broken line probably meant to set, so later lines don't pile up problems.
        if len(view) >= 3 and first not in CORE_STARTS:
            for m, tok in enumerate(view):
                if tok.norm in ("is", "=", "+", "-") and m > 0 and all(name_word(t) for t in view[:m]):
                    if tok.norm in ("is", "=") or (m + 1 < len(view) and view[m + 1].norm == "="):
                        self.add_name(view[:m], names, line, problems, quiet=True)
                    break

    def add_name(self, toks, names, line, problems, quiet=False):
        words = tuple(name_word(t) for t in toks)
        if not toks or None in words or toks[0].kind != "word":
            return
        if words in RESERVED_NAMES:
            if not quiet:
                problems.append(Problem(
                    f'Choose another name than "{words[0]}".',
                    f'"{RESERVED_NAMES[words]}" is a value Plain already has.',
                    line=line.number, col=toks[0].col, end=toks[-1].end))
            return
        special = [t for k, t in enumerate(toks) if t.kind == "word" and t.norm in SPECIAL_WORDS
                   and not (k > 0 and t.norm in NUMBER_WORDS)]
        if special:
            if not quiet:
                name = " ".join(words)
                problems.append(Problem(
                    f'Rename "{name}", for example to "{suggest_rename(words)}".',
                    f'"{special[0].norm}" is one of Plain\'s special words, so it can\'t be part of a name.',
                    line=line.number, col=toks[0].col, end=toks[-1].end))
            return
        names.add(words)
        self.origins.setdefault(words, line.number)

    # Bodies ------------------------------------------------------------------------

    def read_body(self, lines, problems, scope):
        statements = []
        for line in lines:
            if line.problem is not None:
                statements.append(N.ErrorBlock(self.read_body(line.body, problems, scope), line=line.number))
                continue
            try:
                stmt = self.read_line(line, scope, problems)
            except Problem as problem:
                problems.append(problem.at(line.number))
                statements.append(N.ErrorBlock(self.read_body(line.body, problems, scope), line=line.number))
                continue
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
                elif kind == "fails" and isinstance(prev, N.Try) and not prev.fallback:
                    prev.fallback = payload
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
        elif isinstance(stmt, tuple) and isinstance(stmt[1], tuple):
            pass
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
                                  None, line=L, col=view[3].col, end=view[-1].end)
                return ("fails", body())
            if norms[1:3] == ["it", "fails"]:
                raise Problem('Write "if that fails" instead of "if it fails".',
                              'In Plain, "it" means the item being checked inside "where".',
                              line=L, col=view[0].col, end=view[2].end, try_lines=["if that fails"],
                              ideas=[line.raw.replace(view[1].raw, "that", 1)])
            then = reader.find_then(1)
            if then is not None and then < n - 1 and not line.body:
                check = reader.one(reader.check(1, then), 1, then, line, check=True)
                inner = self.read_inline_step(view[then + 1:], line, scope, problems)
                return N.If([(check, [inner])], branch_lines=[L], line=L)
            stop = then if then is not None and then == n - 1 else n
            check = reader.one(reader.check(1, stop), 1, stop, line, check=True)
            return N.If([(check, body())], branch_lines=[L], line=L)

        if first == "otherwise":
            if n > 1 and norms[1] == "if":
                check = reader.one(reader.check(2, n), 2, n, line, check=True)
                return ("otherwise", (check, body(), L))
            if n > 1:
                raise Problem('Put the steps for "otherwise" on the lines below it, moved 4 spaces to the right.',
                              None, line=L, col=view[1].col, end=view[-1].end)
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
                              None, line=L, col=view[1].col, end=view[-1].end)
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

    def read_inline_step(self, tokens, line, scope, problems):
        sub = Line_(line, tokens)
        stmt = self.read_core(tokens[0].norm if tokens[0].kind == "word" else "", tokens, sub, scope,
                              problems, self.line_reader(tokens, scope))
        if stmt is NotCore:
            stmt = self.line_reader(tokens, scope).read_step_line(0, len(tokens), sub)
        if isinstance(stmt, tuple) or stmt is None:
            raise Problem('Put this step on its own line under the "if".', None,
                          line=line.number, col=tokens[0].col, end=tokens[-1].end)
        return stmt

    def read_repeat(self, view, line, reader, body, problems):
        L = line.number
        norms = [t.norm for t in view]
        n = len(view)
        k = 1 if norms[0] == "repeat" else 0
        if k >= n:
            raise Problem('Say how to repeat, like: repeat 3 times, repeat forever or repeat until done is yes',
                          None, line=L, col=view[0].col, end=view[-1].end)
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
                              None, line=L, col=view[0].col, end=view[-1].end)
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
                    f'"{word}" only has a meaning while steps are repeating.', line=stmt.line))
            elif isinstance(stmt, N.GiveBack) and not in_howto:
                problems.append(Problem(
                    'Move "give back" inside a "how to", or delete it.',
                    '"give back" hands a value back from one of your own steps.', line=stmt.line))
            elif isinstance(stmt, N.Step) and stmt.call_it and not stmt.phrase.gives:
                what = "your step" if isinstance(stmt.phrase.run, HowToDef) else f'"{stmt.phrase.main.template.split()[0]}"'
                problems.append(Problem(
                    f'Remove "and call it {" ".join(stmt.call_it)}", or add "give back" to {what}.',
                    f'{what[0].upper() + what[1:]} gives nothing back, so there is no value to keep.',
                    line=stmt.line))
            for child, repeat, howto in children(stmt):
                self.check_placement(child, problems, in_repeat or repeat,
                                     in_howto or howto)


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


def suggest_rename(words):
    words = list(words)
    if len(words) >= 3 and words[1] == "of" and words[0] == "number":
        return " ".join(words[2:]) + " count"
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
        a, b = readings[0].canonical(), readings[1].canonical()
        raise Problem(
            "Add brackets, or reword this, so it has only one meaning.",
            "Plain can read it two ways, and it never guesses which one you mean.",
            line=line.number, col=col, end=end,
            try_lines=[replace_span(line.raw, col, end, a), replace_span(line.raw, col, end, b)])

    def bad_problem(self, bad, line):
        problem = bad.problem
        problem.line = line.number
        if problem.col is None and bad.col is not None:
            problem.col, problem.end = bad.col, bad.end
        if bad.alts and bad.col is not None:
            problem.try_lines = [replace_span(line.raw, bad.col, bad.end, alt) for alt in bad.alts]
            problem.ideas = list(problem.try_lines)
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
        call_it = None
        k = find_call_it(self.t[i:j])
        if k is not None:
            k += i
            name_toks = self.t[k + 3:j]
            words = tuple(name_word(t) for t in name_toks)
            if not name_toks or None in words:
                raise Problem("Write a name after \"and call it\", like: and call it answer",
                              None, line=line.number, col=self.t[k].col, end=self.t[j - 1].end)
            call_it = words
            j = k
        readings = self.step_readings(i, j)
        stmt = self.choose_step(readings, i, j, line)
        stmt.call_it = call_it
        return stmt

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
        for phrase, args, _, _ in (a, b):
            text = phrase.main.render({k: N.arg_text(v) for k, v in args.items()})
            origin = "your step" if isinstance(phrase.run, HowToDef) else "Plain's phrase"
            texts.append(f"{text}    ({origin} \"{phrase.main.template}\")")
        return Problem(
            "Reword this line, or rename your step, so the line has only one meaning.",
            why + " Plain never guesses, so you choose.",
            line=line.number, col=self.t[0].col, end=self.t[-1].end, try_lines=texts)

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
            special = [t.norm for t in toks if t.norm in SPECIAL_WORDS]
            if special:
                raise Problem(
                    f'Rename "{" ".join(words)}", for example to "{suggest_rename(words)}".',
                    f'"{special[0]}" is one of Plain\'s special words, so it can\'t be part of a name.',
                    col=col, end=end)
            if words in RESERVED_NAMES:
                raise Problem(f'Choose another name than "{words[0]}".',
                              f'"{RESERVED_NAMES[words]}" is a value Plain already has.', col=col, end=end)
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
        news = []
        lits = self.literal(s, j)
        for lit in lits:
            if isinstance(comp, N.Between) or (isinstance(comp, N.Compare) and comp.op in NEGATIVE_COMPARISONS) \
                    or (isinstance(comp, N.TypeCheck) and comp.negated):
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
                    news.append(N.Compare(subject, cop, right, col=self.t[s].col, end=self.t[j - 1].end))
        if s < j and is_word(self.t[s], "is"):
            for tc in self.type_checks(None, s, j, w, subject=subject):
                news.append(tc)
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
        problem = Problem(
            "Write the whole check again after \"" + op + "\", so it has only one meaning.",
            'After "is not" or "between", leaving out the first part could mean two different things.')
        return N.Bad(problem, alts, col=col, end=end)

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
                                out.append(N.Compare(left, op, right, col=self.t[i].col, end=self.t[j - 1].end))
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
            for x in self.unary(i + 1, j, w):
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
                    if isinstance(base, (N.Name, N.Field, N.Paren, N.It, N.Value, N.RowField)) and \
                            not (isinstance(base, N.Field) and base.of_form):
                        out.append(self.field_node(base, words, col, end))
        # 15% of bill
        if t[i].kind == "number" and t[i].percent and i + 2 < j + 1 and i + 1 < j and is_word(t[i + 1], "of"):
            pct = N.Lit(t[i].value, raw=t[i].raw, percent=True, col=t[i].col, end=t[i].end)
            for v in self.ofv(i + 2, j, w):
                out.append(v if isinstance(v, N.Bad) else N.PercentOf(pct, v, col=col, end=end))
        if t[i].kind == "number" and i + 2 < j and is_word(t[i + 1], "percent") and is_word(t[i + 2], "of"):
            pct = N.Lit(t[i].value / 100, raw=t[i].raw + "%", percent=True, col=t[i].col, end=t[i + 1].end)
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
                        out.append(N.Field(target, words, of_form=True, col=col, end=end))
        # sales where amount is more than 100
        for k in range(i + 1, j - 1):
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

    def field_node(self, base, words, col, end):
        return N.Field(base, words, quoted=isinstance(words[0], Quoted), col=col, end=end)

    def value_node(self, phrase, args, col, end):
        last = phrase.elements[-1]
        open_end = isinstance(last, Slot) and last.kind not in ("items", "field") and not (
            len(phrase.elements) > 1 and isinstance(phrase.elements[-2], Word)
            and phrase.elements[-2].main == "of")
        return N.Value(phrase, args, open_end, col=col, end=end)

    def atoms(self, i, j, w):
        t = self.t
        out = []
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
                raise bad[0].problem.at(None, piece.col, piece.end)
            if len(readings) != 1:
                if not readings:
                    problem = sub.explain_failure(0, len(view), PieceLine(piece, self.line), check=False)
                    raise problem
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
        key = r.canonical() if not isinstance(r, N.Bad) else ("bad", r.problem.fix, r.col)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


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


def names_in(node):
    if isinstance(node, N.Name):
        yield node
    elif isinstance(node, N.Node):
        for value in vars(node).values():
            if isinstance(value, N.Node):
                yield from names_in(value)
            elif isinstance(value, list):
                for item in value:
                    yield from names_in(item)
            elif isinstance(value, dict):
                for item in value.values():
                    yield from names_in(item)
    elif isinstance(node, list):
        for item in node:
            yield from names_in(item)


def replace_span(raw, col, end, text):
    if col is None:
        return text
    before = raw[:col]
    m = re.match(r"^\(?(a|an|the) ", text, flags=re.IGNORECASE)
    if m:
        article = m.group(1).lower()
        tail = before.rstrip()
        if tail.lower().endswith(" " + article) or tail.lower() == article:
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
