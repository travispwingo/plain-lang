"""Showing, asking, waiting, time and chance."""

from decimal import ROUND_HALF_UP, Decimal

from ..problems import Problem
from ..registry import Items, List, Number, Text, Value, step, value
from ..values import auto_number, same, as_number, show_inline, show_value

TOPIC_SCREEN = "Show and ask"
TOPIC_TIME = "Time and chance"


@step("show {value}", example='show "Hello there"', topic=TOPIC_SCREEN)
def show(run, value: Value) -> None:
    """Shows the value on its own line. Lists show as "a, b and c", and tables as lined-up columns."""
    run.host.show(show_value(value))


@step("ask {question}", example='ask "What is your name?" and call it name', topic=TOPIC_SCREEN)
def ask(run, question: Value) -> Value:
    """Shows the question and waits for an answer. An answer that looks like a number becomes one."""
    return auto_number(run.host.ask(show_value(question)))


@step("ask {question} with choices {choices}",
      example='ask "Which size?" with choices "small", "medium" and "large" and call it size',
      topic=TOPIC_SCREEN)
def ask_choices(run, question: Value, choices: Items) -> Value:
    """Shows a numbered menu. You can type the number or the choice itself. Plain asks again if the answer is neither."""
    options = choices[0] if len(choices) == 1 and isinstance(choices[0], list) else choices
    if not options:
        raise Problem("Give the choices at least one item.", "There's nothing to choose from.")
    run.host.show(show_value(question))
    for number, option in enumerate(options, start=1):
        run.host.show(f"  {number}) {show_inline(option)}")
    while True:
        answer = run.host.ask("Type a number or a choice:")
        for option in options:
            if same(option, answer):
                return option
        n = as_number(answer)
        if n is not None and n == n.to_integral_value() and 1 <= n <= len(options):
            return options[int(n) - 1]
        run.host.show(f"Please type one of the choices, or a number from 1 to {len(options)}.")


@step("wait {seconds} second|seconds", example="wait 2 seconds", topic=TOPIC_SCREEN)
def wait_seconds(run, seconds: Number) -> None:
    """Waits for that many seconds."""
    if seconds < 0:
        raise Problem("Use 0 or more seconds.", f"Plain can't wait {seconds} seconds.")
    run.host.wait(float(seconds))


@step("wait {minutes} minute|minutes", example="wait 1 minute", topic=TOPIC_SCREEN)
def wait_minutes(run, minutes: Number) -> None:
    """Waits for that many minutes."""
    if minutes < 0:
        raise Problem("Use 0 or more minutes.", f"Plain can't wait {minutes} minutes.")
    run.host.wait(float(minutes) * 60)


@step("wait for Enter", example="wait for Enter", topic=TOPIC_SCREEN)
def wait_for_enter(run) -> None:
    """Waits until you press Enter."""
    run.host.ask("Press Enter to go on.")


@step("clear the screen", example="clear the screen", topic=TOPIC_SCREEN)
def clear_screen(run) -> None:
    """Clears everything shown so far."""
    run.host.clear()


@step("start the stopwatch", example="start the stopwatch", topic=TOPIC_TIME)
def start_stopwatch(run) -> None:
    """Starts the stopwatch again from 0."""
    run.stopwatch_start = run.host.clock()


@value("the stopwatch", example="show the stopwatch", topic=TOPIC_TIME)
def stopwatch(run) -> Number:
    """Seconds since "start the stopwatch", or since the program began, to 1 decimal place."""
    seconds = Decimal(repr(round(run.host.clock() - run.stopwatch_start, 6)))    # no float noise
    return seconds.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


@value("the time now", example='show "It is {the time now}."', topic=TOPIC_TIME)
def time_now(run) -> Text:
    """The time as text, like "14:05"."""
    return run.host.now().strftime("%H:%M")


@value("the date today", example='show "Today is {the date today}."', topic=TOPIC_TIME)
def date_today(run) -> Text:
    """The date as text, like "2026-10-23"."""
    return run.host.now().strftime("%Y-%m-%d")


@value("a random number from {low} to {high}", "a random number between {low} and {high}",
       example="set roll to a random number from 1 to 6", topic=TOPIC_TIME)
def random_number(run, low: Number, high: Number) -> Number:
    """A whole number between the two numbers, both included."""
    for n in (low, high):
        if n != n.to_integral_value():
            raise Problem("Use whole numbers for a random number, like 1 and 6.",
                          f"{show_value(n)} is not a whole number.")
    low, high = sorted((int(low), int(high)))
    return Decimal(run.host.random.randint(low, high))


@value("a random item from {items}", example='show a random item from a list of "heads" and "tails"',
       topic=TOPIC_TIME)
def random_item(run, items: List) -> Value:
    """One item of the list, picked by chance."""
    if not items:
        raise Problem("Use a list with at least one item.", "The list is empty, so there's nothing to pick.")
    return run.host.random.choice(items)


@step("shuffle {items}", example="shuffle cards", topic=TOPIC_TIME)
def shuffle(run, items: List) -> None:
    """Puts the list in a random order."""
    run.host.random.shuffle(items)


@value("the problem", example='show "Plain couldn\'t do it: {the problem}"', topic="Core steps")
def the_problem(run) -> Text:
    """Inside "if that fails", the message about what went wrong."""
    return run.problem_text
