"""The plain command. All of its text is written by hand, in plain words."""

import os
import sys
from pathlib import Path

from . import __version__
from .problems import PLAIN_WENT_WRONG, Problem, layout, layout_all

HELP = """Plain: write steps in everyday English, then run them.

  plain                    Type Plain one line at a time
  plain run FILE           Check FILE, help you fix it, then run it  (also: plain FILE)
  plain check FILE         List anything Plain can't follow, without running it
  plain fix FILE           Go through each line Plain can't follow and fix it
  plain tidy FILE          Use Plain's main words and put the "how to" parts last
  plain explain FILE       Show how Plain reads each line
  plain phrases [WORDS]    List Plain's phrases, or find the ones about WORDS

  --no-ai       Don't ask Claude for ideas
  --seed N      Make random numbers come out the same every time
  --version     Show which version of Plain you have

Learn more at plain-lang.dev"""

COMMANDS = {"run", "check", "fix", "tidy", "explain", "phrases", "help"}


def say(text="", err=False):
    stream = sys.stderr if err else sys.stdout
    stream.write(text + "\n")
    stream.flush()


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    options = {"ai": os.environ.get("PLAIN_AI", "").lower() != "off", "seed": None}
    rest = []
    k = 0
    while k < len(args):
        arg = args[k]
        if arg == "--no-ai":
            options["ai"] = False
        elif arg == "--seed":
            if k + 1 >= len(args) or not args[k + 1].lstrip("-").isdigit():
                say("Type a whole number after --seed, like this: plain run game.plain --seed 7", err=True)
                return 2
            options["seed"] = int(args[k + 1])
            k += 1
        elif arg in ("--version", "-V"):
            say(f"Plain {__version__}")
            return 0
        elif arg in ("--help", "-h"):
            say(HELP)
            return 0
        elif arg.startswith("--"):
            say(f'Type plain help to see what you can do. Plain has no option called "{arg}".', err=True)
            return 2
        else:
            rest.append(arg)
        k += 1

    if not rest:
        from .repl import repl
        return repl(options)
    command = rest[0]
    if command not in COMMANDS:
        if command.endswith(".plain") or Path(command).exists():
            command, rest = "run", ["run"] + rest
        else:
            say(f'Type plain help to see what you can do. Plain has no command called "{command}".', err=True)
            return 2
    if command == "help":
        say(HELP)
        return 0
    if command == "phrases":
        return phrases(rest[1:])
    if len(rest) < 2:
        say(f"Type the name of the file to {command}, like this: plain {command} hello.plain", err=True)
        return 2
    path = Path(rest[1])
    if not path.exists():
        say(f'Check the file name "{rest[1]}". There\'s no file with that name here.', err=True)
        return 2
    if path.is_dir():
        say(f'Type the name of a file, not a folder: "{rest[1]}" is a folder.', err=True)
        return 2
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError:
        say(f'Save "{path.name}" as plain text (UTF-8), then try again.', err=True)
        return 2
    try:
        return run_command(command, path, text, options)
    except KeyboardInterrupt:
        say("Stopped.")
        return 130
    except Exception:
        if os.environ.get("PLAIN_DEBUG") == "1":
            raise
        say(PLAIN_WENT_WRONG, err=True)
        return 1


def run_command(command, path, text, options):
    from .parser import Reader
    program = Reader().read(text)
    name = path.name
    if command == "explain":
        from .tidy import explain
        say(explain(program))
        if program.problems:
            say("")
            say(layout_all(program.problems, name, program.source_lines), err=True)
            return 1
        return 0
    if command == "tidy":
        if program.problems:
            say(layout_all(program.problems, name, program.source_lines), err=True)
            say("Fix these first, then tidy again.", err=True)
            return 1
        from .tidy import tidy
        new_text, changes = tidy(text, program)
        if not changes:
            say(f"{name} is already tidy.")
            return 0
        backup = path.with_name(path.name + ".bak")
        backup.write_text(text, encoding="utf-8")
        write_atomic(path, new_text)
        say(f"Tidied {name}:")
        for change in changes:
            say(f"  {change}")
        say(f"Your file from before is in {backup.name}.")
        return 0
    if command == "check":
        if program.problems:
            say(layout_all(program.problems, name, program.source_lines), err=True)
            return 1
        say(f"Plain can follow every line of {name}.")
        return 0
    if program.problems:
        interactive = sys.stdin.isatty() and sys.stdout.isatty()
        if interactive or command == "fix":
            from .fixer import fix_file
            program, text = fix_file(path, text, program, options, interactive=interactive)
            if program is None:
                return 1
            if command == "fix":
                return 0
        else:
            say(layout_all(program.problems, name, program.source_lines), err=True)
            return 1
    elif command == "fix":
        say(f"Plain can follow every line of {name}. There's nothing to fix.")
        return 0
    return run_program(program, path, options)


def run_program(program, path, options):
    from .hosts import TerminalHost
    from .interpreter import Run
    host = TerminalHost(folder=path.resolve().parent, seed=options["seed"])
    try:
        Run(program, host).run()
    except Problem as problem:
        say(layout(problem, path.name, program.source_lines), err=True)
        return 1
    return 0


def write_atomic(path, text):
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text, encoding="utf-8", newline="")
    os.replace(temp, path)


def phrases(words):
    from .registry import CORE_FORMS, catalog
    entries = catalog()
    wanted = [w.lower() for w in words]

    def matches(text):
        return all(w in text.lower() for w in wanted)

    topics = {}
    for core in CORE_FORMS:
        if not wanted or matches(core["wording"] + " " + core["doc"]):
            topics.setdefault(core["topic"], []).append((core["wording"], core["doc"], core["example"], []))
    for entry in entries:
        text = " ".join([entry["wording"], entry["doc"]] + entry["also"])
        if not wanted or matches(text):
            topics.setdefault(entry["topic"], []).append(
                (entry["wording"], entry["doc"], entry["example"], entry["also"]))
    if not topics:
        say(f"Plain has no phrases about \"{' '.join(words)}\". Type plain phrases to see them all.")
        return 1
    for topic, items in topics.items():
        say(topic)
        for wording, doc, example, also in items:
            say(f"  {wording}")
            say(f"      {doc}")
            if also:
                say(f"      You can also write: {'; '.join(also)}")
            say(f"      Example: {example}")
        say("")
    from .words import SPECIAL_WORDS
    if not wanted:
        say("Plain's special words (they can't be part of a name):")
        say("  " + " ".join(sorted(w for w in SPECIAL_WORDS)))
    return 0
