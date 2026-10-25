# Write your own steps

You can teach Plain a new step. You name it in your own words, write what it does once, and then use it as often as you like. Your program gets shorter and easier to read.

## Write a step

Start a line with `how to`, then the words of your new step. Put the steps it takes on the lines below, moved 4 spaces to the right, just like the steps under `if`:

```plain
how to greet (person)
    show "Hello, {person}!"
    show "Nice to see you."

greet "Ann"
greet "Bo"
```

```output
Hello, Ann!
Nice to see you.
Hello, Bo!
Nice to see you.
```

The word in brackets, `person`, is the name for the value you hand in. When you write `greet "Ann"`, Plain takes the steps under `how to greet` with `person` set to "Ann".

## Hand in more than one value

Put brackets wherever a value goes in your sentence:

```plain
how to introduce (guest) to (host)
    show "{host}, meet {guest}."
    show "{guest}, this is {host}."

introduce "Ann" to "Bo"
```

```output
Bo, meet Ann.
Ann, this is Bo.
```

A name in brackets can be more than one word, like `(bill amount)`.

## Give back a value

Some steps find an answer. `give back` gives the answer back, and `and call it` keeps it under a name, just like it does with `ask`:

```plain
how to find the tip on (bill) at (rate)
    give back (bill times rate) rounded to 2 decimal places

find the tip on 42.50 at 15% and call it lunch tip
show "Leave ${lunch tip}."
```

```output
Leave $6.38.
```

`give back` ends your step right away. Plain skips any steps after it:

```plain
how to describe (temperature)
    if temperature is more than 25
        give back "hot"
    give back "mild"

describe 30 and call it word
show "30 degrees is {word}."
describe 12 and call it word
show "12 degrees is {word}."
```

```output
30 degrees is hot.
12 degrees is mild.
```

Your step is always a line of its own. To use its answer inside another line, keep it with `and call it` first, then use the name.

## Put the main steps first

You can use your step above the place where you write it. That lets you put the main steps at the top, where people start reading, and the details at the bottom:

```plain
# Find the tips for two meals
find the tip on 42.50 at 15% and call it lunch tip
find the tip on 80 at 20% and call it dinner tip
show "Lunch: leave ${lunch tip}."
show "Dinner: leave ${dinner tip}."

# The details
how to find the tip on (bill) at (rate)
    give back (bill times rate) rounded to 2 decimal places
```

```output
Lunch: leave $6.38.
Dinner: leave $16.00.
```

A line that starts with `#` is a note for people. Plain skips it. Someone reading from the top sees what the program does, and reads the details only if they want to know how.

## Pick words Plain doesn't already use

Give your step words that Plain doesn't already use for one of its own steps. If your step used the same words in the same places, Plain couldn't tell which one you meant. Plain checks this before it runs anything:

```plain
how to read (book)
    show "Now reading {book}."
```

```problem
your program, line 1: Use different words for this "how to".

    how to read (book)
    ^^^^^^^^^^^^^^^^^^
Try this:
    how to look at (book)
Why: It uses the same words in the same places as Plain's own step "read ...", as in read "sales.csv" and call it sales, so Plain couldn't tell them apart.

Plain found 1 thing to fix, so it hasn't run your program yet.
```

Plain already has its own `read` step, as in `read "notes.txt" and call it notes`. A line like `read "Dune"` could mean either one. Add a word, or pick a different one:

```plain
start reading "Dune"
start reading "Emma"

how to start reading (book)
    show "Now reading {book}."
```

```output
Now reading Dune.
Now reading Emma.
```

Plain compares only the words outside the brackets, and where the brackets go. The names inside the brackets can be anything you like.

## Try it yourself

Press **Try it** on any example above, then change it:

- Make `greet` also ask the person how they are, and show their answer.
- Write `how to double (amount)` that gives back the amount times 2.
- Write `how to roll a die` that gives back a random number from 1 to 6. Use it twice and show both rolls.
