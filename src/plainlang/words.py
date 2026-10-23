"""Plain's closed word tables. Everything that decides what a word means lives here."""

# Plain's special words end names and field words, so they can't be part of a name.
SPECIAL_WORDS = frozenset("""
    and or not is to from by in of with as than then where it its plus minus times
    divided multiplied rounded percent split joined contains starts ends exists does
    equals yes no nothing true false
    zero one two three four five six seven eight nine ten eleven twelve
""".split())

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}

ARTICLES = frozenset({"a", "an", "the"})

# Dropped only at the very start of a line.
POLITE_STARTS = frozenset({"please", "now", "then", "next", "first", "finally"})

CONTRACTIONS = {
    "isn't": ("is", "not"), "doesn't": ("does", "not"), "don't": ("do", "not"),
    "aren't": ("are", "not"), "can't": ("can", "not"),
}

# Each synonym means its main word everywhere, but only where a phrase expects that
# fixed word. Names, field words, how-to wordings and text are never changed.
SYNONYMS = {
    "display": "show",
    "load": "read",
    "fetch": "read",
    "else": "otherwise",
    "sum": "total",
    "mean": "average",
    "biggest": "largest",
    "highest": "largest",
    "lowest": "smallest",
    "options": "choices",
    "delete": "remove",
    "pause": "wait",
}

# Words that start the core forms of a line.
CORE_STARTS = frozenset({
    "set", "if", "otherwise", "repeat", "for", "while", "until", "how", "give",
    "return", "try", "stop", "skip", "end",
})

# Whole-line aliases.
LINE_ALIASES = {
    ("quit",): ("stop", "program"),
    ("exit",): ("stop", "program"),
}

# Comparison wordings: (words, op). "the" is already dropped before ordinary words.
COMPARISONS = [
    (("is", "exactly"), "exact"),
    (("is", "not", "exactly"), "not exact"),
    (("is", "not", "more", "than"), "at most"),
    (("is", "not", "less", "than"), "at least"),
    (("is", "more", "than"), "more"),
    (("is", "greater", "than"), "more"),
    (("is", "bigger", "than"), "more"),
    (("is", "larger", "than"), "more"),
    (("is", "higher", "than"), "more"),
    (("is", "above"), "more"),
    (("is", "less", "than"), "less"),
    (("is", "smaller", "than"), "less"),
    (("is", "fewer", "than"), "less"),
    (("is", "lower", "than"), "less"),
    (("is", "under"), "less"),
    (("is", "below"), "less"),
    (("is", "at", "least"), "at least"),
    (("is", "no", "less", "than"), "at least"),
    (("is", "at", "most"), "at most"),
    (("is", "no", "more", "than"), "at most"),
    (("is", "equal", "to"), "is"),
    (("is", "same", "as"), "is"),
    (("is", "different", "from"), "is not"),
    (("is", "not", "in"), "not in"),
    (("is", "in"), "in"),
    (("is", "not"), "is not"),
    (("is",), "is"),
    (("equals",), "is"),
    (("does", "not", "equal"), "is not"),
    (("contains",), "contains"),
    (("does", "not", "contain"), "not contains"),
    (("starts", "with"), "starts"),
    (("does", "not", "start", "with"), "not starts"),
    (("ends", "with"), "ends"),
    (("does", "not", "end", "with"), "not ends"),
    (("=",), "is"), (("==",), "is"), (("!=",), "is not"), (("≠",), "is not"),
    ((">",), "more"), (("<",), "less"),
    ((">=",), "at least"), (("≥",), "at least"), (("<=",), "at most"), (("≤",), "at most"),
]

# How each comparison is written in main words, for canonical() and messages.
COMPARISON_WORDS = {
    "is": "is", "is not": "is not", "exact": "is exactly", "not exact": "is not exactly",
    "more": "is more than", "less": "is less than", "at least": "is at least",
    "at most": "is at most", "in": "is in", "not in": "is not in",
    "contains": "contains", "not contains": "does not contain",
    "starts": "starts with", "not starts": "does not start with",
    "ends": "ends with", "not ends": "does not end with",
}

NEGATIVE_COMPARISONS = frozenset({
    "is not", "not exact", "not in", "not contains", "not starts", "not ends",
})

# Words that can start a comparison, used to spot elided comparisons.
COMPARISON_STARTS = frozenset({"is", "equals", "does", "contains", "starts", "ends",
                                "=", "==", "!=", "≠", ">", "<", ">=", "≥", "<=", "≤",
                                "more", "less", "at", "greater", "bigger", "larger",
                                "higher", "above", "smaller", "fewer", "lower", "under",
                                "below"})

# Bare comparison wordings allowed after "and"/"or" when the subject is left out.
ELIDED_COMPARISONS = [
    (("more", "than"), "more"), (("greater", "than"), "more"), (("bigger", "than"), "more"),
    (("larger", "than"), "more"), (("higher", "than"), "more"), (("above",), "more"),
    (("less", "than"), "less"), (("smaller", "than"), "less"), (("fewer", "than"), "less"),
    (("lower", "than"), "less"), (("under",), "less"), (("below",), "less"),
    (("at", "least"), "at least"), (("at", "most"), "at most"),
]

# "is [not] KIND" checks.
TYPE_CHECKS = {
    ("empty",): "empty", ("number",): "number", ("whole", "number"): "whole number",
    ("text",): "text", ("list",): "list", ("even",): "even", ("odd",): "odd",
}

ADD_OPS = {"plus": "plus", "+": "plus", "minus": "minus", "-": "minus"}
MUL_OPS = {"times": "times", "*": "times", "×": "times", "/": "divided by", "÷": "divided by"}
MUL_TWO_WORD_OPS = {("multiplied", "by"): "times", ("divided", "by"): "divided by"}

# Words that never appear in anything Plain shows you. Quoted code from other languages
# is the only exception. tests/test_banned_words.py enforces this.
BANNED_WORDS = frozenset("""
    variable variables function functions argument arguments parameter parameters
    boolean null string strings array arrays iterate exception exceptions syntax parse
    token tokens runtime invalid catch caught loop loops innermost header headers block
    blocks binds precedence elide elided property properties postfix scope recursion
    built-in literal operator operators statement statements expression expressions
    execute compile
""".split())
