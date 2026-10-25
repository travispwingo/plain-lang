# How Plain follows plain language

Plain is inspired by the [plain language movement](https://en.wikipedia.org/wiki/Plain_language). The movement asks for writing you can understand and use the first time you read it. Many governments require this by law, so that everyone can understand what they write, not just experts.

Most programming languages are written for programmers. Plain is written for you, so it follows the rules of plain language. Here's how.

## Everyday words

Plain's steps start with words you already use, like `show`, `ask`, `set`, `add`, `repeat` and `save`. Its messages and this website use everyday words too, like name, list and number.

```plain
set price to 40
show "With a 15% tip, that comes to ${price plus 15% of price}."
```

```output
With a 15% tip, that comes to $46.
```

## One meaning for each word

A word in plain language means the same thing every time you see it. In Plain, `is` only ever compares two values, and `set` is how you store one. So `if score is 0` always checks `score`, and never changes it. If you write `is` to store a value, Plain shows you the fix:

```plain
score is 0
```

```problem
your program, line 1: Write "set score to 0" instead.

    score is 0
    ^^^^^^^^^^
Try this:
    set score to 0
Why: In Plain, "is" only compares two values, as in: if score is 0

Plain found 1 thing to fix, so it hasn't run your program yet.
```

Each idea also has one main wording. Plain understands a few [other ways of writing things](/phrases/#other-ways-you-can-write-things), like `display` for `show`, but the lessons, the examples and Plain's messages use only the main words. `plain tidy` changes the others in your file, so the next person to read it meets the same words too.

## The most important thing first

Plain's messages start with what to do. Then they show your line, with `^` marks under the part to change, and only then say why. Plain also helps if you bring a habit from another programming language:

```plain
print "Hello"
```

```problem
your program, line 1: Write "show "Hello"" instead.

    print "Hello"
    ^^^^^^^^^^^^^
Try this:
    show "Hello"
Why: Plain uses "show" to put words on the screen. To put words in a file, write: save ... to "notes.txt"

Plain found 1 thing to fix, so it hasn't run your program yet.
```

Your programs can work the same way: put the main steps at the top, and your own `how to` steps at the end. `plain tidy` moves them there for you.

## Short steps that start with a verb

Each line is one step, and each step starts with what to do: `show`, `ask`, `add`, `repeat`. Lines that make a choice start with `if` or `otherwise`, and lines that make your own steps start with `how to`. If a line gets too long, Plain asks you to split it into shorter steps.

## Talking to you

Every message and every page speaks to you, the way this page does.

## No guessing

A sentence in plain language has only one meaning, and so does every line Plain runs. If a line could mean two things, Plain shows you both and lets you choose. It never picks one for you:

```plain
show a random number from 1 to 6 plus 1
```

```problem
your program, line 1: Add brackets to show which numbers go together.

    show a random number from 1 to 6 plus 1
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Try one of these:
    show (a random number from 1 to 6) plus 1
  or
    show a random number from 1 to (6 plus 1)
Why: Plain can read this two ways: the plus could belong to the last number of "a random number from …", or come after it.

Plain found 1 thing to fix, so it hasn't run your program yet.
```

## Not dumbed down

Writing in plain language isn't baby talk. It's clear and exact, and so is Plain. Numbers with decimals come out exactly right:

```plain
show 0.1 plus 0.2
```

```output
0.3
```

Plain can also work with tables, files and data from the web, and you can make your own steps with `how to`. Before it runs anything, Plain checks your whole program.

## The reader test

Writers who use plain language test their work with the people they write for. Plain aims to pass the same test: someone who has never programmed can read a Plain program, say what it does, and change it. Every example on this website runs each time Plain changes, so what you read here is what Plain really does.

Plain's design also uses ideas from ISO 24495-1, the international standard for plain language.
