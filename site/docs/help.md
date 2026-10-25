# Get help

When Plain stops with a message, you can almost always fix the problem yourself. Try these, in order:

1. **Read Plain's message from the top.** The first line says which line to change and how. That's the fix.
2. **Try the lines under "Try this:".** They show your line with the fix made, ready to put in place of your line.
3. **Follow the link at the end.** When Plain has no fix to offer, the last line of its message says where to look on this site, and on your computer, which `plain phrases` command to type.
4. **See how Plain reads your program.** Type `plain explain` and your file's name, like `plain explain hello.plain`.
5. **Look up a phrase** on [All phrases](/phrases/), or type `plain phrases` and a word, like `plain phrases sort`.
6. **Go back to the lessons.** [Handle problems and read Plain's messages](/learn/10-problems/) walks through the common ones, and [each lesson](/learn/) teaches one thing.

If Plain won't start at all, see [If something goes wrong](/install/#if-something-goes-wrong) on the install page.

## Read Plain's message from the top

Every message has the same parts, in the same order. Here is a program with a mistake, and what Plain says:

```plain
set guests to 12
if guests is bigger then 10
    show "That's a big party!"
```

```problem
your program, line 2: Write "than" instead of "then".

    if guests is bigger then 10
                        ^^^^
Try this:
    if guests is bigger than 10
Why: "Than" compares two things. "Then" means "next".

Plain found 1 thing to fix, so it hasn't run your program yet.
```

- **The first line** names the line and says what to do. On your computer, it starts with your file's name where this page says "your program".
- **Your line** comes next, with `^` marks under the part to change.
- **Try this:** shows your line with the fix made. Not every message has one.
- **Why:** explains the problem in a sentence or two.
- **Where to look:** when Plain has no fix to offer, a line after Why says which part of this site can help. See [Find the right words when Plain has no fix](/learn/10-problems/#find-the-right-words-when-plain-has-no-fix).
- **The last line** says how many things Plain found. Plain checks every line before it runs anything, so nothing has happened yet. Fix them from the top.

Some problems only show up while your program runs, like an answer that isn't a number. Then the first line says "while running", and Why also says where the value came from:

```plain
ask "How many people are sharing the bill?" and call it people
show "Each person pays ${120 divided by people}."
```

```answers
four
```

```problem
How many people are sharing the bill? four
your program, line 2, while running: Check that "people" is a number before you divide by it.

    show "Each person pays ${120 divided by people}."
                                            ^^^^^^
Try this:
    if people is a number
        show "Each person pays ${120 divided by people}."
    otherwise
        show "Please type a number."
Why: You can't divide 120 by "four", because "four" is text, not a number. "people" got its value on line 1, from what was typed.
```

## Use Plain's ideas

When you run a program in Terminal or PowerShell and Plain finds a problem, it offers its ideas as a numbered list. Type a number to use an idea, or press **Enter** to skip it:

```text
  1) show "Hello there"

Type 1 to use it, or press Enter to skip: 1
Saved line 1. Your old line was: show Hello there
Your file from before is in hello.plain.bak.
Hello there
```

Plain changes that line in your file and keeps your old file in a copy that ends in `.bak`. Once every line works, Plain runs your program. If you skip a line, Plain won't run your program yet. To go through the problems again, type `plain fix` and your file's name.

In the playground, press the **Use this** button under the message, then press **Run** again.

## See how Plain reads each line

You can see exactly how Plain understands your program before it runs. Save this program as `party.plain`:

```plain
set guests to 12
display "Welcome!"
show the guests times 2
show guests is more than 10 and less than 20
```

```output
Welcome!
24
yes
```

Then type:

```bash
plain explain party.plain
```

Plain shows each line as you wrote it, and next to it, how it reads it:

```text
  1  set guests to 12                       set guests to 12
  2  display "Welcome!"                     show "Welcome!"
  3  show the guests times 2                show guests times 2
  4  show guests is more than 10 and less than 20
                                            show guests is more than 10 and guests is less than 20
```

Plain uses its main words (`show` for `display`), leaves out words like "the", and writes every check out in full. If the right side isn't what you meant, change your line so it says exactly what you mean.

To put the main words into your file, type:

```bash
plain tidy party.plain
```

Plain changes `display` to `show` and keeps your file from before in `party.plain.bak`. It leaves "the" and the short check as you wrote them. [All phrases](/phrases/#other-ways-you-can-write-things) lists every other way of writing things that Plain understands.

## Look up a phrase

[All phrases](/phrases/) lists everything Plain can do, with an example of each. Type in the box at the top to find one.

In Terminal or PowerShell, type `plain phrases` and a word to find the phrases about it:

```bash
plain phrases sort
```

## Fix web certificate problems {#certificates}

Web certificates let Plain check that a website is who it says it is. If Plain says **"Update your computer's web certificates"**, your computer's list of certificates is out of date. Do the step for your computer, then run your program again:

- **Mac with Homebrew:** type `brew postinstall ca-certificates`.
- **Mac without Homebrew:** install the latest updates, in **System Settings**, **General**, **Software Update**.
- **Windows:** install the latest updates, in **Settings**, **Windows Update**.
- **Linux:** update the `ca-certificates` package. On Ubuntu or Debian, type `sudo apt install --reinstall ca-certificates`.
- **At work:** your workplace's network may use its own certificate. Ask the people who look after your computer to add it.

If Plain says **"the website has to fix its certificate"**, the problem is on the website, not your computer. Check the address, or try again later.

## Tell us about a problem in Plain

If Plain says "Plain itself went wrong", that's a mistake in Plain, not in your program. Please tell us about it, and about anything Plain does that seems wrong or confusing:

[Contact link coming soon]

Include:

- **Your program.** Paste the whole thing, and any files it reads if you can share them.
- **Plain's message,** exactly as Plain shows it. Copy and paste it.
- **What you expected** to happen instead.
- **Your version of Plain.** Type `plain --version` to see it. Say whether you use a Mac, Windows or the playground.

Take out anything private first, like passwords and keys.
