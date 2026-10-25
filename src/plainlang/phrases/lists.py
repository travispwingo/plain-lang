"""Lists and tables."""

import copy
import functools
import re
from decimal import Decimal

from .. import nodes as N
from ..problems import Problem, things
from ..registry import REGISTRY, Field, Items, List, Number, Place, Value, step, value
from ..values import (Quoted, Record, as_number, fit, kind_name, missing_column, order, places, quoted, same,
                      show_value)

TOPIC = "Lists and tables"


@value("a list of {values}", example='set colors to a list of "red", "green" and "blue"', topic=TOPIC)
def list_of(run, values: Items) -> List:
    """Makes a list. Commas and a final "and" separate the items."""
    if len(values) == 1 and isinstance(values[0], list):
        return list(values[0])
    return list(values)


@value("an empty list", example="set todos to an empty list", topic=TOPIC)
def empty_list(run) -> List:
    """A list with nothing in it yet."""
    return []


@value("an empty record", "a new record", example="set person to an empty record", topic=TOPIC)
def empty_record(run) -> Value:
    """A record with no fields yet. Add fields with: set person's name to "Ann"."""
    return Record()


@value("a copy of {value}", example="cross off a task in a copy of todos", topic=TOPIC)
def copy_of(run, value: Value) -> Value:
    """A separate copy, so changing one doesn't change the other. "set" already keeps a copy, so use this to hand your own step a copy of your list."""
    return copy.deepcopy(value)


def empty_problem(run, why):
    """The list is empty. The fix uses your name for the list when you wrote one."""
    name = run.written_name("items")
    fix = f"Check that the list is not empty first, with: if {name} is not empty" if name else \
        "Check that the list is not empty first."
    return Problem(fix, why)


def position(run, items, n):
    if n != n.to_integral_value():
        raise Problem("Use a whole number for the position, like 2.", None)
    count = len(items)
    if count == 0:
        raise empty_problem(run, "The list is empty, so it has no items.")
    if not 1 <= n <= count:
        raise Problem("Use item 1." if count == 1 else f"Use a position from 1 to {count}.",
                      f"The list has {things(count, 'item')}, so there is no item {n}.")
    return int(n) - 1


@value("item {n} of {items}", example="show item 2 of colors", topic=TOPIC)
def item_of(run, n: Number, items: List) -> Value:
    """The item at that position. Positions start at 1."""
    return items[position(run, items, n)]


@value("the first item of {items}", example="show the first item of colors", topic=TOPIC)
def first_item(run, items: List) -> Value:
    """The first item."""
    return items[position(run, items, Decimal(1))]


@value("the last item of {items}", example="show the last item of colors", topic=TOPIC)
def last_item(run, items: List) -> Value:
    """The last item."""
    return items[position(run, items, Decimal(len(items) or 1))]


@value("the first {n} items of {items}", example="show the first 2 items of colors", topic=TOPIC)
def first_items(run, n: Number, items: List) -> List:
    """That many items from the start of the list, or all of them if there are fewer."""
    return items[:max(0, int(n))]


@value("the last {n} items of {items}", example="show the last 2 items of colors", topic=TOPIC)
def last_items(run, n: Number, items: List) -> List:
    """That many items from the end of the list, or all of them if there are fewer."""
    return items[-int(n):] if int(n) > 0 else []


@value("the number of {items}", example="show the number of colors", topic=TOPIC)
def number_of(run, items: List) -> Number:
    """How many items the list has."""
    return Decimal(len(items))


def numbers_in(items, doing):
    out = []
    for item in items:
        if item is None:
            continue
        n = as_number(item)
        if n is None:
            raise Problem(f"Check that every item is a number before you {doing}.",
                          f"{quoted(item)} is {kind_name(item)}, not a number.")
        out.append(n)
    return out


@value("the total of {items}", example="show the total of a list of 1, 2 and 3", topic=TOPIC)
def total(run, items: List) -> Number:
    """Adds up the numbers. Items that are nothing, like blank cells, are skipped."""
    numbers = numbers_in(items, "add them up")
    result = sum(numbers, Decimal(0))
    return fit(result, max((places(n) for n in numbers), default=0))


@value("the average of {items}", example="show the average of a list of 1, 2 and 3", topic=TOPIC)
def average(run, items: List) -> Number:
    """The total divided by how many numbers there are. Items that are nothing, like blank cells, are skipped."""
    numbers = numbers_in(items, "average them")
    if not numbers:
        if items:
            raise Problem("Check that some of the items are numbers before you average them.",
                          "The list has no numbers in it (blank cells don't count), so there's no average.")
        raise empty_problem(run, "The list is empty, so there's no average.")
    result = sum(numbers, Decimal(0)) / len(numbers)
    return fit(result, max(places(n) for n in numbers))


def is_table(value):
    return isinstance(value, list) and bool(value) and all(isinstance(v, Record) for v in value)


def kind_of(values):
    """"numbers" when every value that's there is a number, "text" when every one is text that isn't
    all numbers, and None for an empty or mixed list (comparing a mix already gets its own message)."""
    present = [v for v in values if v is not None]
    if not present:
        return None
    if all(as_number(v) is not None for v in present):
        return "numbers"
    if all(isinstance(v, str) for v in present):
        return "text"
    return None


def text_extreme_problem(run, word):
    """the largest of words: for text, "largest" could mean the longest or the last from A to Z (change 7).
    Plain offers to sort the text, then take its first or last item."""
    last = word == "largest"
    items, node = run.phrase_args.get("items"), run.phrase_node
    end, other = ("last", "first") if last else ("first", "last")
    number = run.line_now()
    raw = run.program.source_lines[number - 1] if number and node is not None and node.col is not None else ""
    said = raw[node.col:].split()[0] if raw[node.col:].split() else word
    word = said.lower() if said.isalpha() else word     # your word: "the biggest of"
    choices = []
    if node is None:
        pass
    elif isinstance(items, N.Name):
        name = items.canonical()
        choices = [[f"sort {name}", run.line_with(node, f"the {end} item of {name}", article=True)],
                   [f"sort {name} from Z to A", run.line_with(node, f"the {other} item of {name}", article=True)]]
    elif isinstance(items, N.Field) and isinstance(items.target, N.Name) and is_table(run.eval(items.target)):
        # the largest of sales's customer: sort the table by that column, by the name the table
        # gives it ("the customers of sales" sorts by customer).
        rows = run.eval(items.target)
        table, field = items.target.canonical(), N.field_text(items.words, items.quoted)
        key = None if items.quoted else rows[0].find(" ".join(items.words), table=True)
        if key is not None and re.fullmatch(r"[A-Za-z]+(?: [A-Za-z]+)*", key):
            field = key
        column = N.arg_text(items)
        choices = [[f"sort {table} by {field}", run.line_with(node, f"the {end} item of {column}", article=True)],
                   [f"sort {table} by {field} from Z to A",
                    run.line_with(node, f"the {other} item of {column}", article=True)]]
    elif items is not None:
        name = next(n for n in ("my list", "sorted list", "my sorted list") if tuple(n.split()) not in run.globals)
        choices = [[f"set {name} to {N.arg_text(items, wrap_math=False)}", f"sort {name}",
                    run.line_with(node, f"the {end} item of {name}", article=True)]]
    choices = [[line.strip() for line in choice] for choice in choices]
    choices = [c for c in choices if run.line_works(run.line_now(), "\n".join(c))]
    return Problem(f"Sort the text first, then take its {'last' if last else 'first'} item.",
                   f'"the {word} of" finds the {word} number. For text, "{word}" could mean the '
                   f'{"longest" if last else "shortest"} text or the {"last" if last else "first"} one from A to Z, '
                   'so Plain sorts text "from A to Z" or "from Z to A" instead.',
                   try_lines=[line for c in choices for line in c], choices=choices)


def extreme(run, items, sign, word):
    present = [item for item in items if item is not None]
    if not present:
        raise empty_problem(run, f"The list is empty, so there's no {word}.")
    if kind_of(present) == "text":
        raise text_extreme_problem(run, word)
    best = present[0]
    for item in present[1:]:
        if order(item, best) * sign > 0:
            best = item
    return best


@value("the largest of {items}", example="show the largest of a list of 3, 9 and 4", topic=TOPIC)
def largest(run, items: List) -> Value:
    """The largest number. For text, sort it and take the last item."""
    return extreme(run, items, 1, "largest")


@value("the smallest of {items}", example="show the smallest of a list of 3, 9 and 4", topic=TOPIC)
def smallest(run, items: List) -> Value:
    """The smallest number. For text, sort it and take the first item."""
    return extreme(run, items, -1, "smallest")


def distinct(values):
    out = []
    for v in values:
        if not any(same(v, seen) for seen in out):
            out.append(v)
    return out


@value("the different items of {items}", example="show the different items of a list of 1, 2, 2 and 3",
       topic=TOPIC)
def different_items(run, items: List) -> List:
    """Each item once, in the order they first appear."""
    return distinct(items)


@value("the different {columns} of {table}", example="show the different categories of expenses", topic=TOPIC)
def different_field(run, columns: Field, table: List) -> List:
    """Each value of one column once, in the order they first appear."""
    exact = isinstance(columns[0], Quoted)
    name = columns[0] if exact else " ".join(columns)
    column = []
    for row in table:
        if not isinstance(row, Record):
            raise Problem(f'Use a table here. {quoted(row)} is {kind_name(row)}, not a row.', None)
        key = row.find(name, exact=exact, table=True)
        if key is None:
            raise missing_column(name, row)
        column.append(row.data[key])
    return distinct(column)


@step("add {value} to {place}", example="add 1 to score", topic=TOPIC)
def add(run, value: Value, place: Place) -> None:
    """Adds a number to a number, or puts an item at the end of a list."""
    if not place.has_value():
        raise Problem(f'Give "{place.label}" a value first, like: set {place.label} to 0',
                      f'"{place.label}" has no value yet, so there\'s nothing to add to.')
    current = place.get()
    if isinstance(current, list):
        if isinstance(value, list):
            current.extend(value)
        else:
            current.append(value)
        return
    a, b = as_number(current), as_number(value)
    if isinstance(current, str) and a is None:
        raise text_add_problem(run, place, current, value)
    if a is None or b is None:
        bad = value if b is None else current
        raise Problem(f"Check that {quoted(bad)} is a number before you add it.",
                      f"You can't add {quoted(value)} to {quoted(current)}, because {quoted(bad)} is "
                      f"{kind_name(bad)}, not a number.")
    place.set(fit(a + b, max(places(a), places(b))))


def text_add_problem(run, place, current, value):
    """Adding to text: offer one text with both parts, the way {} puts text together."""
    label = place.label
    node = run.current.args.get("value") if isinstance(run.current, N.Step) else None
    added = node.pieces if isinstance(node, N.TextLit) else [node] if node is not None else [show_value(value)]
    one_line = "\n" not in current     # text with several lines can't be written in quotes
    shown = f"the text {quoted(current)}" if one_line else "text with several lines"
    why = f'"{label}" is {shown}, and "add" only adds numbers or puts items on a list.'
    came = run.came_from.get(place.node.words) if isinstance(place.node, N.Name) else None
    if came and came[1] == "read":
        why += f' To get a list with one item for each line of a file, write "read the lines of" on line {came[0]}.'
    try_lines = [f"set {label} to a list of {N.TextLit([current]).canonical()}"] if one_line else []
    try_lines.append(f"set {label} to {N.TextLit([place.node] + list(added)).canonical()}")
    choices = [[try_lines[0], f"add {N.arg_text(node) if node is not None else quoted(value)} to {label}"]] \
        if one_line else []
    choices.append([try_lines[-1]])
    return Problem(f'Make "{label}" a list to add items to it, or join the text with {{ }}.', why,
                   try_lines=try_lines, choices=choices)


@step("subtract {value} from {place}", example="subtract 1 from lives", topic=TOPIC)
def subtract(run, value: Number, place: Place) -> None:
    """Takes a number away from a number."""
    if not place.has_value():
        raise Problem(f'Give "{place.label}" a value first, like: set {place.label} to 10', None)
    current = as_number(place.get())
    if current is None:
        raise Problem(f'Check that "{place.label}" is a number before you subtract from it.',
                      f'"{place.label}" is {kind_name(place.get())}, not a number.')
    place.set(fit(current - value, max(places(current), places(value))))


@step("remove item {n} from {items}", example="remove item 1 from todos", topic=TOPIC)
def remove_item(run, n: Number, items: List) -> None:
    """Removes the item at that position. To remove an item by what it is, write remove VALUE from LIST."""
    del items[position(run, items, n)]


@step("remove {value} from {items}", example='remove "milk" from shopping', topic=TOPIC)
def remove(run, value: Value, items: List) -> None:
    """Removes the first item that matches. To remove an item by its position, write remove item NUMBER from LIST."""
    for index, item in enumerate(items):
        if same(item, value):
            del items[index]
            return
    name, node = run.written_name("items"), run.phrase_args.get("value")
    fix = f"Check that the list contains {quoted(value)} first."
    if name and isinstance(node, (N.Name, N.Lit, N.TextLit)):
        fix = f"Check that the list contains {quoted(value)} first, with: if {name} contains {node.canonical()}"
    raise Problem(fix, f"There's no {quoted(value)} in the list.")


def blanks_last(a, b):
    """Order two values for sorting, with blank cells (nothing) after everything else."""
    if a is None or b is None:
        return (a is None) - (b is None)
    return order(a, b)


def sort_key_order(run, items, key, reverse=False):
    keys = [key(item) for item in items]     # a missing field is a problem of its own
    check_sort_words(run, keys)
    pairs = list(zip(keys, items))
    try:
        pairs.sort(key=functools.cmp_to_key(lambda a, b: blanks_last(a[0], b[0])))
    except Problem as problem:
        problem.fix = "Check that the items are all numbers, or all text, before you sort them."
        raise
    items[:] = [item for _, item in pairs]
    if reverse:
        items.reverse()


# Words that sort numbers by size, and words that sort text by the alphabet (change 7): the words
# as a template has them, the kind of values they're for, and the wording to offer for the other kind.
SORT_WORDS = {
    "smallest first": ("numbers", ""),
    "largest first": ("numbers", "from Z to A"),
    "from A to Z": ("text", ""),
    "from Z to A": ("text", "largest first"),
}


def check_sort_words(run, keys):
    """sort names largest first: "largest" and "smallest" are for numbers, and "A to Z" for text."""
    node = run.phrase_node
    if not isinstance(node, N.Step):
        return
    template = node.phrase.template
    said = next((words for words in SORT_WORDS if template.endswith(" " + words)), None)
    kind = kind_of(keys)
    if said is None or kind is None or kind == SORT_WORDS[said][0]:
        return
    offer = SORT_WORDS[said][1]
    base = template[:-len(said)].strip()
    # Your own words for it, like "biggest first": the last words of the step, before any note.
    items = node.args.get("items") or node.args.get("table")
    raw = run.program.source_lines[node.line - 1]
    tail = raw[items.end:] if items is not None and items.end is not None else raw
    yours = re.findall(r"[A-Za-z]+", tail.split("#")[0])[-len(said.split()):]
    if len(yours) == len(said.split()):
        said = " ".join(yours)
    wording = f"{base} {offer}".strip()
    phrase = next(p for p in REGISTRY if p.template == wording)
    args = {k: N.field_text(v, isinstance(v[0], Quoted)) if isinstance(v, tuple) else N.arg_text(v, wrap_math=False)
            for k, v in node.args.items()}
    line = phrase.render(args)
    lines = [line] if run.line_works(node.line, line) else []
    if kind == "text":
        why = (f'"{said}" is for numbers. Text goes in the order of the alphabet, so Plain sorts it '
               'from A to Z, or "from Z to A" for the other way.')
    else:
        why = (f'"{said}" is for text. Numbers go by size, so Plain sorts them smallest first, or '
               '"largest first" for the other way.')
    fix = f'Write "{offer}" instead of "{said}".' if offer else \
        f'Leave out "{said}" to sort {"text from A to Z" if kind == "text" else "numbers smallest first"}.'
    raise Problem(fix, why, try_lines=lines)


def column_getter(column):
    exact = isinstance(column[0], Quoted)
    name = column[0] if exact else " ".join(column)

    def get(row):
        if not isinstance(row, Record):
            raise Problem(f'Use "sort by" on a table. {quoted(row)} is {kind_name(row)}.', None)
        key = row.find(name, exact, table=True)
        if key is None:
            raise missing_column(name, row)
        return row.data[key]
    return get


@step("sort {items}", "sort {items} smallest first", "sort {items} from A to Z", example="sort names", topic=TOPIC)
def sort(run, items: List) -> None:
    """Sorts the list: numbers smallest first, and text from A to Z, ignoring capitals."""
    sort_key_order(run, items, lambda x: x)


@step("sort {items} largest first", example="sort scores largest first", topic=TOPIC)
def sort_largest(run, items: List) -> None:
    """Sorts a list of numbers, largest first."""
    sort_key_order(run, items, lambda x: x, reverse=True)


@step("sort {items} from Z to A", example="sort names from Z to A", topic=TOPIC)
def sort_z_to_a(run, items: List) -> None:
    """Sorts a list of text from Z to A, ignoring capitals."""
    sort_key_order(run, items, lambda x: x, reverse=True)


@step("sort {table} by {column}", "sort {table} by {column} smallest first", "sort {table} by {column} from A to Z",
      example="sort sales by amount", topic=TOPIC)
def sort_by(run, table: List, column: Field) -> None:
    """Sorts a table by one column: numbers smallest first, and text from A to Z."""
    sort_key_order(run, table, column_getter(column))


@step("sort {table} by {column} largest first", example="sort sales by amount, largest first", topic=TOPIC)
def sort_by_largest(run, table: List, column: Field) -> None:
    """Sorts a table by a column of numbers, largest first."""
    sort_key_order(run, table, column_getter(column), reverse=True)


@step("sort {table} by {column} from Z to A", example="sort sales by customer from Z to A", topic=TOPIC)
def sort_by_z_to_a(run, table: List, column: Field) -> None:
    """Sorts a table by a column of text, from Z to A."""
    sort_key_order(run, table, column_getter(column), reverse=True)


@step("reverse {items}", example="reverse names", topic=TOPIC)
def reverse(run, items: List) -> None:
    """Puts the list in the opposite order."""
    items.reverse()
