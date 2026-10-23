"""Running a program that Plain has read. Every side effect goes through the host."""

import copy
import csv
import json
import sys
from decimal import Decimal, DivisionByZero, InvalidOperation
from urllib.parse import quote

from . import nodes as N
from .parser import HowToDef
from .problems import Problem
from .registry import Phrase
from .values import (Record, as_number, contains, exactly, fit, is_empty, kind_name,
                     order, places, quoted, same, show_value)

MAX_DEPTH = 100


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
                    how = "typed" if stmt.phrase.main.template.startswith("ask") else \
                        "read" if stmt.phrase.main.template.startswith("read") else "how to"
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
                    self.problem_text = problem.fix + (f" {problem.why}" if problem.why else "")
                    self.exec_body(stmt.fallback)
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
        if problem.guard and not problem.try_lines and raw.strip():
            problem.try_lines = [f"if {problem.guard} is a number", "    " + raw.strip(), "otherwise",
                                 '    show "Please type a number."']

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
            self.exec_body(howto_body(self.program, howto))
        except GiveBackSignal as signal:
            return signal.value
        finally:
            self.depth -= 1
            self.frames.pop()
        return None

    def call_phrase(self, phrase, args, operand=MISSING):
        values = {}
        for slot in phrase.slots:
            if operand is not MISSING and slot is phrase.slots[0]:
                values[slot.name] = self.check_kind(phrase, slot, operand, None)
                continue
            node = args.get(slot.name)
            if node is None:
                continue
            values[slot.name] = self.slot_value(phrase, slot, node)
        try:
            return phrase.run(self, **values)
        except Problem:
            raise
        except (StopRepeatingSignal, SkipSignal, StopProgramSignal, GiveBackSignal):
            raise
        except RecursionError:
            raise
        except Exception as error:   # data problems become messages, not crashes
            raise data_problem(error) from error

    def slot_value(self, phrase, slot, node):
        if slot.kind == "field":
            return node
        if slot.kind == "place":
            return PlaceRef(self, node)
        if slot.kind == "items":
            return [self.eval(item) for item in node]
        return self.check_kind(phrase, slot, self.eval(node), node)

    def check_kind(self, phrase, slot, value, node):
        verb = phrase.main.template.split()[0]
        col = node.col if node is not None else None
        end = node.end if node is not None else None
        if slot.kind == "number":
            n = as_number(value)
            if n is None:
                raise Problem(
                    f"Use a number here, like 3.",
                    f'"{verb}" needs a number for this part, and {quoted(value)} is {kind_name(value)}.',
                    col=col, end=end)
            return n
        if slot.kind == "text":
            if isinstance(value, Decimal):
                return show_value(value)
            if not isinstance(value, str):
                raise Problem(
                    'Use text here, in double quotes, like "notes.txt".',
                    f'"{verb}" needs text for this part, and {quoted(value)} is {kind_name(value)}.',
                    col=col, end=end)
            return value
        if slot.kind == "list":
            if not isinstance(value, list):
                hint = ""
                if isinstance(value, str) and verb in ("the", "item"):
                    hint = ' To count the characters in text, write "the length of".'
                raise Problem(
                    "Use a list here.",
                    f'"{phrase.main.template.split("{")[0].strip()}" needs a list, and {quoted(value)} is {kind_name(value)}.{hint}',
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
                          f"The list has {len(items)} items, so there is no item {n}.")
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
                return -self.number(node.value, "make negative")
            case N.Math():
                return self.math(node)
            case N.PercentOf():
                pct = self.number(node.percent, "work out a percent of")
                base = self.number(node.value, "work out a percent of")
                return fit(pct * base, max(places(pct), places(base)))
            case N.Field():
                return self.field(node)
            case N.Value():
                return self.call_phrase(node.phrase, node.args)
            case N.Postfix():
                return self.call_phrase(node.phrase, node.args, operand=self.eval(node.value))
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
            raise self.not_a_number(node, value, doing)
        return n

    def not_a_number(self, node, value, doing, other=None):
        why = f"You can't {doing} {quoted(value)}, because {quoted(value)} is {kind_name(value)}, not a number."
        fix = f"Check that {quoted(value)} is a number before you {doing.split()[0]} it."
        try_lines = []
        if isinstance(node, N.Name):
            fix = f'Check that "{node.canonical()}" is a number before you use it here.'
            came = self.came_from.get(node.words)
            if came:
                how = {"typed": "from what was typed", "read": "from what was read",
                       "set": "from a set step", "how to": "from your own step"}[came[1]]
                why += f' "{node.canonical()}" got its value on line {came[0]}, {how}.'
        return Problem(fix, why, col=node.col, end=node.end, try_lines=try_lines)

    def math(self, node):
        left, right = self.eval(node.left), self.eval(node.right)
        a, b = as_number(left), as_number(right)
        verb = {"plus": "add", "minus": "take away", "times": "multiply", "divided by": "divide"}[node.op]
        if a is None or b is None:
            if node.op == "plus" and (isinstance(left, str) or isinstance(right, str)) \
                    and (a is None) != (b is None) and not isinstance(left, list):
                pass
            if isinstance(left, str) and isinstance(right, str) and node.op == "plus":
                raise Problem(
                    'Use { } to join text, like "{first}{second}".',
                    '"plus" only adds numbers. To put text together, write both parts inside one text.',
                    col=node.col, end=node.end)
            bad_node, bad = (node.left, left) if a is None else (node.right, right)
            L, R = quoted(left), quoted(right)
            cannot = {"plus": f"add {R} to {L}", "minus": f"take {R} away from {L}",
                      "times": f"multiply {L} by {R}", "divided by": f"divide {L} by {R}"}[node.op]
            why = f"You can't {cannot}, because {quoted(bad)} is {kind_name(bad)}, not a number."
            problem = Problem(f"Check that {quoted(bad)} is a number before you {verb} it.", why,
                              col=bad_node.col, end=bad_node.end)
            if isinstance(bad_node, N.Name):
                name = bad_node.canonical()
                problem.fix = f'Check that "{name}" is a number before you {verb} it.'
                problem.guard = name
                came = self.came_from.get(bad_node.words)
                if came:
                    how = {"typed": "from what was typed", "read": "from what was read",
                           "set": "from a set step", "how to": "from your own step"}[came[1]]
                    problem.why += f' "{name}" got its value on line {came[0]}, {how}.'
            raise problem
        try:
            match node.op:
                case "plus":
                    result = a + b
                case "minus":
                    result = a - b
                case "times":
                    result = a * b
                case "divided by":
                    if b == 0:
                        raise Problem(
                            f'Check that "{node.right.canonical()}" is not 0 before you divide by it.',
                            "Plain can't divide by 0.", col=node.right.col, end=node.right.end)
                    result = a / b
        except (InvalidOperation, DivisionByZero):
            raise Problem("Check the numbers in this sum.", f"Plain couldn't {verb} them.")
        return fit(result, max(places(a), places(b)))

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
                return order(left, right) > 0
            case "less":
                return order(left, right) < 0
            case "at least":
                return order(left, right) >= 0
            case "at most":
                return order(left, right) <= 0
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


def howto_body(program, howto):
    cache = program.__dict__.setdefault("_howto_bodies", {})
    if id(howto) not in cache:
        for stmt in all_statements(program.statements):
            if isinstance(stmt, N.HowTo) and stmt.phrase is howto.phrase:
                cache[id(howto)] = stmt.body
        cache.setdefault(id(howto), [])
    return cache[id(howto)]


def all_statements(statements):
    for stmt in statements:
        yield stmt
        if isinstance(stmt, N.HowTo):
            yield from all_statements(stmt.body)


def data_problem(error):
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
            return Problem(f'Check the file name "{getattr(error, "filename", "")}".',
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
    raise error
