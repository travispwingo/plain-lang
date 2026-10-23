"""Helpful messages for lines Plain can't follow, with fixes Plain has checked work."""

import difflib
import re

from .problems import Problem
from .registry import REGISTRY, Slot, Word
from .words import (COMPARISONS, CORE_STARTS, ELIDED_COMPARISONS, SPECIAL_WORDS, SYNONYMS,
                    TYPE_CHECKS)

CONFUSABLES = {"then": "than", "than": "then", "were": "where", "weather": "whether"}

STOP_WORDS = {"the", "a", "an", "of", "to", "up", "in", "on", "it", "is", "and", "or", "my",
              "for", "with", "by", "from", "at", "all", "each", "every", "this", "that"}

# Words that start lines in other languages. A line that starts with one isn't setting a name.
HABIT_WORDS = {"elif", "else", "print", "puts", "echo", "say", "write", "console", "open",
               "download", "get", "load"}

# Words a line can lose without changing what it means.
FILLER_WORDS = {"please", "just", "also", "really", "very", "now", "then", "so", "do", "does",
                "did", "actually", "simply"}

# Comparing words that need "than" after them.
NEEDS_THAN = {"more", "less", "bigger", "greater", "larger", "higher", "smaller", "fewer", "lower"}

SHOW_WORDS = {"show", "display", "print", "say"}

COMPARISON_FIRST = {words[0] for words, _ in COMPARISONS}

TYPE_WORDS = {words[0] for words in TYPE_CHECKS} | {"divisible"}

# Everyday verbs people start lines with, and the Plain step that does that job.
VERB_HINTS = {
    "count": ["set count to the number of sales"],
    "print": ['show "Hello"'], "say": ['show "Hello"'], "write": ['show "Hello"', 'save notes to "notes.txt"'],
    "display": ['show "Hello"'], "output": ['show "Hello"'], "tell": ['show "Hello"'],
    "make": ['set colors to a list of "red" and "blue"', "set total to 0"],
    "create": ['set colors to a list of "red" and "blue"', "set person to a new record"],
    "let": ["set total to 0"], "store": ['save todos to "todos.txt"', "set total to 0"],
    "remember": ["set total to 0"], "put": ["set total to 0", "add task to todos"],
    "get": ['read "https://example.com" and call it page', 'ask "Your name?" and call it name'],
    "open": ['read "notes.txt" and call it notes'], "download": ['read "https://example.com" and call it page'],
    "load": ['read "notes.txt" and call it notes'], "input": ['ask "Your name?" and call it name'],
    "type": ['ask "Your name?" and call it name'], "prompt": ['ask "Your name?" and call it name'],
    "loop": ["repeat 3 times", "repeat for each item in todos"], "go": ["repeat for each item in todos"],
    "sum": ["set total to the total of prices"], "total": ["set total to the total of prices"],
    "calculate": ["set total to price times 2"], "compute": ["set total to price times 2"],
    "work": ["set total to price times 2"], "increase": ["add 1 to score"], "decrease": ["subtract 1 from score"],
    "delete": ['remove "milk" from shopping'], "check": ["if score is more than 10"],
    "sleep": ["wait 2 seconds"], "post": ['send message to "https://example.com/api" and call it reply'],
    "return": ["give back total"], "call": ["work out the tip on 20 at 15% and call it tip"],
}

# Habits from other languages, and everyday wordings Plain writes another way:
# (pattern on the whole line, replacement, why). Line-start habits come before the ones
# that read the start of the line as a name, so "elif x is 2" never becomes "set elif x to 2".
def habit_problem(reader, line):
    """A fix for a habit from another language, checked to read cleanly in place."""
    raw = line.raw
    stripped = raw.strip()
    indent = raw[:len(raw) - len(raw.lstrip())]
    toks = reader.t
    col, end = (toks[0].col, toks[-1].end) if toks else (len(indent), len(raw.rstrip()))
    body = re.sub(r"^(?:please|now|then|next|first|finally)\s+", "", stripped, flags=re.IGNORECASE)
    for pattern, replacement, why in HABITS:
        m = re.match(pattern, body, flags=re.IGNORECASE)
        if not m or ("name" in m.groupdict() and m.group("name") and not could_be_name(reader, m.group("name"))):
            continue
        fixed = quote_singles(replacement(m) if callable(replacement) else m.expand(replacement))
        named = tuple(m.group("name").lower().split()) if "name" in m.groupdict() and m.group("name") else None
        ok = reads_cleanly(reader, line, indent + fixed) or \
            (named is not None and reads_with_name(reader, line, indent + fixed, named)) or \
            (fixed.startswith("how to ") and header_reads(reader, line, indent + fixed))
        if ok:
            return Problem(f'Write "{fixed}" instead.', why, line=line.number, col=col, end=end,
                           try_lines=[indent + fixed], ideas=[indent + fixed])
    return None


def header_reads(reader, line, text):
    """Does this read as the first line of a how-to?"""
    from .parser import make_view
    from .source import Line, tokenize
    try:
        tokens, _, _ = tokenize(text, line_no=line.number)
    except Problem:
        return False
    problems = []
    candidate = Line(line.number, line.indent, text, tokens)
    return reader.r.read_howto_header(candidate, problems) is not None and not problems


def python_range(m):
    """for i in range(10): counts 0 to 9."""
    a, b = (int(m["a"]), int(m["b"])) if m["b"] else (0, int(m["a"]))
    return f"repeat for each {m['name']} from {a} to {b - 1}"


def python_def(m):
    """def greet(name, place): becomes how to greet (name) and (place)."""
    names = [n.strip() for n in m["args"].split(",") if n.strip()]
    words = m["f"].replace("_", " ")
    return "how to " + words + "".join((" " if k == 0 else " and ") + f"({n})" for k, n in enumerate(names))


def dotted_field(m):
    return f"{m['a']}{m['o']}'s {m['f'].replace('_', ' ')}{m['b']}"


HABITS = [
    (r"^(?:var|let|const|my|local)\s+(?P<name>[A-Za-z][\w ]*?)\s*=\s*(?P<v>[^=].*?);?$", r"set \g<name> to \g<v>",
     '"var", "let" and "const" come from other languages. In Plain you keep a value with "set".'),
    (r"^set\s+(?P<name>[A-Za-z][\w ]*?)\s*=\s*(?P<v>[^=].*)$", r"set \g<name> to \g<v>",
     'A set step uses "to", not "=": set NAME to VALUE.'),
    (r"^(?P<name>[A-Za-z][\w ]*?)\s*\+\+;?$", r"add 1 to \g<name>",
     '"++" comes from other languages. In Plain you add to a value with "add".'),
    (r"^(?P<name>[A-Za-z][\w ]*?)\s*--;?$", r"subtract 1 from \g<name>",
     '"--" comes from other languages. In Plain you take away with "subtract".'),
    (r"^for\s+(?P<name>[A-Za-z]\w*)\s+in\s+range\(\s*(?P<a>\d+)\s*(?:,\s*(?P<b>\d+)\s*)?\)\s*:?$", python_range,
     '"range" comes from other languages. In Plain you count with: repeat for each NAME from A to B.'),
    (r"^for\s+(?P<name>[A-Za-z]\w*)\s+in\s+(?P<v>[A-Za-z][\w ]*?)\s*:$", r"repeat for each \g<name> in \g<v>",
     'Plain says "repeat for each NAME in LIST" to go through a list.'),
    (r"^def\s+(?P<f>[A-Za-z]\w*)\s*\((?P<args>[^)]*)\)\s*:?$", python_def,
     '"def" comes from other languages. In Plain you make a step of your own with "how to".'),
    (r"^(?P<a>if|while|otherwise if|else if)\s+(?P<c>.+?)\s*\{$", r"\g<a> \g<c>",
     'Plain shows which steps belong together by moving them to the right, so it doesn\'t use { }.'),
    (r"^(?P<a>.*?)(?<!\band)\s+call (?P<w>it|them)\s+(?P<n>.+)$", r"\g<a> and call \g<w> \g<n>",
     'Plain says "and call it" to keep what a step gives back.'),
    (r"^wait\s+(?P<n>[\d.]+)\s*(?:s|sec|secs|second|seconds)?\.?$", r"wait \g<n> seconds",
     'Say what to wait for: seconds or minutes.'),
    (r"^(?P<a>[^\"“]*?)\b(?:None|nil|null|undefined|NULL)\b(?P<b>.*)$", r"\g<a>nothing\g<b>",
     'Plain says "nothing" when there\'s no value.'),
    (r"^(?P<a>[^\"“]*?)\b(?P<o>[A-Za-z]\w*)\.(?P<f>(?!(?:csv|txt|json|md|html|tsv|log|plain)\b)[A-Za-z]\w*)\b"
     r"(?P<b>(?!\s*\().*)$", dotted_field,
     '"." comes from other languages. In Plain you write a field like this: sale\'s amount.'),
    (r"^elif\b(?P<v>.*)$", r"otherwise if\g<v>", 'Plain says "otherwise if".'),
    (r"^else\s+if\b(?P<v>.*)$", r"otherwise if\g<v>", 'Plain says "otherwise if".'),
    (r"^break$", "stop repeating", '"break" comes from other languages. Plain says "stop repeating".'),
    (r"^continue$", "skip to the next round",
     '"continue" comes from other languages. Plain says "skip to the next round".'),
    (r"^//\s*(?P<v>.*)$", r"# \g<v>", "Notes in Plain start with #."),
    (r"^(?P<a>.*\S)\s*//(?!\s*\d)\s*(?P<v>.*)$", r"\g<a>  # \g<v>", "Notes in Plain start with #."),
    (r"^(?:print|console\.log|puts|echo|say)\s*\((?P<v>.*)\)\s*;?$", r"show \g<v>",
     'Plain uses "show" to put words on the screen.'),
    (r"^(?:print|puts|echo|say|write)\s+(?P<v>[^()].*)$", r"show \g<v>",
     'Plain uses "show" to put words on the screen. To put words in a file, write: save ... to "notes.txt"'),
    (r"^(?:open|download|get|load)\s+(?P<v>.+)$", r"read \g<v>",
     'Plain uses "read" for files and web pages.'),
    (r"^(?P<name>[A-Za-z][\w ]*?)\.(?:append|push)\(\s*(?P<v>.+?)\s*\)\s*;?$", r"add \g<v> to \g<name>",
     '".append" comes from other languages. In Plain you put an item at the end of a list with "add".'),
    (r"^(?P<name>[A-Za-z][\w ]*?)\.(?:append|push)\(\s*(?P<v>[A-Za-z][\w ]*)\s*\)\s*;?$", r'add "\g<v>" to \g<name>',
     '".append" comes from other languages. In Plain you put an item at the end of a list with "add".'),
    (r"^(?P<name>[A-Za-z][\w ]*?)\s*\+=\s*(?P<v>.+)$", r"add \g<v> to \g<name>",
     '"+=" comes from other languages. In Plain you add to a value with "add".'),
    (r"^(?P<name>[A-Za-z][\w ]*?)\s*-=\s*(?P<v>.+)$", r"subtract \g<v> from \g<name>",
     '"-=" comes from other languages. In Plain you take away with "subtract".'),
    (r"^(?P<name>[A-Za-z][\w ]*?)\s*=\s*(?P<v>[^=].*)$", r"set \g<name> to \g<v>",
     'In Plain, "=" only compares two values. To keep a value, write "set".'),
    (r"^(?P<name>[A-Za-z][\w ]*?) is (?P<v>.+)$", r"set \g<name> to \g<v>",
     'In Plain, "is" only compares two values, as in: if score is 0'),
    (r"^(?P<a>.*\bis) (?P<v>.+?) or (?:more|over|above|higher|greater|bigger|larger|older)(?P<b>\s*:?)$",
     r"\g<a> at least \g<v>\g<b>",
     'Plain says "is at least 18" for "18 or more", and "is at most 18" for "18 or less".'),
    (r"^(?P<a>.*\bis) (?P<v>.+?) or (?:less|fewer|under|below|lower|smaller|younger)(?P<b>\s*:?)$",
     r"\g<a> at most \g<v>\g<b>",
     'Plain says "is at least 18" for "18 or more", and "is at most 18" for "18 or less".'),
    (r"^(?P<a>.*)\bis over\b(?P<b>.+)$", r"\g<a>is more than\g<b>",
     'In everyday English "is over" means "has finished", so Plain uses "is more than".'),
]


def explain_unreadable(reader, i, j, line, check=False):
    """The best problem for a span Plain couldn't read: a habit fix, an unknown name, a
    checked repair, or the closest phrases."""
    toks = reader.t[i:j]
    piece = getattr(line, "piece", None)
    if piece is not None:
        line = line.whole
    if not toks:
        return Problem("Finish this line.", None, line=getattr(line, "number", None))
    col, end = toks[0].col, toks[-1].end
    raw = line.raw if line is not None else ""
    stripped = raw.strip()
    indent = raw[:len(raw) - len(raw.lstrip())]
    number = line.number if line is not None else None
    whole = number is not None and piece is None

    # A slip on one of Plain's own line-starting words, then habits from other languages.
    if whole:
        slip = core_slip(reader, line)
        if slip:
            return repair_problem(slip, line, number)
        problem = habit_problem(reader, line)
        if problem is not None:
            return problem
        problem = inline_habit(reader, line)
        if problem:
            return problem

    if "'" in stripped and any(t.kind == "squote" for t in toks):
        fixed = quote_singles(stripped)
        tok = next(t for t in toks if t.kind == "squote")
        ok = reads_cleanly(reader, line, indent + fixed)
        return Problem("Use double quotes around text.",
                       "Plain keeps the single quote mark for words like sale's.",
                       line=number, col=tok.col, end=tok.end, try_lines=[fixed] if ok else [],
                       ideas=[indent + fixed] if ok else [])

    # One of your steps used inside { } in a text.
    if piece is not None and number is not None:
        problem = step_in_piece(reader, line, piece)
        if problem:
            return problem

    # Two texts side by side: show "a" "b". (Not for your own steps: there it's a wording slip.)
    if whole and not (toks and toks[0].norm in reader.r.howto_index):
        for a, b in zip(toks, toks[1:]):
            if a.kind == "text" and b.kind == "text":
                joined = a.raw[:-1] + " " + b.raw[1:]
                fixed = raw[:a.col] + joined + raw[b.end:]
                if reads_cleanly(reader, line, fixed):
                    return Problem("Write the two texts as one text.",
                                   "Plain reads one value at each place in a step, so the words go in one pair of quotes.",
                                   line=number, col=a.col, end=b.end, try_lines=[fixed.rstrip()], ideas=[fixed])

    # A web address written without quotes.
    if whole:
        bare = bare_address(raw)
        if bare:
            start, stop = bare
            fixed = raw[:start] + '"' + raw[start:stop] + '"' + raw[stop:]
            ok = reads_cleanly(reader, line, fixed)
            return Problem("Put the web address in double quotes.",
                           "A web address is text, so it goes inside double quotes like other text.",
                           line=number, col=start, end=stop, try_lines=[fixed.rstrip()],
                           ideas=[fixed] if ok else [])

    # Then or than, and other words that are easy to mix up.
    if number is not None:
        mixups = repairs(reader, line, toks, limit=1, confusables_only=True)
        if mixups:
            return repair_problem(mixups[0], line, number)

    # A step Plain doesn't know at all.
    first = toks[0]
    if piece is None and i == 0 and first.kind == "word" and first.norm not in CORE_STARTS \
            and not knows_step(reader, first):
        repair = repairs(reader, line, toks, limit=3) if number is not None else []
        if repair:
            return repair_problem(repair[0], line, number)
        close = closest_phrases(stripped, names=reader.names)
        fits = [indent + c for c in close if number is not None and reads_cleanly(reader, line, indent + c)
                and any(w in c.split() for w in stripped.lower().split()[1:] if w not in STOP_WORDS)]
        return Problem(
            "Start this line with a step Plain knows, like one of these." if close else
            "Start this line with a step Plain knows. Type plain phrases to see them all.",
            f'Plain doesn\'t know a step that starts with "{first.raw}".',
            line=number, col=first.col, end=first.end, examples=close, ideas=fits, ask_claude=True)

    if whole:
        problem = (step_inside(reader, line) or (check and where_problem(reader, line))
                   or it_problem(reader, line) or file_name_problem(reader, line))
        if problem:
            return problem

    # Words that aren't any name you set.
    ghosts = ghost_names(reader, line) if whole else set()
    unknown = unknown_runs(reader, toks, ghosts)
    if piece is None and i == 0 and first.norm in reader.r.howto_index:
        # The first word of your own step isn't an unknown name.
        unknown = [run[1:] if run[0] is first else run for run in unknown]
        unknown = [run for run in unknown if run]
    if unknown:
        if whole:
            problem = its_problem(reader, line, unknown)
            if problem:
                return problem
        run_toks = unknown[0]
        words = " ".join(t.norm for t in run_toks)
        ucol, uend = run_toks[0].col, run_toks[-1].end
        said = raw[ucol:uend]
        known = {" ".join(n): n for n in reader.names if n not in ghosts}
        close = closest_name(words, list(known))
        if close:
            where = reader.r.origins.get(known[close[0]])
            fixed = raw[:ucol] + close[0] + raw[uend:] if number else None
            ok = number is not None and reads_cleanly(reader, line, fixed)
            return Problem(
                f'Write "{close[0]}" instead of "{said}".',
                (f'You set "{close[0]}" on line {where}. ' if where else "") + f'Nothing in your program sets "{said}".',
                line=number, col=ucol, end=uend, ideas=[fixed] if ok else [])
        problem = howto_name_problem(reader, run_toks, said, number)
        if problem:
            return problem
        if whole:
            problem = inner_quotes(reader, line, run_toks)
            if problem:
                return problem
        repair = repairs(reader, line, toks, limit=3) if number else []
        if repair:
            return repair_problem(repair[0], line, number)
        if whole:
            problem = text_problem(reader, line, run_toks)
            if problem:
                return problem
        return Problem(
            f'Set "{said}" before this line uses it, or check the spelling.',
            f'Plain doesn\'t know a name "{said}". Nothing in your program sets it.',
            line=number, col=ucol, end=uend, ask_claude=True)

    if whole:
        problem = howto_call_problem(reader, line) or phrasing_problem(reader, line) \
            or never_set(reader, line)
        if problem:
            return problem
    repair = repairs(reader, line, toks, limit=3) if number else []
    if repair:
        return repair_problem(repair[0], line, number)
    close = closest_phrases(stripped, names=reader.names)
    return Problem(
        "Reword this line using phrases Plain knows, like one of these." if close else "Reword this line.",
        "Plain couldn't follow this line.", line=number, col=col, end=end, examples=close, ask_claude=True)


def edit_distance(a, b):
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def closest_name(words, names):
    """A name you set that's probably what you meant: at most 2 letters different."""
    best = None
    for name in names:
        distance = edit_distance(words, name)
        # One letter off is a typo. Two letters off only counts when the start matches,
        # so "trys" is "tries", but "name" isn't "age".
        if distance == 1 or (distance == 2 and len(words) >= 4 and words[0] == name[0]):
            if best is None or distance < best[0]:
                best = (distance, name)
    return [best[1]] if best else []


def quote_singles(text):
    return re.sub(r"(?<![\w])'([^']*)'", r'"\1"', text)


def knows_step(reader, tok):
    return knows_word(reader, tok.norm)


def knows_word(reader, word):
    words = {word, SYNONYMS.get(word)}
    return any(w in reader.r.step_index or w in reader.r.howto_index for w in words if w)


def could_be_name(reader, words):
    """Could these words, at the start of a line, be a name you meant to set?"""
    first = words.split()[0].lower()
    return first not in CORE_STARTS and first not in HABIT_WORDS and not knows_word(reader, first)


def core_slip(reader, line):
    """A line whose first word is one letter away from one of Plain's line-starting words."""
    view = reader.t
    tok = view[0] if view else None
    if tok is None or tok.kind != "word" or len(tok.norm) < 3 or tok.norm in CORE_STARTS \
            or knows_step(reader, tok):
        return None
    for core in sorted(CORE_STARTS):
        if edit_distance(tok.norm, core) == 1:
            text = line.raw[:tok.col] + core + line.raw[tok.end:]
            if reads_cleanly(reader, line, text):
                return (f'Write "{core}" instead of "{tok.raw}".', text, tok,
                        f'"{core}" starts one of Plain\'s own lines, and "{tok.raw}" is one letter away from it.')
    return None


def ghost_names(reader, line):
    """Names a broken line only seemed to set: "show answer is 42" makes "show answer"."""
    from .parser import make_view
    view = make_view(line.tokens)
    if not view or view[0].kind != "word" or view[0].norm in CORE_STARTS:
        return set()
    return {n for n in reader.names if n[0] == view[0].norm and reader.r.origins.get(n) == line.number}


def phrase_words():
    out = set()
    for phrase in REGISTRY:
        for e in phrase.elements:
            if isinstance(e, Word):
                out.update(e.alts)
    for words, _ in COMPARISONS + ELIDED_COMPARISONS:
        out.update(words)
    for words in TYPE_CHECKS:
        out.update(words)
    out.update({"between", "divisible", "repeating", "forever", "once", "twice", "round", "back",
                "each", "every", "fails", "program", "next", "skip", "down"})
    return out


def unknown_runs(reader, toks, ignore=frozenset()):
    known_words = phrase_words() | CORE_STARTS | set(SYNONYMS)
    names = reader.names - set(ignore)
    runs, current = [], []
    for tok in toks:
        if tok.kind == "word" and tok.norm not in SPECIAL_WORDS:
            current.append(tok)
        else:
            if current:
                runs.append(current)
            current = []
    if current:
        runs.append(current)
    out = []
    for run in runs:
        # Drop known phrase words from the edges; what's left must not be a name you set.
        while run and run[0].norm in known_words and not covers_name(run, names):
            run = run[1:]
        while run and run[-1].norm in known_words and not covers_name(run, names):
            run = run[:-1]
        if run and not covers_name(run, names) and not all(t.norm in known_words for t in run):
            out.append(run)
    return out


def covers_name(run, names):
    words = tuple(t.norm for t in run)
    for size in range(len(words), 0, -1):
        for start in range(0, len(words) - size + 1):
            if words[start:start + size] in names and size == len(words):
                return True
    return False


def reads_cleanly(reader, line, text):
    """Would this line read with exactly one meaning, in the same place in the program?"""
    if text is None:
        return False
    from .parser import make_view
    from .source import Line, tokenize
    try:
        tokens, note, note_col = tokenize(text, line_no=line.number)
    except Problem:
        return False
    if not tokens:
        return note is not None     # a note on its own line is always fine
    candidate = Line(line.number, line.indent, text, tokens, note, note_col, list(getattr(line, "body", [])))
    problems = []
    was_quiet = reader.r.quiet
    reader.r.quiet = True
    try:
        stmt = reader.r.read_line(candidate, reader.scope, problems)
    except Problem:
        return False
    except Exception:
        return False
    finally:
        reader.r.quiet = was_quiet
    return stmt is not None and not problems_on_line(problems, line.number)


def reads_with_name(reader, line, text, words):
    """reads_cleanly, as if a name had already been set."""
    names = reader.r.main_names
    added = words not in names
    names.add(words)
    try:
        return reads_cleanly(reader, line, text)
    finally:
        if added:
            names.discard(words)


def problems_on_line(problems, number):
    return [p for p in problems if p.line in (None, number)]


# Changes inside a line ----------------------------------------------------------------

def inline_habit(reader, line):
    """len(x) and [1, 2, 3] from other languages, anywhere in a line."""
    toks, raw = line.tokens, line.raw
    for k, tok in enumerate(toks):
        if tok.kind == "word" and tok.norm == "len" and k + 1 < len(toks) and toks[k + 1].norm == "(":
            close = closing(toks, k + 1, "(", ")")
            if close is None or close == k + 2:
                continue
            inner = raw[toks[k + 1].end:toks[close].col].strip()
            old = raw[tok.col:toks[close].end]
            texts = [raw[:tok.col] + f"the {what} of {inner}" + raw[toks[close].end:] for what in ("number", "length")]
            texts = [t for t in texts if reads_cleanly(reader, line, t)]
            if texts:
                return Problem(
                    f'Write "the number of {inner}" instead of "{old}".',
                    '"len( )" comes from other languages. Plain says "the number of" for the items '
                    'in a list, and "the length of" for the characters in text.',
                    line=line.number, col=tok.col, end=toks[close].end,
                    try_lines=[t.rstrip() for t in texts], choices=[[t.rstrip()] for t in texts], ideas=texts)
        if tok.kind == "symbol" and tok.norm == "[":
            close = closing(toks, k, "[", "]")
            if close is None:
                continue
            if k > 0 and toks[k - 1].end == tok.col and toks[k - 1].kind == "word":
                # fruits[1] picks an item. Other languages usually count from 0, Plain from 1.
                if close != k + 2 or toks[k + 1].kind != "number" or not toks[k + 1].raw.isdigit():
                    continue
                name, n = toks[k - 1].raw, int(toks[k + 1].raw) + 1
                text = raw[:toks[k - 1].col] + f"item {n} of {name}" + raw[toks[close].end:]
                return Problem(
                    f'Write "item {n} of {name}" to get item {n}, counting from 1.',
                    f'Square brackets come from other languages, where "{raw[toks[k - 1].col:toks[close].end]}" '
                    f'usually means item {n}. Plain counts from 1, so the first item is "item 1 of {name}".',
                    line=line.number, col=toks[k - 1].col, end=toks[close].end,
                    try_lines=[text.rstrip()] if reads_cleanly(reader, line, text) else [])
            items, start = [], k + 1
            for m in range(k + 1, close + 1):
                if toks[m].norm in (",", "]") and toks[m].kind == "symbol" and m > start:
                    items.append(raw[toks[start].col:toks[m - 1].end])
                    start = m + 1
            new = "an empty list" if not items else "a list of " + (
                items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1])
            old = raw[tok.col:toks[close].end]
            text = raw[:tok.col] + new + raw[toks[close].end:]
            if reads_cleanly(reader, line, text):
                return Problem(
                    f'Write "{new}" instead of "{old}".',
                    'Square brackets come from other languages. Plain makes a list with "a list of".',
                    line=line.number, col=tok.col, end=toks[close].end,
                    try_lines=[text.rstrip()], ideas=[text])
    return None


def closing(toks, k, opener, closer):
    depth = 0
    for m in range(k, len(toks)):
        if toks[m].kind == "symbol" and toks[m].norm == opener:
            depth += 1
        elif toks[m].kind == "symbol" and toks[m].norm == closer:
            depth -= 1
            if depth == 0:
                return m
    return None


def with_article(raw, view, k):
    """Where a value starting at view[k] begins in the line, counting a dropped "the" or "a"."""
    col = view[k].col
    m = re.search(r"\b(the|an|a)\s+$", raw[:col], flags=re.IGNORECASE)
    if m and not any(t.col == m.start() for t in view):
        return m.start()
    return col


def never_set(reader, line):
    """add 5 to total, when nothing sets total: a word like "total" that Plain also uses in its
    own phrases, written where one of your names belongs."""
    view = reader.t
    if not view or view[0].kind != "word":
        return None
    for phrase in reader.r.step_index.get(SYNONYMS.get(view[0].norm, view[0].norm), []):
        elements, pos, spans = phrase.elements, 1, {}
        for k, el in enumerate(elements[1:], start=1):
            if isinstance(el, Word):
                at = next((m for m in range(pos, len(view)) if view[m].norm in el.alts), None)
                if at is None:
                    break
                if k > 1 and isinstance(elements[k - 1], Slot):
                    spans[elements[k - 1]] = (pos, at)
                pos = at + 1
        else:
            if isinstance(elements[-1], Slot):
                spans[elements[-1]] = (pos, len(view))
            for slot, (a, b) in spans.items():
                if slot.kind not in ("place", "list") or a >= b:
                    continue
                toks = view[a:b]
                words = tuple(t.norm for t in toks)
                if all(t.kind == "word" and t.norm not in SPECIAL_WORDS for t in toks) and words not in reader.names:
                    name = " ".join(words)
                    start = "an empty list" if slot.kind == "list" or any(t.kind == "text" for t in view) else "0"
                    return Problem(f'Set "{name}" to a starting value before this line, like: set {name} to {start}',
                                   f'Nothing in your program sets "{name}" before this line uses it.',
                                   line=line.number, col=toks[0].col, end=toks[-1].end, ask_claude=True)
    return None


def step_inside(reader, line):
    """One of your how-tos, or a step like read or ask, used inside another line."""
    view, raw = reader.t, line.raw
    indent = raw[:len(raw) - len(raw.lstrip())]
    norms = [t.norm for t in view]
    fix = 'Put this step on a line of its own, and keep what it gives back with "and call it".'
    for p in range(1, len(view)):
        phrases = giving_steps(reader, view[p])
        if not phrases:
            continue
        what = (f'"{view[p].raw}" is a step' if phrases[0].origin == "built-in" else
                f'"{howto_wording(phrases[0].run)}" is one of your own steps')
        why = what + ", and each step in Plain goes on a line of its own."
        set_form = norms[0] == "set" and "to" in norms and p == norms.index("to") + 1
        for e in range(p + 1, len(view) + 1):   # the shortest step that reads
            col, end = view[p].col, view[e - 1].end
            step = raw[col:end]
            if set_form:
                # set x to double 4: the step can keep its value under x itself.
                if e < len(view):
                    continue
                text = f"{indent}{step} and call it {raw[view[1].col:view[p - 2].end]}"
                if reads_cleanly(reader, line, text):
                    return Problem(fix, why, line=line.number, col=col, end=end,
                                   try_lines=[text.rstrip()], ideas=[text])
                continue
            name = result_name(reader, phrases[0])
            if name is None:
                return None
            first = f"{indent}{step} and call it {name}"
            second = raw[:col] + name + raw[end:]
            if reads_cleanly(reader, line, first) and reads_with_name(reader, line, second, tuple(name.split())):
                return Problem(fix, why, line=line.number, col=col, end=end,
                               try_lines=[first.rstrip(), second.rstrip()], ideas=[first + "\n" + second])
    return None


def step_in_piece(reader, line, piece):
    """One of your how-tos used inside { } in a text: do it on the line before, then use the name."""
    toks = piece.tokens
    if not toks:
        return None
    phrases = giving_steps(reader, toks[0])
    if not phrases:
        return None
    raw = line.raw
    indent = raw[:len(raw) - len(raw.lstrip())]
    name = result_name(reader, phrases[0])
    if name is None:
        return None
    inner = raw[piece.col + 1:piece.end - 1].strip()
    first = f"{indent}{inner} and call it {name}"
    second = raw[:piece.col + 1] + name + raw[piece.end - 1:]
    if not (reads_cleanly(reader, line, first) and reads_with_name(reader, line, second, tuple(name.split()))):
        return None
    what = (f'"{toks[0].raw}" is a step' if phrases[0].origin == "built-in" else
            f'"{howto_wording(phrases[0].run)}" is one of your own steps')
    return Problem('Put this step on a line of its own, and keep what it gives back with "and call it".',
                   what + ", and each step in Plain goes on a line of its own.",
                   line=line.number, col=piece.col, end=piece.end,
                   try_lines=[first.rstrip(), second.rstrip()], ideas=[first + "\n" + second])


def giving_steps(reader, tok):
    """Steps starting with this word, when every one of them gives back a value."""
    if tok.kind != "word":
        return []
    phrases = [h.phrase for h in reader.r.howto_index.get(tok.norm, [])]
    for w in {tok.norm, SYNONYMS.get(tok.norm)}:
        phrases += reader.r.step_index.get(w, []) if w else []
    return phrases if phrases and all(p.gives for p in phrases) else []


def result_name(reader, phrase):
    """A name for what a step gives back: the word before a small word ("tip" in
    "work out the tip on (bill)"), or "result"."""
    words = phrase.elements
    options = [e.main for e, nxt in zip(words[1:], words[2:])
               if isinstance(e, Word) and isinstance(nxt, Word) and nxt.main in STOP_WORDS
               and e.main not in STOP_WORDS | SPECIAL_WORDS][:1] + ["result"] + [f"result {n}" for n in range(2, 10)]
    return next((o for o in options if tuple(o.split()) not in reader.names), None)


def where_problem(reader, line):
    """A "where" inside an if or until, followed by another comparison: offer brackets."""
    view, raw = reader.t, line.raw
    indent = raw[:len(raw) - len(raw.lstrip())]
    w = next((k for k, t in enumerate(view) if t.kind == "word" and t.norm == "where"), None)
    if w is None or w < 2:
        return None
    for k in range(w + 2, len(view)):
        if view[k].norm not in COMPARISON_FIRST or reader.depth[k] != reader.depth[w]:
            continue
        stop = view[k - 1].end
        for s in range(w - 1, 0, -1):
            start = with_article(raw, view, s)
            bracketed = raw[:start] + "(" + raw[start:stop] + ")" + raw[stop:]
            if not reads_cleanly(reader, line, bracketed):
                continue
            last = view[w - 1].norm if view[w - 1].kind == "word" else "rows"
            name = f"matching {last}" if ("matching", last) not in reader.names else "matching rows"
            words = tuple(name.split())
            first = f"{indent}set {name} to {raw[start:stop]}"
            second = raw[:start] + name + raw[stop:]
            choices = [[bracketed.rstrip()]]
            if words not in reader.names and reads_with_name(reader, line, first, words) \
                    and reads_with_name(reader, line, second, words):
                choices = [[first.rstrip(), second.rstrip()], [bracketed.rstrip()]]
            return Problem(
                'Put brackets around the "where" part, or keep the matching rows under a name first.',
                '"where" checks each row up to the end of the line, so here it took in the comparison after it too.',
                line=line.number, col=start, end=stop, try_lines=[l for c in choices for l in c],
                choices=choices, ideas=[bracketed])
    return None


def it_problem(reader, line):
    """Using "it" or "its" outside a "where"."""
    view = reader.t
    for k, tok in enumerate(view):
        if tok.kind == "word" and tok.norm == "where":
            return None
        if tok.kind != "word" or tok.norm not in ("it", "its"):
            continue
        if k >= 2 and view[k - 1].norm == "call" and view[k - 2].norm == "and":
            continue
        if tok.norm == "it" and not (k + 1 < len(view) and view[k + 1].kind == "poss"):
            return Problem('Write the name of the item instead of "it".',
                           'In Plain, "it" means the item being checked inside "where", as in: '
                           'the scores where it is more than 10',
                           line=line.number, col=tok.col, end=tok.end)
        return Problem('Write the name of the item with \'s instead of "its".',
                       'In Plain, "its" means a field of the item being checked inside "where", as in: '
                       'the sales where its amount is more than 100',
                       line=line.number, col=tok.col, end=tok.end)
    return None


def file_name_problem(reader, line):
    """A file name written without quotes: people.csv."""
    toks, raw = line.tokens, line.raw
    m = re.search(r'\b(?:read|to) (?!")(?P<f>[A-Za-z][\w ]*\.(?:csv|txt|json|md|html|tsv))\b', raw)
    if m and not raw[:m.start("f")].count('"') % 2:
        start, stop = m.start("f"), m.end("f")
        fixed = raw[:start] + '"' + m.group("f") + '"' + raw[stop:]
        if reads_cleanly(reader, line, fixed):
            return Problem("Put the file name in double quotes.",
                           "A file name is text, and text goes in double quotes.",
                           line=line.number, col=start, end=stop,
                           try_lines=[fixed.rstrip()], ideas=[fixed])
    for k in range(len(toks) - 2):
        a, dot, ext = toks[k:k + 3]
        if a.kind == "word" and dot.kind == "symbol" and dot.norm == "." and ext.kind == "word" \
                and a.end == dot.col and dot.end == ext.col:
            fixed = raw[:a.col] + '"' + raw[a.col:ext.end] + '"' + raw[ext.end:]
            if reads_cleanly(reader, line, fixed):
                return Problem("Put the file name in double quotes.",
                               "A file name is text, and text goes in double quotes.",
                               line=line.number, col=a.col, end=ext.end,
                               try_lines=[fixed.rstrip()], ideas=[fixed])
    return None


def its_problem(reader, line, unknown):
    """A field inside "where" after "of", as in "the length of name": write "its"."""
    wheres = [t.col for t in reader.t if t.kind == "word" and t.norm == "where"]
    if not wheres:
        return None
    raw, view = line.raw, reader.t
    for run in unknown:
        k = next((m for m, t in enumerate(view) if t is run[0]), None)
        if run[0].col < wheres[0] or not k or view[k - 1].norm != "of":
            continue
        fixed = raw[:run[0].col] + "its " + raw[run[0].col:]
        if reads_cleanly(reader, line, fixed):
            said = raw[run[0].col:run[-1].end]
            return Problem(
                f'Write "its {said}" instead of "{said}".',
                'Inside "where", a word on its own is a field of each row only at the start of a check. '
                'Anywhere else, write "its" in front of it.',
                line=line.number, col=run[0].col, end=run[-1].end, try_lines=[fixed.rstrip()], ideas=[fixed])
    return None


def inner_quotes(reader, line, run_toks):
    """show "She said "hi" to me": quote marks inside text are written twice."""
    toks, raw = line.tokens, line.raw
    k = next((m for m, t in enumerate(toks) if t.col == run_toks[0].col), None)
    if not k or toks[k - 1].kind != "text" or toks[k - 1].end != run_toks[0].col:
        return None
    before = toks[k - 1]
    m = next((m for m in range(k, len(toks)) if toks[m].kind == "text"), None)
    if m is None or toks[m - 1].end != toks[m].col:
        return None
    after = toks[m]
    fixed = raw[:before.end - 1] + '""' + raw[before.end:after.col] + '""' + raw[after.col + 1:]
    if not reads_cleanly(reader, line, fixed):
        return None
    return Problem('Write "" for each quote mark inside text.',
                   'A single " ends the text, so Plain needs two of them, "", to show one quote mark.',
                   line=line.number, col=before.end - 1, end=after.col + 1,
                   try_lines=[fixed.rstrip()], ideas=[fixed])


def text_problem(reader, line, run_toks):
    """Text written without quotes, after show, ask or set ... to."""
    from .parser import find_call_it
    view, raw = reader.t, line.raw
    first = view[0].norm if view[0].kind == "word" else ""
    norms = [t.norm for t in view]
    stop = len(view)
    if first in SHOW_WORDS or SYNONYMS.get(first) == "show":
        start, how = 1, "shown"
    elif first == "ask":
        start, how = 1, "shown"
        stop = find_call_it(view) or len(view)
        stop = next((m for m in range(1, stop - 1) if norms[m] == "with" and norms[m + 1] in ("choices", "options")), stop)
    elif first == "set" and "to" in norms[2:]:
        start, how = norms.index("to", 2) + 1, "kept"
    else:
        return None
    if start >= stop or view[start] is not run_toks[0]:
        return None
    span = view[start:stop]
    s = len(raw) - len(raw[view[start - 1].end:].lstrip())
    e = span[-1].end
    if '"' in raw[s:e] or "“" in raw[s:e]:
        return None
    # Text, not a name: a word with a capital, or after show and ask, several unknown words
    # or the whole value.
    capital = re.search(r"\b[A-Z]", raw[s:e])
    if not (capital or how == "shown" and (len(run_toks) > 1 or len(span) == len(run_toks))):
        return None
    fixed = raw[:s] + '"' + raw[s:e] + '"' + raw[e:]
    if not reads_cleanly(reader, line, fixed):
        return None
    said = raw[s:run_toks[-1].end]
    return Problem(
        "Put the text in double quotes.",
        f'Words in double quotes are {how} just as you wrote them. Without quotes, Plain looks '
        f'for a name "{said}", and you haven\'t set one.',
        line=line.number, col=s, end=e, try_lines=[fixed.rstrip()], ideas=[fixed])


# Your own steps ("how to") ------------------------------------------------------------

def howto_wording(howto):
    return re.sub(r"\{([^}]*)\}", r"(\1)", howto.phrase.template)


def words_used(lines):
    """Every word in these lines and the lines under them, including inside { } in text."""
    from .parser import walk
    out = set()
    for line in walk(lines):
        for tok in line.tokens:
            if tok.kind == "word":
                out.add(tok.norm)
            elif tok.kind == "text":
                for piece in tok.value:
                    if not isinstance(piece, str):
                        out.update(t.norm for t in piece.tokens if t.kind == "word")
    return out


def bracket_fix(reader, howto):
    """A word in a how-to's wording that its steps use as a name: (the word, the wording
    with brackets around it), checked to read."""
    from .parser import make_view
    from .source import Line, tokenize
    line = howto.line
    used = words_used(line.body)
    names = reader.r.main_names | howto.own_names
    for tok in make_view(line.tokens)[3:]:
        if tok.kind != "word" or tok.norm in SPECIAL_WORDS or tok.norm in STOP_WORDS \
                or tok.norm not in used or (tok.norm,) in names:
            continue
        text = line.raw[:tok.col] + "(" + tok.raw + ")" + line.raw[tok.end:]
        try:
            tokens, note, note_col = tokenize(text, line_no=line.number)
        except Problem:
            continue
        problems = []
        new = reader.r.read_howto_header(Line(line.number, line.indent, text, tokens, note, note_col, line.body),
                                         problems)
        if new is not None and not problems and (tok.norm,) in new.params:
            return tok.raw, text.strip()
    return None


def bracket_problem(fix, howto, number, col, end):
    word, wording = fix
    return Problem(
        f'Put brackets around "{word}" on line {howto.line.number}, so your step takes it as a value.',
        f'Words in brackets are the values you hand to your step when you use it. Without brackets, '
        f'"{word}" is just one of the words of the step.',
        line=number, col=col, end=end, try_lines=[wording])


def howto_name_problem(reader, run_toks, said, number):
    """A name set only inside one of your how-tos, or a how-to word its steps use as a name."""
    words = tuple(t.norm for t in run_toks)
    col, end = run_toks[0].col, run_toks[-1].end
    for howto in getattr(reader.r, "howtos", []):
        if howto is reader.scope or words not in howto.own_names or words in howto.params:
            continue
        origin = reader.r.origins.get(words)
        wording = howto_wording(howto)
        return Problem(
            f'Add "give back {said}" to your step "{wording}", then keep what it gives back with "and call it {said}".',
            f'"{said}" is set only inside your step "{wording}"' + (f" (line {origin})" if origin else "")
            + ", so it belongs to that step and the rest of your program can't use it.",
            line=number, col=col, end=end)
    if reader.scope is not None:
        fix = bracket_fix(reader, reader.scope)
        if fix and (fix[0].lower(),) == words:
            return bracket_problem(fix, reader.scope, number, col, end)
    return None


def howto_call_problem(reader, line):
    """A line that starts like one of your how-tos but doesn't follow its wording."""
    view = reader.t
    first = view[0]
    if first.kind != "word" or first.norm not in reader.r.howto_index:
        return None
    howto = reader.r.howto_index[first.norm][0]
    fix = bracket_fix(reader, howto)
    if fix:
        return bracket_problem(fix, howto, line.number, first.col, view[-1].end)
    why = ("Your step needs one value in place of each part in brackets." if howto.params else
           "Plain matches a line to your step only when it uses the same words.")
    return Problem(f'Write this line the way your step on line {howto.line.number} is worded: {howto_wording(howto)}',
                   why, line=line.number, col=first.col, end=view[-1].end)


# Everyday phrasings ---------------------------------------------------------------------

def phrasing_problem(reader, line):
    return (elided_type(reader, line) or add_items(reader, line) or list_brackets(reader, line)
            or join_text(reader, line) or bare_possessive(reader, line))


def elided_type(reader, line):
    """if age is even or odd: write "is" again after "or"."""
    view, raw = reader.t, line.raw
    for k in range(len(view) - 1):
        tok, nxt = view[k], view[k + 1]
        if tok.kind == "word" and tok.norm in ("and", "or") and nxt.kind == "word" and nxt.norm in TYPE_WORDS:
            text = raw[:tok.end] + " is" + raw[tok.end:]
            if reads_cleanly(reader, line, text):
                old = raw[tok.col:nxt.end]
                return Problem(
                    f'Write "{tok.raw} is {old[len(tok.raw):].strip()}" instead of "{old}".',
                    f'After "and" or "or", write "is" again before a word like "{nxt.raw}".',
                    line=line.number, col=tok.col, end=nxt.end, try_lines=[text.rstrip()], ideas=[text])
    return None


def add_items(reader, line):
    """add "tea" and "rice" to shopping: add a list of them."""
    view, raw = reader.t, line.raw
    norms = [t.norm for t in view]
    if len(view) < 5 or norms[0] != "add" or "to" not in norms:
        return None
    to = len(norms) - 1 - norms[::-1].index("to")
    if "and" not in norms[1:to]:
        return None
    text = raw[:view[1].col] + "a list of " + raw[view[1].col:]
    if not reads_cleanly(reader, line, text):
        return None
    return Problem('Write "a list of" before the items, to add each one.',
                   'To add several items at once, make them into a list with "a list of".',
                   line=line.number, col=view[1].col, end=view[to - 1].end,
                   try_lines=[text.rstrip()], ideas=[text])


def list_brackets(reader, line):
    """if age is in a list of 1, 5 and 6 or age is 3: brackets show where the list ends."""
    view, raw = reader.t, line.raw
    for k in range(len(view) - 1):
        if not (view[k].norm == "list" and view[k + 1].norm == "of"):
            continue
        start = with_article(raw, view, k)
        found = []
        for m in range(k + 2, len(view)):
            if view[m].kind == "word" and view[m].norm in ("and", "or") and reader.depth[m] == reader.depth[k]:
                stop = view[m - 1].end
                text = raw[:start] + "(" + raw[start:stop] + ")" + raw[stop:]
                if reads_cleanly(reader, line, text):
                    found.append((text, stop))
        if found:
            # The longest list that still reads keeps every "and" item in it.
            text, stop = found[-1]
            return Problem('Put brackets around the list.',
                           'A list takes in everything after "a list of", so brackets show Plain where it ends.',
                           line=line.number, col=start, end=stop, try_lines=[text.rstrip()], ideas=[text])
    return None


def join_text(reader, line):
    """show "Total is " total: put the value inside the text, in { }."""
    from .parser import find_call_it
    view, raw = reader.t, line.raw
    first = view[0].norm if view[0].kind == "word" else ""
    if first in SHOW_WORDS or SYNONYMS.get(first) == "show":
        slot = view[1:]
    elif first == "ask":
        slot = view[1:find_call_it(view) or len(view)]
    else:
        return None
    groups, current = [], []
    for tok in slot:
        if tok.kind == "text":
            if current:
                groups.append(current)
                current = []
            groups.append(tok)
        else:
            current.append(tok)
    if current:
        groups.append(current)
    if all(isinstance(g, list) for g in groups) or not any(isinstance(g, list) for g in groups):
        return None
    merged = ""
    for g in groups:
        part = g.raw[1:-1] if not isinstance(g, list) else "{" + raw[g[0].col:g[-1].end] + "}"
        if merged and not merged[-1].isspace() and part and not part[0].isspace() and part[0] not in ".,!?;:)":
            merged += " "
        merged += part
    text = raw[:slot[0].col] + '"' + merged + '"' + raw[slot[-1].end:]
    if not reads_cleanly(reader, line, text):
        return None
    return Problem("Put the value inside the text, in { }.",
                   "To show a value as part of text, write it in { } inside the quotes.",
                   line=line.number, col=slot[0].col, end=slot[-1].end, try_lines=[text.rstrip()], ideas=[text])


def bare_possessive(reader, line):
    """show x's: a field name goes after 's."""
    view = reader.t
    for k, tok in enumerate(view):
        if tok.kind == "poss" and k > 0 and (k + 1 == len(view) or view[k + 1].kind not in ("word", "text")):
            return Problem(f'Write the name of a field after "{view[k - 1].raw}\'s".',
                           '"\'s" picks out one field of a record, as in: sale\'s amount',
                           line=line.number, col=view[k - 1].col, end=tok.end)
    return None


# One-word repairs -----------------------------------------------------------------------

def repairs(reader, line, toks, limit=3, confusables_only=False):
    """Small changes that make the line read cleanly: then/than, a missing "than", two words
    run together, a typo, or a word that means nothing here."""
    if line.number is None:
        return []
    found = []
    for repair in repair_options(reader, line, toks, confusables_only):
        if reads_cleanly(reader, line, repair[1]):
            found.append(repair)
            if len(found) >= limit:
                break
    return found


def repair_options(reader, line, toks, confusables_only):
    raw = line.raw
    words = [t for t in toks if t.kind == "word"]
    for tok in words:
        if tok.norm in CONFUSABLES:
            option = CONFUSABLES[tok.norm]
            yield (f'Write "{option}" instead of "{tok.raw}".', raw[:tok.col] + option + raw[tok.end:],
                   tok, explain_swap(tok.norm, option))
    if confusables_only:
        return
    for tok in words:
        after = next((t for t in line.tokens if t.col >= tok.end), None)
        if tok.norm in NEEDS_THAN and not (after is not None and after.norm == "than"):
            yield (f'Write "{tok.raw} than" instead of "{tok.raw}".', raw[:tok.end] + " than" + raw[tok.end:],
                   tok, 'Plain compares with "than", as in: if age is more than 18')
    vocabulary = phrase_words() | CORE_STARTS | {w for n in reader.names for w in n}
    for tok in words:
        if len(tok.norm) < 4 or tok.norm in vocabulary:
            continue
        for cut in range(2, len(tok.norm) - 1):
            if tok.norm[:cut] in vocabulary and tok.norm[cut:] in vocabulary:
                split = tok.raw[:cut] + " " + tok.raw[cut:]
                yield (f'Write "{split}" instead of "{tok.raw}".', raw[:tok.col] + split + raw[tok.end:], tok,
                       f'Plain reads "{tok.raw}" as the two words "{split}".')
    tried = 0
    ordered = sorted(vocabulary)
    for tok in words:
        if tok.norm in vocabulary or tok.norm in SPECIAL_WORDS:
            continue   # never swap a word Plain knows ("times" is not a typo of "timer")
        for option in difflib.get_close_matches(tok.norm, ordered, n=3, cutoff=0.75):
            if option == tok.norm:
                continue
            tried += 1
            yield (f'Write "{option}" instead of "{tok.raw}".', raw[:tok.col] + option + raw[tok.end:],
                   tok, explain_swap(tok.norm, option)
                   or f'Plain doesn\'t know the word "{tok.raw}" here. "{option}" is close to it.')
        if tried > 60:
            break
    # Only words that mean nothing here, or the same word twice, are ever dropped.
    for k in range(1, len(toks)):
        tok = toks[k]
        if tok.kind == "word" and tok.norm not in CORE_STARTS and \
                (tok.norm in FILLER_WORDS or tok.norm == toks[k - 1].norm):
            yield (f'Remove the word "{tok.raw}".', (raw[:tok.col].rstrip() + " " + raw[tok.end:].lstrip()).rstrip(),
                   tok, f'Plain can follow the line without "{tok.raw}".')


def bare_address(raw):
    """Where a web address sits outside quotes, as (start, stop), or None."""
    inside = False
    for k, ch in enumerate(raw):
        if ch in '"“”':
            inside = not inside if ch == '"' else ch == "“"
        elif not inside and raw.startswith(("http://", "https://"), k) and (k == 0 or not raw[k - 1].isalnum()):
            stop = k
            while stop < len(raw) and not raw[stop].isspace():
                stop += 1
            return k, stop
    return None


def explain_swap(old, new):
    if {old, new} == {"then", "than"}:
        return '"Than" compares two things. "Then" means "next".'
    return None


def repair_problem(repair, line, number):
    fix, text, tok, why = repair
    return Problem(fix, why, line=number, col=tok.col, end=tok.end,
                   try_lines=[text.rstrip()], ideas=[text])


EXAMPLE_LISTS = ("sales", "prices", "todos", "colors", "names", "scores", "cards", "shopping",
                 "expenses", "people", "notes")


def closest_phrases(text, count=3, names=()):
    """Examples of the phrases closest to a line: the ones sharing the most words with it.
    When the line uses one of your names, the examples use it too."""
    all_words = re.findall(r"[a-z0-9]+", text.lower())
    yours = next((" ".join(n) for n in sorted(names, key=len, reverse=True)
                  if " ".join(n) in " ".join(all_words)), None)

    def personal(example):
        if yours:
            for word in EXAMPLE_LISTS:
                example = re.sub(rf"\b{word}\b", yours, example)
        return example

    if all_words and all_words[0] in VERB_HINTS:
        return [personal(e) for e in VERB_HINTS[all_words[0]][:count]]
    first, rest = (all_words[0], set(all_words[1:]) - STOP_WORDS) if all_words else ("", set())
    scored, seen = [], set()
    for phrase in REGISTRY:
        main = phrase.main
        if id(main) in seen or main.kind not in ("step", "value", "postfix"):
            continue
        seen.add(id(main))
        words = {a for p in REGISTRY if p.main is main for e in p.elements if isinstance(e, Word) for a in e.alts}
        score = 2 * len(rest & words)
        lead = main.elements[0]
        if main.kind == "step" and isinstance(lead, Word) and first and \
                (first in lead.alts or difflib.get_close_matches(first, list(lead.alts), n=1, cutoff=0.8)):
            score += 1
        if score >= 2 or (score == 1 and not rest):
            scored.append((score, personal(main.example)))
    scored.sort(key=lambda s: -s[0])
    return [example for _, example in scored[:count]]
