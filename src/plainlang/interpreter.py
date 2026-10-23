"""Running a program that Plain has read. Every side effect goes through the host."""

import copy
import csv
import json
import sys
from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation, Overflow
from pathlib import Path
from urllib.parse import quote

from . import nodes as N
from .parser import HowToDef, Reader
from .problems import Problem, things
from .registry import Phrase
from .values import (Record, as_number, contains, exactly, fit, is_empty, kind_name,
                     order, places, quoted, same, show_value)

MAX_DEPTH = 100

# Where a name's value came from, for messages: "got its value on line 2, from what was typed".
HOW = {"typed": "from what was typed", "read": "from what was read", "web": "from the website's reply",
       "set": "from a set step", "how to": "from your own step"}
GIVES = {"ask": "typed", "read": "read", "send": "web"}    # the steps that give back a value

TEXT_EXAMPLES = {"file": '"notes.txt"', "source": '"notes.txt"', "new_name": '"notes.txt"',
                 "folder": '"photos"', "address": '"https://example.com"', "separator": '", "'}


@dataclass(eq=False)
class JoinTextProblem(Problem):
    """Text put together with plus. Plain offers the same line with one text instead."""
    joined: str = ""


class StopRepeatingSignal(Exception):
    pass


class SkipSignal(Exception):
    pass


class StopProgramSignal(Exception):
    pass


class GiveBackSignal(Exception):
    def __init__(self, value):
        self.value = value


class PlaceRef:
    """Somewhere a step can keep a value: a name, a field of a record or an item of a list."""

    def __init__(self, run, node):
        self.run, self.node = run, node

    @property
    def label(self):
        return self.node.canonical()

    def get(self):
        return self.run.eval(self.node)

    def set(self, value):
        self.run.assign(self.node, value)

    def has_value(self):
        if isinstance(self.node, N.Name):
            return self.run.lookup(self.node, missing=None) is not MISSING
        return True


MISSING = object()


class Run:
    def __init__(self, program, host):
        self.program = program
        self.host = host
        self.globals = {}
        self.frames = []
        self.items = []          # the current item inside "where"
        self.problem_text = None
        self.timer_start = host.clock()
        self.depth = 0
        self.came_from = {}      # name -> (line, how)
        self.current = None      # the step being run
        self.phrase_args = {}    # the written parts of the phrase being run, for messages

    # Running ---------------------------------------------------------------------

    def run(self):
        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(max(old_limit, 30000))
        try:
            self.exec_body(self.program.statements)
        except StopProgramSignal:
            pass
        except (StopRepeatingSignal, SkipSignal, GiveBackSignal):
            pass
        finally:
            sys.setrecursionlimit(old_limit)

    def exec_body(self, statements):
        for stmt in statements:
            self.exec(stmt)

    def exec(self, stmt):
        self.current = stmt
        try:
            self._exec(stmt)
        except Problem as problem:
            if problem.line is None:
                problem.line = stmt.line
                self.place_problem(problem, stmt)
            problem.running = True
            raise
        except RecursionError:
            raise Problem(
                f"Make your step stop using itself before it goes {MAX_DEPTH} steps deep.",
                f"A how-to can use itself, but only up to {MAX_DEPTH} times inside itself.",
                line=stmt.line, running=True)

    def _exec(self, stmt):
        match stmt:
            case N.SetStep():
                value = self.eval(stmt.value)
                if isinstance(value, (list, Record)):
                    value = copy.deepcopy(value)
                self.assign(stmt.target, value)
                self.note_source(stmt.target, stmt.line, "set")
            case N.Step():
                result = self.call_step(stmt)
                if stmt.call_it:
                    target = N.Name(stmt.call_it, stmt.call_it in self.own_names())
                    self.assign(target, result)
                    how = "how to" if isinstance(stmt.phrase.run, HowToDef) else \
                        GIVES.get(stmt.phrase.main.template.split()[0], "set")
                    self.note_source(target, stmt.line, how)
            case N.If():
                for check, body in stmt.branches:
                    if check is None or self.truth(check):
                        self.exec_body(body)
                        break
            case N.Repeat():
                self.exec_repeat(stmt)
            case N.StopRepeating():
                raise StopRepeatingSignal()
            case N.Skip():
                raise SkipSignal()
            case N.StopProgram():
                raise StopProgramSignal()
            case N.GiveBack():
                raise GiveBackSignal(self.eval(stmt.value))
            case N.Try():
                try:
                    self.exec_body(stmt.body)
                except Problem as problem:
                    before = self.problem_text
                    self.problem_text = problem.fix + (f" {problem.why}" if problem.why else "")
                    try:
                        self.exec_body(stmt.fallback)
                    finally:
                        self.problem_text = before    # "the problem" means something only in here
            case N.HowTo():
                pass
            case N.ErrorBlock():
                raise Problem("Fix this line before running.", line=stmt.line)

    def place_problem(self, problem, stmt):
        lines = self.program.source_lines
        raw = lines[stmt.line - 1] if 0 < stmt.line <= len(lines) else ""
        if problem.col is None:
            spot = raw.find(problem.focus) if problem.focus else -1
            if spot >= 0:
                problem.col, problem.end = spot, spot + len(problem.focus)
            elif raw.strip():
                problem.col = len(raw) - len(raw.lstrip())
                problem.end = len(raw.rstrip())
        if isinstance(problem, JoinTextProblem) and problem.col is not None and not problem.try_lines:
            start, stop, joined = problem.col, problem.end, problem.joined
            if raw[start - 1:start] == "{" and raw[stop:stop + 1] == "}":   # a whole {…} piece
                start, stop, joined = start - 1, stop + 1, joined[1:-1]
            line = (raw[:start] + joined + raw[stop:]).strip()
            if self.line_works(stmt.line, line):
                problem.try_lines, problem.ideas = [line], [line]
        if problem.guard and not problem.try_lines and raw.strip() and not isinstance(stmt, (N.If, N.Repeat)):
            problem.try_lines = [f"if {problem.guard} is a number", "    " + raw.strip(), "otherwise",
                                 '    show "Please type a number."']

    def line_works(self, number, new_line):
        """Whether the program still reads cleanly with new_line in place of line `number`."""
        lines = list(self.program.source_lines)
        if not 0 < number <= len(lines):
            return False
        old = lines[number - 1]
        lines[number - 1] = old[:len(old) - len(old.lstrip())] + new_line
        return not Reader().read("\n".join(lines)).problems

    def exec_repeat(self, stmt):
        def round_(body):
            try:
                self.exec_body(body)
            except SkipSignal:
                pass

        try:
            match stmt.kind:
                case "times":
                    count = self.whole(stmt.count, "repeat")
                    if count < 0:
                        raise Problem("Use 0 or more for the number of times to repeat.",
                                      f"Plain can't repeat {count} times.")
                    for _ in range(count):
                        round_(stmt.body)
                case "forever":
                    while True:
                        round_(stmt.body)
                case "while":
                    while self.truth(stmt.check):
                        round_(stmt.body)
                case "until":
                    while True:
                        round_(stmt.body)
                        if self.truth(stmt.check):
                            break
                case "each":
                    items = self.eval(stmt.items)
                    if isinstance(items, str):
                        name = stmt.items.canonical()
                        raise Problem(
                            f'Write "the lines of {name}", "the words of {name}" or "the characters of {name}" to say how to go through the text.',
                            f'"{name}" is text, so Plain needs to know which parts to go through.',
                            col=stmt.items.col, end=stmt.items.end)
                    if isinstance(items, Record):
                        raise Problem("Go through a list here. A record has fields, not items.",
                                      None, col=stmt.items.col, end=stmt.items.end)
                    if not isinstance(items, list):
                        raise Problem("Give \"repeat for each\" a list to go through.",
                                      f"{quoted(items)} is {kind_name(items)}, not a list.",
                                      col=stmt.items.col, end=stmt.items.end)
                    for item in list(items):
                        self.assign(stmt.name, item)
                        round_(stmt.body)
                case "count":
                    start = self.whole(stmt.start, "repeat")
                    stop = self.whole(stmt.stop, "repeat")
                    numbers = range(start, stop - 1, -1) if stmt.down else range(start, stop + 1)
                    for n in numbers:
                        self.assign(stmt.name, Decimal(n))
                        round_(stmt.body)
        except StopRepeatingSignal:
            pass

    # Steps -----------------------------------------------------------------------

    def call_step(self, stmt):
        phrase = stmt.phrase
        if isinstance(phrase.run, HowToDef):
            return self.call_howto(phrase.run, stmt.args)
        return self.call_phrase(phrase, stmt.args)

    def call_howto(self, howto, args):
        if self.depth >= MAX_DEPTH:
            raise Problem(
                f"Make your step stop using itself before it goes {MAX_DEPTH} steps deep.",
                f"A how-to can use itself, but only up to {MAX_DEPTH} times inside itself.")
        frame = {}
        for slot, name in zip(howto.phrase.slots, howto.params):
            frame[name] = self.eval(args[slot.name])
        self.frames.append((frame, howto))
        self.depth += 1
        try:
            self.exec_body(howto.body)
        except GiveBackSignal as signal:
            return signal.value
        finally:
            self.depth -= 1
            self.frames.pop()
        return None

    def call_phrase(self, phrase, args, operand=MISSING, operand_node=None):
        values = {}
        written = dict(args)
        for slot in phrase.slots:
            if operand is not MISSING and slot is phrase.slots[0]:
                written[slot.name] = operand_node
                values[slot.name] = self.check_kind(phrase, slot, operand, operand_node, written)
                continue
            node = args.get(slot.name)
            if node is None:
                continue
            values[slot.name] = self.slot_value(phrase, slot, node, written)
        self.phrase_args = written
        try:
            return phrase.run(self, **values)
        except Problem:
            raise
        except (StopRepeatingSignal, SkipSignal, StopProgramSignal, GiveBackSignal):
            raise
        except RecursionError:
            raise
        except Exception as error:   # data problems become messages, not crashes
            raise data_problem(error, self.host.folder) from error

    def written_name(self, slot):
        """Your name, when you wrote one of your names in that part of the phrase being run."""
        node = self.phrase_args.get(slot)
        return node.canonical() if isinstance(node, N.Name) else None

    def slot_value(self, phrase, slot, node, written):
        if slot.kind == "field":
            return node
        if slot.kind == "place":
            return PlaceRef(self, node)
        if slot.kind == "items":
            return [self.eval(item) for item in node]
        return self.check_kind(phrase, slot, self.eval(node), node, written)

    def check_kind(self, phrase, slot, value, node, written):
        label = phrase_label(phrase)
        col = node.col if node is not None else None
        end = node.end if node is not None else None
        given = f"{described(node, value)} is {kind_name(value)}"
        if isinstance(value, (list, Record)) and not isinstance(node, N.Name):
            given = f"this is {quoted(value)}"
        if slot.kind == "number":
            n = as_number(value)
            if n is None:
                raise Problem("Use a number here, like 3.",
                              f'"{label}" needs a number for this part, and {given}.', col=col, end=end)
            return n
        if slot.kind == "text":
            if isinstance(value, Decimal):
                return show_value(value)
            if not isinstance(value, str):
                example = TEXT_EXAMPLES.get(slot.name, '"hello"')
                raise Problem(f"Use text here, in double quotes, like {example}.",
                              f'"{label}" needs text for this part, and {given}.', col=col, end=end)
            return value
        if slot.kind == "list":
            if not isinstance(value, list):
                hint = ""
                if isinstance(value, str) and phrase.main.template == "the number of {items}":
                    hint = ' To count the characters in text, write "the length of".'
                elif isinstance(value, str) and "item" in label and isinstance(node, (N.Name, N.TextLit)):
                    parts = {k: v.canonical() for k, v in written.items() if isinstance(v, N.Node)}
                    parts[slot.name] = f"the characters of {node.canonical()}"
                    hint = f" To pick from the characters of text, write: {phrase.main.render(parts)}"
                raise Problem("Use a list here.", f'"{label}" needs a list, and {given}.{hint}',
                              col=col, end=end)
            return value
        return value

    # Names -----------------------------------------------------------------------

    def own_names(self):
        return self.frames[-1][1].own_names if self.frames else set()

    def lookup(self, node, missing=MISSING):
        scope = self.frames[-1][0] if node.own and self.frames else self.globals
        if node.words in scope:
            return scope[node.words]
        if missing is None:
            return MISSING
        name = node.canonical()
        line = self.program.origins.get(node.words)
        where = f' It gets a value on line {line}, which hasn\'t run yet.' if line else ""
        raise Problem(
            f'Give "{name}" a value before this line uses it.',
            f'"{name}" has no value yet.{where}', col=node.col, end=node.end)

    def assign(self, target, value):
        match target:
            case N.Name():
                scope = self.frames[-1][0] if target.own and self.frames else self.globals
                scope[target.words] = value
            case N.Field():
                record = self.eval(target.target)
                if not isinstance(record, Record):
                    raise Problem(
                        f'Use a record here. "{target.target.canonical()}" is {kind_name(record)}.',
                        "Only records have fields you can set.", col=target.col, end=target.end)
                name = target.words[0] if target.quoted else " ".join(target.words)
                record.set(name, value, exact=target.quoted)
            case N.Value():
                items = self.eval(target.args.get("items"))
                position = self.position_of(target, items)
                items[position] = value
            case _:
                raise Problem("Write a name, a field or an item of a list here.")

    def position_of(self, target, items):
        template = target.phrase.main.template
        if not isinstance(items, list) or not items:
            raise Problem("Use a list with at least one item here.")
        if "first" in template:
            return 0
        if "last" in template:
            return len(items) - 1
        n = self.whole(target.args["n"], "item")
        if not 1 <= n <= len(items):
            raise Problem(f"Use a position from 1 to {len(items)}.",
                          f"The list has {things(len(items), 'item')}, so there is no item {n}.")
        return n - 1

    def note_source(self, target, line, how):
        if isinstance(target, N.Name):
            self.came_from[target.words] = (line, how)

    # Values ----------------------------------------------------------------------

    def eval(self, node):
        try:
            return self._eval(node)
        except Problem as problem:
            if problem.col is None and node.col is not None:
                problem.col, problem.end = node.col, node.end
            raise

    def _eval(self, node):
        match node:
            case N.Lit():
                return node.value
            case N.TextLit():
                return self.text(node)
            case N.Name():
                return self.lookup(node)
            case N.Paren():
                return self.eval(node.inner)
            case N.It():
                return self.items[-1]
            case N.RowField():
                item = self.items[-1]
                if not isinstance(item, Record):
                    raise Problem(f'Write "it" instead of "its {" ".join(node.words)}" for items that aren\'t records.',
                                  f"{quoted(item)} is {kind_name(item)}, so it has no fields.")
                return item.get(node.words[0] if node.quoted else " ".join(node.words), exact=node.quoted)
            case N.Neg():
                return -self.number(node.value, "make it negative")
            case N.Math():
                return self.math(node)
            case N.PercentOf():
                pct = self.number(node.percent, "work out a percent with it")
                base = self.number(node.value, "work out a percent of it")
                return fit(pct * base, max(self.places_of(node.percent, pct), places(base)))
            case N.Field():
                return self.field(node)
            case N.Value():
                return self.call_phrase(node.phrase, node.args)
            case N.Postfix():
                return self.call_phrase(node.phrase, node.args, operand=self.eval(node.value),
                                        operand_node=node.value)
            case N.Where():
                return self.where(node)
            case N.Compare():
                return self.compare(node)
            case N.Between():
                v = self.eval(node.value)
                result = order(v, self.eval(node.low)) >= 0 and order(v, self.eval(node.high)) <= 0
                return result != node.negated
            case N.TypeCheck():
                return self.type_check(node)
            case N.Not():
                return not self.truth(node.value)
            case N.Logic():
                if node.op == "and":
                    return all(self.truth(item) for item in node.items)
                return any(self.truth(item) for item in node.items)
            case N.ListOf():
                return [self.eval(item) for item in node.items]
        raise Problem("Plain itself went wrong while working out a value.")

    def text(self, node):
        out = []
        for piece in node.pieces:
            if isinstance(piece, str):
                out.append(piece)
            else:
                value = show_value(self.eval(piece))
                out.append(quote(value, safe="") if node.url else value)
        return "".join(out)

    def number(self, node, doing):
        value = self.eval(node)
        n = as_number(value)
        if n is None:
            raise self.number_problem(node, value, doing,
                                      f"{described(node, value)} is {kind_name(value)}, not a number.")
        return n

    def number_problem(self, node, value, doing, why):
        """A value that isn't a number where one is needed. It names your name, says where its
        value came from, and offers the "Please type a number" check only for typed answers."""
        name = node.canonical() if isinstance(node, N.Name) else None
        subject = f'"{name}"' if name else quoted(value)
        if isinstance(value, (list, Record, bool)) or isinstance(node, N.TextLit):
            fix = f"Use a number here instead of {subject}."
        else:
            fix = f"Check that {subject} is a number before you {doing}."
        problem = Problem(fix, why, col=node.col, end=node.end)
        came = self.came_from.get(node.words) if name else None
        if came:
            problem.why += f' "{name}" got its value on line {came[0]}, {HOW[came[1]]}.'
            if came[1] == "typed":
                problem.guard = name
        return problem

    def math(self, node):
        if node.op == "plus" and any(written_text(part) for part in plus_parts(node)):
            raise self.join_problem(node)
        try:
            left, right = self.eval(node.left), self.eval(node.right)
        except JoinTextProblem:
            if node.op != "plus":
                raise
            raise self.join_problem(node) from None    # offer the whole run of plus signs as one text
        a, b = as_number(left), as_number(right)
        verb = {"plus": "add", "minus": "take away", "times": "multiply", "divided by": "divide"}[node.op]
        if a is None or b is None:
            if isinstance(left, str) and isinstance(right, str) and node.op == "plus":
                raise self.join_problem(node)
            bad_node, bad = (node.left, left) if a is None else (node.right, right)
            L, R = described(node.left, left), described(node.right, right)
            cannot = {"plus": f"add {R} to {L}", "minus": f"take {R} away from {L}",
                      "times": f"multiply {L} by {R}", "divided by": f"divide {L} by {R}"}[node.op]
            doing = {"plus": "add it", "minus": "take it away", "times": "multiply it",
                     "divided by": "divide it"}[node.op]
            raise self.number_problem(
                bad_node, bad, doing,
                f"You can't {cannot}, because {described(bad_node, bad)} is {kind_name(bad)}, not a number.")
        try:
            match node.op:
                case "plus":
                    result = a + b
                case "minus":
                    result = a - b
                case "times":
                    result = a * b
                case "divided by":
                    if b == 0 and isinstance(node.right, N.Lit):
                        raise Problem("Divide by a number other than 0.", "Plain can't divide by 0.",
                                      col=node.right.col, end=node.right.end)
                    if b == 0:
                        raise Problem(
                            f'Check that "{node.right.canonical()}" is not 0 before you divide by it.',
                            "Plain can't divide by 0.", col=node.right.col, end=node.right.end)
                    result = a / b
        except (InvalidOperation, DivisionByZero):
            raise Problem("Check the numbers in this sum.", f"Plain couldn't {verb} them.")
        except Overflow:
            raise Problem("Use smaller numbers here.", "The answer is too big for Plain to work with.")
        return fit(result, max(self.places_of(node.left, a), self.places_of(node.right, b)))

    def join_problem(self, node):
        joined = joined_text(plus_parts(node))
        return JoinTextProblem(
            f"Write {joined} to put the text together.",
            "Adding only works with numbers. To put text together, write it all inside one pair of "
            "quotes, with each value in { }.", col=node.col, end=node.end, joined=joined)

    def places_of(self, node, value):
        """A written percent counts the places you wrote: 15% has none, 2.5% has one."""
        if isinstance(node, N.Lit) and node.percent and node.raw:
            digits = node.raw.lstrip("$€£").rstrip("%")
            return places(Decimal(digits)) if digits.replace(".", "").isdigit() else places(value)
        return places(value)

    def field(self, node):
        target = self.eval(node.target)
        name = node.words[0] if node.quoted else " ".join(node.words)
        if isinstance(target, Record):
            return target.get(name, exact=node.quoted)
        if isinstance(target, list) and target and all(isinstance(r, Record) for r in target):
            column = []
            for row in target:
                key = row.find(name, exact=node.quoted)
                column.append(row.data[key] if key is not None else None)
            if all(row.find(name, exact=node.quoted) is None for row in target):
                fields = ", ".join(str(k) for k in target[0].data)
                raise Problem(f"Use one of the fields this table has: {fields}.",
                              f'There\'s no field "{name}" in this table.')
            return column
        if isinstance(target, list) and not target:
            return []
        raise Problem(
            f'Use a record or a table before "{name}".',
            f"{quoted(target)} is {kind_name(target)}, so it has no field \"{name}\".")

    def where(self, node):
        items = self.eval(node.base)
        if not isinstance(items, list):
            raise Problem('Use "where" after a list or a table.',
                          f"{quoted(items)} is {kind_name(items)}, not a list.",
                          col=node.base.col, end=node.base.end)
        out = []
        for item in items:
            self.items.append(item)
            try:
                if self.truth(node.check):
                    out.append(item)
            finally:
                self.items.pop()
        return out

    def truth(self, node):
        value = self.eval(node)
        if not isinstance(value, bool):
            text = node.canonical()
            raise Problem(
                f"Write a check with a yes or no answer here, like: {text} is not empty",
                f"{quoted(value)} is {kind_name(value)}, not yes or no.",
                col=node.col, end=node.end)
        return value

    def compare(self, node):
        left, right = self.eval(node.left), self.eval(node.right)
        op = node.op
        match op:
            case "is":
                return same(left, right)
            case "is not":
                return not same(left, right)
            case "exact":
                return exactly(left, right)
            case "not exact":
                return not exactly(left, right)
            case "more":
                return self.ordered(node, left, right) > 0
            case "less":
                return self.ordered(node, left, right) < 0
            case "at least":
                return self.ordered(node, left, right) >= 0
            case "at most":
                return self.ordered(node, left, right) <= 0
            case "in":
                return contains(right, left)
            case "not in":
                return not contains(right, left)
            case "contains":
                return contains(left, right)
            case "not contains":
                return not contains(left, right)
            case "starts" | "not starts" | "ends" | "not ends":
                if not isinstance(left, str):
                    left = show_value(left)
                r = show_value(right).strip().casefold()
                l = left.strip().casefold()
                result = l.startswith(r) if op.endswith("starts") else l.endswith(r)
                return result != op.startswith("not")
        raise Problem("Plain itself went wrong while comparing.")

    def ordered(self, node, left, right):
        """order(left, right), with a message that uses your names."""
        try:
            return order(left, right)
        except Problem:
            bad_node, bad, good_node, good = (node.left, left, node.right, right) \
                if as_number(left) is None else (node.right, right, node.left, left)
            bad_text = described(bad_node, bad)
            raise self.number_problem(
                bad_node, bad, "compare it",
                f"You can't compare {bad_text} with {described(good_node, good)}, because {bad_text} "
                f"is {kind_name(bad)}, not a number.") from None

    def type_check(self, node):
        value = self.eval(node.value)
        match node.kind:
            case "empty":
                result = is_empty(value)
            case "number":
                result = as_number(value) is not None
            case "whole number":
                n = as_number(value)
                result = n is not None and n == n.to_integral_value()
            case "text":
                result = isinstance(value, str) and as_number(value) is None
            case "list":
                result = isinstance(value, list)
            case "even" | "odd":
                n = self.whole_value(value, node.value)
                result = (n % 2 == 0) == (node.kind == "even")
            case "divisible":
                n = self.whole_value(value, node.value)
                d = self.whole(node.arg, "divide")
                if d == 0:
                    raise Problem("Check that the number is not 0 before you divide by it.",
                                  "Plain can't divide by 0.", col=node.arg.col, end=node.arg.end)
                result = n % d == 0
        return result != node.negated

    def whole(self, node, doing):
        return self.whole_value(self.eval(node), node)

    def whole_value(self, value, node):
        n = as_number(value)
        if n is None or n != n.to_integral_value():
            raise Problem("Use a whole number here, like 3.",
                          f"{quoted(value)} is not a whole number.",
                          col=node.col if node is not None else None,
                          end=node.end if node is not None else None)
        return int(n)


def phrase_label(phrase):
    """The words that name a phrase in messages: "the words of", "in uppercase", "rounded to"."""
    words = []
    for part in phrase.main.template.split():
        if part.startswith("{"):
            if words:
                break
        elif not part.startswith("["):
            words.append(part.split("|")[-1])
    return " ".join(words)


def described(node, value):
    """A value in a message: as you'd see it, or by your name for a list, table or record."""
    if isinstance(node, N.Name) and isinstance(value, (list, Record)):
        return f'"{node.canonical()}"'
    return quoted(value)


def written_text(node):
    """Text written in quotes that isn't a number, like "Score: "."""
    if not isinstance(node, N.TextLit):
        return False
    return not all(isinstance(p, str) for p in node.pieces) or as_number("".join(node.pieces)) is None


def plus_parts(node):
    """The parts of a run of plus signs: a plus b plus c gives a, b and c."""
    if isinstance(node, N.Math) and node.op == "plus":
        return plus_parts(node.left) + plus_parts(node.right)
    return [node]


def joined_text(parts):
    """One text that holds every part, the way Plain puts text together: "Score: {score}"."""
    pieces = []
    for part in parts:
        if isinstance(part, N.TextLit):
            pieces += part.pieces
        elif isinstance(part, N.Lit) and isinstance(part.value, Decimal) and not part.percent:
            pieces.append(part.canonical())
        else:
            pieces.append(part.inner if isinstance(part, N.Paren) else part)
    return N.TextLit(pieces).canonical()


def file_name(path, folder):
    """A file name the way you'd write it in your program, never a full path."""
    if not path:
        return ""
    try:
        return Path(path).relative_to(folder).as_posix()
    except (TypeError, ValueError):
        return Path(path).name


def data_problem(error, folder=None):
    """Turn a Python error caused by your data into a message in Plain's words."""
    match error:
        case json.JSONDecodeError():
            return Problem("Check that the file or page holds JSON.",
                           f"Plain couldn't read it as JSON. It went wrong at line {error.lineno}, column {error.colno}.")
        case UnicodeDecodeError():
            return Problem("Save the file as text (UTF-8), then try again.",
                           "Plain couldn't read the letters in this file.")
        case csv.Error():
            return Problem("Check that the file is a CSV file.", "Plain couldn't read it as a CSV table.")
        case FileNotFoundError():
            return Problem(f'Check the file name "{file_name(error.filename, folder)}".',
                           "There's no file with that name.")
        case IsADirectoryError():
            return Problem("Use a file name here, not a folder name.", None)
        case PermissionError():
            return Problem("Check that you're allowed to use this file.",
                           "Your computer didn't let Plain open it.")
        case OSError():
            return Problem("Check the file name and try again.", f"Plain couldn't use the file.")
        case InvalidOperation() | DivisionByZero():
            return Problem("Check the numbers in this step.", "Plain couldn't work out the result.")
        case Overflow() | OverflowError():
            return Problem("Use a smaller number here.", "The number is too big for this step.")
    raise error
