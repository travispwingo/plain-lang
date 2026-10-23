"""The core steps, read by hand in parser.py. Listed here for the phrase reference and the AI."""

from ..registry import core

core("set NAME to VALUE", "Keeps a value under a name. Lists and records are copied.", "set score to 0")
core("STEP and call it NAME", "Keeps what a step gives back under a name.", 'ask "Your name?" and call it name')
core("if CHECK", "Takes the steps under it only when the check is yes.", 'if score is more than 10')
core("otherwise if CHECK", "Another check, tried when the ones above weren't yes.", "otherwise if score is 10")
core("otherwise", "The steps to take when none of the checks above were yes.", "otherwise")
core("repeat N times", "Takes the steps under it N times. Also: repeat once, repeat twice.", "repeat 3 times")
core("repeat forever", "Repeats until you leave with \"stop repeating\" or end with \"stop the program\".", "repeat forever")
core("repeat until CHECK", "Takes the steps, then checks. Stops once the check is yes.", "repeat until guess is secret")
core("repeat while CHECK", "Checks first, and takes the steps while the check is yes.", "repeat while lives is more than 0")
core("repeat for each NAME in LIST", "Takes the steps once for each item of the list.", "repeat for each sale in sales")
core("repeat for each NAME from A to B", "Counts up from A to B. Write \"down to\" to count down.", "repeat for each n from 1 to 10")
core("stop repeating", "Leaves the repeat it's in.", "stop repeating")
core("skip to the next round", "Goes straight to the next round of the repeat.", "skip to the next round")
core("stop the program", "Ends the program now.", "stop the program")
core("how to WORDS (NAME)", "Makes a step of your own. Words in brackets are values you hand in.", "how to greet (person)")
core("give back VALUE", "Ends your own step and hands back a value.", "give back total")
core("try", "Takes the steps under it. If one has a problem, Plain goes to \"if that fails\".", "try")
core("if that fails", "The steps to take when a step under \"try\" had a problem. \"the problem\" says what went wrong.", "if that fails")
core("N% of VALUE", "A part of a value, like 15% of a bill. \"N percent of VALUE\" works too.", "show 15% of 80",
     topic="Numbers and text")
