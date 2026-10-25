"""Build plain-lang.dev into site/dist. Standard library only.

    python site/build.py            build the site
    python site/build.py --serve    build, then serve it on http://localhost:8000
"""

import hashlib
import html
import http.server
import json
import re
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DOCS = SITE / "docs"
STATIC = SITE / "static"
DIST = SITE / "dist"
CACHE = SITE / ".cache"
sys.path.insert(0, str(ROOT / "src"))

PYODIDE = "314.0.7"
PYODIDE_FILES = {
    "pyodide.mjs": "6f1d60f7bf529beb300f0f47983c921d3982363640ba20af0e38efdddbc66109",
    "pyodide.asm.mjs": "f7cdc8ece80678ceb712f8e65ebe6d3a83203a180c399865f49612a051693635",
    "pyodide.asm.wasm": "cc36e3cab04fdfc9a63ff13eb52eae2b911bf46c025cc7b281f394bd3de1d5e6",
    "pyodide-lock.json": "5dc2fc119108bc148c7457dc86e7675b5c87e1cafd420b9c34c1eaef7b36c010",
    "python_stdlib.zip": "fa1957e5777068fc4f7437f96d860ae2fbe9c19732ba06c84e004ec16dd7dd7a",
}

NAV = [("Try it", "/"), ("Learn", "/learn/"), ("Examples", "/examples/"), ("All phrases", "/phrases/"),
       ("Install", "/install/")]

HEADERS = {
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Embedder-Policy": "require-corp",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": ("default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; "
                                "worker-src 'self'; connect-src 'self' https:; img-src 'self' data:; "
                                "style-src 'self'"),
}


# Markdown -----------------------------------------------------------------------

def inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", lambda m: f"<code>{m.group(1)}</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*([^*]+)\*(?![\w*])", r"<em>\1</em>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def fences(text):
    """Split markdown into ("text", lines) and ("fence", info, body) parts."""
    parts, buf, lines, k = [], [], text.split("\n"), 0
    while k < len(lines):
        line = lines[k]
        if line.startswith("```"):
            if buf:
                parts.append(("text", buf))
                buf = []
            info = line[3:].strip()
            body = []
            k += 1
            while k < len(lines) and not lines[k].startswith("```"):
                body.append(lines[k])
                k += 1
            parts.append(("fence", info, "\n".join(body)))
        else:
            buf.append(line)
        k += 1
    if buf:
        parts.append(("text", buf))
    return parts


def try_link(code, files):
    from base64 import urlsafe_b64encode
    encoded = urlsafe_b64encode(code.encode()).decode().rstrip("=")
    link = f"/#code={encoded}"
    if files:
        link += "&files=" + ",".join(files)
    return link


def block_options(info):
    words = info.split()
    options = {"kind": words[0] if words else ""}
    for word in words[1:]:
        key, _, value = word.partition("=")
        options[key] = value or True
    return options


def markdown(text):
    """Returns (html, title, headings)."""
    out, title, headings = [], None, []
    for part in fences(text):
        if part[0] == "fence":
            _, info, body = part
            options = block_options(info)
            kind = options["kind"]
            code = html.escape(body)
            if kind == "plain":
                files = [f for f in str(options.get("files", "")).split(",") if f]
                button = "" if options.get("fragment") else \
                    f'<a class="try" href="{try_link(body, files)}">Try it</a>'
                out.append(f'<div class="example"><pre class="plain"><code>{code}</code></pre>{button}</div>')
            elif kind == "answers":
                out.append(f'<p class="label">What you type:</p><pre class="answers"><code>{code}</code></pre>')
            elif kind == "output":
                out.append(f'<p class="label">What it shows:</p><pre class="output"><code>{code}</code></pre>')
            elif kind == "problem":
                out.append(f'<p class="label">What Plain says:</p><pre class="problem"><code>{code}</code></pre>')
            else:
                out.append(f'<pre class="{html.escape(kind) or "text"}"><code>{code}</code></pre>')
            continue
        paragraph, items, ordered = [], [], False

        def flush():
            nonlocal paragraph, items
            if paragraph:
                out.append("<p>" + inline(" ".join(paragraph)) + "</p>")
                paragraph = []
            if items:
                tag = "ol" if ordered else "ul"
                out.append(f"<{tag}>" + "".join(f"<li>{inline(i)}</li>" for i in items) + f"</{tag}>")
                items = []

        for line in part[1]:
            m = re.match(r"^(#{1,3})\s+(.*)$", line)
            if m:
                flush()
                level, words = len(m.group(1)), m.group(2).strip()
                given = re.search(r"\s*\{#([a-z0-9-]+)\}$", words)
                if given:
                    words = words[:given.start()]
                if level == 1 and title is None:
                    title = words
                anchor = given.group(1) if given else slug(words)
                headings.append(words)
                out.append(f'<h{level} id="{anchor}">{inline(words)}</h{level}>')
            elif re.match(r"^\s*[-*]\s+", line):
                if paragraph:
                    flush()
                ordered = False
                items.append(re.sub(r"^\s*[-*]\s+", "", line))
            elif re.match(r"^\s*\d+\.\s+", line):
                if paragraph:
                    flush()
                ordered = True
                items.append(re.sub(r"^\s*\d+\.\s+", "", line))
            elif not line.strip():
                flush()
            elif items and line.startswith("  "):
                items[-1] += " " + line.strip()
            else:
                if items:
                    flush()
                paragraph.append(line.strip())
        flush()
    return "\n".join(out), title, headings


# Pages --------------------------------------------------------------------------

def page(title, body, path, description="", scripts=()):
    nav = "".join(
        f'<a href="{href}"{" aria-current=\"page\"" if (href == path or (href != "/" and path.startswith(href))) else ""}>{name}</a>'
        for name, href in NAV)
    script_tags = "".join(f'<script type="module" src="{s}"></script>' for s in scripts)
    full_title = "Plain" if title == "Plain" else f"{title} · Plain"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(full_title)}</title>
<meta name="description" content="{html.escape(description)}">
<link rel="stylesheet" href="/style.css">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
{script_tags}
</head>
<body>
<a class="skip" href="#main">Skip to the page</a>
<header class="top">
  <a class="brand" href="/">Plain</a>
  <nav aria-label="Main">{nav}</nav>
  <form class="search" role="search" action="/search/">
    <label for="q" class="hidden">Search</label>
    <input id="q" name="q" type="search" placeholder="Search" autocomplete="off">
  </form>
</header>
<main id="main">
{body}
</main>
<footer>
  <p><a href="/help/">Get help</a> · <a href="/install/">Install Plain</a> · plain-lang.dev</p>
  <p>Plain is inspired by the <a href="https://en.wikipedia.org/wiki/Plain_language">plain language movement</a>. <a href="/why/">See how</a>.</p>
</footer>
<script type="module" src="/search.js"></script>
</body>
</html>
"""


def write(path, text):
    target = DIST / path.lstrip("/")
    if path.endswith("/"):
        target = target / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


IDEAS = "Ideas to change:"


def example_programs():
    out = []
    for path in sorted((ROOT / "examples").glob("*.plain")):
        lines = path.read_text(encoding="utf-8").split("\n")
        notes = []
        for line in lines:
            if line.startswith("#"):
                notes.append(line.lstrip("# ").strip())
            else:
                break
        title = notes[0] if notes else path.stem
        files = {}
        for name in re.findall(r'"([^"{}]+\.(?:csv|txt|json))"', "\n".join(lines)):
            data = path.parent / name
            if data.exists():
                files[name] = data.read_text(encoding="utf-8")
        # "# Ideas to change:", then one "# - idea" line each (change 23: not "# Try:", next to a real try step).
        ideas = notes[notes.index(IDEAS) + 1:] if IDEAS in notes else []
        out.append({"name": path.stem, "title": title, "about": notes[1] if len(notes) > 1 else "",
                    "change": [n[1:].strip() for n in ideas if n.startswith("-")],
                    "code": "\n".join(lines).strip() + "\n", "files": files})
    order = ["hello", "guess", "big_sales", "github", "tips", "todo"]
    out.sort(key=lambda e: (order.index(e["name"]) if e["name"] in order else len(order), e["name"]))
    return out


def home_page(examples):
    intro, _, _ = markdown((DOCS / "home.md").read_text(encoding="utf-8"))
    data = json.dumps([{k: e[k] for k in ("name", "title", "code", "files")} for e in examples])
    body = f"""
<section class="hero">{intro}</section>
<section class="playground" aria-label="Try Plain">
  <div class="bar">
    <label>Example <select id="examples"></select></label>
    <span class="grow"></span>
    <button id="run" class="primary" disabled>Run</button>
    <button id="stop" disabled>Stop</button>
    <button id="copy">Copy link</button>
  </div>
  <div class="editor">
    <pre class="gutter" id="gutter" aria-hidden="true"></pre>
    <textarea id="code" spellcheck="false" autocapitalize="off" autocomplete="off" aria-label="Your program"></textarea>
  </div>
  <div class="tabs" role="tablist">
    <button role="tab" id="tab-output" aria-selected="true" aria-controls="output">What your program shows</button>
    <button role="tab" id="tab-files" aria-selected="false" aria-controls="files">Files</button>
  </div>
  <div id="output" class="panel" role="tabpanel" aria-live="polite"></div>
  <div id="files" class="panel" role="tabpanel" hidden>
    <p class="note">These files stay in this browser tab only. Download any you want to keep. Files you add from your computer stay in your browser and are never sent anywhere.</p>
    <ul id="file-list"></ul>
    <div class="file-actions">
      <label class="button">Add a file from your computer <input id="upload" type="file" hidden></label>
      <button id="reset-files">Put back the example's files</button>
    </div>
    <div id="file-view" hidden>
      <p><strong id="file-name"></strong></p>
      <textarea id="file-text" spellcheck="false"></textarea>
      <p><button id="file-save">Keep these changes</button> <a id="file-download" class="button" download>Download</a></p>
    </div>
  </div>
  <p id="status" role="status">Getting Plain ready. This takes a few seconds the first time.</p>
</section>
<script id="examples-data" type="application/json">{html.escape(data, quote=False)}</script>
"""
    return page("Plain", body, "/", "Plain is a programming language you write in plain English. Try it in your browser.",
                scripts=["/playground.js"])


def phrases_page():
    from plainlang.registry import reference
    from plainlang.words import SPECIAL_WORDS
    topics = {}
    for entry in reference():
        topics.setdefault(entry["topic"], []).append(entry)
    parts = ["<h1>All phrases</h1>",
             "<p>Every wording Plain understands, with an example you can run. Type a word to find a phrase.</p>",
             '<p><label for="filter">Find a phrase </label><input id="filter" type="search" placeholder="for example: sort"></p>']
    labels = {"changes": "changes a file", "internet": "sends data over the internet", "reads": "reads a file or web page"}
    for topic, items in topics.items():
        parts.append(f'<h2 id="{slug(topic)}">{html.escape(topic)}</h2><dl class="phrases">')
        for item in items:
            effect = "".join(f'<span class="tag">{labels[e]}</span>' for e in item["effects"] if e in labels)
            parts.append(f'<div class="phrase"><dt><code>{html.escape(item["wording"])}</code> {effect}</dt>'
                         f'<dd><p>{html.escape(item["doc"])}</p>'
                         f'<pre class="plain"><code>{html.escape(item["example"])}</code></pre></dd></div>')
        parts.append("</dl>")
    parts.append('<h2 id="special-words">Plain\'s special words</h2>')
    parts.append("<p>Plain uses these words to tell where a name ends, so they can't be part of a name:</p>")
    parts.append("<p class=\"words\">" + " ".join(f"<code>{w}</code>" for w in sorted(SPECIAL_WORDS)) + "</p>")
    other, _, _ = markdown(other_ways_markdown())
    parts.append(f'<section class="other-ways">{other}</section>')
    return page("All phrases", "\n".join(parts), "/phrases/", "Every wording Plain understands.",
                scripts=["/phrases.js"])


def other_ways_markdown():
    """The "Other ways you can write things" section, made from words.py and the phrase registry (change 2)."""
    from plainlang.registry import other_ways
    ways = other_ways()
    lines = ["## Other ways you can write things", "",
             "Plain understands these too, so you don't have to remember the exact words. Each one means "
             "exactly the same as the main wording. The lessons and examples use only the main wording.", "",
             "### Plain changes these to the main words", "",
             "`plain explain` shows the main words, and `plain tidy` writes them into your file for you.", ""]
    lines += [f"- {way.sentence()}" for way in ways if way.tidy]
    lines += ["", "### Plain also understands these", "",
              "They mean the same as the main words, and `plain tidy` leaves them as you wrote them.", ""]
    lines += [f"- {way.sentence()}" for way in ways if not way.tidy]
    return "\n".join(lines) + "\n"


def examples_page(examples):
    intro, _, _ = markdown((DOCS / "examples.md").read_text(encoding="utf-8"))
    parts = [intro]
    for e in examples:
        link = try_link(e["code"], list(e["files"]))
        change = "".join(f"<li>{html.escape(c)}</li>" for c in e["change"])
        parts.append(f'<section class="example-card" id="{e["name"]}"><h2>{html.escape(e["title"])}</h2>'
                     f'<p>{html.escape(e["about"])}</p>'
                     f'<div class="example"><pre class="plain"><code>{html.escape(e["code"])}</code></pre>'
                     f'<a class="try" href="{link}">Try it</a></div>'
                     + (f"<h3>Things you could change</h3><ul>{change}</ul>" if change else "") + "</section>")
    return page("Examples", "\n".join(parts), "/examples/", "Small Plain programs you can run and change.")


def doc_pages():
    pages, search = [], []
    for path in sorted(DOCS.rglob("*.md")):
        rel = path.relative_to(DOCS)
        if rel.parts[0] in ("home.md", "examples.md"):
            continue
        body, title, headings = markdown(path.read_text(encoding="utf-8"))
        if rel.name == "index.md":
            url = "/" + "/".join(rel.parts[:-1]) + "/" if len(rel.parts) > 1 else "/"
        else:
            url = "/" + "/".join(rel.with_suffix("").parts) + "/"
        if rel.parts[0] == "learn" and rel.name != "index.md":
            body = lesson_nav(rel) + body + lesson_nav(rel, bottom=True)
        pages.append((url, title or rel.stem, body))
        search.append({"title": title or rel.stem, "url": url, "headings": headings})
    return pages, search


def lessons():
    return sorted(p for p in (DOCS / "learn").glob("*.md") if p.name != "index.md")


def lesson_nav(rel, bottom=False):
    all_lessons = lessons()
    names = [p.name for p in all_lessons]
    k = names.index(rel.name)
    links = []
    if k > 0:
        prev = all_lessons[k - 1]
        links.append(f'<a href="/learn/{prev.stem}/">← {lesson_title(prev)}</a>')
    links.append('<a href="/learn/">All lessons</a>')
    if k + 1 < len(all_lessons):
        nxt = all_lessons[k + 1]
        links.append(f'<a href="/learn/{nxt.stem}/">{lesson_title(nxt)} →</a>')
    return f'<nav class="lesson-nav" aria-label="Lessons">{" · ".join(links)}</nav>'


def lesson_title(path):
    for line in path.read_text(encoding="utf-8").split("\n"):
        if line.startswith("# "):
            return html.escape(line[2:].strip())
    return path.stem


# Files the playground needs ----------------------------------------------------------

def pyodide_files():
    target = DIST / "pyodide" / PYODIDE
    target.mkdir(parents=True, exist_ok=True)
    cache = CACHE / "pyodide" / PYODIDE
    cache.mkdir(parents=True, exist_ok=True)
    for name, digest in PYODIDE_FILES.items():
        cached = cache / name
        if not cached.exists() or sha256(cached) != digest:
            url = f"https://cdn.jsdelivr.net/npm/pyodide@{PYODIDE}/{name}"
            print(f"Downloading {url}")
            with urllib.request.urlopen(url, timeout=60) as response:
                cached.write_bytes(response.read())
        if sha256(cached) != digest:
            raise SystemExit(f"{name} doesn't match its pinned SHA-256, so the build stopped.")
        shutil.copy(cached, target / name)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plain_zip():
    target = DIST / "play" / "plainlang.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    src = ROOT / "src"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted((src / "plainlang").rglob("*.py")):
            z.write(path, path.relative_to(src))


def play_files(examples):
    folder = DIST / "play" / "files"
    folder.mkdir(parents=True, exist_ok=True)
    for path in (DOCS / "files").glob("*"):
        shutil.copy(path, folder / path.name)
    for e in examples:
        for name, text in e["files"].items():
            (folder / name).write_text(text, encoding="utf-8")


def headers_file():
    lines = ["/*"] + [f"  {k}: {v}" for k, v in HEADERS.items()]
    lines += ["", f"/pyodide/*", "  Cache-Control: public, max-age=31536000, immutable", ""]
    (DIST / "_headers").write_text("\n".join(lines), encoding="utf-8")


def build():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    for path in STATIC.rglob("*"):
        if path.is_file():
            target = DIST / path.relative_to(STATIC)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(path, target)
    examples = example_programs()
    write("/", home_page(examples))
    write("/phrases/", phrases_page())
    write("/examples/", examples_page(examples))
    pages, search = doc_pages()
    for url, title, body in pages:
        write(url, page(title, body, url, ""))
    from plainlang.registry import reference
    search.append({"title": "All phrases", "url": "/phrases/", "headings": [e["wording"] for e in reference()]})
    search.append({"title": "Examples", "url": "/examples/", "headings": [e["title"] for e in examples]})
    (DIST / "search.json").write_text(json.dumps(search), encoding="utf-8")
    write("/search/", page("Search", '<h1>Search</h1><ul id="results"></ul>', "/search/", ""))
    write("/404.html", page("Page not found", "<h1>Page not found</h1><p>Go to the <a href=\"/\">home page</a> "
                                               "to try Plain, or <a href=\"/learn/\">start learning</a>.</p>", "/404", ""))
    plain_zip()
    play_files(examples)
    pyodide_files()
    headers_file()
    print(f"Built the site in {DIST.relative_to(ROOT)}.")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def end_headers(self):
        for key, value in HEADERS.items():
            self.send_header(key, value)
        super().end_headers()

    def log_message(self, *args):
        pass


def serve(port=8000):
    Handler.extensions_map[".mjs"] = "text/javascript"
    Handler.extensions_map[".wasm"] = "application/wasm"
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Serving the site at http://localhost:{port} (press Ctrl-C to stop).")
    server.serve_forever()


if __name__ == "__main__":
    build()
    if "--serve" in sys.argv:
        serve(int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8000)
