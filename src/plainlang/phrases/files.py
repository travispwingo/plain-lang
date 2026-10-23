"""Files: text, CSV and JSON. One "read" covers files and web pages."""

import csv
import io
import json
import re
from decimal import Decimal
from pathlib import Path

from ..problems import Problem
from ..registry import List, Text, Value, step, value
from ..values import (Record, auto_number, kind_name, number_text, quoted, show_inline, show_table,
                      show_value)

TOPIC = "Files"
SPREADSHEET_ENDINGS = {".xlsx", ".xls", ".numbers", ".ods"}


def is_address(source):
    return source.lower().startswith(("https://", "http://"))


def path_for(run, name):
    if not name.strip():
        raise Problem('Write a file name in quotes, like "notes.txt".', "The file name is empty.")
    path = Path(name).expanduser() if name.startswith("~") else Path(name)
    if path.is_absolute() or name.startswith("~"):
        if not getattr(run.host, "can_use_any_folder", False):
            raise Problem(f'Use a file name without a folder at the start, like "{path.name}".',
                          "Here, files live in your program's own folder.")
        return path
    return run.host.folder / path


def spreadsheet_problem(name):
    stem = Path(name).stem
    return Problem(
        f'Save "{name}" as a CSV file, then read "{stem}.csv".',
        "Plain reads spreadsheets saved as CSV. In Excel, choose File > Save As > CSV. "
        "In Google Sheets, choose File > Download > CSV.", focus=f'"{name}"')


def decode(data):
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def from_json(value):
    if isinstance(value, dict):
        return Record({k: from_json(v) for k, v in value.items()})
    if isinstance(value, list):
        return [from_json(v) for v in value]
    return value


def json_text(value, indent=None, depth=0):
    """A value as JSON. Numbers keep the exact digits Plain shows, never going through float."""
    if isinstance(value, Record):
        parts = [f"{json.dumps(str(k), ensure_ascii=False)}: {json_text(v, indent, depth + 1)}"
                 for k, v in value.data.items()]
        return json_group("{", parts, "}", indent, depth)
    if isinstance(value, list):
        return json_group("[", [json_text(v, indent, depth + 1) for v in value], "]", indent, depth)
    if isinstance(value, Decimal):
        return number_text(value)
    return json.dumps(value, ensure_ascii=False)


def json_group(start, parts, stop, indent, depth):
    if not parts:
        return start + stop
    if indent is None:
        return start + ", ".join(parts) + stop
    inside = "\n" + " " * (indent * (depth + 1))
    return start + inside + ("," + inside).join(parts) + "\n" + " " * (indent * depth) + stop


def parse_json(text):
    return from_json(json.loads(text, parse_float=Decimal, parse_int=Decimal))


def parse_csv(text):
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    # The delimiter is the one that splits the header line into the most fields. Commas
    # inside quotes don't count. A tie goes to the comma.
    delimiter = max((",", ";", "\t"), key=lambda d: len(next(csv.reader([lines[0]], delimiter=d))))
    rows = [row for row in csv.reader(io.StringIO(text), delimiter=delimiter) if any(c.strip() for c in row)]
    if not rows:
        return []
    keys = unique_keys([k.strip() or f"column {n}" for n, k in enumerate(rows[0], start=1)])
    table = []
    for row in rows[1:]:
        record = Record()
        for n, key in enumerate(keys):
            cell = row[n] if n < len(row) else ""
            record.data[key] = None if not cell.strip() else auto_number(cell)
        table.append(record)
    return table


def unique_keys(keys):
    """Column names, with a number added to a repeated one ("a", "a 2") so no column is lost."""
    out = []
    for key in keys:
        name, n = key, 1
        while name in out:
            n += 1
            name = f"{key} {n}"
        out.append(name)
    return out


def read_file(run, name):
    path = path_for(run, name)
    ending = path.suffix.lower()
    if ending in SPREADSHEET_ENDINGS:
        raise spreadsheet_problem(name)
    if not path.exists():
        raise missing_file(run, name, path)
    if path.is_dir():
        raise Problem(f'Write "the files in "{name}"" to list a folder.', f'"{name}" is a folder, not a file.')
    text = decode(path.read_bytes())
    if ending == ".csv":
        return parse_csv(text)
    if ending == ".json":
        return parse_json(text)
    return text[:-1] if text.endswith("\n") else text   # the file's last line break isn't part of the text


def alternative(name):
    path = Path(name)
    return str(path.with_name(f"{path.stem} 2{path.suffix}"))


def missing_file(run, name, path):
    import difflib
    folder = path.parent
    try:
        names = [p.name for p in folder.iterdir() if p.is_file()]
    except OSError:
        names = []
    close = difflib.get_close_matches(path.name, names, n=1, cutoff=0.6)
    where = "in the same folder as your program"
    if close:
        better = (Path(name).parent / close[0]).as_posix()    # keep the folder you wrote
        return Problem(f'Write "{better}" instead of "{name}".', f'There\'s no file "{name}" {where}.',
                       focus=f'"{name}"')
    return Problem(f'Check the file name "{name}".', f'There\'s no file "{name}" {where}.', focus=f'"{name}"')


@step("read {source}", example='read "sales.csv" and call it sales', effects={"reads"}, topic=TOPIC)
def read(run, source: Text) -> Value:
    """Reads a file or a web page. A .csv file gives a table, .json gives records and lists, and anything else gives text. A web address gives the page; JSON replies become records and lists."""
    if is_address(source):
        from .web import read_web
        return read_web(run, source)
    if re.match(r"^www\.|^[\w-]+\.(com|org|net|dev|io|edu|gov)(/|$)", source.strip(), flags=re.IGNORECASE):
        raise Problem(f'Start the web address with "https://", like "https://{source.strip()}".',
                      "Without https:// at the start, Plain looks for a file with that name.",
                      focus=f'"{source}"')
    return read_file(run, source)


@step("read the lines of {source}", example='read the lines of "todos.txt" and call it todos',
      effects={"reads"}, topic=TOPIC)
def read_lines(run, source: Text) -> List:
    """Reads a file (or web page) as a list with one item for each line."""
    if is_address(source):
        from .web import read_web
        text = read_web(run, source, raw=True)
    else:
        path = path_for(run, source)
        if path.suffix.lower() in SPREADSHEET_ENDINGS:
            raise spreadsheet_problem(source)
        if not path.exists():
            raise missing_file(run, source, path)
        text = decode(path.read_bytes())
    return [auto_number(line) for line in text.splitlines()]


def is_table(value):
    return isinstance(value, list) and bool(value) and all(isinstance(v, Record) for v in value)


def file_text(value):
    """A value as text for a file: the way "show" shows it, but a table keeps every row."""
    return show_table(value, limit=None) if is_table(value) else show_value(value)


def as_lines(value):
    if isinstance(value, list) and not is_table(value):
        return "\n".join(show_inline(v) for v in value) + ("\n" if value else "")
    text = file_text(value)
    return text if text.endswith("\n") or not text else text + "\n"


def csv_text(value):
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    if isinstance(value, Record):
        value = [value]
    if isinstance(value, list) and value and all(isinstance(v, Record) for v in value):
        columns = []
        for row in value:
            for key in row.data:
                if key not in columns:
                    columns.append(key)
        writer.writerow(columns)
        for row in value:
            writer.writerow(["" if row.data.get(c) is None else show_value(row.data.get(c)) for c in columns])
    elif isinstance(value, list):
        for item in value:
            writer.writerow(["" if item is None else show_inline(item)])
    else:
        writer.writerow([show_value(value)])
    return out.getvalue()


@step("save {value} to {file}", example='save todos to "todos.txt"', effects={"changes"}, topic=TOPIC)
def save(run, value: Value, file: Text) -> None:
    """Replaces the file. To .csv a table saves as rows; to .json any value saves as JSON; anything else saves as text, with a list as one item per line."""
    path = path_for(run, file)
    ending = path.suffix.lower()
    if ending in SPREADSHEET_ENDINGS:
        raise Problem(f'Save to a .csv file instead, like "{Path(file).stem}.csv".',
                      "Plain saves spreadsheets as CSV, which Excel and Google Sheets can open.")
    if ending == ".csv":
        text = csv_text(value)
    elif ending == ".json":
        text = json_text(value, indent=2) + "\n"
    else:
        text = as_lines(value)
    if not path.parent.exists():
        path.parent.mkdir(parents=True)
    path.write_text(text, encoding="utf-8", newline="")


@step("add {value} to the file {file}", example='add "Saw a fox" to the file "diary.txt"',
      effects={"changes"}, topic=TOPIC)
def add_to_file(run, value: Value, file: Text) -> None:
    """Adds one line at the end of the file, and makes the file if needed."""
    path = path_for(run, file)
    line = file_text(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="") as handle:
        handle.write(line + "\n")


@value("the file {file} exists", example='if the file "todos.txt" exists', topic=TOPIC)
def file_exists(run, file: Text) -> Value:
    """Yes if the file is there, no if it isn't."""
    return path_for(run, file).exists()


@value("the file {file} does not exist", example='if the file "todos.txt" does not exist', topic=TOPIC)
def file_missing(run, file: Text) -> Value:
    """Yes if the file isn't there."""
    return not path_for(run, file).exists()


@value("the files in {folder}", example='show the files in "photos"', topic=TOPIC)
def files_in(run, folder: Text) -> List:
    """The names of the files in a folder, A to Z."""
    path = path_for(run, folder) if folder not in (".", "") else run.host.folder
    if not path.is_dir():
        raise Problem(f'Check the folder name "{folder}".', f'There\'s no folder "{folder}" next to your program.')
    return sorted((p.name for p in path.iterdir() if p.is_file()), key=str.casefold)


@step("rename {file} to {new_name}", example='rename "old.txt" to "new.txt"', effects={"changes"}, topic=TOPIC)
def rename(run, file: Text, new_name: Text) -> None:
    """Gives a file a new name."""
    path = path_for(run, file)
    if not path.exists():
        raise missing_file(run, file, path)
    target = path_for(run, new_name)
    if not target.parent.is_dir():
        folder = Path(new_name).parent.as_posix()
        raise Problem(f'Check the folder name "{folder}".',
                      f'There\'s no folder "{folder}" next to your program. Saving a file into a folder '
                      "makes the folder.", focus=f'"{new_name}"')
    if target.exists():
        raise Problem(f'Choose a new name that isn\'t taken, like "{alternative(new_name)}".',
                      f'There\'s already a file "{new_name}", and Plain never replaces a file when it renames one.')
    path.rename(target)
