"""Every Plain example on the website runs (or is checked) exactly as the page shows it.

In site/docs/**/*.md, a ```plain block must be followed by
  - an optional ```answers block (what you type), then a ```output block (what it shows), or
  - a ```problem block (the exact message), or
it must carry the word "fragment" (```plain fragment): then it only has to pass plain check.
Options on the ```plain line: files=a.csv,b.txt (from site/docs/files/) and web=name
(a fixture from site/docs/fixtures/name.json).
"""

import json
import sys
import unittest

from .support import ROOT, run_source
from plainlang.parser import Reader

DOCS = ROOT / "site" / "docs"
sys.path.insert(0, str(ROOT / "site"))
from build import block_options, fences  # noqa: E402


def doc_examples():
    for path in sorted(DOCS.rglob("*.md")):
        parts = [p for p in fences(path.read_text(encoding="utf-8")) if p[0] == "fence"]
        k = 0
        while k < len(parts):
            _, info, body = parts[k]
            options = block_options(info)
            if options["kind"] != "plain":
                k += 1
                continue
            example = {"path": path, "code": body + "\n", "options": options,
                       "answers": None, "output": None, "problem": None}
            m = k + 1
            while m < len(parts) and block_options(parts[m][1])["kind"] in ("answers", "output", "problem"):
                example[block_options(parts[m][1])["kind"]] = parts[m][2] + "\n"
                m += 1
            yield example
            k = m


class DocExamples(unittest.TestCase):
    def test_every_example(self):
        count = 0
        for ex in doc_examples():
            count += 1
            rel = ex["path"].relative_to(ROOT)
            first = ex["code"].strip().split("\n")[0]
            with self.subTest(page=str(rel), example=first):
                options = ex["options"]
                if options.get("fragment"):
                    program = Reader().read(ex["code"])
                    self.assertEqual([], [p.fix for p in program.problems])
                    continue
                self.assertTrue(ex["output"] is not None or ex["problem"] is not None,
                                "Add an ```output or ```problem block after this example, or mark it fragment.")
                files = [DOCS / "files" / f for f in str(options.get("files", "")).split(",") if f]
                web = None
                if options.get("web"):
                    web = json.loads((DOCS / "fixtures" / f"{options['web']}.json").read_text())
                answers = ex["answers"].split("\n")[:-1] if ex["answers"] else []
                out, host, _ = run_source(ex["code"], answers=answers, web=web, data=files,
                                          name="your program", seed=int(options.get("seed", 0)))
                expected = ex["output"] if ex["output"] is not None else ex["problem"]
                self.assertEqual(expected.rstrip("\n"), out.rstrip("\n"))
        self.assertGreater(count, 0, "The website has no Plain examples yet.")


if __name__ == "__main__":
    unittest.main()
