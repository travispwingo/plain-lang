"""Messages in the playground (src/plainlang/browser.py). The playground has no command to type,
so a message that points to the docs shows only the plain-lang.dev link.

Checking a program never calls the browser, so under CPython an empty stand-in for Pyodide's js
module is enough. node site/tests/pyodide.mjs runs these with the real one.
"""

import json
import sys
import types
import unittest
from unittest import mock

from .support import ROOT  # noqa: F401  (puts src on the path)

try:
    import js  # noqa: F401  (only exists under Pyodide)
    from plainlang import browser
except ImportError:
    with mock.patch.dict(sys.modules, {"js": types.ModuleType("js")}):
        from plainlang import browser


def messages(source):
    return [p["text"] for p in json.loads(browser.check_in_page(source))]


class PlaygroundMessages(unittest.TestCase):
    def test_a_pointer_is_only_the_link(self):
        for source, last in (
                ('set names to a list of "Bea" and "Al"\nsort names by by\n',
                 "Find a phrase that fits at plain-lang.dev/phrases/#lists-and-tables"),
                ("draw a circle\n", "Find a phrase that fits at plain-lang.dev/phrases/"),
                ("show the weather in paris\n", "Learn how to set a name at plain-lang.dev/learn/02-names/")):
            with self.subTest(source=source):
                [text] = messages(source)
                self.assertEqual(last, text.split("\n")[-1])
                self.assertNotIn("plain phrases", text)
                self.assertNotIn("type:", text)

    def test_a_message_with_a_fix_has_no_pointer(self):
        [text] = messages("show Hello there\n")
        self.assertNotIn("plain-lang.dev", text)
        self.assertTrue(text.endswith("you haven't set one."), text)


if __name__ == "__main__":
    unittest.main()
