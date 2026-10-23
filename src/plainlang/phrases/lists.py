"""Lists and tables."""

import copy
from decimal import Decimal

from ..problems import Problem
from ..registry import Field, Items, List, Number, Place, Value, step, value
from ..values import (Quoted, Record, as_number, fit, kind_name, order, places, quoted, same,
                      show_value)

TOPIC = "Lists and tables"


@value("a list of {items}", example='set colors to a list of "red", "green" and "blue"', topic=TOPIC)
def list_of(run, items: Items) -> List:
    """Makes a list. Commas and a final "and" separate the items."""
    if len(items) == 1 and isinstance(items[0], list):
        return list(items[0])
    return list(items)


@value("an empty list", example="set todos to an empty list", topic=TOPIC)
def empty_list(run) -> List:
    """A list with nothing in it yet."""
    return []


@value("a new record", example="set person to a new record", topic=TOPIC)
def new_record(run) -> Value:
    """A record with no fields yet. Add fields with: set person's name to "Ann"."""
    return Record()


@value("a copy of {value}", example="set backup to a copy of todos", topic=TOPIC)
def copy_of(run, value: Value) -> Value:
    """A separate copy, so changing one doesn't change the other."""
    return copy.deepcopy(value)


def position(items, n, what="item"):
    if n != n.to_integral_value():
        raise Problem("Use a whole number for the position, like 2.", None)
    count = len(items)
    if count == 0:
        raise Problem("Check that the list is not empty first, with: if LIST is not empty",
                      "The list is empty, so it has no items.")
    if not 1 <= n <= count:
        raise Problem(f"Use a position from 1 to {count}.",
                      f"The list has {count} {'item' if count == 1 else 'items'}, so there is no item {n}.")
    return int(n) - 1


@value("item {n} of {items}", example="show item 2 of colors", topic=TOPIC)
def item_of(run, n: Number, items: List) -> Value:
    """The item at that position. Positions start at 1."""
    return items[position(items, n)]


@value("the first item of {items}", example="show the first item of colors", topic=TOPIC)
def first_item(run, items: List) -> Value:
    """The first item."""
    return items[position(items, Decimal(1))]


@value("the last item of {items}", example="show the last item of colors", topic=TOPIC)
def last_item(run, items: List) -> Value:
    """The last item."""
    return items[position(items, Decimal(len(items) or 1))]


@value("the first {n} items of {items}", example="show the first 2 items of colors", topic=TOPIC)
def first_items(run, n: Number, items: List) -> List:
    """The first N items, or all of them if there are fewer."""
    return items[:max(0, int(n))]


@value("the last {n} items of {items}", example="show the last 2 items of colors", topic=TOPIC)
def last_items(run, n: Number, items: List) -> List:
    """The last N items, or all of them if there are fewer."""
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
            raise Problem(f"Check that every item is a number before you {doing} them.",
                          f"{quoted(item)} is {kind_name(item)}, not a number.")
        out.append(n)
    return out


@value("the total of {items}", example="show the total of a list of 1, 2 and 3", topic=TOPIC)
def total(run, items: List) -> Number:
    """Adds up the numbers. Empty cells (nothing) are skipped."""
    numbers = numbers_in(items, "add up")
    result = sum(numbers, Decimal(0))
    return fit(result, max((places(n) for n in numbers), default=0))


@value("the average of {items}", example="show the average of a list of 1, 2 and 3", topic=TOPIC)
def average(run, items: List) -> Number:
    """The total divided by how many numbers there are. Empty cells are skipped."""
    numbers = numbers_in(items, "average")
    if not numbers:
        if items:
            raise Problem("Check that some of the items are numbers before you average them.",
                          "The list has no numbers in it (empty cells don't count), so there's no average.")
        raise Problem("Check that the list is not empty first, with: if LIST is not empty",
                      "The list is empty, so there's no average.")
    result = sum(numbers, Decimal(0)) / len(numbers)
    return fit(result, max(places(n) for n in numbers))


def extreme(items, sign, word):
    present = [item for item in items if item is not None]
    if not present:
        raise Problem("Check that the list is not empty first, with: if LIST is not empty",
                      f"The list is empty, so there's no {word}.")
    best = present[0]
    for item in present[1:]:
        if order(item, best) * sign > 0:
            best = item
    return best


@value("the largest of {items}", example="show the largest of a list of 3, 9 and 4", topic=TOPIC)
def largest(run, items: List) -> Value:
    """The largest number, or the last text in A to Z order."""
    return extreme(items, 1, "largest")


@value("the smallest of {items}", example="show the smallest of a list of 3, 9 and 4", topic=TOPIC)
def smallest(run, items: List) -> Value:
    """The smallest number, or the first text in A to Z order."""
    return extreme(items, -1, "smallest")


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


@value("the different {field} of {table}", example="show the different categories of expenses", topic=TOPIC)
def different_field(run, field: Field, table: List) -> List:
    """Each value of one column once, in the order they first appear."""
    exact = isinstance(field[0], Quoted)
    name = field[0] if exact else " ".join(field)
    column = []
    for row in table:
        if not isinstance(row, Record):
            raise Problem(f'Use a table here. {quoted(row)} is {kind_name(row)}, not a row.', None)
        key = row.find(name, exact=exact)
        if key is None:
            fields = ", ".join(str(k) for k in row.data)
            raise Problem(f"Use one of the fields this table has: {fields}.",
                          f'There\'s no field "{name}" in this table.')
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
        label = place.label
        joined = show_value(value) if not isinstance(value, str) else value
        raise Problem(
            f'Make "{label}" a list to add items to it, or join the text with {{ }}.',
            f'"{label}" is the text {quoted(current)}, and "add" only adds numbers or puts items on a list.',
            try_lines=[f"set {label} to a list of {quoted(current)}",
                       f'set {label} to "{{{label}}} {joined}"'])
    if a is None or b is None:
        bad = value if b is None else current
        raise Problem(f"Check that {quoted(bad)} is a number before you add it.",
                      f"You can't add {quoted(value)} to {quoted(current)}, because {quoted(bad)} is "
                      f"{kind_name(bad)}, not a number.")
    place.set(fit(a + b, max(places(a), places(b))))


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
    """Removes the item at that position."""
    del items[position(items, n)]


@step("remove {value} from {items}", example='remove "milk" from shopping', topic=TOPIC)
def remove(run, value: Value, items: List) -> None:
    """Removes the first item that matches."""
    for index, item in enumerate(items):
        if same(item, value):
            del items[index]
            return
    raise Problem(f"Check that the list contains {quoted(value)} first, with: if LIST contains VALUE",
                  f"There's no {quoted(value)} in the list.")


def sort_key_order(items, key):
    import functools

    def cmp(a, b):
        return order(key(a), key(b))

    try:
        items.sort(key=functools.cmp_to_key(cmp))
    except Problem as problem:
        problem.fix = "Check that the items are all numbers, or all text, before you sort them."
        raise


def field_getter(field):
    exact = isinstance(field[0], Quoted)
    name = field[0] if exact else " ".join(field)

    def get(row):
        if not isinstance(row, Record):
            raise Problem(f'Use "sort by" on a table. {quoted(row)} is {kind_name(row)}.', None)
        return row.get(name, exact)
    return get


@step("sort {items}", example="sort names", topic=TOPIC)
def sort(run, items: List) -> None:
    """Sorts the list, smallest first. Text sorts A to Z, ignoring capitals."""
    sort_key_order(items, lambda x: x)


@step("sort {items} largest first", example="sort scores largest first", topic=TOPIC)
def sort_largest(run, items: List) -> None:
    """Sorts the list, largest first."""
    sort_key_order(items, lambda x: x)
    items.reverse()


@step("sort {items} by {field}", example="sort sales by amount", topic=TOPIC)
def sort_by(run, items: List, field: Field) -> None:
    """Sorts a table by one field, smallest first."""
    sort_key_order(items, field_getter(field))


@step("sort {items} by {field} largest first", example="sort sales by amount, largest first", topic=TOPIC)
def sort_by_largest(run, items: List, field: Field) -> None:
    """Sorts a table by one field, largest first."""
    sort_key_order(items, field_getter(field))
    items.reverse()


@step("reverse {items}", example="reverse names", topic=TOPIC)
def reverse(run, items: List) -> None:
    """Puts the list in the opposite order."""
    items.reverse()
