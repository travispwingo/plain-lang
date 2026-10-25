"""Plain explains itself in the same words everywhere (changes 5 and 22).

"column" is the word for a table and "field" the word for one record: messages, the phrase
reference and the lessons use the word that matches the kind of value."""

import re
import tempfile
import unittest
from pathlib import Path

from .support import ROOT, run_source
from plainlang.registry import reference

SALES = "date,customer,amount\n2026-10-01,Ann,120.50\n2026-10-02,Bo,80\n"
TWINS = "Unit Price,unit_price\n1,2\n"
LEARN = ROOT / "site" / "docs" / "learn"

# Lines whose message is about a table, and lines whose message is about one record. None of the
# lines says "field" or "column" itself, so the words come from the message.
ABOUT_A_TABLE = [
    "sort sales by price",
    "sort sales by price, largest first",
    "sort sales by price from Z to A",
    "show the different prices of sales",
    "show sales's price",
    "show the prices of sales",
    "show sales where price is more than 3",
    "show sales where its price is more than 3",
    "show the number of sales where price is empty",
    "show twins's unit price",
    "sort twins by unit price",
]
ABOUT_A_RECORD = [
    'set person to an empty record\nset person\'s name to "Ann"\nshow person\'s age',
    'set person to an empty record\nset person\'s name to "Ann"\nshow the age of person',
    "set person to an empty record\nshow person's age",
    "set person to the first item of sales\nshow person's price",
    "repeat for each sale in sales\n    show sale's price",
    "set person to the first item of twins\nshow person's unit price",
    "set person to an empty record\nif person has yes\n    show 1",
    'set n to 5\nif n has "age"\n    show 1',
]


def message(lines):
    """What Plain shows for these lines, after reading sales.csv and twins.csv."""
    source = 'read "sales.csv" and call it sales\nread "twins.csv" and call it twins\n' + lines + "\n"
    with tempfile.TemporaryDirectory() as tmp:
        for name, text in (("sales.csv", SALES), ("twins.csv", TWINS)):
            (Path(tmp) / name).write_text(text)
        out, _, _ = run_source(source, data=[Path(tmp) / "sales.csv", Path(tmp) / "twins.csv"])
    return out


def says(text, word):
    return re.search(rf"\b{word}s?\b", text, re.IGNORECASE) is not None


class ColumnsAndFields(unittest.TestCase):    # change 5
    def test_messages_about_a_table_say_column(self):
        for lines in ABOUT_A_TABLE:
            with self.subTest(line=lines):
                out = message(lines)
                self.assertIn(", line", out)
                self.assertTrue(says(out, "column"), out)
                self.assertFalse(says(out, "field"), out)

    def test_messages_about_a_record_say_field(self):
        for lines in ABOUT_A_RECORD:
            with self.subTest(line=lines):
                out = message(lines)
                self.assertIn(", line", out)
                self.assertTrue(says(out, "field"), out)
                self.assertFalse(says(out, "column"), out)

    def test_a_record_with_no_fields_yet(self):
        out = message("set person to an empty record\nshow person's age")
        self.assertIn('Set the field "age" before you use it.', out)
        self.assertIn("a record with no fields yet", out)

    def test_json_problems_count_characters(self):
        out, _, _ = run_source('read "https://example.com/data.json" and call it data\n',
                               web={"GET https://example.com/data.json": {
                                   "status": 200, "body": '{"a": 1,,}',
                                   "headers": {"Content-Type": "application/json"}}})
        self.assertIn("It went wrong at line 1, character 9.", out)
        self.assertFalse(says(out, "column"), out)

    def test_the_reference_uses_the_word_for_each_kind(self):
        for entry in reference():
            wording, doc = entry["wording"], entry["doc"]
            with self.subTest(wording=wording):
                if "TABLE" in wording:
                    self.assertNotIn("FIELD", wording)
                    self.assertFalse(says(doc, "field"), doc)
                if "COLUMN" in wording:
                    self.assertIn("TABLE", wording)
                if "RECORD" in wording:
                    self.assertNotIn("COLUMN", wording)
                    self.assertFalse(says(doc, "column"), doc)
        wordings = [e["wording"] for e in reference()]
        for wording in ("sort TABLE by COLUMN", "the different COLUMNs of TABLE", "the COLUMNs of TABLE",
                        "RECORD's FIELD"):
            self.assertIn(wording, wordings)

    def test_lesson_8_teaches_field_once(self):
        text = (LEARN / "08-spreadsheets.md").read_text(encoding="utf-8")
        self.assertIn("Each row is a **record**. Its value in one column is a **field**, like `sale's amount`.", text)
        prose = re.sub(r"```.*?```", "", text, flags=re.S)
        before = prose.split("Its value in one column is a **field**")[0]
        self.assertFalse(says(before, "field"), "Lesson 8 uses \"field\" before it teaches it.")

    def test_lessons_use_field_and_column(self):
        for path in sorted(LEARN.glob("*.md")):
            prose = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
            with self.subTest(page=path.name):
                self.assertNotRegex(prose, r"\bpieces? of (a|the) reply\b|\bpart of the reply\b|\bevery piece\b")
                if path.name < "08":     # "field" is taught in lesson 8
                    self.assertFalse(says(prose, "field"), path.name)


class ExplainInTheSyntaxWords(unittest.TestCase):    # change 22
    def test_reference_words(self):
        docs = {e["wording"]: e["doc"] for e in reference()}
        self.assertEqual("Ends your own step and gives back a value.", docs["give back VALUE"])
        self.assertIn("Items that are nothing, like blank cells, are skipped.", docs["the total of LIST"])
        self.assertIn("Items that are nothing, like blank cells, are skipped.", docs["the average of LIST"])
        self.assertIn("a list of A, B and C", docs)
        self.assertIn("read FILE or ADDRESS", docs)
        self.assertIn("repeat NUMBER times", docs)

    def test_two_meanings(self):
        out, _, _ = run_source("set a to yes\nset b to no\nset c to yes\nif a and b or c\n    show 1\n")
        self.assertIn("This line can mean two things", out)
        self.assertNotIn("two ways", out)

    def test_your_own_step(self):
        out, _, _ = run_source("how to count down from (n)\n    count down from n\ncount down from 3\n")
        self.assertIn("Your own step can use itself", out)
        out, _, _ = run_source("how to add (amount) to (account)\n    show amount\n")
        self.assertIn("Plain's own step", out)

    def test_characters_in_a_file(self):
        from plainlang.interpreter import data_problem
        try:
            b"\xff".decode("utf-8")
        except UnicodeDecodeError as error:
            self.assertEqual("Plain couldn't read the characters in this file.", data_problem(error).why)


class RemoveSideBySide(unittest.TestCase):    # change 33, kept as is
    def test_item_makes_the_difference(self):
        from plainlang.parser import Reader
        program = Reader().read("set scores to a list of 3, 1 and 2\nremove 3 from scores\nremove item 3 from scores\n")
        self.assertEqual([], program.problems)
        self.assertEqual(["remove {value} from {items}", "remove item {n} from {items}"],
                         [s.phrase.main.template for s in program.statements[1:]])
        out, _, _ = run_source("set scores to a list of 3, 1, 2 and 3\nremove 3 from scores\nshow scores\n"
                               "remove item 3 from scores\nshow scores\n")
        self.assertEqual("1, 2 and 3\n1 and 2\n", out)

    def test_the_docs_show_them_side_by_side(self):
        docs = {e["wording"]: e["doc"] for e in reference()}
        self.assertIn("remove item NUMBER from LIST", docs["remove VALUE from LIST"])
        self.assertIn("remove VALUE from LIST", docs["remove item NUMBER from LIST"])
        lesson = (LEARN / "05-lists.md").read_text(encoding="utf-8")
        self.assertIn('- `remove "milk" from shopping` takes out the first item that is "milk".\n'
                      "- `remove item 1 from shopping` takes out the item at position 1.", lesson)


class Examples(unittest.TestCase):    # change 23
    def test_idea_notes_are_not_try(self):
        for path in sorted((ROOT / "examples").glob("*.plain")):
            with self.subTest(example=path.name):
                self.assertNotIn("# Try:", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
