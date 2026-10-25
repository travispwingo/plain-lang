"""The core steps, checks and words read by hand in parser.py. Listed here for the phrase reference
and the AI. The checks and the arithmetic words come from the tables in words.py (change 18), so a
new comparison can't be left out of the reference."""

from ..nodes import OPPOSITES
from ..registry import core
from ..words import ADD_OPS, COMPARISON_WORDS, MUL_OPS, MUL_TWO_WORD_OPS, NEGATIVE_COMPARISONS, TYPE_CHECKS

core("set NAME to VALUE", "Keeps a value under a name. Lists and records are copied.", "set score to 0")
core("STEP and call it NAME", "Keeps what a step gives back under a name.", 'ask "Your name?" and call it name')
core("if CHECK", "Takes the steps under it only when the check is yes.", 'if score is more than 10')
core("otherwise if CHECK", "Another check, tried when the ones above weren't yes.", "otherwise if score is 10")
core("otherwise", "The steps to take when none of the checks above were yes.", "otherwise")
core("repeat N times", "Takes the steps under it N times. Also: repeat once, repeat twice.", "repeat 3 times")
core("repeat forever", "Repeats until you leave with \"stop repeating\" or end with \"stop the program\".", "repeat forever")
core("repeat until CHECK", "Takes the steps, then checks. Stops once the check is yes.", "repeat until guess is secret")
core("repeat while CHECK", "Checks first, and takes the steps while the check is yes.", "repeat while lives is more than 0")
core("repeat for each NAME in LIST", "Takes the steps once for each item of the list.", "repeat for each sale in sales")
core("repeat for each NAME from A to B", "Counts up from A to B. Write \"down to\" to count down.", "repeat for each n from 1 to 10")
core("stop repeating", "Leaves the repeat it's in.", "stop repeating")
core("skip to the next round", "Goes straight to the next round of the repeat.", "skip to the next round")
core("stop the program", "Ends the program now.", "stop the program")
core("how to WORDS (NAME)", "Makes a step of your own. Words in brackets are values you hand in.", "how to greet (person)")
core("give back VALUE", "Ends your own step and hands back a value.", "give back total")
core("try", "Takes the steps under it. If one has a problem, Plain goes to \"if that fails\".", "try")
core("if that fails", "The steps to take when a step under \"try\" had a problem. \"the problem\" says what went wrong.", "if that fails")


# Checks ---------------------------------------------------------------------------
# Each comparison in its main words, with what goes on each side, what it does and an example.

COMPARISON_ENTRIES = {
    "is": ("VALUE", "VALUE", "Yes when both are the same. For text, capitals and spaces at either end don't matter.",
           'if answer is "yes"'),
    "exact": ("TEXT", "TEXT", 'Like "is", but capitals and spaces must match too.',
              'if name is exactly "Ann"'),
    "more": ("NUMBER", "NUMBER", "Yes when the first number is bigger.", "if score is more than 10"),
    "less": ("NUMBER", "NUMBER", "Yes when the first number is smaller.", "if temperature is less than 5"),
    "at least": ("NUMBER", "NUMBER", "Yes when the first number is bigger or the same, so 18 is at least 18.",
                 "if age is at least 18"),
    "at most": ("NUMBER", "NUMBER", "Yes when the first number is smaller or the same, so 3 is at most 3.",
                "if score is at most 3"),
    "in": ("VALUE", "LIST", "Yes when the list has that item, or the text has it in it.",
           'if answer is in a list of "y" and "yes"'),
    "contains": ("LIST", "VALUE", "Yes when the list has that item, or the text has the other text in it.",
                 'if shopping contains "milk"'),
    "has": ("RECORD", "TEXT", "Yes when the record has a field with that name.", 'if person has "name"'),
    "starts": ("TEXT", "TEXT", "Yes when the text starts with the other text.", 'if name starts with "A"'),
    "ends": ("TEXT", "TEXT", "Yes when the text ends with the other text.", 'if email ends with ".org"'),
}

# "is [not] KIND": what it does and an example, for each kind in TYPE_CHECKS, and "divisible by".
KIND_ENTRIES = {
    "empty": ("VALUE", "Yes for empty text, an empty list, an empty record or nothing.", "if answer is empty"),
    "number": ("VALUE", 'Yes for a number, or text that is a number, like "42".', "if answer is a number"),
    "whole number": ("VALUE", "Yes for a number with nothing after the decimal point, like 7.",
                     "if guess is a whole number"),
    "text": ("VALUE", 'Yes for text that isn\'t a number. "42" is a number, but "hello" is text.',
             "if answer is text"),
    "list": ("VALUE", "Yes for a list, or a table read from a file.", "if reply is a list"),
    "even": ("NUMBER", "Yes for 0, 2, 4 and so on.", "if score is even"),
    "odd": ("NUMBER", "Yes for 1, 3, 5 and so on.", "if score is odd"),
    "divisible": ("NUMBER", "Yes when the number divides by N with nothing left over.", "if year is divisible by 4"),
}

KIND_WORDS = {"number": "a number", "whole number": "a whole number", "list": "a list", "divisible": "divisible by N"}


for op, words in COMPARISON_WORDS.items():
    if op in NEGATIVE_COMPARISONS:
        continue      # listed with its positive form: "does not contain" with "contains"
    left, right, doc, example = COMPARISON_ENTRIES[op]
    core(f"{left} {words} {right}", f'{doc} The opposite is "{COMPARISON_WORDS[OPPOSITES[op]]}".', example,
         topic="Checks")

core("NUMBER is between A and B", 'Yes when the number is from A to B. Both A and B count. The opposite is '
     '"is not between".', "if pick is between 1 and 10", topic="Checks")
for kind in list(dict.fromkeys(TYPE_CHECKS.values())) + ["divisible"]:
    left, doc, example = KIND_ENTRIES[kind]
    words = KIND_WORDS.get(kind, kind)
    core(f"{left} is {words}", f'{doc} The opposite is "is not {words}".', example, topic="Checks")
core("CHECK and CHECK", "Yes when both checks are yes.", "if age is at least 18 and ticket is yes", topic="Checks")
core("CHECK or CHECK", "Yes when either check is yes. Use brackets when one check has both \"and\" and \"or\".",
     'if answer is "y" or answer is "yes"', topic="Checks")
core("not CHECK", "Yes when the check is no.", "if not (score is 10 or score is 20)", topic="Checks")


# Numbers and names ----------------------------------------------------------------

ARITHMETIC_ENTRIES = {
    "plus": ("Adds two numbers.", "show 2 plus 3"),
    "minus": ("Takes the second number away from the first.", "show 10 minus 4"),
    "times": ("Multiplies two numbers. Times and divided by come before plus and minus, and brackets go first.",
              "show 6 times 7"),
    "divided by": ("Divides the first number by the second.", "show 10 divided by 4"),
}

for word in dict.fromkeys(list(ADD_OPS.values()) + list(MUL_OPS.values()) + list(MUL_TWO_WORD_OPS.values())):
    doc, example = ARITHMETIC_ENTRIES[word]
    core(f"NUMBER {word} NUMBER", doc, example, topic="Numbers and names")
core("N% of VALUE", "A part of a value, like 15% of a bill.", "show 15% of 80",
     topic="Numbers and names")
core("RECORD's FIELD", "One field of a record, like one cell of a row. After a name that ends in s, you can write just "
     "the apostrophe: players' score.", "show person's name", topic="Numbers and names")
core("the FIELDs of TABLE", "One column of a table, as a list: the amounts of sales.", "show the amounts of sales",
     topic="Numbers and names")
core("LIST where CHECK", "The items of a list for which the check is yes. In the check, \"it\" is the item being "
     "checked.", "show scores where it is more than 3", topic="Numbers and names")
core("its FIELD", "In a \"where\" check on a table, one field of the row being checked. You can leave out "
     "\"its\" before the field.", "show sales where its amount is more than 100", topic="Numbers and names")
