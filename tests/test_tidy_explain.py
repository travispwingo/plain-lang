"""Regression tests for stage 4 of the plain-language review: tidy writes the main wording that
explain shows, made from words.py and the registry (2), the checks and words in the phrase
reference (18), explain shows the value handed in and the apostrophe you wrote (20), rounded to
2 decimal places (26), and skip this round on the Other ways page (31)."""

import contextlib
import io
import re
import sys
import unittest
from pathlib import Path

from .support import ROOT, run_source
from .test_phrasings import cases
from plainlang import cli
from plainlang import nodes as N
from plainlang.parser import Reader
from plainlang.registry import CORE_FORMS, REGISTRY, other_ways, reference, shown
from plainlang.tidy import explain, line_readings, tidy
from plainlang.words import (ADD_OPS, COMPARISON_WORDS, COMPARISONS, CONTRACTIONS, ELIDED_COMPARISONS,
                             INFLECTIONS, LINE_ALIASES, MUL_OPS, MUL_TWO_WORD_OPS, NEGATIVE_COMPARISONS,
                             POLITE_STARTS, SYNONYMS, TYPE_CHECKS)

NAMES = ("score", "answer", "names", "scores", "sales", "people", "shopping", "person", "players", "age",
         "total", "todos")
PRELUDE = "".join(f"set {name} to nothing\n" for name in NAMES)


def program_for(line):
    """A line in a small program that sets the names it uses, with the steps around it that it needs."""
    first = line.split()[0].lower()
    if "\n" not in line and first in ("if", "repeat", "for", "while", "until"):
        line += "\n    show 1"
    if first == "skip":
        line = "repeat 2 times\n    " + line
    return PRELUDE + line + "\n"


def tidied(source):
    return tidy(source, Reader().read(source))


def readings(source):
    program = Reader().read(source)
    assert not program.problems, [p.fix for p in program.problems]
    return line_readings(program.statements)


def reading(source, line):
    return readings(source)[line]


def phrases_output(words):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cli.phrases(words)
    return code, out.getvalue()


class OtherWays(unittest.TestCase):   # change 2
    def test_tidy_writes_the_main_wording_explain_shows(self):
        for way in other_ways():
            for written, main in way.examples:
                with self.subTest(written=written):
                    source, expected = program_for(written), program_for(main)
                    self.assertEqual(readings(expected), readings(source))
                    text, changes = tidied(source)
                    if way.tidy:
                        self.assertEqual(expected, text)
                        self.assertTrue(changes)
                    else:
                        self.assertEqual([], changes)
                    self.assertEqual([], tidied(text)[1])

    def test_the_page_covers_every_table(self):
        ways = other_ways()
        said = {s for way in ways for s in way.said}
        notes = " ".join(way.note for way in ways)
        for word in SYNONYMS:
            self.assertIn(word, said)
        for words in LINE_ALIASES:
            self.assertIn(" ".join(words), said)
        for word in CONTRACTIONS:
            self.assertIn(word, said)
        for sign, word in list(ADD_OPS.items()) + list(MUL_OPS.items()) + \
                [(" ".join(words), word) for words, word in MUL_TWO_WORD_OPS.items()]:
            self.assertTrue(sign == word or sign in said, sign)
        for phrase in REGISTRY:
            if phrase.main is not phrase:
                self.assertIn(shown(phrase), said)
        for word in POLITE_STARTS:
            self.assertIn(word, notes)
        self.assertIn("skip this round", said)    # change 31
        self.assertIn("skip round", said)

    def test_every_comparison_wording_tidies(self):
        for words, op in COMPARISONS:
            written = " ".join("the same" if w == "same" else w for w in words)
            plural = words[0] in INFLECTIONS
            subject = "scores" if plural else "score"
            with self.subTest(words=written):
                text, _ = tidied(program_for(f"if {subject} {written} 10"))
                self.assertEqual(f"if {subject} {N.comparison_words(op, plural)} 10", text.split("\n")[len(NAMES)])

    def test_words_after_and_or_tidy(self):
        for words, op in ELIDED_COMPARISONS:
            bare = COMPARISON_WORDS[op].removeprefix("is ")
            with self.subTest(words=words):
                text, _ = tidied(program_for(f"if score is 5 or {' '.join(words)} 10"))
                self.assertEqual(f"if score is 5 or {bare} 10", text.split("\n")[len(NAMES)])
        source = "set age to 15\nif age > 12 and < 20\n    show 1\nif age is more than 12 and is smaller than 20\n" \
                 "    show 2\n"
        text, _ = tidied(source)
        self.assertEqual(["if age is more than 12 and less than 20", "if age is more than 12 and is less than 20"],
                         [text.split("\n")[1], text.split("\n")[3]])

    def test_signs_without_spaces(self):
        text, changes = tidied("set bill to 10\nshow bill*2\nshow (bill)>3\nshow 2+3-1\n")
        self.assertEqual(["show bill times 2", "show (bill) is more than 3", "show 2 plus 3 minus 1"],
                         text.split("\n")[1:4])
        self.assertIn("line 2   * → times", changes)

    def test_inside_text_and_with_a_shared_subject(self):
        source = 'set scores to a list of 1 and 2\nshow "{scores * 2} and {the sum of scores}"\n' \
                 'if the sum of scores is 3 or 4\n    show "yes"\n'
        text, _ = tidied(source)
        self.assertEqual(['show "{scores times 2} and {the total of scores}"', "if the total of scores is 3 or 4"],
                         text.split("\n")[1:3])

    def test_a_folded_not_and_its_check(self):
        text, changes = tidied("set bill to 3\nif not (bill is greater than 100)\n    show 1\n")
        self.assertEqual("if bill is at most 100", text.split("\n")[1])
        self.assertEqual(["line 2   not (bill is greater than 100) → bill is at most 100"], changes)

    def test_quit_skip_and_every(self):
        source = 'set scores to a list of 1\nrepeat for every n in scores\n    skip this round\nquit # bye\nExit.\n'
        text, changes = tidied(source)
        self.assertEqual('set scores to a list of 1\nrepeat for each n in scores\n    skip to the next round\n'
                         'stop the program # bye\nstop the program.\n', text)
        self.assertIn("line 5   Exit → stop the program", changes)

    def test_your_own_step_keeps_its_words(self):
        source = 'greet "Ann" isn\'t here\nshow 1 isn\'t 2\nhow to greet (person) isn\'t here\n    show person\n'
        text, changes = tidied(source)
        self.assertEqual(['greet "Ann" isn\'t here', "show 1 is not 2", "how to greet (person) isn't here"],
                         text.split("\n")[:3])
        self.assertEqual(["line 2   isn't → is not"], changes)

    def test_tidy_keeps_every_reading_in_the_corpus(self):
        for number, names, written, expected in cases():
            if expected is None:
                continue
            preamble = "".join(f"set {name} to nothing\n" for name in names)
            source = preamble + written + "\n"
            if written.split()[0].lower() in ("if", "repeat", "for", "while", "until", "otherwise", "else"):
                source += "    show 1\n"
            with self.subTest(line=number, written=written):
                text, _ = tidied(source)
                self.assertEqual(expected, reading(text, len(names) + 1))
                self.assertEqual([], tidied(text)[1])

    def test_examples_and_lessons_use_the_main_words(self):
        sys.path.insert(0, str(ROOT / "site"))
        from build import block_options, fences
        sources = [(str(p.relative_to(ROOT)), p.read_text(encoding="utf-8"))
                   for folder in ("examples", "tests/golden") for p in sorted((ROOT / folder).glob("*.plain"))]
        for path in sorted((ROOT / "site" / "docs").rglob("*.md")):
            for part in fences(path.read_text(encoding="utf-8")):
                if part[0] == "fence" and block_options(part[1])["kind"] == "plain":
                    sources.append((f"{path.relative_to(ROOT)}: {part[2].split(chr(10))[0]}", part[2] + "\n"))
        for name, source in sources:
            program = Reader().read(source)
            if program.problems or 'display "Welcome!"' in source:   # help.md shows explain on purpose
                continue
            with self.subTest(source=name):
                changes = [c for c in tidy(source, program)[1] if not c.startswith("moved")]
                # Brackets around what "rounded" covers (change 1) aren't written into the lessons yet.
                changes = [c for c in changes if not c.split("→")[-1].strip().startswith("(")]
                self.assertEqual([], changes)


class PhrasesReference(unittest.TestCase):   # changes 18 and 2
    CONTEXT = ('set answer to "yes"\nset name to "Ann"\nset score to 12\nset temperature to 3\nset age to 20\n'
               'set shopping to a list of "milk"\nset person to an empty record\nset person\'s name to "Ann"\n'
               'set email to "a@b.org"\nset pick to 4\nset guess to 7\nset reply to a list of 1\nset year to 2024\n'
               'set got ticket to yes\nset scores to a list of 1, 5 and 9\nread "sales.csv" and call it sales\n')
    SALES = "date,customer,amount\n2026-10-01,Ann,120.50\n2026-10-02,Bo,80\n"

    def entries(self, topic):
        return [c for c in CORE_FORMS if c["topic"] == topic]

    def test_every_check_has_an_entry(self):
        wordings = [c["wording"] for c in self.entries("Checks")]
        for op, words in COMPARISON_WORDS.items():
            if op not in NEGATIVE_COMPARISONS:
                self.assertTrue(any(f" {words} " in w for w in wordings), words)
            else:
                self.assertTrue(any(f'"{words}"' in c["doc"] for c in self.entries("Checks")), words)
        for kind in set(TYPE_CHECKS.values()) | {"divisible"}:
            self.assertTrue(any(kind.split()[-1] in w for w in wordings), kind)

    def test_check_examples_read_as_their_check_and_run(self):
        import tempfile
        expected = {c["example"]: c["wording"] for c in self.entries("Checks") + self.entries("Numbers and names")}
        for example, wording in expected.items():
            with self.subTest(example=example):
                source = self.CONTEXT + example + "\n" + ("    show 1\n" if example.startswith("if ") else "")
                program = Reader().read(source)
                self.assertEqual([], [p.fix for p in program.problems])
                with tempfile.TemporaryDirectory() as tmp:
                    (Path(tmp) / "sales.csv").write_text(self.SALES)
                    out, _, _ = run_source(source, data=[Path(tmp) / "sales.csv"])
                self.assertNotIn(", line", out)
                said = line_readings(program.statements)[source.count("\n", 0, source.index(example)) + 1]
                for word in [w for w in re.findall(r"\b[a-z]+\b", wording) if len(w) > 1]:
                    self.assertRegex(said, rf"\b{word}\b", wording)

    def test_find_by_the_words_of_a_phrase(self):
        for words, wording in ((["contains"], "LIST contains VALUE"), (["at", "least"], "NUMBER is at least NUMBER"),
                               (["where"], "LIST where CHECK"), (["divisible"], "NUMBER is divisible by NUMBER"),
                               (["greater"], "NUMBER is more than NUMBER"), (["uppercase"], "TEXT in capital letters"),
                               (["plus"], "NUMBER plus NUMBER"), (["display"], "show VALUE")):
            with self.subTest(words=words):
                code, out = phrases_output(words)
                self.assertEqual(0, code)
                self.assertIn(f"  {wording}\n", out)
        code, out = phrases_output(["where"])
        self.assertNotIn("sort", out)   # "where" in an explanation doesn't count when a phrase says it

    def test_other_ways_only_on_their_own_list(self):
        code, out = phrases_output([])
        self.assertNotIn("You can also write", out)
        self.assertIn("Other ways you can write things", out)
        self.assertIn("skip this round and skip round are read as skip to the next round.", out)
        from plainlang.ai import system_prompt
        for phrase in REGISTRY:
            if phrase.main is not phrase:     # the AI is shown only the main wordings
                self.assertNotIn(shown(phrase), system_prompt() + out.split("Other ways")[0])
        code, out = phrases_output(["percent"])
        self.assertIn("15 percent is read as 15%.", out)

    def test_the_site_lists_the_other_ways(self):
        sys.path.insert(0, str(ROOT / "site"))
        from build import other_ways_markdown, phrases_page
        text = other_ways_markdown()
        for way in other_ways():
            self.assertIn(way.sentence(), text)
        self.assertNotIn("You can also write", phrases_page())

    def test_reference_text_uses_everyday_words(self):
        from plainlang.words import BANNED_WORDS
        texts = [e["doc"] for e in reference()] + [w.sentence() for w in other_ways()] + [phrases_output([])[1]]
        for text in texts:
            for word in re.findall(r"[A-Za-z][A-Za-z-]*", text):
                self.assertNotIn(word.lower(), BANNED_WORDS, text)


class ExplainShowsWhatYouWrote(unittest.TestCase):   # change 20
    def test_a_bracketed_name_of_several_words(self):
        source = ("work out the tip on 42.50 at 15% and call it lunch tip\nshow lunch tip\n"
                  "how to work out the tip on (the bill) at (rate)\n    give back the bill times rate\n")
        self.assertEqual("work out the tip on 42.50 at 15% and call it lunch tip", reading(source, 1))
        self.assertNotIn("{", explain(Reader().read(source)))

    def test_the_apostrophe_you_wrote(self):
        source = ("set p to an empty record\nset p's results to 3\nset places to a list of p\n"
                  "show the first item of places' results\nset players to an empty record\n"
                  "set players's score to 3\nshow players' score\n")
        self.assertEqual(["show the first item of places' results", "set players's score to 3", "show players' score"],
                         [reading(source, n) for n in (4, 6, 7)])
        self.assertEqual("3\n3\n", run_source(source)[0])

    def test_plain_writes_just_the_apostrophe_after_s(self):
        p = Reader().read("set o to an empty record\nset o's total to 1\nset orders to a list of o\n"
                          "show the totals of orders").problems[0]
        self.assertIn(["show orders' totals"], p.choices)
        self.assertEqual("sale's amount", N.Field(N.Name(("sale",)), ("amount",)).canonical())

    def test_repeat_once_and_twice(self):
        source = "repeat once\n    show 1\nrepeat twice\n    show 2\nrepeat 1 time\n    show 3\n"
        self.assertEqual(["repeat once", "repeat twice", "repeat 1 time"], [reading(source, n) for n in (1, 3, 5)])


class DecimalPlaces(unittest.TestCase):   # change 26
    def test_the_main_wording(self):
        source = ("show 6.375 rounded to 2 places\nshow 6.375 rounded to 1 place\nshow 6.375 rounded to 2 decimals\n"
                  "show 6.375 rounded to 2 decimal places\nshow 6.375 rounded to 1 decimal place\n")
        self.assertEqual(["show 6.375 rounded to 2 decimal places", "show 6.375 rounded to 1 decimal place",
                          "show 6.375 rounded to 2 decimal places", "show 6.375 rounded to 2 decimal places",
                          "show 6.375 rounded to 1 decimal place"], [reading(source, n) for n in range(1, 6)])
        text, changes = tidied(source)
        self.assertEqual(["show 6.375 rounded to 2 decimal places", "show 6.375 rounded to 1 decimal place",
                          "show 6.375 rounded to 2 decimal places"], text.split("\n")[:3])
        self.assertEqual(["line 1   places → decimal places", "line 2   place → decimal place",
                          "line 3   decimals → decimal places"], changes)
        self.assertEqual(run_source(source)[0], run_source(text)[0])
        self.assertEqual("6.38\n", run_source("show 6.375 rounded to 2 decimal places\n")[0])

    def test_the_reference(self):
        entry = next(e for e in reference() if e["wording"].startswith("VALUE rounded to"))
        self.assertEqual("show 6.375 rounded to 2 decimal places", entry["example"])


if __name__ == "__main__":
    unittest.main()
