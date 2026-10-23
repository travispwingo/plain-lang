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

# Everyday verbs people start lines with, and the Plain step that does that job.
VERB_HINTS = {
    "count": ["set count to the number of sales", "show the number of sales where amount is more than 100"],
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

# Habits from other languages: (pattern on the whole line, replacement, why).
HABITS = [
    (r"^(?P<name>[A-Za-z][\w ]*?)\s*\+=\s*(?P<v>.+)$", r"add \g<v> to \g<name>",
     '"+=" comes from other languages. In Plain you add to a value with "add".'),
    (r"^(?P<name>[A-Za-z][\w ]*?)\s*-=\s*(?P<v>.+)$", r"subtract \g<v> from \g<name>",
     '"-=" comes from other languages. In Plain you take away with "subtract".'),
    (r"^(?P<name>[A-Za-z][\w ]*?)\s*=\s*(?P<v>[^=].*)$", r"set \g<name> to \g<v>",
     'In Plain, "=" only compares two values. To keep a value, write "set".'),
    (r"^(?P<name>[A-Za-z][\w ]*?) is (?P<v>.+)$", r"set \g<name> to \g<v>",
     'In Plain, "is" only compares two values, as in: if score is 0'),
    (r"^(?:print|console\.log|puts|echo|say)\s*\((?P<v>.*)\)\s*;?$", r"show \g<v>",
     'Plain uses "show" to put words on the screen.'),
    (r"^(?:print|puts|echo|say|write)\s+(?P<v>[^()].*)$", r"show \g<v>",
     'Plain uses "show" to put words on the screen. To put words in a file, write: save ... to "notes.txt"'),
    (r"^(?:open|download|get|load)\s+(?P<v>.+)$", r"read \g<v>",
     'Plain uses "read" for files and web pages.'),
    (r"^elif\b(?P<v>.*)$", r"otherwise if\g<v>", 'Plain says "otherwise if".'),
    (r"^else\s+if\b(?P<v>.*)$", r"otherwise if\g<v>", 'Plain says "otherwise if".'),
    (r"^break$", "stop repeating", '"break" comes from other languages. Plain says "stop repeating".'),
    (r"^continue$", "skip to the next round",
     '"continue" comes from other languages. Plain says "skip to the next round".'),
    (r"^//\s*(?P<v>.*)$", r"# \g<v>", "Notes in Plain start with #."),
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

    # Whole-line habits from other languages.
    if number is not None and piece is None:
        for pattern, replacement, why in HABITS:
            m = re.match(pattern, stripped, flags=re.IGNORECASE)
            if not m:
                continue
            if pattern.startswith("^(?P<name>") and m.group("name").split()[0].lower() in CORE_STARTS:
                continue
            fixed = re.sub(pattern, replacement, stripped, flags=re.IGNORECASE)
            fixed = quote_singles(fixed)
            if reads_cleanly(reader, line, indent + fixed):
                return Problem(f'Write "{fixed}" instead.', why, line=number, col=col, end=end,
                               try_lines=[fixed], ideas=[indent + fixed])

    if "'" in stripped and any(t.kind == "squote" for t in toks):
        fixed = quote_singles(stripped)
        tok = next(t for t in toks if t.kind == "squote")
        return Problem("Use double quotes around text.",
                       "Plain keeps the single quote mark for words like sale's.",
                       line=number, col=tok.col, end=tok.end, try_lines=[fixed],
                       ideas=[indent + fixed] if reads_cleanly(reader, line, indent + fixed) else [])

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
        close = closest_phrases(stripped)
        return Problem(
            "Start this line with a step Plain knows, like one of these." if close else
            "Start this line with a step Plain knows. Type plain phrases to see them all.",
            f'Plain doesn\'t know a step that starts with "{first.raw}".',
            line=number, col=first.col, end=first.end, try_lines=close)

    # A "where" with another comparison after it, inside an if or until.
    if any(t.norm == "where" for t in toks) and check:
        return Problem(
            'Put brackets around the "where" part, or keep the matching rows under a name first.',
            '"where" checks each row up to the end of the line, so here it took in the comparison after it too.',
            line=number, col=col, end=end,
            try_lines=["set matching rows to the sales where amount is more than 100",
                       "if the number of matching rows is at least 5",
                       "if the number of (sales where amount is more than 100) is at least 5"])

    # Words that aren't any name you set.
    unknown = unknown_runs(reader, toks)
    if unknown:
        run_toks = unknown[0]
        words = " ".join(t.norm for t in run_toks)
        ucol, uend = run_toks[0].col, run_toks[-1].end
        known = {" ".join(n): n for n in reader.names}
        close = closest_name(words, list(known))
        if close:
            where = reader.r.origins.get(known[close[0]])
            fixed = raw[:ucol] + close[0] + raw[uend:] if number else None
            ok = number is not None and reads_cleanly(reader, line, fixed)
            return Problem(
                f'Write "{close[0]}" instead of "{words}".',
                (f'You set "{close[0]}" on line {where}. ' if where else "") + f'Nothing in your program sets "{words}".',
                line=number, col=ucol, end=uend, ideas=[fixed] if ok else [])
        if looks_like_text(reader, toks, run_toks):
            text_toks = text_span(toks, run_toks)
            tcol, tend = text_toks[0].col, text_toks[-1].end
            fixed = raw[:tcol] + '"' + raw[tcol:tend] + '"' + raw[tend:]
            ok = number is not None and reads_cleanly(reader, line, fixed)
            phrase = raw[tcol:tend]
            return Problem(
                "Put the text in double quotes.",
                f'Words in double quotes are shown just as you wrote them. Without quotes, Plain looks '
                f'for a name "{phrase}", and you haven\'t set one.',
                line=number, col=tcol, end=tend, try_lines=[fixed.strip()], ideas=[fixed] if ok else [])
        repair = repairs(reader, line, toks, limit=3) if number else []
        if repair:
            return repair_problem(repair[0], line, number)
        return Problem(
            f'Set "{words}" before this line uses it, or check the spelling.',
            f'Plain doesn\'t know a name "{words}". Nothing in your program sets it.',
            line=number, col=ucol, end=uend)

    repair = repairs(reader, line, toks, limit=3) if number else []
    if repair:
        return repair_problem(repair[0], line, number)
    close = closest_phrases(stripped)
    return Problem(
        "Reword this line using phrases Plain knows, like one of these." if close else "Reword this line.",
        "Plain couldn't follow this line.", line=number, col=col, end=end, try_lines=close)


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
        limit = 1 if len(words) <= 3 else 2
        if distance <= limit and (best is None or distance < best[0]):
            best = (distance, name)
    return [best[1]] if best else []


def quote_singles(text):
    return re.sub(r"(?<![\w])'([^']*)'", r'"\1"', text)


def knows_step(reader, tok):
    words = {tok.norm, SYNONYMS.get(tok.norm)}
    return any(w in reader.r.step_index or w in reader.r.howto_index for w in words if w)


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


def unknown_runs(reader, toks):
    known_words = phrase_words() | CORE_STARTS | set(SYNONYMS)
    names = reader.names
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


def looks_like_text(reader, toks, run_toks):
    first = toks[0].norm
    if first in ("show", "display", "ask", "print", "say") or SYNONYMS.get(first) == "show":
        return True
    return any(t.raw[:1].isupper() for t in run_toks[1:]) and len(run_toks) > 1


def text_span(toks, run_toks):
    """From the unknown words to the end of the slot they're in."""
    start = toks.index(run_toks[0])
    end = start
    while end + 1 < len(toks) and toks[end + 1].kind in ("word", "symbol") and \
            toks[end + 1].norm not in ("and",) and not (toks[end + 1].kind == "symbol" and toks[end + 1].norm in "()"):
        end += 1
    if start > 0 and toks[0].norm in ("show", "display") and start == 1:
        return toks[1:end + 1]
    return toks[start:end + 1]


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
        return False
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


def problems_on_line(problems, number):
    return [p for p in problems if p.line in (None, number)]


def repairs(reader, line, toks, limit=3, confusables_only=False):
    """One-word changes that make the line read cleanly: then/than, typos, an extra word."""
    if line.number is None:
        return []
    raw = line.raw
    vocabulary = sorted(phrase_words() | CORE_STARTS | {w for n in reader.names for w in n})
    found = []
    tried = 0
    for tok in toks:
        if tok.kind != "word":
            continue
        options = []
        if tok.norm in CONFUSABLES:
            options.append(CONFUSABLES[tok.norm])
        if not confusables_only:
            options += [w for w in difflib.get_close_matches(tok.norm, vocabulary, n=3, cutoff=0.75)
                        if w != tok.norm]
        for option in options:
            tried += 1
            text = raw[:tok.col] + option + raw[tok.end:]
            if reads_cleanly(reader, line, text):
                found.append((f'Write "{option}" instead of "{tok.raw}".', text, tok, explain_swap(tok.norm, option)))
                break
        if len(found) >= limit or tried > 60:
            break
    if not found and not confusables_only:
        for tok in toks[1:]:
            if tok.kind != "word" or tok.norm in CORE_STARTS:
                continue
            text = (raw[:tok.col].rstrip() + " " + raw[tok.end:].lstrip()).rstrip()
            if reads_cleanly(reader, line, text):
                found.append((f'Remove the word "{tok.raw}".', text, tok, None))
                break
    return found


def explain_swap(old, new):
    if {old, new} == {"then", "than"}:
        return '"Than" compares two things. "Then" means "next".'
    return None


def repair_problem(repair, line, number):
    fix, text, tok, why = repair
    return Problem(fix, why, line=number, col=tok.col, end=tok.end,
                   try_lines=[text.strip()], ideas=[text])


def closest_phrases(text, count=3):
    all_words = re.findall(r"[a-z]+", text.lower())
    if all_words and all_words[0] in VERB_HINTS:
        return VERB_HINTS[all_words[0]][:count]
    words = set(all_words) - STOP_WORDS
    scored = []
    seen = set()
    for phrase in REGISTRY:
        main = phrase.main
        if id(main) in seen:
            continue
        seen.add(id(main))
        template_words = set()
        for p in REGISTRY:
            if p.main is main:
                template_words |= {a for e in p.elements if isinstance(e, Word) for a in e.alts}
        score = len(words & template_words)
        first = main.elements[0]
        if isinstance(first, Word) and words and difflib.get_close_matches(
                text.lower().split()[0] if text.split() else "", list(first.alts), n=1, cutoff=0.7):
            score += 2
        if score:
            scored.append((score, main.example))
    scored.sort(key=lambda s: -s[0])
    return [example for _, example in scored[:count]]
