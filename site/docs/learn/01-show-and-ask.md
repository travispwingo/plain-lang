# Show words and ask questions

You can make a program that shows words on the screen and asks you questions. That's all most programs do: they show things, ask things, and work things out in between.

## Show words

Put the words you want to show in double quotes, after `show`:

```plain
show "Hello there!"
show "Plain shows each line on its own."
```

```output
Hello there!
Plain shows each line on its own.
```

Plain runs your steps from the top down, one line at a time.

## Ask a question

`ask` shows a question and waits for an answer. `and call it` keeps the answer under a name, so you can use it later:

```plain
ask "What is your name?" and call it name
show "Nice to meet you, {name}!"
```

```answers
Ann
```

```output
What is your name? Ann
Nice to meet you, Ann!
```

The `{name}` part puts the answer into the text. You can put any name or value inside `{ }`.

## Numbers work too

If an answer looks like a number, Plain treats it as one:

```plain
ask "How old are you?" and call it age
show "Next year you will be {age plus 1}."
```

```answers
41
```

```output
How old are you? 41
Next year you will be 42.
```

## Try it yourself

Press **Try it** on any example above, then change it:

- Ask for a favorite food and show it back.
- Ask for two numbers and show them added together.
