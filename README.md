# Plain

Write steps in everyday English, then run them.

```text
ask "What is your name?" and call it name
show "Hello, {name}!"
```

Plain is a programming language for people who have never programmed. It reads like plain English, and it means the same thing every time you run it. When Plain can't follow a line, it tells you how to fix it, in plain words.

Try it in your browser at **[plain-lang.dev](https://plain-lang.dev)**. You don't need to install anything.

## Install

You need Python 3.13 or newer and [pipx](https://pipx.pypa.io).

```bash
pipx install plainlang
```

Then write a file called `hello.plain` and run it:

```bash
plain run hello.plain
```

To let Plain ask Claude for ideas when it can't follow a line, install the optional helper and set your Anthropic key:

```bash
pipx install "plainlang[ai]"
```

Another program called Plain (a web framework) also installs a `plain` command. If you have it, run this Plain with `python -m plainlang`.

## What you can do

| Command | What it does |
|---|---|
| `plain` | Type Plain one line at a time |
| `plain run FILE` | Check FILE, help you fix it, then run it |
| `plain check FILE` | List anything Plain can't follow, without running it |
| `plain fix FILE` | Go through each line Plain can't follow and fix it |
| `plain tidy FILE` | Use Plain's main words and put your own steps last |
| `plain explain FILE` | Show how Plain reads each line |
| `plain phrases [WORDS]` | List Plain's phrases, or find the ones about WORDS |

## Working on Plain

- The design is in [docs/design.md](docs/design.md). Its amendments come first and win over the spec.
- The core uses only Python's standard library. Run the tests with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -t .
```

- `PLAIN_UPDATE=1` rewrites the expected outputs of golden tests after a deliberate change.
- Build and serve the website (with the browser playground) with:

```bash
python3 site/build.py --serve
```
