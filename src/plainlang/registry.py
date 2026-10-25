"""The phrase registry: the single source of truth for every built-in phrase.

Each phrase is one Python function. Its template, type annotations, doc and example feed
`plain phrases`, the website reference, the AI's knowledge of Plain and the tests.

Templates are written the way you'd say them, articles included ("a random number from
{low} to {high}"). Articles are dropped for matching. `[word]` is an optional word and
`second|seconds` gives alternatives.
"""

import inspect
import re
from dataclasses import dataclass, field

from .words import ARTICLES, INFLECTIONS, SPECIAL_WORDS, SYNONYMS


class Value:      """Any value."""
class Number:     """A number."""
class Text:       """Text."""
class List:       """A list (or a table)."""
class Place:      """Somewhere a value can be kept: a name, a field or an item."""
class Field:      """The words of a field name."""
class Items:      """Items separated by commas and a final "and"."""


SLOT_KINDS = {Value: "value", Number: "number", Text: "text", List: "list",
              Place: "place", Field: "field", Items: "items"}


@dataclass(frozen=True)
class Word:
    alts: tuple
    optional: bool = False

    @property
    def main(self):
        return self.alts[0]


@dataclass(frozen=True)
class Slot:
    name: str
    kind: str


@dataclass(eq=False)
class Phrase:
    template: str
    elements: tuple
    kind: str                      # step, value, postfix
    run: object                    # a Python function, or a HowTo for your own steps
    gives: bool = False
    effects: frozenset = frozenset()
    origin: str = "built-in"
    doc: str = ""
    example: str = ""
    topic: str = ""
    main: "Phrase" = None          # the main wording when a phrase has several

    @property
    def fixed_count(self):
        return sum(1 for e in self.elements if isinstance(e, Word) and not e.optional)

    @property
    def first_words(self):
        first = self.elements[0]
        if isinstance(first, Word):
            return set(first.alts)
        second = self.elements[1]
        return set(second.alts) if isinstance(second, Word) else set()

    @property
    def shape(self):
        return tuple("_" if isinstance(e, Slot) else e.main for e in self.elements
                     if not (isinstance(e, Word) and e.optional))

    @property
    def slots(self):
        return [e for e in self.elements if isinstance(e, Slot)]

    def render(self, args):
        """This phrase in its own wording with the given values filled in."""
        out, count, slots = [], None, iter(self.slots)
        for part in template_parts(self.template):
            if part.startswith("{"):
                # Slots in order, so a bracketed name of your own with several words, like
                # {the bill}, shows the value handed in (change 20).
                slot = next(slots, None)
                count = args.get(slot.name if slot else part.strip("{}"), part)
                out.append(count)
            elif part.startswith("["):
                continue
            elif "|" in part:   # second|seconds: "1 second", "2 decimal places"
                alts = part.split("|")
                out.append(alts[0] if count in ("1", "one") else alts[-1])
            else:
                out.append(part)
        return " ".join(out)


def template_parts(template):
    """A template's words and slots, keeping a slot of several words whole: "find the tip on {the bill}"."""
    return re.findall(r"\{[^}]*\}|\S+", template)


REGISTRY: list[Phrase] = []
CORE_FORMS: list[dict] = []


def compile_template(template, kinds):
    elements = []
    parts = template.split()
    for k, part in enumerate(parts):
        if part.startswith("{"):
            name = part.strip("{}")
            elements.append(Slot(name, kinds.get(name, "value")))
        elif part.startswith("["):
            elements.append(Word(tuple(part.strip("[]").lower().split("|")), optional=True))
        elif part.lower() in ARTICLES and kept_article(parts[k + 1] if k + 1 < len(parts) else None):
            elements.append(Word((part.lower(),)))    # "from Z to A": Plain keeps an "a" before "to"
        elif part.lower() in ARTICLES:
            continue
        else:
            elements.append(Word(tuple(part.lower().split("|"))))
    return tuple(elements)


def kept_article(after):
    """Plain leaves out "a", "an" and "the" only before an ordinary word (amendment 10), so a
    template keeps one at the end or before one of Plain's special words, as a line does."""
    return after is None or (not after.startswith("{") and after.lower() in SPECIAL_WORDS | ARTICLES)


def register(kind, templates, func, example, effects, topic):
    signature = inspect.signature(func)
    kinds = {}
    for name, param in list(signature.parameters.items())[1:]:
        kinds[name] = SLOT_KINDS.get(param.annotation, "value")
    gives = signature.return_annotation not in (None, inspect.Signature.empty, "None")
    doc = inspect.getdoc(func) or ""
    main = None
    for template in templates:
        elements = compile_template(template, kinds)
        phrase_kind = "postfix" if kind == "value" and isinstance(elements[0], Slot) else kind
        phrase = Phrase(template, elements, phrase_kind, func, gives=gives or kind != "step",
                        effects=frozenset(effects), doc=doc, example=example, topic=topic)
        phrase.main = main or phrase
        main = main or phrase
        REGISTRY.append(phrase)
    return func


def step(*templates, example, effects=(), topic):
    return lambda func: register("step", templates, func, example, effects, topic)


def value(*templates, example, effects=(), topic):
    return lambda func: register("value", templates, func, example, effects, topic)


def core(wording, doc, example, topic="Core steps"):
    CORE_FORMS.append({"wording": wording, "doc": doc, "example": example, "topic": topic})


def word_matches(token, alts):
    if token.kind not in ("word", "symbol"):
        return False
    return token.norm in alts or SYNONYMS.get(token.norm) in alts or INFLECTIONS.get(token.norm) in alts


# One placeholder for each kind of value (change 22). "column" is for tables and "field" for one
# record (change 5).
PLACEHOLDERS = {
    "file": "FILE", "source": "FILE or ADDRESS", "address": "ADDRESS", "folder": "FOLDER", "question": "QUESTION",
    "choices": "LIST", "field": "FIELD", "column": "COLUMN", "columns": "COLUMNs", "table": "TABLE",
    "items": "LIST", "values": "A, B and C", "text": "TEXT",
    "separator": "TEXT", "old": "TEXT", "new": "TEXT", "n": "NUMBER", "places": "NUMBER",
    "seconds": "NUMBER", "minutes": "NUMBER", "low": "NUMBER", "high": "NUMBER", "value": "VALUE",
    "data": "VALUE", "place": "NAME", "page": "PAGE", "new_name": "FILE",
}


def wording(template):
    """A template with its slots as capital placeholders: "sort LIST by FIELD"."""
    out = []
    for part in template.split():
        if part.startswith("{"):
            name = part.strip("{}")
            out.append(PLACEHOLDERS.get(name, name.upper()))
        elif part.startswith("["):
            out.append("[" + part.strip("[]") + "]")
        else:
            out.append(part)
    return " ".join(out)


def catalog():
    """Every built-in phrase in main wording, grouped by topic, in a stable order."""
    import plainlang.phrases  # noqa: F401  (registers everything)
    seen, out = set(), []
    for phrase in REGISTRY:
        if phrase.main is not phrase or id(phrase) in seen:
            continue
        seen.add(id(phrase))
        out.append({
            "topic": phrase.topic, "wording": wording(phrase.template), "doc": phrase.doc,
            "example": phrase.example, "effects": sorted(phrase.effects), "template": phrase.template,
        })
    return out


def reference():
    """The core steps, checks and words, then every phrase: what `plain phrases` and the website list."""
    import plainlang.phrases  # noqa: F401  (registers everything)
    entries = [dict(core, effects=[]) for core in CORE_FORMS]
    return entries + catalog()


def fixed_words(text):
    """The words of a wording that you write as they are: not VALUE, LIST, COLUMNs, FILE or ADDRESS
    or the other placeholders."""
    text = re.sub(r"\b([A-Z]{2,}) or ([A-Z]{2,})\b", r"\1 \2", text)
    return [w.lower() for w in re.findall(r"[A-Za-z']+", text) if not (w.isupper() or re.match(r"[A-Z]{2}", w))]


# Other ways you can write things (change 2) -------------------------------------------------

@dataclass
class OtherWay:
    said: list                 # the other wordings: "is greater than", ">"
    main: list                 # the main wording, or one for each of the other wordings
    tidy: bool = True          # plain tidy writes the main wording, as plain explain shows it
    note: str = ""
    examples: list = field(default_factory=list)   # (a line written this way, the same line in main words)

    def sentence(self, code=lambda text: f"`{text}`"):
        said, main = [code(s) for s in self.said], [code(m) for m in self.main]
        if not main:
            return self.note
        reading = f"{join(said)} {'is' if len(said) == 1 else 'are'} read as {join(main)}."
        return f"{self.note} {reading}" if self.note else reading


def join(items, last="and"):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + f" {last} " + items[-1]


def shown(phrase):
    """A phrase as the reference writes it, with words for its slots: "sort LIST smallest first"."""
    return phrase.render({s.name: PLACEHOLDERS.get(s.name, s.name.upper()) for s in phrase.slots})


SAMPLES = {"value": "2", "number": "2", "text": '"hello"', "list": "names", "items": "names",
           "field": "amount", "place": "score"}

CONTRACTION_EXAMPLES = {
    "isn't": ('if answer isn\'t "no"', 'if answer is not "no"'),
    "doesn't": ('if the file "notes.txt" doesn\'t exist', 'if the file "notes.txt" does not exist'),
    "don't": ('if names don\'t contain "Ann"', 'if names do not contain "Ann"'),
    "aren't": ("if scores aren't empty", "if scores are not empty"),
}

# The words that agree with a plural name, in INFLECTIONS, each in a line.
PLURAL_EXAMPLES = {"are": "if scores are empty", "do": 'if names do not contain "Ann"',
                   "contain": 'if names contain "Ann"', "have": 'if people have "email"'}


def other_ways():
    """Every other way to write something that Plain understands, made from the tables in words.py
    and the registry, for `plain phrases`, the website and the tests."""
    import plainlang.phrases  # noqa: F401  (registers everything)
    from .nodes import StopProgram
    from .words import (ADD_OPS, ARTICLES, COMPARISON_WORDS, COMPARISONS, CONTRACTIONS, INFLECTIONS,
                        LINE_ALIASES, MUL_OPS, MUL_TWO_WORD_OPS, NUMBER_WORDS, POLITE_STARTS, SYNONYMS)
    out = []
    for main in dict.fromkeys(SYNONYMS.values()):
        said = [word for word, m in SYNONYMS.items() if m == main]
        phrase = next(p for p in REGISTRY if p.main is p and main in fixed_words(wording(p.template))
                      and re.search(rf"\b{main}\b", p.example))
        out.append(OtherWay(said, [main], examples=[(re.sub(rf"\b{main}\b", word, phrase.example, count=1),
                                                      phrase.example) for word in said]))
    stop = StopProgram(line=0).canonical()
    aliases = [" ".join(words) for words in LINE_ALIASES]
    out.append(OtherWay(aliases, [stop], examples=[(a, stop) for a in aliases]))
    for op, main in COMPARISON_WORDS.items():
        said = [w for w in dict.fromkeys(" ".join("the same" if x == "same" else x for x in words)
                                         for words, o in COMPARISONS if o == op and words[0] not in INFLECTIONS)
                if w != main]
        if said:
            out.append(OtherWay(said, [main], examples=[(f"if score {w} 10", f"if score {main} 10") for w in said]))
    out.append(OtherWay(list(CONTRACTIONS), [" ".join(words) for words in CONTRACTIONS.values()],
                        examples=[CONTRACTION_EXAMPLES[c] for c in CONTRACTIONS]))
    signs = {}
    for sign, word in list(ADD_OPS.items()) + list(MUL_OPS.items()) + \
            [(" ".join(words), word) for words, word in MUL_TWO_WORD_OPS.items()]:
        if sign != word:
            signs.setdefault(word, []).append(sign)
    for word, said in signs.items():
        out.append(OtherWay(said, [word], examples=[(f"show 6 {s} 3", f"show 6 {word} 3") for s in said]))
    out.append(OtherWay(["15 percent"], ["15%"], examples=[("show 15 percent of 80", "show 15% of 80")]))
    alternatives = {}
    for phrase in REGISTRY:
        if phrase.main is not phrase:
            alternatives.setdefault(phrase.main, []).append(phrase)
    for main, alts in alternatives.items():
        examples = []
        for alt in alts:
            args = {s.name: SAMPLES[s.kind] for s in main.slots}
            show = "" if main.kind == "step" else "show "
            examples.append((show + alt.render(args), show + main.render(args)))
        out.append(OtherWay([shown(a) for a in alts], [shown(main)], examples=examples))
    out.append(OtherWay(["for each", "while", "until"], ["repeat for each", "repeat while", "repeat until"],
                        note="At the start of a line,",
                        examples=[("for each sale in sales", "repeat for each sale in sales"),
                                  ("while score is less than 10", "repeat while score is less than 10"),
                                  ('until answer is "yes"', 'repeat until answer is "yes"')]))
    out.append(OtherWay(["repeat for every"], ["repeat for each"],
                        examples=[("repeat for every sale in sales", "repeat for each sale in sales")]))
    out.append(OtherWay(["skip this round", "skip round"], ["skip to the next round"],
                        examples=[("skip this round", "skip to the next round"),
                                  ("skip round", "skip to the next round")]))
    ends = ["end", "end if", "end repeat", "end try"]
    out.append(OtherWay(ends, [], note=f"A line {join([f'`{e}`' for e in ends], 'or')} is left out, because Plain "
                        "goes by how far each line is moved to the right. `plain tidy` deletes it. To finish the "
                        "program, write `stop the program`.",
                        examples=[(f"if score is 10\n    show score\n{e}", "if score is 10\n    show score")
                                  for e in ends]))

    # Plain reads these the same, and plain tidy leaves them as you wrote them.
    out.append(OtherWay(['SHOW "Hi"'], ['show "Hi"'], tidy=False, note="Capitals don't matter:",
                        examples=[('SHOW "Hi"', 'show "Hi"')]))
    out.append(OtherWay(['Then show "Done"'], ['show "Done"'], tidy=False,
                        note=f"These words at the start of a line are left out: {join(sorted(POLITE_STARTS))}.",
                        examples=[(f'{w.capitalize()} show "Done"', 'show "Done"') for w in sorted(POLITE_STARTS)]))
    out.append(OtherWay(["show the total"], ["show total"], tidy=False,
                        note=f"You can leave out {join(sorted(ARTICLES))}:",
                        examples=[("show the total", "show total")]))
    out.append(OtherWay(['if answer is "y" or "yes"', "if age is more than 12 and less than 20"],
                        ['if answer is "y" or answer is "yes"', "if age is more than 12 and age is less than 20"],
                        tidy=False, note="You can leave out the words you'd say twice:",
                        examples=[('if answer is "y" or "yes"', 'if answer is "y" or answer is "yes"'),
                                  ("if age is more than 12 and less than 20",
                                   "if age is more than 12 and age is less than 20")]))
    plural = [PLURAL_EXAMPLES[word] for word in INFLECTIONS]
    out.append(OtherWay(plural, [], tidy=False,
                        note="After a name that holds several things, write the words the way you'd say them: "
                        + join([f"`{p}`" for p in plural], "or") + ".",
                        examples=[(p, p) for p in plural]))
    out.append(OtherWay([], [], tidy=False, note="After a name that ends in s, you can write just the apostrophe, "
                        "as in `players' score`.", examples=[("show players' score", "show players' score")]))
    words = list(NUMBER_WORDS)
    out.append(OtherWay([], [], tidy=False, note=f"The number words `{words[0]}` to `{words[-1]}` work like numbers, "
                        "as in `repeat three times`. `$42.50` is the number 42.50, and `15%` is 0.15.",
                        examples=[("repeat three times", "repeat three times"), ("show $42.50", "show $42.50")]))
    out.append(OtherWay([], [], tidy=False, note='`“curly quotes”` from Word or Google Docs work like '
                        '`"straight quotes"`.', examples=[("show “curly quotes”", 'show "curly quotes"')]))
    return out
