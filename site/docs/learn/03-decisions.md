# Make decisions

You can make your program take different steps depending on the answer to a check. You write a check, like `age is at least 18`, and Plain takes the steps under it only when the answer is yes.

## Take steps only when a check is yes

Start the line with `if`, then write the check. Put the steps that depend on it on the lines below, moved 4 spaces to the right. The Tab key does this for you.

```plain
ask "How old are you?" and call it age
if age is at least 18
    show "You can vote."
show "Thanks for asking."
```

```answers
41
```

```output
How old are you? 41
You can vote.
Thanks for asking.
```

If you answer 15, Plain skips `show "You can vote."`. The last line is back at the left edge, so it isn't part of the `if`. Plain always shows it.

## Choose between two sets of steps

Add `otherwise` to say what to do when the check is no:

```plain
ask "How old are you?" and call it age
if age is at least 18
    show "You can vote."
otherwise
    show "You can vote in {18 minus age} years."
```

```answers
15
```

```output
How old are you? 15
You can vote in 3 years.
```

## Check more than two things

Use `otherwise if` for each extra check. Plain tries the checks from the top and takes the steps under the first one that's yes. It skips all the others. `otherwise` at the end covers everything else:

```plain
ask "What's the temperature outside?" and call it temperature
if temperature is more than 25
    show "It's hot. Take water."
otherwise if temperature is less than 5
    show "It's cold. Take a coat."
otherwise
    show "It's a nice day."
show "Have a good walk."
```

```answers
2
```

```output
What's the temperature outside? 2
It's cold. Take a coat.
Have a good walk.
```

## Compare values in words

You can write these checks:

- `is` and `is not`: the same, or not the same.
- `is more than` and `is less than`.
- `is at least` and `is at most`: these count the number itself, so 18 is at least 18.
- `is between 1 and 10`: both 1 and 10 count.
- `contains`, `starts with` and `ends with`: for text. `contains` also looks for an item in a list.
- `has`: whether a record has a value under a name, as in `if reply has "results"`. You'll meet records in [the lesson on spreadsheets](/learn/08-spreadsheets/).
- `is empty`: yes for empty text, an empty list or nothing.
- `is a number`, `is a whole number` and `is text`: what kind of value it is. An answer like "42" counts as a number, and "hello" counts as text.
- `is a list`: whether the value is a list. You'll meet lists in [the lesson on lists](/learn/05-lists/).
- `is even`, `is odd` and `is divisible by 3`: for whole numbers. `is divisible by 3` is yes when 3 goes into the number with nothing left over.

Each check has a "not" form too, like `is not empty` or `is not divisible by 3`.

If you're used to `=`, `>` and `<`, those work too, and `plain tidy` changes them to words for you. For a name that holds several things, write the words the way you'd say them: `if scores are empty`, `if names contain "Ann"` or `if todos do not contain "jam"`.

```plain
ask "Pick a number from 1 to 10." and call it pick
if pick is between 1 and 10
    show "Thanks!"
otherwise
    show "{pick} is not from 1 to 10."
```

```answers
12
```

```output
Pick a number from 1 to 10. 12
12 is not from 1 to 10.
```

Here `is text` checks what kind of answer you typed, then `is divisible by 3` checks the number:

```plain
ask "Type a number." and call it answer
if answer is text
    show "That's a word, not a number."
otherwise if answer is divisible by 3
    show "{answer} is in the 3 times table."
otherwise
    show "{answer} is not in the 3 times table."
```

```answers
12
```

```output
Type a number. 12
12 is in the 3 times table.
```

When Plain compares text, it ignores capitals and any spaces at the start or end. So "Pineapple" counts as "pineapple":

```plain
ask "What would you like on your pizza?" and call it toppings
if toppings contain "pineapple"
    show "Bold choice!"
otherwise
    show "Coming right up."
```

```answers
Ham and Pineapple
```

```output
What would you like on your pizza? Ham and Pineapple
Bold choice!
```

When capitals must match too, write `is exactly`.

## Check two things at once

Join two checks with `and` when both must be yes. Use `or` when either one is enough:

```plain
ask "How old are you?" and call it age
ask "Do you have a ticket?" and call it got ticket
if age is at least 18 and got ticket is yes
    show "Come on in."
otherwise
    show "Sorry, not tonight."
```

```answers
30
y
```

```output
How old are you? 30
Do you have a ticket? y
Come on in.
```

If you use both `and` and `or` in one check, put brackets around the part that goes together. Otherwise Plain asks you to, because it never guesses which one you meant.

## Leave out the words you'd repeat

You don't have to write `answer is` again after `or`. Plain uses the start of the check again for you:

```plain
ask "Do you want to hear a joke?" and call it answer
if answer is "y" or "yes" or "sure"
    show "Why did the bicycle fall over? It was two tired."
otherwise
    show "Maybe later."
```

```answers
Sure
```

```output
Do you want to hear a joke? Sure
Why did the bicycle fall over? It was two tired.
```

This works when the next part is a value, like `"yes"` or `100`, or starts with a comparison, like `more than 100`. So `guess is less than 1 or more than 100` checks `guess` both times.

Plain stops you when the short form can't be right:

```plain
ask "Do you want to hear a joke?" and call it answer
if answer is "y" and "yes"
    show "Here goes."
```

```problem
your program, line 2: Use "or" here, or write the whole check again after "and".

    if answer is "y" and "yes"
                         ^^^^^
Why: A value can't be two things at once. Did you mean "or"?

Plain found 1 thing to fix, so it hasn't run your program yet.
```

After `is not` and `is between`, write the whole check each time. A short form there could mean two different things, so Plain asks you to write it in full.

## Use yes and no

When you compare an answer with `yes` or `no`, Plain counts "yes", "y" and "true" as yes, and "no", "n" and "false" as no. Capitals don't matter:

```plain
ask "Is it raining?" and call it raining
if raining is yes
    show "Take an umbrella."
otherwise if raining is no
    show "Leave the umbrella at home."
otherwise
    show "Please answer yes or no."
```

```answers
Y
```

```output
Is it raining? Y
Take an umbrella.
```

You can also keep yes or no under a name, as in `set finished to no`, and check it later with `if finished is yes`.

## Write a short decision on one line

When there's only one step, you can put it on the same line, after `then`:

```plain
set score to 10
if score is 10 then show "You win!"
```

```output
You win!
```

The one-line form takes just one step and no `otherwise`. For anything more, put the steps on their own lines.

## Try it yourself

Press **Try it** on any example above, then change it:

- Change the voting age in the first two examples to 16.
- Ask for the temperature and show "It's freezing!" when it's at most 0.
- Ask "Are you hungry?" and suggest a snack only when the answer is yes.
- Ask for a word, and say whether it starts with "a".
- Ask for a year, and say whether it is divisible by 4.
