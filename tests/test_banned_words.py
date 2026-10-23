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
