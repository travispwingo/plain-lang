"""Numbers and text."""

from decimal import Decimal

from ..problems import Problem
from ..registry import Field, List, Number, Place, Text, Value, step, value
from ..values import as_number, auto_number, kind_name, quoted, round_to, show_value

TOPIC = "Numbers and text"


@value("{value} rounded", example="show 6.5 rounded", topic=TOPIC)
def rounded(run, value: Number) -> Number:
    """Rounds to a whole number. Halves go up."""
    return round_to(value, 0)


@value("{value} rounded to {places} decimal place|places", "{value} rounded to {places} place|places",
       "{value} rounded to {places} decimal|decimals", example="show 6.375 rounded to 2 decimal places", topic=TOPIC)
def rounded_to(run, value: Number, places: Number) -> Number:
    """Rounds to that many decimal places. Halves go up."""
    if places != places.to_integral_value() or not 0 <= places <= 10:
        raise Problem("Use a whole number of places from 0 to 10.", None)
    return round_to(value, int(places))


@value("{value} rounded down", example="show 7.9 rounded down", topic=TOPIC)
def rounded_down(run, value: Number) -> Number:
    """Rounds down to a whole number."""
    return round_to(value, 0, "down")


@value("{value} rounded up", example="show 7.1 rounded up", topic=TOPIC)
def rounded_up(run, value: Number) -> Number:
    """Rounds up to a whole number."""
    return round_to(value, 0, "up")


@value("{value} as a number", example='show "42" as a number', topic=TOPIC)
def as_a_number(run, value: Value) -> Number:
    """Turns text like "42" into the number 42."""
    n = as_number(value)
    if n is None:
        name = run.written_name("value")
        fix = f'Check that "{name}" is a number first, with: if {name} is a number' if name else \
            'Use text that reads as a number here, like "42".'
        raise Problem(fix, f"{quoted(value)} is {kind_name(value)}, and it doesn't read as a number.")
    return n


@value("{value} as text", example="show 42 as text", topic=TOPIC)
def as_text(run, value: Value) -> Text:
    """Turns any value into text, the way "show" would show it."""
    return show_value(value)


@value("the length of {text}", example='show the length of "hello"', topic=TOPIC)
def length(run, text: Value) -> Number:
    """How many characters, counting spaces and punctuation."""
    if isinstance(text, list):
        raise Problem('Write "the number of" to count the items in a list.',
                      '"the length of" counts the characters in text.')
    return Decimal(len(show_value(text)))


@value("{text} in capital letters", "{text} in capitals", "{text} in uppercase",
       example='show "hello" in capital letters', topic=TOPIC)
def capital_letters(run, text: Text) -> Text:
    """The same text in capital letters: "hello" becomes "HELLO"."""
    return text.upper()


@value("{text} in small letters", "{text} in lowercase", example='show "HELLO" in small letters', topic=TOPIC)
def small_letters(run, text: Text) -> Text:
    """The same text in small letters: "HELLO" becomes "hello"."""
    return text.lower()


@value("the words of {text}", example='show the words of "one two three"', topic=TOPIC)
def words(run, text: Text) -> List:
    """A list of the words in the text."""
    return text.split()


@value("the lines of {text}", example="show the lines of story", topic=TOPIC)
def lines(run, text: Text) -> List:
    """A list with one item for each line of the text."""
    return [auto_number(line) for line in text.splitlines()]


@value("the characters of {text}", example='show the characters of "abc"', topic=TOPIC)
def characters(run, text: Text) -> List:
    """Every character in the text: letters, digits, spaces and punctuation."""
    return list(text)


@value("{text} split by {separator}", example='show "a,b,c" split by ","', topic=TOPIC)
def split_by(run, text: Text, separator: Text) -> List:
    """Splits the text into a list wherever the separator appears."""
    if separator == "":
        return list(text)
    return text.split(separator)


@value("{items} joined with {separator}", example='show colors joined with " - "', topic=TOPIC)
def joined_with(run, items: List, separator: Text) -> Text:
    """Joins the items of a list into one text, with the separator between them."""
    return separator.join(show_value(item) for item in items)


@step("replace {old} with {new} in {place}", example='replace "cat" with "dog" in story', topic=TOPIC)
def replace(run, old: Text, new: Text, place: Place) -> None:
    """Changes every match in the text kept under that name. Capitals must match exactly."""
    current = place.get()
    if not isinstance(current, str):
        raise Problem(f'Use "replace" on text. "{place.label}" is {kind_name(current)}.', None)
    place.set(current.replace(old, new))
