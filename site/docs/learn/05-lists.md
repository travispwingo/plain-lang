# Work with lists

You can keep many values together in a list: the guests at a party, the prices on a receipt, the scores in a game. Then you can count them, add them up, sort them and pick out the ones you want.

## Make a list

Write `a list of`, then the items. Put commas between them and `and` before the last one:

```plain
set guests to a list of "Ann", "Bo" and "Cy"
show guests
show "You invited {the number of guests} people."
```

```output
Ann, Bo and Cy
You invited 3 people.
```

`the number of` counts the items. When you show a list, Plain writes it the way you would say it.

## Get one item

Write `item`, its position, `of` and the list. Positions start at 1, so item 1 is the first one:

```plain
set guests to a list of "Ann", "Bo", "Cy" and "Di"
show item 2 of guests
show the first item of guests
show the last item of guests
set item 2 of guests to "Ed"
show guests
```

```output
Bo
Ann
Di
Ann, Ed, Cy and Di
```

`set item 2 of guests to "Ed"` puts a new value in that position.

## Add and remove items

Start with `an empty list`, then use `add` to put items at the end:

```plain
set shopping to an empty list
repeat 3 times
    ask "What do you need?" and call it thing
    add thing to shopping
show "Your list: {shopping}"
```

```answers
eggs
milk
bread
```

```output
What do you need? eggs
What do you need? milk
What do you need? bread
Your list: eggs, milk and bread
```

`remove` takes an item out. You can say which item, or give its position:

- `remove "milk" from shopping` takes out the first item that is "milk".
- `remove item 1 from shopping` takes out the item at position 1.

```plain
set shopping to a list of "eggs", "milk", "bread" and "jam"
remove "milk" from shopping
remove item 1 from shopping
show shopping
```

```output
bread and jam
```

The word `item` makes the difference. In a list of numbers, `remove 3 from scores` takes out the first 3 in the list, and `remove item 3 from scores` takes out the third item, whatever it is.

## Sort a list

`sort` puts the list in order. Numbers go smallest first, and `largest first` goes the other way. Text goes from A to Z, and `from Z to A` goes the other way:

```plain
set scores to a list of 72, 95, 58 and 88
sort scores
show scores
sort scores largest first
show scores
set names to a list of "Cy", "Ann" and "Bo"
sort names
show names
sort names from Z to A
show names
```

```output
58, 72, 88 and 95
95, 88, 72 and 58
Ann, Bo and Cy
Cy, Bo and Ann
```

`sort` changes the list itself, so it stays sorted afterwards.

## Add up a list of numbers

You can add up a list of numbers, find their average, and find the largest and the smallest:

```plain
set scores to a list of 72, 95, 58 and 88
show "Total: {the total of scores}"
show "Average: {the average of scores}"
show "Best: {the largest of scores}"
show "Worst: {the smallest of scores}"
```

```output
Total: 313
Average: 78.25
Best: 95
Worst: 58
```

`the largest of` and `the smallest of` are for numbers. For a list of text, sort it, then take its first or last item.

## Pick out the items you want

`where` keeps only the items that pass a check. In the check, `it` means each item in turn:

```plain
set scores to a list of 72, 95, 58, 88 and 95
show scores where it is at least 80
show "{the number of scores where it is at least 80} scores passed."
```

```output
95, 88 and 95
3 scores passed.
```

`the different items of` gives each item once, in the order they first appear:

```plain
set votes to a list of "tea", "coffee", "Tea", "juice" and "coffee"
set drinks to the different items of votes
show drinks
show "People asked for {the number of drinks} drinks."
```

```output
tea, coffee and juice
People asked for 3 drinks.
```

Plain treats "tea" and "Tea" as the same item, because it ignores capitals when it compares text.

## Copy a list

To copy a list, `set` a new name to it. Plain keeps a separate copy, so changing one list doesn't change the other:

```plain
set chores to a list of "dishes", "laundry" and "dusting"
set backup to chores
add "windows" to chores
show "Chores: {chores}"
show "Backup: {backup}"
```

```output
Chores: dishes, laundry, dusting and windows
Backup: dishes, laundry and dusting
```

Your own steps are different. They get the very list you hand them, so a change inside the step changes your list too:

```plain
set chores to a list of "dishes", "laundry" and "dusting"
finish the first chore in chores
show "Still to do: {chores}"

how to finish the first chore in (tasks)
    show "Done: {the first item of tasks}"
    remove item 1 from tasks
```

```output
Done: dishes
Still to do: laundry and dusting
```

To keep your list as it is, hand the step a copy, with `a copy of`:

```plain
set chores to a list of "dishes", "laundry" and "dusting"
list in order a copy of chores
show "Your list as you wrote it: {chores}"

how to list in order (tasks)
    sort tasks
    show "In order: {tasks}"
```

```output
In order: dishes, dusting and laundry
Your list as you wrote it: dishes, laundry and dusting
```

You'll learn to write your own steps in [the next lesson](/learn/06-your-own-steps/).

## Try it yourself

Press **Try it** on any example above, then change it:

- Ask for 5 things instead of 3, then sort the list before you show it.
- Make a list of prices and show the total and the most expensive one.
- Show only the scores below 60, and how many there are.
