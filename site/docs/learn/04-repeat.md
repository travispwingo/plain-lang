# Repeat steps

You can make Plain take the same steps again and again: a set number of times, once for each item in a list, or until something is true. Each time through the steps is one round.

## Repeat steps a set number of times

Write `repeat`, then how many times. Put the steps to repeat on the lines below, moved 4 spaces to the right, just like the steps under `if`:

```plain
repeat 3 times
    show "Hip hip hooray!"
show "Done."
```

```output
Hip hip hooray!
Hip hip hooray!
Hip hip hooray!
Done.
```

`show "Done."` is back at the left edge, so Plain shows it once, after the repeating is over. You can also write `repeat once` and `repeat twice`.

## Count from one number to another

`repeat for each` with `from` and `to` counts for you. Each round, the name you choose holds the next number:

```plain
repeat for each count from 1 to 5
    show "{count} times 3 is {count times 3}."
```

```output
1 times 3 is 3.
2 times 3 is 6.
3 times 3 is 9.
4 times 3 is 12.
5 times 3 is 15.
```

Both numbers count, so this takes 5 rounds. To count down, write `down to`:

```plain
repeat for each count from 5 down to 1
    show "{count}..."
show "Liftoff!"
```

```output
5...
4...
3...
2...
1...
Liftoff!
```

`to` only counts up, so always write `down to` to count down. If you write `from 5 to 1`, Plain points it out before it runs anything:

```plain
repeat for each count from 5 to 1
    show "{count}..."
```

```problem
your program, line 1: Write "repeat for each count from 5 down to 1" to count down.

    repeat for each count from 5 to 1
                               ^^^^^^
Try this:
    repeat for each count from 5 down to 1
Why: "to" only counts up, so from 5 to 1 would take no rounds at all.

Plain found 1 thing to fix, so it hasn't run your program yet.
```

When an end is worked out while the program runs, as in `from 1 to the number of guests`, Plain can't see it in advance. If the first number turns out bigger, the repeat takes no rounds.

## Take steps for each item in a list

`repeat for each` also goes through a list, one item per round:

```plain
set guests to a list of "Ann", "Sam" and "Lee"
repeat for each guest in guests
    show "Welcome, {guest}!"
show "Everyone is here."
```

```output
Welcome, Ann!
Welcome, Sam!
Welcome, Lee!
Everyone is here.
```

You'll learn much more about lists in [the next lesson](/learn/05-lists/).

## Repeat until something is true

`repeat until` takes the steps, then checks. It stops once the check is yes:

```plain
repeat until answer is "yes"
    ask "Are we there yet?" and call it answer
show "Hooray!"
```

```answers
no
nope
yes
```

```output
Are we there yet? no
Are we there yet? nope
Are we there yet? yes
Hooray!
```

Because Plain checks after each round, the steps always run at least once. That's why this works: `answer` gets its first value in the first round, before Plain checks it.

## Repeat while something is true

`repeat while` checks first, and takes the steps only while the check is yes. If the check is no from the start, the steps never run:

```plain
set savings to 100
set years to 0
repeat while savings are less than 200
    set savings to savings times 1.10
    add 1 to years
show "At 10% a year, $100 grows past $200 in {years} years."
show "You'd have ${savings rounded to 2 places}."
```

```output
At 10% a year, $100 grows past $200 in 8 years.
You'd have $214.36.
```

## Stop early or skip a round

`repeat forever` keeps going until it reaches `stop repeating`. Use it when you don't know ahead of time how many rounds you need:

```plain
set total to 0
repeat forever
    ask "Price? (Type done to finish.)" and call it price
    if price is "done"
        stop repeating
    if price is not a number
        show "Please type a number, like 4.50."
        skip to the next round
    add price to total
show "Total: ${total}"
```

```answers
4.50
abc
2.25
done
```

```output
Price? (Type done to finish.) 4.50
Price? (Type done to finish.) abc
Please type a number, like 4.50.
Price? (Type done to finish.) 2.25
Price? (Type done to finish.) done
Total: $6.75
```

- `stop repeating` leaves the repeat right away. Plain goes on with the first line after it.
- `skip to the next round` leaves out the rest of this round and starts the next one. Here, it means "abc" never reaches `add price to total`.
- Both work in every kind of repeat, not only `repeat forever`.

If a program keeps repeating and never stops, press **Stop** in the playground, or **Control+C** in Terminal or PowerShell.

## Put it together: a guessing game

This game picks a secret number and gives you hints until you find it. `a random number from 1 to 20` picks a whole number by chance, and 1 and 20 can both come up.

```plain seed=9
set secret to a random number from 1 to 20
set tries to 0
show "I'm thinking of a number from 1 to 20."
repeat forever
    ask "Your guess?" and call it guess
    if guess is not a whole number
        show "Please type a whole number, like 7."
        skip to the next round
    add 1 to tries
    if guess is less than secret
        show "Higher!"
    otherwise if guess is more than secret
        show "Lower!"
    otherwise
        show "You got it in {tries} tries!"
        stop repeating
show "Thanks for playing."
```

```answers
10
lots
17
15
```

```output
I'm thinking of a number from 1 to 20.
Your guess? 10
Higher!
Your guess? lots
Please type a whole number, like 7.
Your guess? 17
Lower!
Your guess? 15
You got it in 3 tries!
Thanks for playing.
```

On this page the secret number is always 15, so the example can show you exactly what happens. When you press **Try it**, Plain picks a new secret number each time you run the game.

## Try it yourself

Press **Try it** on any example above, then change it:

- Show the 7 times table, from 1 to 12.
- Make the countdown start at 10.
- Add your own name to the list of guests.
- In the guessing game, pick from 1 to 100 instead of 1 to 20.
- Harder: end the game after 5 tries, and show the secret number when that happens.
