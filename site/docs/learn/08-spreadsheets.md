# Work with spreadsheets saved as CSV

You can read a spreadsheet, pick out the rows you want, sort them, add up a column and save the result as a new spreadsheet. Plain reads spreadsheets saved as **CSV**, a simple kind of file that every spreadsheet app can save and open.

## Save your spreadsheet as CSV

Save a CSV copy of your spreadsheet first. Plain can't open Excel, Google Sheets or Numbers files directly:

- **Excel:** choose File > Save As, then choose **CSV** as the file type.
- **Google Sheets:** choose File > Download > **Comma-separated values (.csv)**.
- **Numbers on a Mac:** choose File > Export To > **CSV**.

Put the CSV file in the same folder as your program. In the playground, add it from your computer in the **Files** tab.

A CSV file is plain text. The first line holds the column names. Each line after that is one row, with commas between the cells. This is `sales.csv`, the file most examples on this page use:

```text
date,customer,amount
2026-10-01,Ann,120.50
2026-10-02,Bo,80
2026-10-03,Cy,300
2026-10-04,Di,99.99
2026-10-05,Ed,150
```

If you try to read an Excel file, Plain tells you what to do:

```plain
read "sales.xlsx" and call it sales
```

```problem
your program, line 1, while running: Save "sales.xlsx" as a CSV file, then read "sales.csv".

    read "sales.xlsx" and call it sales
         ^^^^^^^^^^^^
Why: Plain reads spreadsheets saved as CSV. In Excel, choose File > Save As > CSV. In Google Sheets, choose File > Download > CSV.
```

## Read a CSV file into a table

`read` turns a CSV file into a **table**. `show` lines up its columns:

```plain files=sales.csv
read "sales.csv" and call it sales
show sales
show "You have {the number of sales} sales."
```

```output
date        customer  amount
2026-10-01  Ann       120.50
2026-10-02  Bo        80
2026-10-03  Cy        300
2026-10-04  Di        99.99
2026-10-05  Ed        150
You have 5 sales.
```

Each row is a **record**: a set of values, each kept under a column name. Cells that look like numbers become numbers, so you can add them up.

## Get one value from a row

After the name for a row, write `'s` and a column name. `sale's amount` is the amount in one row. It works well when you repeat for each row:

```plain files=sales.csv
read "sales.csv" and call it sales
repeat for each sale in sales
    show "{sale's customer} spent ${sale's amount}."
```

```output
Ann spent $120.50.
Bo spent $80.
Cy spent $300.
Di spent $99.99.
Ed spent $150.
```

Capitals don't matter in column names, and a space works the same as `_`. So for a column named `Unit_Price`, you can write `order's unit price`.

## Get a whole column

`the amounts of sales` is a list of every amount, one from each row. You can add an "s" to the column name so it reads naturally. `the total of`, `the average of`, `the largest of` and `the smallest of` all work on a column:

```plain files=sales.csv
read "sales.csv" and call it sales
show the amounts of sales
show "Total: ${the total of the amounts of sales}"
show "Average: ${the average of the amounts of sales rounded to 2 places}"
show "Largest: ${the largest of the amounts of sales}"
```

```output
120.50, 80, 300, 99.99 and 150
Total: $750.49
Average: $150.10
Largest: $300
```

## Pick rows with "where"

`where` keeps only the rows that pass a check. In the check, a column name means that row's value:

```plain files=sales.csv
read "sales.csv" and call it sales
set big sales to sales where amount is more than 100
show big sales
show "{the number of big sales} sales were over $100."
```

```output
date        customer  amount
2026-10-01  Ann       120.50
2026-10-03  Cy        300
2026-10-05  Ed        150
3 sales were over $100.
```

## Sort the rows

`sort sales by amount` puts the rows in order, smallest first. Add `largest first` to start with the biggest. Text columns sort from A to Z.

```plain files=sales.csv
read "sales.csv" and call it sales
sort sales by amount, largest first
show sales
```

```output
date        customer  amount
2026-10-03  Cy        300
2026-10-05  Ed        150
2026-10-01  Ann       120.50
2026-10-04  Di        99.99
2026-10-02  Bo        80
```

`sort` changes the table in your program. Your CSV file stays as it was until you save over it.

## Save a table as a CSV file

`save` writes a table to a CSV file that Excel and Google Sheets can open. If a file with that name is already there, Plain replaces it.

```plain files=sales.csv
read "sales.csv" and call it sales
set big sales to sales where amount is more than 100
sort big sales by amount, largest first
save big sales to "big sales.csv"
show "Saved {the number of big sales} sales to big sales.csv."
```

```output
Saved 3 sales to big sales.csv.
```

The new file holds the column names and the three big sales:

```text
date,customer,amount
2026-10-03,Cy,300
2026-10-05,Ed,150
2026-10-01,Ann,120.50
```

In the playground, open it from the **Files** tab.

## Find the different values in a column

You can list each different value in a column once, then use that list to add up each group. The next examples use `08-spending.csv`, a household budget with a `category` column:

```text
date,name,category,amount
2026-10-01,Rent,home,950
2026-10-02,Groceries,food,82.40
2026-10-03,Bus pass,travel,45
2026-10-05,Pizza night,food,
2026-10-08,Electricity,home,61.15
2026-10-09,Train ticket,travel,23.50
2026-10-12,Groceries,food,67.10
```

`the different categories of spending` gives each category once, in the order it first appears. Together with `repeat` and `where`, it gives you a total for each category:

```plain files=08-spending.csv
read "08-spending.csv" and call it spending
show the different categories of spending
repeat for each kind in the different categories of spending
    set rows to spending where category is kind
    show "{kind}: ${the total of the amounts of rows}"
```

```output
home, food and travel
home: $1011.15
food: $149.50
travel: $68.50
```

In `where category is kind`, the left side is a column of each row, and the right side is your name `kind`.

## Handle blank cells

You can add up a column even when some cells are blank. Plain reads a blank cell as `nothing`, and totals and averages skip it, so one missing amount doesn't spoil your sums. In the budget, the Pizza night row has no amount, so the average below divides by 6, not 7. To find the blank cells, use `is empty`:

```plain files=08-spending.csv
read "08-spending.csv" and call it spending
show "Total: ${the total of the amounts of spending}"
show "Average: ${the average of the amounts of spending rounded to 2 places}"
set missing to spending where amount is empty
show "Still to fill in:"
show missing
```

```output
Total: $1229.15
Average: $204.86
Still to fill in:
date        name         category  amount
2026-10-05  Pizza night  food      nothing
```

## Try it yourself

Press **Try it** on any example above, then change it:

- Show only the food rows of the budget.
- Sort the sales by customer, from A to Z.
- Show the smallest sale.
- Save the travel rows to a new file called "travel.csv".
- Save one of your own spreadsheets as CSV, add it in the **Files** tab, and show it with `show`.
