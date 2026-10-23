"""Running .plain files in tests: scripted answers, web fixtures, a fake clock, a temp folder."""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from plainlang.hosts import TestHost  # noqa: E402
from plainlang.interpreter import Run  # noqa: E402
from plainlang.parser import Reader  # noqa: E402
from plainlang.problems import Problem, layout, layout_all  # noqa: E402

SIDECARS = {".plain", ".in", ".out", ".args", ".json", ".err", ".bak"}
UPDATE = os.environ.get("PLAIN_UPDATE") == "1"


def sidecar(path, ending):
    return path.with_name(path.stem + ending)


def run_source(source, folder=None, answers=(), seed=0, web=None, name="program.plain", data=()):
    """Read and run a program in a temp folder. Returns (output text, host, folder files)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for item in data:
            if item.is_dir():
                shutil.copytree(item, tmp / item.name)
            else:
                shutil.copy(item, tmp / item.name)
        host = TestHost(tmp, answers=answers, seed=seed, web=web)
        program = Reader().read(source)
        if program.problems:
            out = layout_all(program.problems, name, program.source_lines) + "\n"
        else:
            try:
                Run(program, host).run()
                out = host.output()
            except Problem as problem:
                out = host.output() + layout(problem, name, program.source_lines) + "\n"
        files = {p.name: p.read_text(encoding="utf-8") for p in tmp.iterdir() if p.is_file()}
        return out, host, files


def run_golden(path):
    path = Path(path)
    answers = sidecar(path, ".in").read_text(encoding="utf-8").split("\n")[:-1] \
        if sidecar(path, ".in").exists() else []
    seed = 0
    if sidecar(path, ".args").exists():
        words = sidecar(path, ".args").read_text().split()
        if "--seed" in words:
            seed = int(words[words.index("--seed") + 1])
    web = json.loads(sidecar(path, ".web.json").read_text()) if path.with_name(path.stem + ".web.json").exists() else None
    data = [p for p in path.parent.iterdir()
            if p.is_file() and p.suffix not in SIDECARS and not p.name.endswith(".web.json")]
    out, host, files = run_source(path.read_text(encoding="utf-8"), answers=answers, seed=seed,
                                  web=web, name=path.name, data=data)
    return out
