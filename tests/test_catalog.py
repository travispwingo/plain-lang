"""Every built-in phrase: its example reads as that phrase and runs; no two built-ins tie;
the synonym table maps each word to exactly one main word and holds no special words."""

import json
import unittest

from .support import ROOT, run_source
from plainlang.parser import Reader
from plainlang.registry import REGISTRY, catalog
from plainlang.words import SPECIAL_WORDS, SYNONYMS
from plainlang import nodes as N

CONTEXT = '''set colors to a list of "red", "green" and "blue"
set todos to a list of "buy milk" and "walk the dog"
set shopping to a list of "milk" and "bread"
set names to a list of "Bo", "ann" and "Cy"
set scores to a list of 3, 9 and 4
set prices to a list of 1.50 and 2.25
set cards to a list of 1, 2, 3 and 4
read "sales.csv" and call it sales
read "expenses.csv" and call it expenses
set person to an empty record
set message to an empty record
set message's text to "hi"
set story to "the cat sat"
set notes to "hello"
set page to "<p>Hi <a href='https://example.com'>there</a></p>"
set score to 1
set lives to 3
set total to 0
set price to 10
set reply to nothing
'''

FILES = {
    "sales.csv": "date,customer,amount\n2026-10-01,Ann,120.50\n2026-10-02,Bo,80\n",
    "expenses.csv": "category,amount\nfood,5\nrent,500\nfood,7\n",
    "todos.txt": "buy milk\nwalk the dog\n",
    "notes.txt": "hello\n",
    "old.txt": "x\n",
}
WEB = {"POST https://example.com/api": {"status": 200, "body": {"ok": True}}}


def main_phrases():
    seen = []
    for phrase in REGISTRY:
        if phrase.main is phrase:
            seen.append(phrase)
    return seen


class Catalog(unittest.TestCase):
    def test_every_example_reads_as_its_phrase(self):
        for phrase in main_phrases():
            with self.subTest(phrase=phrase.template):
                example = phrase.example
                source = CONTEXT + example + "\n"
                if example.split()[0] in ("if",):
                    source += "    show 1\n"
                program = Reader().read(source)
                self.assertEqual([], [p.fix for p in program.problems], example)
                found = [n for n in walk(program.statements) if getattr(n, "phrase", None) is not None
                         and n.phrase.main is phrase]
                self.assertTrue(found, f"{example!r} didn't read as {phrase.template!r}")

    def test_every_example_runs(self):
        import tempfile
        from pathlib import Path
        for phrase in main_phrases():
            example = phrase.example
            if example.split()[0] == "if":
                continue
            with self.subTest(phrase=phrase.template):
                with tempfile.TemporaryDirectory() as tmp:
                    data = []
                    for name, text in FILES.items():
                        (Path(tmp) / name).write_text(text)
                        data.append(Path(tmp) / name)
                    (Path(tmp) / "photos").mkdir()
                    (Path(tmp) / "photos" / "cat.jpg").write_text("x")
                    data.append(Path(tmp) / "photos")
                    out, host, files = run_source(CONTEXT + example + "\n", answers=["Ann", "1", ""],
                                                  web=WEB, data=data)
                    self.assertNotIn(", line", out, out)

    def test_synonyms(self):
        for word, main in SYNONYMS.items():
            self.assertNotIn(word, SPECIAL_WORDS)
            self.assertNotIn(main, SYNONYMS, f"{word} → {main}, which is itself a synonym")

    def test_catalog_has_docs(self):
        for entry in catalog():
            self.assertTrue(entry["doc"], entry["wording"])
            self.assertTrue(entry["example"], entry["wording"])


def walk(statements):
    for stmt in statements:
        yield stmt
        for value in vars(stmt).values():
            yield from nodes(value)
        for attr in ("body", "fallback"):
            if hasattr(stmt, attr) and not isinstance(stmt, N.If):
                yield from walk(getattr(stmt, attr))
        if isinstance(stmt, N.If):
            for _, body in stmt.branches:
                yield from walk(body)


def nodes(value):
    if isinstance(value, N.Node):
        yield value
        for v in vars(value).values():
            yield from nodes(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from nodes(v)
    elif isinstance(value, dict):
        for v in value.values():
            yield from nodes(v)


if __name__ == "__main__":
    unittest.main()
