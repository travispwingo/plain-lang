# Read and save files

You can save your program's work in a file, so it's still there the next time the program runs. You can also read files you already have, like a shopping list or a set of notes.

Plain looks for files in the same folder as your program. In the playground on this site, your files live in the **Files** tab, next to **What your program shows**. There you can open them, change them, add files from your computer and download them. They stay only in this browser tab, so download any you want to keep.

## Read a file

`read` gives you everything in the file as one piece of text. `and call it` keeps it under a name:

```plain files=07-shopping.txt
read "07-shopping.txt" and call it shopping
show "Here's what's in the file:"
show shopping
```

```output
Here's what's in the file:
milk
eggs
bread
```

## Read a file one line at a time

`read the lines of` gives you a list, with one item for each line of the file. Then you can use everything from [the lesson on lists](/learn/05-lists/):

```plain files=07-shopping.txt
read the lines of "07-shopping.txt" and call it shopping
show "You need {the number of shopping} things."
show "First on the list: {the first item of shopping}"
```

```output
You need 3 things.
First on the list: milk
```

## Save to a file

`save` puts a value in a file. If the file isn't there, Plain makes it. If it is, Plain replaces what was in it:

```plain files=07-shopping.txt
read the lines of "07-shopping.txt" and call it shopping
add "jam" to shopping
sort shopping
save shopping to "07-shopping.txt"

read the lines of "07-shopping.txt" and call it saved
show "The file now holds: {saved}"
```

```output
The file now holds: bread, eggs, jam and milk
```

Plain saves a list with one item on each line, so `read the lines of` gives you the same list back.

## Add a line to the end of a file

`add … to the file` keeps what's already in the file and puts one new line at the end. It's good for a diary or a log:

```plain
add "Saw a fox." to the file "diary.txt"
add "Planted beans." to the file "diary.txt"
read "diary.txt" and call it diary
show diary
```

```output
Saw a fox.
Planted beans.
```

If the file isn't there yet, Plain makes it.

## Check that a file is there

`the file … exists` is yes when the file is there and no when it isn't. Use it so your program works the first time, before it has saved anything:

```plain
set visits to 0
if the file "visits.txt" exists
    read "visits.txt" and call it visits
add 1 to visits
save visits to "visits.txt"
show "Visit number {visits}."
```

```output
Visit number 1.
```

Run it again and the number goes up, because `visits.txt` is still there. In the playground, it waits for you in the **Files** tab. You can also write `the file "visits.txt" does not exist`.

## Know what each file ending gives you

The ending of a file's name tells Plain what's inside, and so what `read` gives you:

- **`.csv`**: `read` gives you a table, with rows and columns. `save` writes a table as rows.
- **`.json`**: `read` gives you records and lists. `save` can write any value.
- **Anything else, like `.txt`**: `read` gives you text. `save` writes text, and a list as one item per line.

So a list saved to a `.json` file comes back as the same list, numbers and all:

```plain
set scores to a list of 72, 95 and 58
save scores to "scores.json"
read "scores.json" and call it saved scores
show "{the number of saved scores} scores, {the total of saved scores} points in all."
```

```output
3 scores, 225 points in all.
```

[The next lesson](/learn/08-spreadsheets/) shows you how to work with tables from `.csv` files.

## Work with folders

A file name can start with a folder, like `"trip/monday.txt"`. Plain makes the folder if it needs to. `the files in` gives you the names of the files in a folder, from A to Z:

```plain
save "Went to the beach." to "trip/monday.txt"
save "Walked in the hills." to "trip/tuesday.txt"
show the files in "trip"
rename "trip/tuesday.txt" to "wednesday.txt"
show the files in "trip"
```

```output
monday.txt and tuesday.txt
monday.txt and wednesday.txt
```

`rename` gives a file a new name. The file stays in the same folder, so you write only the new name.

If you run this a second time, Plain stops at `rename`, because there's already a file called `wednesday.txt`. Plain never replaces a file when it renames one.

## Try it yourself

Press **Try it** on any example above, then change it:

- Ask for one more thing you need, add it to the shopping list, and save the list.
- Make the diary ask "What happened today?" and add your answer to the file.
- Save your three favorite foods to "foods.txt", then open the **Files** tab to see the file.
