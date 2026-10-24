# Keep values under names

You can keep a value under a name, then use that name anywhere you need the value. That's how a program remembers things: a score, a price, someone's answer.

## Keep a value with set

Write `set`, then a name, then `to`, then the value:

```plain
set city to "Lisbon"
set guests to 12
show "The party is in {city}."
show "{guests} people are coming."
```

```output
The party is in Lisbon.
12 people are coming.
```

Text goes in double quotes. Numbers don't need quotes. When you write `{guests}` inside text, Plain puts in the value you kept under `guests`.

If you set a name again, the new value replaces the old one:

```plain
set guests to 12
set guests to 15
show "{guests} people are coming."
```

```output
15 people are coming.
```

Always use `set` to keep a value. If you write `guests is 12`, Plain offers to change it to `set guests to 12`, because in Plain, `is` only compares two values. You'll use it that way in [the next lesson](/learn/03-decisions/).

## Use names of more than one word

A name can be several words long, and it can end in a number. Write it the same way each time you use it:

```plain
set big count to 1200
set lunch tip to 6.40
set player 2 to "Sam"
show "The big count is {big count}."
show "Leave ${lunch tip} for lunch."
show "{player 2} goes next."
```

```output
The big count is 1200.
Leave $6.40 for lunch.
Sam goes next.
```

Capitals don't matter, and Plain skips "the" at the start of a name. So `The Total`, `the total` and `total` are all the same name.

## Change a number

`add` and `subtract` change the number kept under a name. To work out a new value from the old one, use `set` again:

```plain
set score to 0
add 10 to score
add 5 to score
subtract 3 from score
show "Your score is {score}."
set score to score times 2
show "Doubled, it's {score}."
```

```output
Your score is 12.
Doubled, it's 24.
```

## Do arithmetic with exact numbers

Write arithmetic in words: `plus`, `minus`, `times` and `divided by`. Plain works with exact decimal numbers, the same way you would on paper:

```plain
show 0.1 plus 0.2
show 19.99 plus 5.01
show 2.50 times 4
show 10 divided by 3
```

```output
0.3
25.00
10.00
3.3333333333
```

- Plain shows 0.1 plus 0.2 as `0.3`. Many programming languages show `0.30000000000000004`.
- An answer shows at least as many decimal places as the most precise number that went into it. So money stays in cents: `25.00`.
- A long answer stops at 10 decimal places.
- `times` and `divided by` come before `plus` and `minus`, just like at school. Use brackets to change the order: `(2 plus 3) times 4` is 20.

You can write prices and percentages the way you see them on a bill:

```plain
set bill to $42.50
set tip to 15% of bill
show "The exact tip is ${tip}."
show "Leave ${tip rounded to 2 places}."
```

```output
The exact tip is $6.375.
Leave $6.38.
```

Plain ignores a `$` in front of a number, and `15%` means 0.15. `rounded to 2 places` rounds the number, and halves go up.

## Put values into text

Inside `{ }` you can put any name, or arithmetic. This is also how you join pieces of text together:

```plain
set given name to "Ann"
set family name to "Lee"
set full name to "{given name} {family name}"
set tickets to 3
show "{full name} bought {tickets} tickets for ${tickets times 12.50}."
```

```output
Ann Lee bought 3 tickets for $37.50.
```

`plus` only adds numbers. To join text, put the pieces next to each other inside one pair of quotes, each in its own `{ }`.

## Choose names Plain can read

Pick names that don't use Plain's special words. Plain uses a few short words to understand each line, such as `to`, `of`, `in`, `and`, `or`, `is`, `with`, `plus` and `yes`, so they can't be part of a name. If you use one, Plain asks you to rename it before it runs anything:

```plain
set number of players to 4
```

```problem
your program, line 1: Rename "number of players", for example to "player count".

    set number of players to 4
        ^^^^^^^^^^^^^^^^^
Why: "of" is one of Plain's special words, so it can't be part of a name.

Plain found 1 thing to fix, so it hasn't run your program yet.
```

Take Plain's idea, or pick your own name without a special word:

```plain
set player count to 4
show "{player count} people are playing."
```

```output
4 people are playing.
```

The number words `zero` to `twelve` are special words too, but they can come after the first word of a name, as in `round two`. You can see every special word at the end of [All phrases](/phrases/#special-words).

## Try it yourself

Press **Try it** on any example above, then change it:

- Keep the name of a city and the number of days of a trip, and show one sentence with both.
- Start `savings` at 100. Add 25, then add 40, then show how much you have.
- Work out a 20% tip on a bill of $64.80, rounded to 2 places.
- Write `set cups of tea to 3` and read what Plain says. Then pick a name it accepts.
