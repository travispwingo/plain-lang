"""From source text to lines of tokens, grouped by indentation."""

import re
from dataclasses import dataclass, field
from decimal import Decimal

from .problems import Problem
from .words import CONTRACTIONS

CURRENCY = "$€£"
SYMBOLS = ["==", "!=", ">=", "<=", "(", ")", ",", ":", ".", "!", ";", "+", "-", "*", "/",
           "×", "÷", "=", "≠", ">", "<", "≥", "≤", "%"]
NUMBER = re.compile(r"[$€£]?\d+(\.\d+)?%?")
DASHES = {"–": "-", "—": "-", "−": "-"}
OPENERS = {'"': '"', "“": "”"}
APOSTROPHES = "'’"


@dataclass(slots=True)
class Token:
    kind: str          # word, number, text, symbol, poss
    raw: str
    norm: str
    col: int
    end: int
    value: object = None   # Decimal for numbers, a list of pieces for text
    percent: bool = False

    def __repr__(self):
        return f"<{self.kind} {self.raw!r}>"


@dataclass(slots=True)
class Piece:
    """A {…} part of a text: the tokens inside the braces."""
    tokens: list
    col: int
    end: int


@dataclass(eq=False)
class Line:
    number: int
    indent: int
    raw: str
    tokens: list
    note: str | None = None
    note_col: int | None = None
    body: list = field(default_factory=list)
    problem: Problem | None = None
    is_header: bool = False

    def __repr__(self):
        return f"<line {self.number}: {self.raw.strip()!r}>"


def normalize(text):
    if text.startswith("﻿"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")


def tokenize(text, start=0, stop=None, line_no=None, in_braces=False):
    """Split one line (or the inside of a {…} piece) into tokens.

    Returns (tokens, note, note_col). Raises Problem for text that is never closed."""
    stop = len(text) if stop is None else stop
    tokens, i = [], start
    while i < stop:
        ch = text[i]
        if ch.isspace():
            i += 1
        elif ch == "#" and not in_braces:
            return tokens, text[i + 1:stop].strip(), i
        elif ch in OPENERS:
            tok, i = read_text(text, i, stop, line_no)
            tokens.append(tok)
        elif ch.isdigit() or (ch in CURRENCY and i + 1 < stop and text[i + 1].isdigit()):
            i = read_number(text, i, stop, tokens, line_no)
        elif ch.isalpha() or ch == "_":
            i = read_word(text, i, stop, tokens)
        elif ch in APOSTROPHES:
            # A quote mark that isn't part of a word: 'text' written with single quotes.
            j = i + 1
            while j < stop and text[j] not in APOSTROPHES:
                j += 1
            raw = text[i:min(j + 1, stop)]
            tokens.append(Token("squote", raw, raw, i, min(j + 1, stop)))
            i = min(j + 1, stop)
        else:
            sym = next((s for s in SYMBOLS if text.startswith(s, i)), None)
            if sym is None:
                sym = DASHES.get(ch, ch)
                tokens.append(Token("symbol", ch, sym, i, i + 1))
                i += 1
            else:
                tokens.append(Token("symbol", sym, sym, i, i + len(sym)))
                i += len(sym)
    return tokens, None, None


def read_word(text, i, stop, tokens):
    j = i
    while j < stop and (text[j].isalnum() or text[j] == "_"):
        j += 1
    word = text[i:j]
    # Contractions (isn't) and possessives (sale's).
    if j + 1 < stop and text[j] in APOSTROPHES and text[j + 1].isalpha():
        k = j + 1
        while k < stop and text[k].isalpha():
            k += 1
        tail = text[j + 1:k].lower()
        whole = (word + "'" + tail).lower()
        if whole in CONTRACTIONS:
            first, second = CONTRACTIONS[whole]
            tokens.append(Token("word", text[i:k], first, i, k))
            tokens.append(Token("word", text[i:k], second, i, k))
            return k
        if tail == "s" and (k >= stop or not (text[k].isalnum() or text[k] == "_")):
            tokens.append(Token("word", word, word.lower(), i, j))
            tokens.append(Token("poss", text[j:k], "'s", j, k))
            return k
    tokens.append(Token("word", word, word.lower(), i, j))
    return j


def read_number(text, i, stop, tokens, line_no):
    m = NUMBER.match(text, i, stop)
    raw = m.group(0)
    end = m.end()
    # 1,000 is a number written with a comma.
    if end + 3 < stop + 1 and re.match(r",\d{3}(?!\d)", text[end:stop]):
        j = end
        while re.match(r",\d{3}(?!\d)", text[j:stop]):
            j += 4
        raw_all = text[i:j]
        raise Problem(
            f"Write {raw_all.replace(',', '').lstrip(CURRENCY)} without the comma.",
            "Plain uses commas to separate items in a list, so numbers are written without them.",
            line=line_no, col=i, end=j)
    digits = raw.lstrip(CURRENCY)
    percent = digits.endswith("%")
    digits = digits.rstrip("%")
    value = Decimal(digits)
    if percent:
        value = value / 100
    if end < stop and (text[end].isalpha() or text[end] == "_"):
        # A word that starts with digits, like 2nd. Read it as a word.
        return read_word(text, i, stop, tokens)
    tokens.append(Token("number", raw, digits, i, end, value, percent))
    return end


def read_text(text, i, stop, line_no):
    """Read "…" (or “…”) with {…} pieces. "" is one quote mark; {{ and }} are braces."""
    opener = text[i]
    closer = OPENERS[opener]
    pieces, buf, j = [], [], i + 1
    while j < stop:
        ch = text[j]
        if ch == closer:
            if closer == '"' and j + 1 < stop and text[j + 1] == '"':
                buf.append('"')
                j += 2
                continue
            if buf:
                pieces.append("".join(buf))
            raw = text[i:j + 1]
            return Token("text", raw, raw, i, j + 1, pieces), j + 1
        if ch == "{":
            if j + 1 < stop and text[j + 1] == "{":
                buf.append("{")
                j += 2
                continue
            end = find_closing_brace(text, j, stop, line_no)
            inner, _, _ = tokenize(text, j + 1, end, line_no, in_braces=True)
            if not inner:
                raise Problem("Put a name or a value inside the { }, or write {{ }} to show the braces.",
                              "Plain puts the value of whatever is inside { } into the text.",
                              line=line_no, col=j, end=end + 1)
            if buf:
                pieces.append("".join(buf))
                buf = []
            pieces.append(Piece(inner, j, end + 1))
            j = end + 1
            continue
        if ch == "}":
            if j + 1 < stop and text[j + 1] == "}":
                buf.append("}")
                j += 2
                continue
            raise Problem("Write }} to show a closing brace, or add the { that goes with it.",
                          "In text, { and } mark the part where Plain puts in a value.",
                          line=line_no, col=j, end=j + 1)
        buf.append(ch)
        j += 1
    close = "”" if opener == "“" else '"'
    raise Problem(f"Add a {close} at the end of the text.",
                  "Text starts and ends with a double quote mark, so Plain knows where it stops.",
                  line=line_no, col=i, end=stop)


def find_closing_brace(text, j, stop, line_no):
    depth, k = 0, j
    in_text = None
    while k < stop:
        ch = text[k]
        if in_text:
            if ch == in_text:
                in_text = None
        elif ch in OPENERS:
            in_text = OPENERS[ch]
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return k
        k += 1
    raise Problem("Add the } that closes this { in your text.",
                  "In text, { and } mark the part where Plain puts in a value.",
                  line=line_no, col=j, end=j + 1)


def indent_of(raw):
    width = 0
    for ch in raw:
        if ch == " ":
            width += 1
        elif ch == "\t":
            width += 4
        else:
            break
    return width


def read_lines(text):
    """Every non-blank line as a Line with tokens. Tokenizing problems are kept on the line."""
    lines = []
    for number, raw in enumerate(normalize(text).split("\n"), start=1):
        if not raw.strip():
            continue
        line = Line(number, indent_of(raw), raw, [])
        try:
            line.tokens, line.note, line.note_col = tokenize(raw, line_no=number)
        except Problem as problem:
            line.problem = problem
        if not line.tokens and line.problem is None:
            continue  # a note on its own line
        lines.append(line)
    return lines


HEADER_STARTS = {"if", "otherwise", "else", "repeat", "for", "while", "until", "how", "try"}


def looks_like_header(line):
    words = [t.norm for t in line.tokens if t.kind == "word"]
    if not words:
        return False
    first = words[0]
    if line.tokens and line.tokens[-1].norm == ":":
        return True
    if first == "if":
        if words[1:3] in (["that", "fails"], ["it", "fails"]):
            return True
        # One-line form: if CHECK then STEP
        norms = [t.norm for t in line.tokens]
        if "then" in norms:
            k = norms.index("then")
            return k == len(norms) - 1 or all(t.norm in ".:!" for t in line.tokens[k + 1:])
        return True
    if first in ("otherwise", "else"):
        norms = [t.norm for t in line.tokens]
        if len(norms) > 1 and norms[1] == "if" and "then" in norms:
            k = norms.index("then")
            return k == len(norms) - 1
        return True
    return first in HEADER_STARTS


def is_end_line(line):
    words = [t.norm for t in line.tokens if t.norm not in ".:!;"]
    return bool(words) and words[0] == "end" and len(words) <= 3


def build_blocks(lines):
    """Group lines into a tree by indentation. Returns (top lines, problems)."""
    problems, top = [], []
    stack = [(0, top, None)]   # frames of (indent, body list, header line)
    previous = None
    for line in lines:
        line.is_header = looks_like_header(line) if line.problem is None else False
        if is_end_line(line):
            headers = [frame for frame in stack if frame[2] is not None]
            match = next((f for f in reversed(headers) if f[2].indent == line.indent), None)
            if match is not None:
                while stack[-1] is not match:
                    stack.pop()
                stack.pop()
                previous = None
                continue
            problems.append(Problem(
                'Line up this "end" with the line that starts its steps, or delete it.',
                'Plain doesn\'t need "end" lines. It goes by how far each line is moved to the right.',
                line=line.number, col=line.indent, end=len(line.raw.rstrip())))
            continue
        if line.indent > stack[-1][0]:
            if previous is not None and not previous.is_header and previous.problem is None \
                    and first_word(previous) in ("if", "otherwise", "else") and line.indent > previous.indent:
                previous.is_header = True   # "if … then …" with steps under it
            if previous is not None and previous.is_header and line.indent > previous.indent \
                    and stack[-1][1] and stack[-1][1][-1] is previous:
                stack.append((line.indent, previous.body, previous))
            else:
                problems.append(indent_problem(line, previous))
        else:
            while len(stack) > 1 and stack[-1][0] > line.indent:
                stack.pop()
            if stack[-1][0] != line.indent:
                problems.append(indent_problem(line, previous))
        stack[-1][1].append(line)
        previous = line
    check_empty_headers(top, problems)
    return top, problems


def indent_problem(line, previous):
    return Problem(
        "Move this line so it lines up with the steps above it.",
        "Plain uses how far each line is moved to the right to see which steps belong together.",
        line=line.number, col=0, end=max(line.indent, 1))


def check_empty_headers(lines, problems, following=None):
    for index, line in enumerate(lines):
        if line.is_header and not line.body:
            word = first_word(line)
            if word in ("for", "while", "until"):
                word = "repeat"
            if word == "else":
                word = "otherwise"
            nxt = lines[index + 1] if index + 1 < len(lines) else None
            if nxt is not None:
                problems.append(Problem(
                    f'Move this line 4 spaces to the right (or press Tab), so it belongs to the "{word}" on line {line.number}.',
                    f'Steps that belong to "{word}" sit further right than the "{word}" line itself.',
                    line=nxt.number, col=nxt.indent, end=nxt.indent + 1,
                    try_lines=[line.raw.strip(), "    " + nxt.raw.strip()]))
            else:
                problems.append(Problem(
                    f'Add the steps that belong to this "{word}" on the lines below it, moved 4 spaces to the right.',
                    f'A "{word}" line needs at least one step under it.',
                    line=line.number, col=line.indent, end=len(line.raw.rstrip())))
        check_empty_headers(line.body, problems)


def first_word(line):
    for t in line.tokens:
        if t.kind == "word":
            return t.norm
    return ""
