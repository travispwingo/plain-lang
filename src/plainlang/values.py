"""Plain's values: numbers, text, yes/no, nothing, lists and records.

Numbers are exact decimals. Equality is friendly: text ignores capitals and spaces at
either end, and "yes"/"y"/"true" count as yes. `is exactly` is the strict form.
"""

import re
from decimal import (ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Context, Decimal,
                     InvalidOperation, localcontext)

from .problems import Problem, things

CONTEXT = Context(prec=28, rounding=ROUND_HALF_UP)
MAX_PLACES = 10
TABLE_ROWS = 20
YES_WORDS = {"yes", "y", "true"}
NO_WORDS = {"no", "n", "false"}

NUMBERISH = re.compile(
    r"^(?P<sign1>[+-]?)(?P<cur>[$€£]?)(?P<sign2>[+-]?)"
    r"(?P<digits>\d+(?:\.\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?)(?P<pct>%?)$")


class Percent(Decimal):
    """A number written as a percent, like 15%. It keeps the decimal places you wrote (none
    for 15%, one for 2.5%), so it shows the same whether it's written in a line or kept
    under a name."""
    written_places = 0


def percent(value, written_places):
    p = Percent(value)
    p.written_places = written_places
    return p


def places(d):
    exponent = d.as_tuple().exponent
    return max(0, -exponent) if isinstance(exponent, int) else 0


def needed_places(d):
    """The decimal places d needs: its places without the zeros at the end."""
    if d.is_zero():
        return 0
    digits = "".join(map(str, d.as_tuple().digits))
    return max(0, places(d) - (len(digits) - len(digits.rstrip("0"))))


def round_places(d, p):
    """d rounded to p decimal places, halves up, however many digits it has."""
    context = Context(prec=max(CONTEXT.prec, len(d.as_tuple().digits) + p), rounding=ROUND_HALF_UP)
    return d.quantize(Decimal(1).scaleb(-p), context=context)


def fit(d, min_places):
    """Keep at least min_places decimal places, and more only when the value needs them.

    A long result that rounds to a short one at MAX_PLACES (99.999…9 is 100) becomes the
    short one. More than MAX_PLACES places only come from such long results, so they set
    no minimum.
    """
    if not d.is_finite():
        return d
    if d.is_zero():
        d = abs(d)
    needed = needed_places(d)
    if needed > MAX_PLACES:
        short = needed_places(round_places(d, MAX_PLACES))
        if short < MAX_PLACES:
            needed = short
    if min_places > MAX_PLACES:
        min_places = 0
    try:
        return round_places(d, max(needed, min_places))
    except InvalidOperation:
        return d


def number_text(d):
    if d.is_zero():
        d = abs(d)
    if places(d) > MAX_PLACES:
        d = round_places(d, MAX_PLACES)
        if d.is_zero():
            d = abs(d)
    return format(d, "f")


def auto_number(text):
    """An answer, CSV cell or line of a file that looks like a number becomes one."""
    if not isinstance(text, str):
        return text
    s = text.strip()
    m = NUMBERISH.match(s)
    if not m or (m["sign1"] and m["sign2"]):
        return text
    digits = m["digits"]
    if len(digits) > 1 and digits[0] == "0" and digits[1].isdigit():
        return text   # 02134 stays text
    value = Decimal(digits.replace(",", ""))
    if m["pct"]:
        value = value / 100
    if "-" in (m["sign1"], m["sign2"]):
        value = -value
    return value


def is_number(v):
    return isinstance(v, Decimal)


def as_number(v):
    """A number, or text that reads as a number. Otherwise None."""
    if isinstance(v, Decimal):
        return v
    if isinstance(v, str):
        n = auto_number(v)
        if isinstance(n, Decimal):
            return n
    return None


def kind_name(v):
    if v is None:
        return "nothing"
    if isinstance(v, bool):
        return "yes/no"
    if isinstance(v, Decimal):
        return "a number"
    if isinstance(v, str):
        return "text"
    if isinstance(v, Record):
        return "a record"
    if isinstance(v, list):
        return "a table" if v and all(isinstance(x, Record) for x in v) else "a list"
    return "a value"


def quoted(v):
    """A value as you'd see it in a message. Lists, tables and records are described, not shown."""
    if isinstance(v, str):
        return f'"{v}"'
    if isinstance(v, list):
        if not v:
            return "an empty list"
        if kind_name(v) == "a table":
            return f"a table with {things(len(v), 'row')}"
        return f"a list of {things(len(v), 'item')}"
    if isinstance(v, Record):
        return f"a record with {things(len(v.data), 'field')}" if v.data else "an empty record"
    return show_value(v)


def missing_column(name, row):
    """A table has no column with that name: "column" is the word for tables, and "field" for one
    record (change 5)."""
    columns = ", ".join(str(k) for k in row.data)
    if not columns:
        return Problem(f'Set "{name}" in each row before you use it.', "The rows of this table have nothing in them yet.")
    return Problem(f"Use one of the columns this table has: {columns}.", f'There\'s no column "{name}" in this table.')


class Quoted(str):
    """A field name written in quotes, matched exactly."""


# Records -------------------------------------------------------------------------

def norm_key(key):
    """Field names ignore capitals, spaces, _, - and camelCase: "userId", "user_id" and
    "user id" are the same field."""
    return "".join(re.split(r"[\s_\-]+", str(key).lower()))


def plural_forms(name):
    yield name
    if name.endswith("ies"):
        yield name[:-3] + "y"
    if name.endswith("es"):
        yield name[:-2]
    if name.endswith("s"):
        yield name[:-1]


class Record:
    """Named fields, looked up the friendly way. The original keys and order are kept."""

    __slots__ = ("data",)

    def __init__(self, data=None):
        self.data = dict(data or {})

    def find(self, name, exact=False, table=False):
        """The original key for a field name, or None. With table=True the record is a row of a
        table, so a message says "column" (change 5)."""
        if exact or name in self.data:          # an exact name always wins
            return name if name in self.data else None
        wanted = norm_key(name)
        for form in plural_forms(wanted):
            matches = [k for k in self.data if norm_key(k) == form]
            if len(matches) > 1:
                word, whole = ("column", "table") if table else ("field", "record")
                raise Problem(
                    f'Write the {word} name in quotes to pick one: {", ".join(chr(34) + m + chr(34) for m in matches)}.',
                    f'This {whole} has more than one {word} that matches "{name}".')
            if matches:
                return matches[0]
        return None

    def get(self, name, exact=False):
        key = self.find(name, exact)
        if key is None:
            if not self.data:
                raise Problem(f'Set the field "{name}" before you use it.',
                              f'This is a record with no fields yet, so it has no field "{name}".')
            fields = ", ".join(str(k) for k in self.data)
            raise Problem(
                f'Use one of the fields this record has: {fields}.',
                f'There\'s no field "{name}" in this record.')
        return self.data[key]

    def set(self, name, value, exact=False):
        key = self.find(name, exact) if self.data else None
        self.data[key if key is not None else name] = value

    def __eq__(self, other):
        return isinstance(other, Record) and self.data == other.data

    def __repr__(self):
        return f"Record({self.data!r})"

    def __deepcopy__(self, memo):
        import copy
        return Record(copy.deepcopy(self.data, memo))


# Comparing -----------------------------------------------------------------------

def as_shown(n):
    """A number as Plain shows it (at most 10 decimal places). Numbers that show the same are
    the same, so 1 divided by 3 times 3 is 1."""
    if places(n) <= MAX_PLACES:
        return n
    return n.quantize(Decimal(1).scaleb(-MAX_PLACES), context=CONTEXT)


def same(a, b):
    """Friendly equality, used by `is`."""
    if isinstance(a, bool) or isinstance(b, bool):
        if isinstance(a, bool) and isinstance(b, bool):
            return a == b
        other, flag = (b, a) if isinstance(a, bool) else (a, b)
        if isinstance(other, str):
            word = other.strip().lower()
            return (word in YES_WORDS) if flag else (word in NO_WORDS)
        return False
    if isinstance(a, Decimal) or isinstance(b, Decimal):
        na, nb = as_number(a), as_number(b)
        return na is not None and nb is not None and as_shown(na) == as_shown(nb)
    if isinstance(a, str) and isinstance(b, str):
        return a.strip().casefold() == b.strip().casefold()
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, Record) and isinstance(b, Record):
        return a.data.keys() == b.data.keys() and all(same(a.data[k], b.data[k]) for k in a.data)
    return a == b


def exactly(a, b):
    if type(a) is not type(b):
        return False
    return a == b


def text_key(v):
    return v.strip().casefold() if isinstance(v, str) else v


def order(a, b):
    """-1, 0 or 1. Numbers compare as numbers, text alphabetically ignoring capitals."""
    na, nb = as_number(a), as_number(b)
    if na is not None and nb is not None:
        na, nb = as_shown(na), as_shown(nb)
        return (na > nb) - (na < nb)
    if isinstance(a, str) and isinstance(b, str):
        ka, kb = text_key(a), text_key(b)
        return (ka > kb) - (ka < kb)
    bad, good = (a, b) if na is None else (b, a)
    raise Problem(
        f'Check that {quoted(bad)} is a number before you compare it.',
        f'You can\'t compare {quoted(bad)} with {quoted(good)}, because {quoted(bad)} is {kind_name(bad)}, not a number.')


def contains(whole, part):
    if isinstance(whole, str):
        if not isinstance(part, str):
            part = show_value(part)
        return part.strip().casefold() in whole.casefold()
    if isinstance(whole, list):
        return any(same(item, part) for item in whole)
    raise Problem(
        "Use contains with text or a list.",
        f"{quoted(whole)} is {kind_name(whole)}, so it can't contain anything.")


def is_empty(v):
    return v is None or v == "" or (isinstance(v, (list, Record)) and not (v.data if isinstance(v, Record) else v))


# Showing -------------------------------------------------------------------------

def show_value(v):
    if v is None:
        return "nothing"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, Decimal):
        return number_text(v)
    if isinstance(v, str):
        return v
    if isinstance(v, Record):
        return ", ".join(f"{k}: {show_inline(x)}" for k, x in v.data.items()) or "(empty record)"
    if isinstance(v, list):
        if not v:
            return "(empty list)"
        if all(isinstance(x, Record) for x in v):
            return show_table(v)
        items = [show_inline(x) for x in v]
        return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]
    return str(v)


def show_inline(v):
    if isinstance(v, list):
        return "[" + show_value(v) + "]" if v else "(empty list)"
    if isinstance(v, Record):
        return "{" + show_value(v) + "}"
    return show_value(v)


def show_table(rows, limit=TABLE_ROWS):
    """Lined-up columns. With limit=None every row is shown, as when saving to a file."""
    columns = []
    for row in rows:
        for key in row.data:
            if key not in columns:
                columns.append(key)
    shown = rows if limit is None else rows[:limit]
    cells = [[str(c) for c in columns]] + [
        [show_inline(row.data.get(c)) if c in row.data else "" for c in columns] for row in shown]
    widths = [max(len(r[i]) for r in cells) for i in range(len(columns))]
    lines = ["  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip() for r in cells]
    if limit is not None and len(rows) > limit:
        lines.append(f"…and {len(rows) - limit} more")
    return "\n".join(lines)


def round_to(d, digits, mode="half up"):
    rounding = {"half up": ROUND_HALF_UP, "down": ROUND_FLOOR, "up": ROUND_CEILING}[mode]
    with localcontext(CONTEXT):
        return d.quantize(Decimal(1).scaleb(-digits), rounding=rounding)
