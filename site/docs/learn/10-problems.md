# Handle problems and read Plain's messages

You can fix most problems in your program by reading Plain's message. Every message has the same parts, in the same order: what to change, your line, and why. You can also see how Plain reads each line, let Plain fix lines for you, and plan for problems that only happen while your program runs.

## Read a message

Read each message from the top. This program leaves out the quotes on its second line:

```plain
show "Hi!"
show Hello there
```

```problem
your program, line 2: Put the text in double quotes.

    show Hello there
         ^^^^^^^^^^^
Try this:
    show "Hello there"
Why: Words in double quotes are shown just as you wrote them. Without quotes, Plain looks for a name "Hello there", and you haven't set one.

Plain found 1 thing to fix, so it hasn't run your program yet.
```

Here's what each part tells you:

1. **The fix comes first.** The first line says where the problem is (`your program, line 2`), then what to do. On your computer, Plain names your file instead of "your program". Often the first line is all you need.
2. **Your line, with `^` marks** under the part to change.
3. **`Try this:`** shows your line with the fix made. Not every message has one.
4. **`Why:`** explains the problem in a sentence or two.

## Fix problems Plain finds before running

Plain checks every line before it runs any of them, so you can fix problems before anything happens. If it finds a line it can't follow, nothing runs, not even the lines above it. That's why `Hi!` didn't appear above.

Plain lists up to 5 problems at a time, so you can fix them all in one go. The last line says how many it found:

```plain
show "Let's keep score."
score is 0
ask "How many points?" and call it points
add points to scor
show "Your score is {score}."
```

```problem
your program, line 2: Write "set score to 0" instead.

    score is 0
    ^^^^^^^^^^
Try this:
    set score to 0
Why: In Plain, "is" only compares two values, as in: if score is 0

your program, line 4: Write "score" instead of "scor".

    add points to scor
                  ^^^^
Why: You set "score" on line 2. Nothing in your program sets "scor".

Plain found 2 things to fix, so it hasn't run your program yet.
```

## Find the right words when Plain has no fix

Sometimes Plain can't tell what you meant, so it has no fix to offer. Then the line after `Why:` says where to look on this site. On your computer, it also gives a `plain phrases` command that lists the phrases to try:

```plain
set names to a list of "Bea" and "Al"
sort names by by
```

```problem
your program, line 2: Reword this line.

    sort names by by
    ^^^^^^^^^^^^^^^^
Why: Plain couldn't follow this line.
Find a phrase that fits at plain-lang.dev/phrases/#lists-and-tables, or type: plain phrases sort

Plain found 1 thing to fix, so it hasn't run your program yet.
```

[Lists and tables](/phrases/#lists-and-tables), on the All phrases page, shows every way to sort, with an example of each. `plain phrases sort` lists the same phrases in Terminal or PowerShell. In the playground, the message gives just the link.

## Fix problems that happen while running

Some problems only show up while the program runs, because they depend on values: what someone types, what's in a file, or what a website sends back. These messages say `while running` on the first line. Plain has already taken the steps above that line.

This program splits a bill. It works until someone says 0 people:

```plain
ask "How much was the bill?" and call it bill
ask "How many people?" and call it people
show "Each person pays ${(bill divided by people) rounded to 2 decimal places}."
show "Thanks!"
```

```answers
60
0
```

```problem
How much was the bill? 60
How many people? 0
your program, line 3, while running: Check that "people" is not 0 before you divide by it.

    show "Each person pays ${(bill divided by people) rounded to 2 decimal places}."
                                              ^^^^^^
Why: Plain can't divide by 0.
```

The program stops at the line with the problem, so `Thanks!` never appears.

## Plan for problems with "try"

You can follow the fix in the message and check `people` with an `if`. Or, when you can't know every way a step might go wrong, put it under `try`. If one of the steps under `try` has a problem, Plain skips the rest of them and takes the steps under `if that fails` instead. There, `the problem` holds the message Plain would have shown:

```plain
ask "How much was the bill?" and call it bill
ask "How many people?" and call it people
try
    show "Each person pays ${(bill divided by people) rounded to 2 decimal places}."
if that fails
    show "Plain couldn't split the bill."
    show the problem
show "Thanks!"
```

```answers
60
0
```

```output
How much was the bill? 60
How many people? 0
Plain couldn't split the bill.
Check that "people" is not 0 before you divide by it. Plain can't divide by 0.
Thanks!
```

This time the program goes on to the end. `try` is most useful for steps that depend on the world outside your program, like reading a file or [getting data from the web](/learn/09-web/).

`try` only helps with problems that happen while running. A line Plain can't follow stops the whole program before it starts, even if it sits under `try`.

## See how Plain reads each line

On your computer, `plain explain` shows each of your lines next to the way Plain reads it. The right side uses Plain's main words, and shows anything Plain left out or filled in:

```text
$ plain explain dice.plain
  1  Please show "Let's roll some dice."    show "Let's roll some dice."
  2  ask "How many dice should I roll?" and call it count
                                            ask "How many dice should I roll?" and call it count
  3  set the total to 0                     set total to 0
  4  for each roll from 1 to count          repeat for each roll from 1 to count
  5      add a random number from 1 to 6 to total
                                            add a random number from 1 to 6 to total
  6  Show the total!                        show total
  7  if total is more than 10 and less than 15
                                            if total is more than 10 and total is less than 15
  8      show "Nice roll."                  show "Nice roll."
```

You can see that Plain leaves out "Please", "the" and the "!", reads `for each` as `repeat for each`, and reads line 7 as two checks on `total`. When your program does something you didn't expect, this shows you whether Plain read a line the way you meant it. If a line has a problem, `plain explain` shows the message at the end.

## Let Plain fix lines for you

On your computer, `plain fix` goes through each line Plain can't follow. For each one, it shows the message and numbered ideas. Type a number to use an idea, or press Enter to skip that line:

```text
$ plain fix game.plain
game.plain, line 4: Write "tries" instead of "trys".

    show "You took {trys} tries."
                    ^^^^
Why: You set "tries" on line 1. Nothing in your program sets "trys".

  1) show "You took {tries} tries."

Type 1 to use it, or press Enter to skip: 1
Saved line 4. Your old line was: show "You took {trys} tries."
Your file from before is in game.plain.bak.
```

Plain checks every idea before it offers it, so each numbered idea is a line Plain can follow. Before it changes your file, Plain keeps a copy of the old one, ending in `.bak`. `plain run` offers the same ideas when it finds a problem, then runs your program once you've fixed every line.

In the playground, Plain's ideas appear as **Use this** buttons under the message. Press one to put the fix into your program.

## Try it yourself

Press **Try it** on any example above, then change it:

- Break a working program on purpose: take out a quote, misspell a name, or take away the spaces before a step under `if`. Read each message.
- In the bill splitter, type `four` as the number of people. What does Plain say?
- Change the bill splitter so it checks `if people is 0` and shows a friendly message, as Plain's message suggests.
- On your computer, run `plain explain` on one of your own programs.
