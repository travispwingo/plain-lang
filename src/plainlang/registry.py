"""The phrase registry: the single source of truth for every built-in phrase.

Each phrase is one Python function. Its template, type annotations, doc and example feed
`plain phrases`, the website reference, the AI's knowledge of Plain and the tests.

Templates are written the way you'd say them, articles included ("a random number from
{low} to {high}"). Articles are dropped for matching. `[word]` is an optional word and
`second|seconds` gives alternatives.
"""

import inspect
from dataclasses import dataclass, field

from .words import ARTICLES, SYNONYMS


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
        out = []
        for part in self.template.split():
            if part.startswith("{"):
                name = part.strip("{}")
                out.append(args.get(name, part))
            elif part.startswith("["):
                continue
            elif "|" in part:   # second|seconds: "1 second", "2 seconds"
                alts = part.split("|")
                out.append(alts[0] if out and out[-1] in ("1", "one") else alts[-1])
            else:
                out.append(part)
        return " ".join(out)


REGISTRY: list[Phrase] = []
CORE_FORMS: list[dict] = []


def compile_template(template, kinds):
    elements = []
    for part in template.split():
        if part.startswith("{"):
            name = part.strip("{}")
            elements.append(Slot(name, kinds.get(name, "value")))
        elif part.startswith("["):
            elements.append(Word(tuple(part.strip("[]").lower().split("|")), optional=True))
        elif part.lower() in ARTICLES:
            continue
        else:
            elements.append(Word(tuple(part.lower().split("|"))))
    return tuple(elements)


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
    return token.norm in alts or SYNONYMS.get(token.norm) in alts


PLACEHOLDERS = {
    "file": "FILE", "source": "FILE", "address": "ADDRESS", "folder": "FOLDER", "question": "QUESTION",
    "choices": "LIST", "field": "FIELD", "table": "TABLE", "items": "LIST", "text": "TEXT",
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
        others = [p.template for p in REGISTRY if p.main is phrase and p is not phrase]
        out.append({
            "topic": phrase.topic, "wording": wording(phrase.template), "doc": phrase.doc,
            "example": phrase.example, "also": [wording(o) for o in others], "effects": sorted(phrase.effects),
            "template": phrase.template,
        })
    return out
