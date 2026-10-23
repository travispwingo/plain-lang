"""The tree Plain reads a program into. Every node can print itself back in main words
(canonical), which drives `plain explain`, the phrasing tests and de-duplicating readings."""

from dataclasses import dataclass, field
from decimal import Decimal

from .registry import Slot
from .values import number_text
from .words import COMPARISON_WORDS

PRECEDENCE = {"plus": 1, "minus": 1, "times": 2, "divided by": 2}


@dataclass(eq=False, kw_only=True)
class Node:
    col: int | None = None
    end: int | None = None

    def canonical(self):
        raise NotImplementedError


# Values ---------------------------------------------------------------------------

@dataclass(eq=False)
class Lit(Node):
    value: object
    raw: str | None = None
    percent: bool = False

    def canonical(self):
        v = self.value
        if self.raw is not None and isinstance(v, Decimal):
            return self.raw
        if v is None:
            return "nothing"
        if isinstance(v, bool):
            return "yes" if v else "no"
        if isinstance(v, Decimal):
            return number_text(v)
        return '"' + str(v).replace('"', '""') + '"'


@dataclass(eq=False)
class TextLit(Node):
    pieces: list          # str or Node
    url: bool = False

    def canonical(self):
        out = []
        for p in self.pieces:
            if isinstance(p, str):
                out.append(p.replace('"', '""').replace("{", "{{").replace("}", "}}"))
            else:
                out.append("{" + p.canonical() + "}")
        return '"' + "".join(out) + '"'


@dataclass(eq=False)
class Name(Node):
    words: tuple
    own: bool = False

    def canonical(self):
        return " ".join(self.words)


@dataclass(eq=False)
class It(Node):
    def canonical(self):
        return "it"


@dataclass(eq=False)
class RowField(Node):
    words: tuple
    quoted: bool = False

    def canonical(self):
        return "its " + field_text(self.words, self.quoted)


@dataclass(eq=False)
class Paren(Node):
    inner: Node

    def canonical(self):
        return "(" + self.inner.canonical() + ")"


@dataclass(eq=False)
class Neg(Node):
    value: Node

    def canonical(self):
        return "-" + wrap(self.value, 3)


@dataclass(eq=False)
class Math(Node):
    op: str
    left: Node
    right: Node

    def canonical(self):
        p = PRECEDENCE[self.op]
        return f"{wrap(self.left, p)} {self.op} {wrap(self.right, p + 1)}"


@dataclass(eq=False)
class PercentOf(Node):
    percent: Node
    value: Node

    def canonical(self):
        return f"{self.percent.canonical()} of {self.value.canonical()}"


@dataclass(eq=False)
class Field(Node):
    target: Node
    words: tuple
    quoted: bool = False
    of_form: bool = False     # "the amounts of sales" rather than "sale's amount"
    raw: tuple | None = None  # the field words as you wrote them, capitals kept, for a new field

    def canonical(self):
        if self.of_form:
            return f"the {field_text(self.words, self.quoted)} of {self.target.canonical()}"
        target = self.target.canonical()
        if isinstance(self.target, (Value, Where, PercentOf, Math, Postfix)) or \
                (isinstance(self.target, Field) and self.target.of_form):
            target = f"({target})"
        return f"{target}'s {field_text(self.words, self.quoted)}"


@dataclass(eq=False)
class Value(Node):
    phrase: object
    args: dict
    open_end: bool = False    # its last slot takes one value and isn't after "of"

    def canonical(self):
        return self.phrase.main.render({k: arg_text(v) for k, v in self.args.items()}) \
            if self.phrase.main is self.phrase else self.phrase.render(
                {k: arg_text(v) for k, v in self.args.items()})


@dataclass(eq=False)
class Postfix(Node):
    phrase: object
    value: Node
    args: dict

    def canonical(self):
        args = {k: arg_text(v) for k, v in self.args.items()}
        first = self.phrase.slots[0].name
        args[first] = wrap(self.value, 0.5)
        return self.phrase.render(args)


@dataclass(eq=False)
class Where(Node):
    base: Node
    check: Node

    def canonical(self):
        return f"{self.base.canonical()} where {self.check.canonical()}"


@dataclass(eq=False)
class ListOf(Node):
    items: list

    def canonical(self):
        return "a list of " + join_items([arg_text(i) for i in self.items])


# Checks ---------------------------------------------------------------------------

@dataclass(eq=False)
class Compare(Node):
    left: Node
    op: str
    right: Node
    said_not: bool = False    # written with "not", like "is not more than", which reads as "is at most"

    def canonical(self):
        return f"{self.left.canonical()} {COMPARISON_WORDS[self.op]} {self.right.canonical()}"


@dataclass(eq=False)
class Between(Node):
    value: Node
    low: Node
    high: Node
    negated: bool = False

    def canonical(self):
        word = "is not between" if self.negated else "is between"
        return f"{self.value.canonical()} {word} {self.low.canonical()} and {self.high.canonical()}"


@dataclass(eq=False)
class TypeCheck(Node):
    value: Node
    kind: str
    negated: bool = False
    arg: Node | None = None

    def canonical(self):
        word = "is not" if self.negated else "is"
        kind = {"number": "a number", "whole number": "a whole number", "list": "a list"}.get(self.kind, self.kind)
        if self.kind == "divisible":
            kind = "divisible by " + self.arg.canonical()
        return f"{self.value.canonical()} {word} {kind}"


@dataclass(eq=False)
class Not(Node):
    value: Node

    def canonical(self):
        return "not " + wrap_check(self.value)


@dataclass(eq=False)
class Logic(Node):
    op: str
    items: list
    group: bool = False   # made by elision: "answer is "y" or "yes""

    def canonical(self):
        return f" {self.op} ".join(
            "(" + i.canonical() + ")" if isinstance(i, Logic) and i.op != self.op else i.canonical()
            for i in self.items)


@dataclass(eq=False)
class Bad(Node):
    """A reading that is itself a problem, like an ambiguous line."""
    problem: object
    alts: list = field(default_factory=list)   # replacement texts for col..end

    def canonical(self):
        return "<problem: " + self.problem.fix + ">"


def make_logic(op, items, group=False, col=None, end=None):
    flat = []
    for item in items:
        if isinstance(item, Logic) and item.op == op:
            flat.extend(item.items)
            group = group and item.group
        else:
            flat.append(item)
    return Logic(op, flat, group, col=col, end=end)


# Steps ----------------------------------------------------------------------------

@dataclass(eq=False, kw_only=True)
class Statement:
    line: int
    synonym_edits: list = field(default_factory=list)   # for plain tidy
    col: int | None = None      # where the step is on its line, for the ^ marks
    end: int | None = None


@dataclass(eq=False)
class SetStep(Statement):
    target: Node
    value: Node

    def canonical(self):
        return f"set {self.target.canonical()} to {self.value.canonical()}"


@dataclass(eq=False)
class Step(Statement):
    phrase: object
    args: dict
    call_it: tuple | None = None
    call_span: tuple | None = None    # where "and call it NAME" is on the line

    def canonical(self):
        main = self.phrase.main
        text = main.render({k: arg_text(v, wrap_math=False) for k, v in self.args.items()})
        if self.call_it:
            text += " and call it " + " ".join(self.call_it)
        return text


@dataclass(eq=False)
class If(Statement):
    branches: list            # [(check or None, [statements])]
    branch_lines: list = field(default_factory=list)
    branch_edits: dict = field(default_factory=dict)   # {line of an "otherwise": synonym edits}

    def canonical(self):
        return "if " + self.branches[0][0].canonical()


@dataclass(eq=False)
class Repeat(Statement):
    kind: str                 # times, forever, until, while, each, count
    body: list
    count: Node | None = None
    check: Node | None = None
    name: Node | None = None
    items: Node | None = None
    start: Node | None = None
    stop: Node | None = None
    down: bool = False

    def canonical(self):
        match self.kind:
            case "times":
                return f"repeat {self.count.canonical()} times"
            case "forever":
                return "repeat forever"
            case "until" | "while":
                return f"repeat {self.kind} {self.check.canonical()}"
            case "each":
                return f"repeat for each {self.name.canonical()} in {self.items.canonical()}"
            case "count":
                way = "down to" if self.down else "to"
                return f"repeat for each {self.name.canonical()} from {self.start.canonical()} {way} {self.stop.canonical()}"


@dataclass(eq=False)
class StopRepeating(Statement):
    def canonical(self):
        return "stop repeating"


@dataclass(eq=False)
class Skip(Statement):
    def canonical(self):
        return "skip to the next round"


@dataclass(eq=False)
class StopProgram(Statement):
    def canonical(self):
        return "stop the program"


@dataclass(eq=False)
class HowTo(Statement):
    phrase: object
    params: list              # name tuples, in slot order
    body: list
    own_names: frozenset = frozenset()

    def canonical(self):
        return "how to " + self.phrase.template.replace("{", "(").replace("}", ")")


@dataclass(eq=False)
class GiveBack(Statement):
    value: Node

    def canonical(self):
        return "give back " + self.value.canonical()


@dataclass(eq=False)
class Try(Statement):
    body: list
    fallback: list = field(default_factory=list)

    def canonical(self):
        return "try"


@dataclass(eq=False)
class ErrorBlock(Statement):
    body: list

    def canonical(self):
        return "<a line Plain couldn't read>"


# Helpers --------------------------------------------------------------------------

def field_text(words, quoted):
    return f'"{words[0]}"' if quoted else " ".join(words)


def wrap(node, level):
    """Brackets around arithmetic that binds less tightly than its place needs."""
    last = node.phrase.elements[-1] if isinstance(node, Value) else None
    if isinstance(last, Slot) and (level >= 1 or level > 0 and last.kind == "items"):
        return "(" + node.canonical() + ")"   # (the number of guests) plus 1, (a list of 1 and 2) joined with "-"
    if isinstance(node, Math) and PRECEDENCE[node.op] < level:
        return "(" + node.canonical() + ")"
    if isinstance(node, Postfix) and level > 0.5:
        return "(" + node.canonical() + ")"
    if isinstance(node, (Compare, Logic, Between, TypeCheck, Not, Where)) and level > 0:
        return "(" + node.canonical() + ")"
    return node.canonical()


def wrap_check(node):
    if isinstance(node, (Logic, Compare, Between, TypeCheck)):
        return "(" + node.canonical() + ")"
    return node.canonical()


def arg_text(v, wrap_math=True):
    if isinstance(v, Node):
        if wrap_math and isinstance(v, (Math, Postfix)):
            return "(" + v.canonical() + ")"
        return v.canonical()
    if isinstance(v, tuple):
        return " ".join(v)
    if isinstance(v, list):
        return join_items([arg_text(i) for i in v])
    return str(v)


def join_items(items):
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]
