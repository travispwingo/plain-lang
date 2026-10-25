"""Where a message points when Plain can't follow a line and has no fix of its own.

Every place a pointer names exists on plain-lang.dev (as site/build.py makes it), and the
plain phrases command next to it lists a phrase from the part of the page the link goes to.
"""

import re
import sys
import unittest

from .support import ROOT
from .test_phrasings import cases, read_in_context
from plainlang.problems import layout
from plainlang.registry import find_phrases, reference
from plainlang.suggest import NAMES_LESSON, anchor

sys.path.insert(0, str(ROOT / "site"))
import build  # noqa: E402

POINTER = re.compile(r"^(?:Find a phrase that fits|Learn how to set a name) at plain-lang\.dev(?P<place>/\S*?)"
                     r"(?:, or type: plain phrases(?P<words>(?: \S+)*))?$", re.M)


def site_places():
    """Every page and #place on it that the site build makes, read from the pages themselves."""
    pages = {"/phrases/": build.phrases_page()} | {url: body for url, _, body in build.doc_pages()[0]}
    places = set(pages)
    for url, text in pages.items():
        places |= {f"{url}#{name}" for name in re.findall(r'\bid="([^"]+)"', text)}
    return places


def pointers_in(text):
    return [(m["place"], m["words"]) for m in POINTER.finditer(text)]


def corpus_messages():
    """The messages for every line of the phrasing study that Plain must not read."""
    for number, names, written, reading in cases():
        if reading is None:
            program, _ = read_in_context(names, written)
            for problem in program.problems:
                yield written, layout(problem, "t.plain", program.source_lines)


class Pointers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.places = site_places()
        cls.topics = {anchor(e["topic"]): e["topic"] for e in reference()}

    def assertPointerWorks(self, place, words):
        self.assertIn(place, self.places, "This place isn't on the site.")
        if words is None:
            return
        if not words:
            self.assertEqual("/phrases/", place, "plain phrases on its own lists every phrase, so link to all of them.")
            return
        _, entries, _ = find_phrases(words.split())
        topic = self.topics[place.partition("#")[2]]
        self.assertIn(topic, [e["topic"] for e in entries], f"plain phrases{words} doesn't list a phrase from {place}")

    def test_every_place_a_pointer_can_name_is_on_the_site(self):
        for place in ["/phrases/", NAMES_LESSON] + [f"/phrases/#{a}" for a in self.topics]:
            with self.subTest(place=place):
                self.assertIn(place, self.places)

    def test_the_messages_in_the_tests_and_the_docs(self):
        texts = [p.read_text(encoding="utf-8") for p in sorted((ROOT / "tests" / "problems").glob("*.err"))]
        texts += [p.read_text(encoding="utf-8") for p in sorted((ROOT / "site" / "docs").rglob("*.md"))]
        found = [pointer for text in texts for pointer in pointers_in(text)]
        self.assertGreaterEqual(len(found), 5)
        for place, words in found:
            with self.subTest(place=place, words=words):
                self.assertPointerWorks(place, words)

    def test_the_lines_people_write(self):
        count = 0
        for written, message in corpus_messages():
            for place, words in pointers_in(message):
                count += 1
                with self.subTest(line=written):
                    self.assertPointerWorks(place, words)
        self.assertGreater(count, 0)

    def test_a_pointer_is_the_last_line_of_its_message(self):
        for written, message in corpus_messages():
            lines = message.split("\n")
            with self.subTest(line=written):
                self.assertTrue(all(not POINTER.match(line) for line in lines[:-1]), message)

    def test_only_messages_without_a_fix_point_to_the_docs(self):
        for written, message in corpus_messages():
            if pointers_in(message):
                with self.subTest(line=written):
                    self.assertNotIn("\nTry this:", message)
                    self.assertNotIn("\nTry one of these:", message)


if __name__ == "__main__":
    unittest.main()
