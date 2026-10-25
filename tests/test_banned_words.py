"""No banned word appears in anything Plain shows you, and only the hosts touch the outside world."""

import ast
import re
import unittest

from .support import ROOT
from plainlang.words import BANNED_WORDS

SRC = ROOT / "src" / "plainlang"
SHOWN_CALLS = {"Problem", "say"}
UI_MODULES = {"cli.py", "repl.py", "fixer.py", "ai.py", "browser.py", "hosts.py"}


def shown_strings(path):
    """String pieces that end up in front of a person: messages, help text, phrase docs."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []

    def strings(node):
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                out.append((child.lineno, child.value))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            if name in SHOWN_CALLS:
                for arg in list(node.args) + [k.value for k in node.keywords]:
                    strings(arg)
        if isinstance(node, ast.FunctionDef) and any(
                isinstance(d, ast.Call) and getattr(d.func, "id", "") in ("step", "value")
                for d in node.decorator_list):
            doc = ast.get_docstring(node)
            if doc:
                out.append((node.lineno, doc))
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") in ("HELP", "PLAIN_WENT_WRONG")
                                                for t in node.targets):
            strings(node.value)
    return out


class BannedWords(unittest.TestCase):
    def test_messages_use_everyday_words(self):
        for path in sorted(SRC.rglob("*.py")):
            if path.name == "words.py":
                continue
            for lineno, text in shown_strings(path):
                for word in re.findall(r"[A-Za-z][A-Za-z-]*", text):
                    with self.subTest(file=path.name, line=lineno):
                        self.assertNotIn(word.lower(), BANNED_WORDS, text)


class MainWords(unittest.TestCase):
    """Explanations use Plain's own main words (change 22): never a word that plain tidy changes, a
    retired wording, or a placeholder outside the one-per-kind list."""

    RETIRED = ["hands back", "hand back", "how-to", "how-tos", "the letters of", "is over", "if it fails",
               "timer", "true", "false", "return", "fetch", "mean", "a new record", "in capitals"]
    PLACEHOLDERS = {"VALUE", "NUMBER", "TEXT", "LIST", "TABLE", "COLUMN", "COLUMNs", "FIELD", "RECORD", "FILE",
                    "ADDRESS", "FOLDER", "QUESTION", "PAGE", "NAME", "CHECK", "STEP", "WORDS"}

    def explanations(self):
        from plainlang.registry import reference
        return reference()

    def test_explanations_use_main_words(self):
        from plainlang.words import LINE_ALIASES, SYNONYMS
        other = set(SYNONYMS) | {w for words in LINE_ALIASES for w in words}
        for entry in self.explanations():
            text = f'{entry["doc"]} {entry["example"]}'
            with self.subTest(wording=entry["wording"]):
                for word in re.findall(r"[A-Za-z][A-Za-z-]*", text):
                    stem = re.sub(r"(es|s|d|ed|ing)$", "", word.lower())
                    self.assertFalse({word.lower(), stem, stem + "e"} & other, f"{word!r} in {text!r}")
                for retired in self.RETIRED:
                    self.assertNotRegex(text.lower(), rf"\b{re.escape(retired)}\b")

    def test_one_placeholder_for_each_kind(self):
        for entry in self.explanations():
            with self.subTest(wording=entry["wording"]):
                for word in re.findall(r"[A-Z][A-Za-z]+", entry["wording"]):
                    if re.match(r"[A-Z]{2}", word):
                        self.assertIn(word, self.PLACEHOLDERS)
                self.assertNotRegex(entry["wording"] + " " + entry["doc"], r"\bN\b")    # NUMBER, not N

    def test_messages_say_your_own_step(self):
        """Messages call a "how to" step "your own step", never "a how-to" (change 22)."""
        for path in sorted(SRC.rglob("*.py")):
            for lineno, text in shown_strings(path):
                with self.subTest(file=path.name, line=lineno):
                    self.assertNotRegex(text.lower(), r"\bhow-tos?\b")
                    self.assertNotIn("can read this line two ways", text)


class SiteWords(unittest.TestCase):
    """The website's pages follow the same rule (design section 0)."""

    def test_site_pages(self):
        docs = ROOT / "site" / "docs"
        for path in sorted(docs.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            prose = re.sub(r"```.*?```", "", text, flags=re.S)      # code isn't prose
            prose = re.sub(r"`[^`]*`", "", prose)
            for word in re.findall(r"[A-Za-z][A-Za-z-]*", prose):
                with self.subTest(page=str(path.relative_to(ROOT)), word=word):
                    self.assertNotIn(word.lower(), BANNED_WORDS)


class OnlyHostsTouchTheWorld(unittest.TestCase):
    def test_io_guard(self):
        pattern = re.compile(r"\b(print\(|input\(|time\.sleep|urllib\.request|urlopen)")
        for path in sorted(SRC.rglob("*.py")):
            if path.name in UI_MODULES:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                with self.subTest(file=path.name, line=number):
                    self.assertIsNone(pattern.search(line), line)


if __name__ == "__main__":
    unittest.main()
