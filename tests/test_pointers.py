"""Where a message points when Plain can't follow a line and has no fix of its own.

Every place a pointer names exists on plain-lang.dev (as site/build.py makes it), and the
plain phrases command next to it lists a phrase from the part of the page the link goes to.
"""

import re
import sys
import unittest
from types import SimpleNamespace

from .support import ROOT
from .test_phrasings import cases, read_in_context
from plainlang.parser import Reader
from plainlang.problems import layout
from plainlang.registry import find_phrases, reference
from plainlang.suggest import NAMES_LESSON, anchor, phrases_pointer

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


def corpus_messages(with_problem=False):
    """The messages for every line of the phrasing study that Plain must not read."""
    for number, names, written, reading in cases():
        if reading is None:
            program, _ = read_in_context(names, written)
            for problem in program.problems:
                message = layout(problem, "t.plain", program.source_lines)
                yield (written, message, problem) if with_problem else (written, message)


def pointer_for(source):
    """(place, words) of the pointer in the message for the last line of a program, or None."""
    program = Reader().read(source + "\n")
    last = source.count("\n") + 1
    found = [pointer for p in program.problems if p.line == last
             for pointer in pointers_in(layout(p, "t.plain", program.source_lines))]
    return found[0] if found else None


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
        for written, message, problem in corpus_messages(with_problem=True):
            if pointers_in(message):
                with self.subTest(line=written):
                    self.assertNotIn("\nTry this:", message)
                    self.assertNotIn("\nTry one of these:", message)
                    self.assertEqual([], problem.ideas, "plain fix offers an idea for this one")

    def test_no_pointer_when_plain_fix_has_an_idea(self):
        program = Reader().read("loop 5 times\n    show 1\n")
        self.assertEqual(["repeat 3 times"], program.problems[0].ideas)
        self.assertIsNone(program.problems[0].docs)


class ChoosingThePlace(unittest.TestCase):
    def test_the_link_goes_with_the_example_shown(self):
        # "times" alone fits "NUMBER times NUMBER", but the example is "repeat 3 times".
        reader = SimpleNamespace(r=SimpleNamespace(quiet=False), names=set())
        pointer = phrases_pointer(reader, "loop 5 times", ["repeat 3 times", "repeat for each item in todos"])
        self.assertEqual("Find a phrase that fits at plain-lang.dev/phrases/#core-steps", pointer["docs"])
        self.assertEqual("times", pointer["look_up"])

    def test_two_words_of_a_phrase_in_your_line_beat_the_example(self):
        # The example "start the stopwatch" shares only "start" with this line.
        self.assertEqual(("/phrases/#checks", " start"), pointer_for('set colors to "red"\nif colors start with "a"'))

    def test_a_word_only_in_an_explanation_names_no_phrase(self):
        # "score" is only in the explanation of RECORD's FIELD ("players' score").
        self.assertEqual(("/phrases/#checks", " bigger"), pointer_for("score gets bigger"))

    def test_your_word_comes_before_the_steps_that_hold_phrases(self):
        self.assertEqual(("/phrases/#checks", " bigger"), pointer_for("set score to 5\nif score bigger than 3"))

    def test_a_name_that_stands_for_a_phrase_word(self):
        self.assertEqual(("/phrases/#numbers-and-text", " letters"),
                         pointer_for('set story to "hi"\nshow story in big letters'))
        self.assertEqual(("/phrases/#lists-and-tables", " sort"),
                         pointer_for('set names to a list of "a" and "b"\nsort names backwards'))

    def test_a_name_nothing_sets_points_to_lesson_2(self):
        for source in ("set score to 1\nshow score plus bonus", "set total to the number of guests",
                       'ask "Which city?" and call it city\nshow the weather in city'):
            with self.subTest(source=source):
                self.assertEqual((NAMES_LESSON, None), pointer_for(source))


if __name__ == "__main__":
    unittest.main()
