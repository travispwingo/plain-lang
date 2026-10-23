# Study kit: testing Plain with people

Plain's success test is **read, understand, act**: an adult who has never programmed can read a Plain program, say what it does, and confidently change it. Two kinds of sessions test this. Neither needs a computer for the person taking part, except the last task of the site test.

## 1. Phrasing study (before and during the build)

**Who:** 8 to 10 adults who have never programmed.
**Time:** about 30 minutes each.
**You need:** this sheet, paper, and a pen.

Say: "There are no wrong answers. I'm testing Plain, not you. Write the steps the way you'd explain them to a careful friend who does exactly what you say."

Ask them to write steps for each task:

1. Ask someone's name, then greet them by name.
2. Pick a secret number from 1 to 100, and let someone guess it. Say "higher" or "lower" after each guess, and how many tries it took.
3. From a list of sales with dates, customers and amounts, keep the sales over 100, put the biggest first, add them up, and save them.
4. Look up a project on a website and show its name and how many stars it has. Say something helpful if the website doesn't answer.
5. Work out a tip for a bill at a given percent, for two different meals.
6. A to-do list you can add to, show, and cross things off, that remembers the list for next time.

**Record:** every line exactly as written. Add each one to `tests/phrasings.txt` as `their line => how Plain reads it` when Plain reads it, or `! their line` when it shouldn't. Lines many people write the same way become main words, and common alternatives become synonyms, if they clash with nothing.

## 2. Read, understand, act (before each release)

**Who:** 5 new adults who have never programmed (not from the phrasing study).
**You need:** printouts of the six sample programs in `examples/`.

For each sample:

1. "Please read this. Tell me in your own words what it does." (Understand)
2. "Make it do this instead:" one change, such as "make the game pick from 1 to 50" or "keep sales over 200". They write the change on the printout. (Act)

**Pass:** at least 4 of 5 people explain each sample correctly and make its change correctly, without help.

## 3. Messages test

Show each person 5 broken programs (from `tests/problems/`) and Plain's message for each. Ask them to fix the program using only the message. **Pass:** 4 of 5 people fix each one.

## 4. Site test (before launch)

5 new adults use only plain-lang.dev to: run an example, change it, and write a 5-line program of their own. Note every place they stop, guess or ask for help. Fix those before launch.
