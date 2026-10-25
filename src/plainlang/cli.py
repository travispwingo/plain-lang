"""The plain command. All of its text is written by hand, in plain words."""

import errno
import os
import shutil
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

  --seed N      Make random numbers come out the same every time
  --version     Show which version of Plain you have

Learn more at plain-lang.dev"""

COMMANDS = {"run", "check", "fix", "tidy", "explain", "phrases", "help"}


def say(text="", err=False):
    stream = sys.stderr if err else sys.stdout
    try:
        stream.write(text + "\n")
        stream.flush()
    except OSError as error:
        # Whatever was reading the output (like "head" in plain phrases | head) has stopped, so
        # stop quietly, as a program's show does. Windows reports that as EINVAL.
        if not isinstance(error, BrokenPipeError) and error.errno != errno.EINVAL:
            raise
        os.dup2(os.open(os.devnull, os.O_WRONLY), stream.fileno())
        raise SystemExit(0) from None


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    options = {"seed": None}
    rest = []
    k = 0
    while k < len(args):
        arg = args[k]
        if arg == "--seed":
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
            if Path(command + ".plain").exists():
                say(f"Type plain run {command}.plain to run it. Plain has no command called \"{command}\".", err=True)
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
    return open_and_run(command, rest[1], options)


def open_and_run(command, name, options):
    """Read the file NAME and run, check, fix, tidy or explain it. The REPL's :run uses this too."""
    path = Path(name)
    if not path.exists():
        if path.suffix == "" and path.with_suffix(".plain").exists():
            say(f'Type plain {command} {name}.plain to {command} it. Plain files end in .plain.', err=True)
        else:
            say(f'Check the file name "{name}". There\'s no file with that name here.', err=True)
        return 2
    if path.is_dir():
        say(f'Type the name of a file, not a folder: "{name}" is a folder.', err=True)
        return 2
    try:
        text = path.read_bytes().decode("utf-8")      # a BOM stays, so fix and tidy keep it
        if text.lstrip().startswith("{\\rtf"):
            say(f'Save "{path.name}" as plain text, then try again. In TextEdit, choose Format > Make Plain Text.',
                err=True)
            return 2
    except UnicodeDecodeError:
        say(f'Save "{path.name}" as plain text (UTF-8), then try again.', err=True)
        return 2
    except OSError:
        say(f'Check that you\'re allowed to read "{path.name}". Plain can\'t open it.', err=True)
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
        from .fixer import cant_save, write_atomic
        backup = path.with_name(path.name + ".bak")
        try:
            shutil.copyfile(path, backup)         # the file exactly as it was
            write_atomic(path, new_text)
        except OSError:
            say(cant_save(path), err=True)
            return 1
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
            program, text = fix_file(path, text, program, interactive=interactive)
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


def phrases(words, again="plain phrases"):
    """List Plain's phrases, or the ones about WORDS. `again` is how to list them all."""
    from .registry import OFFERED_FIXES, find_phrases
    wanted = [x for w in words for x in w.lower().split()]
    offered, entries, ways = find_phrases(wanted)
    for word in offered:   # plain phrases timer: Plain writes "the stopwatch"
        say(f'Plain doesn\'t read "{word}". Write "{OFFERED_FIXES[word][0]}" instead.')
    if not entries and not ways:
        if offered:
            return 0
        say(f"Plain has no phrases about \"{' '.join(words)}\". Type {again} to see them all.")
        return 1
    if offered:
        say("")
    topic = None
    for entry in entries:
        if entry["topic"] != topic:
            if topic is not None:
                say("")
            topic = entry["topic"]
            say(topic)
        say(f"  {entry['wording']}")
        say(f"      {entry['doc']}")
        say(f"      Example: {entry['example']}")
    if entries:
        say("")
    if ways:
        say("Other ways you can write things")
        for tidy in (True, False):
            group = [w for w in ways if w.tidy == tidy]
            if not group:
                continue
            say("  plain tidy changes these to the main words:" if tidy else
                "  Plain also understands these, and plain tidy leaves them as you wrote them:")
            for way in group:
                say(f"    {way.sentence(code=lambda text: text).replace('`', '')}")
        say("")
    from .words import SPECIAL_WORDS
    if not wanted:
        say("Plain's special words (they can't be part of a name):")
        say("  " + " ".join(sorted(w for w in SPECIAL_WORDS)))
    return 0
