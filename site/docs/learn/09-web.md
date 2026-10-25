# Get data from the web

You can get the weather, look things up and send information to websites, all with the same `read` step you use for files. Give `read` a web address that starts with `https://`, and Plain gets the page for you.

## Read a web address

Put the address in double quotes, or keep it under a name, and give it to `read`. Many websites have addresses made for programs. Instead of a page to look at, they answer with data. This one is from Open-Meteo, a free weather service:

```plain web=09-weather
set address to "https://api.open-meteo.com/v1/forecast?latitude=51.51&longitude=-0.13&current=temperature_2m,wind_speed_10m"
read address and call it weather
show weather's current
show "In London it is {weather's current's temperature 2m}°C."
show "The wind is blowing at {weather's current's wind speed 10m} km/h."
```

```output
time: 2026-10-23T14:00, interval: 900, temperature_2m: 12.4, wind_speed_10m: 18.7
In London it is 12.4°C.
The wind is blowing at 18.7 km/h.
```

Press **Try it** to see the weather in London right now. Your numbers will be different from these.

## Reach inside a reply with 's

Use `'s` to get each piece of a reply. The weather service answers in **JSON**, a format many websites use. Plain turns a JSON reply into a record, so `'s` works just as it does on a row of a [spreadsheet](/learn/08-spreadsheets/):

- `weather's current` is the part of the reply called `current`.
- `weather's current's temperature 2m` is the `temperature_2m` inside that part.

Capitals don't matter, and a space works the same as `_`, just as with column names. Not sure what a reply holds? Show it, as the first `show` above does, and you'll see the name of every piece.

## Put your own values into an address

Put a name in `{ }` inside the address, the same way you put a value into any text. This example uses JSONPlaceholder, a free practice website full of made-up people:

```plain web=09-people
ask "Which person, from 1 to 10?" and call it person number
read "https://jsonplaceholder.typicode.com/users/{person number}" and call it person
show "Person {person number} is {person's name} from {person's address's city}."
```

```answers
3
```

```output
Which person, from 1 to 10? 3
Person 3 is Clementine Bauch from McKenziehaven.
```

Plain makes each value safe to use in an address, so an answer with spaces, like `New York`, works too.

## Plan for a website that says no

You can plan for a website that's down, slow, or has nothing at the address you asked for. Put the steps that might fail under `try`. If one of those steps has a problem, Plain skips the rest of them and takes the steps under `if that fails` instead. There, `the problem` holds the message Plain would have shown:

```plain web=09-people
ask "Which person, from 1 to 10?" and call it person number
try
    read "https://jsonplaceholder.typicode.com/users/{person number}" and call it person
    show "Person {person number} is {person's name}."
if that fails
    show "Sorry, Plain couldn't get person {person number}."
    show the problem
show "Goodbye!"
```

```answers
99
```

```output
Which person, from 1 to 10? 99
Sorry, Plain couldn't get person 99.
Check the address. There's nothing at jsonplaceholder.typicode.com/users/99 (code 404). The website answered, but it has no page at that address.
Goodbye!
```

Without `try`, the program would stop at that line and show the message. With `try`, you decide what happens next, and the program goes on.

## Send data to a website

`send` hands a value to a website. A record or a list goes as JSON, and anything else goes as text. The website's reply comes back the same way `read` gives it. Here, `a new record` makes an empty record, and `set note's title to "Buy milk"` puts a value in it under the name `title`:

```plain web=09-send
set note to a new record
set note's title to "Buy milk"
set note's done to no
send note to "https://jsonplaceholder.typicode.com/posts" and call it reply
show "The website saved your note as number {reply's id}."
```

```output
The website saved your note as number 101.
```

In `and call it reply`, "it" is the website's reply, so `reply` holds what the website sent back.

JSONPlaceholder only pretends to save what you send, so it's a safe place to practice. A real website's own instructions tell you which address to send to, and what to put in the record you send.

## Get the words on a web page

`the text of` gives you just the words of an ordinary web page, without the formatting codes around them:

```plain web=09-page
read "https://example.com" and call it page
show the text of page
```

```output
This domain is for use in documentation examples without needing permission. This is not a service; avoid relying on it for testing and monitoring purposes.
```

## Know what the playground can't read

The playground can read most websites, but not all of them. It runs your program inside your web browser, so it follows the browser's rules, and some websites don't let pages in a browser read them. example.com is one of them. If you press **Try it** on the last example, Plain asks you to check your internet connection, then explains that some websites don't let pages in a browser read them.

That's a rule of the browser, not a mistake in your program. Run the same program on your computer with `plain run` and it works. See [Install Plain](/install/) to set that up. The weather and JSONPlaceholder examples work in the playground, because those websites allow it.

In the playground, addresses must also start with `https://`, not `http://`.

## Try it yourself

Press **Try it** on any example above, then change it:

- Show the weather somewhere else. Find your town's latitude and longitude on a map, and put them in the address.
- Show person 3's email and the name of their company: `person's company's name`.
- Put the weather example under `try`, and show a friendly message if it fails. Then turn off your internet and run it.
- Look up a city by name. Ask for the city, then read `https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1`. The reply's `results` is a list, and its first item has the city's `latitude` and `longitude`.
