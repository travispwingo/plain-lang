# Install Plain

You can try Plain in your browser right now, with nothing to install: [open the playground](/), pick an example and press **Run**.

Install Plain on your computer when you want to keep your programs and data files there, or have Plain ask Claude for ideas. It takes about 15 minutes. You don't need to know anything about programming.

You'll type a few commands into a window called Terminal (on a Mac) or PowerShell (on Windows). A command is a line of text that tells your computer what to do. Type each one exactly as shown, or copy it from this page and paste it. Then press **Return** (Mac) or **Enter** (Windows). Nothing happens until you do.

## Install on a Mac

You'll install three things: Python, the free program Plain runs on; pipx, a helper that installs programs like Plain; and Plain itself.

**1. Open Terminal.** Press **Command+Space**, type `Terminal` and press **Return**. A window opens with a line that ends in `%`. This is where you type commands. Leave it open.

**2. Download Python.** Go to [python.org/downloads](https://www.python.org/downloads/) and click the yellow **Download Python** button. Any version from 3.13 up works.

**3. Install Python.** Open the file you downloaded. You'll find it in your Downloads folder. Click **Continue** and **Agree** until you can click **Install**. Your Mac may ask for the password you use to log in.

**4. Install the web certificates.** When the installer finishes, a Finder window opens. Double-click **Install Certificates.command** in it. This lets Plain check that websites are who they say they are. A Terminal window shows a few lines and ends with `[Process completed]`. You can close that window.

**5. Check Python.** Quit Terminal (press **Command+Q**) and open it again, so it finds the new Python. Then type:

```bash
python3 --version
```

You should see `Python` and a version number, like `Python 3.15.1`. If your Mac offers to install "command line developer tools" instead, click **Cancel** and go back to step 2.

**6. Install pipx.** Type:

```bash
python3 -m pip install --user pipx
```

You'll see several lines while it works. The last one may be a warning that pipx is "not on PATH". PATH is the list of places your computer looks for commands. That's fine: the next step adds pipx to it.

**7. Tell Terminal where pipx is.** Type:

```bash
python3 -m pipx ensurepath
```

It says it added a folder to your PATH, and that you need to open a new terminal.

**8. Install Plain.** Quit Terminal and open it again. Then type:

```bash
pipx install plainlang
```

After a moment, it lists `plain` as a new command and says `done!`

**9. Check Plain.** Type:

```bash
plain --version
```

You should see `Plain` and a version number, like `Plain 0.1.0`. Plain is installed.

### Run your first program on a Mac

**1. Open TextEdit.** Press **Command+Space**, type `TextEdit` and press **Return**. Click **New Document**.

**2. Make it plain text.** Choose **Make Plain Text** from the **Format** menu. Plain can't read the rich text TextEdit uses at first.

**3. Type this line:**

```plain fragment
show "Hello there!"
```

**4. Save it.** Choose **Save** from the **File** menu. Name it `hello.plain`, choose **Documents** as the place, and click **Save**. If TextEdit asks which ending to use, click **Use .plain**.

**5. Run it.** In Terminal, type these two commands, one at a time:

```bash
cd Documents
plain run hello.plain
```

The first command moves Terminal into your Documents folder, where you saved the file. The second runs your program. You should see:

```text
Hello there!
```

You've written and run a program. Next, try the [lessons](/learn/).

## Install on Windows

You'll install three things: Python, the free program Plain runs on; pipx, a helper that installs programs like Plain; and Plain itself.

**1. Open PowerShell.** Press the **Windows** key, type `PowerShell` and press **Enter**. A window opens with a line like `PS C:\Users\Ann>`. This is where you type commands.

**2. Download Python.** Go to [python.org/downloads](https://www.python.org/downloads/) and click the yellow **Download Python install manager** button.

**3. Install Python.** Open the file you downloaded. You'll find it in your Downloads folder. Click **Install**.

**4. Check Python.** Close PowerShell and open it again. Then type:

```bash
python --version
```

The first time, Python may ask you a few yes or no questions. Type `y` and press **Enter** for each one. Be sure to say yes to **Install CPython now?** CPython is Python itself. If a window opened by itself after step 3 and asked these questions, answer them there the same way.

When it's done, you should see `Python` and a version number, like `Python 3.15.1`. Any version from 3.13 up works. If you don't see it, type `python --version` again. If the Microsoft Store opens instead, Python isn't installed yet: go back to step 2.

If you used the standalone installer instead (the link under the yellow button), tick **Add python.exe to PATH** on its first screen before you click **Install Now**.

**5. Install pipx.** Type:

```bash
python -m pip install --user pipx
```

You'll see several lines while it works. The last one may be a warning that pipx is "not on PATH". PATH is the list of places your computer looks for commands. That's fine: the next step adds pipx to it.

**6. Tell PowerShell where pipx is.** Type:

```bash
python -m pipx ensurepath
```

It says it added a folder to your PATH, and that you need to open a new terminal.

**7. Install Plain.** Close PowerShell and open it again. Then type:

```bash
pipx install plainlang
```

After a moment, it lists `plain` as a new command and says `done!`

**8. Check Plain.** Type:

```bash
plain --version
```

You should see `Plain` and a version number, like `Plain 0.1.0`. Plain is installed.

### Run your first program on Windows

**1. Open Notepad.** Press the **Windows** key, type `Notepad` and press **Enter**.

**2. Type this line:**

```plain fragment
show "Hello there!"
```

**3. Save it.** Choose **Save as** from the **File** menu. Choose **Documents** on the left. Type `hello.plain` as the file name, and set **Save as type** to **All files**. If there's an **Encoding** choice, leave it on **UTF-8**. Click **Save**.

**4. Open PowerShell in your Documents folder.** Open File Explorer and go to **Documents**, where you saved the file. Click the address bar at the top, type `powershell` and press **Enter**. A new PowerShell window opens, already in that folder.

**5. Run it.** In the new window, type:

```bash
plain run hello.plain
```

You should see:

```text
Hello there!
```

You've written and run a program. Next, try the [lessons](/learn/).

## If something goes wrong

Find the message you see, then follow the fix.

- **"command not found: plain"** (Mac) or **"The term 'plain' is not recognized"** (Windows). Close Terminal or PowerShell and open it again. If you still see it, run step 7 (Mac) or step 6 (Windows) again, then close and open the window again. On Windows, restarting your computer can also help.
- **"command not found: pipx"** or **"The term 'pipx' is not recognized"**. Type `python3 -m pipx` (Mac) or `python -m pipx` (Windows) where the steps say `pipx`. For example: `python3 -m pipx install plainlang`.
- **"Check the file name "hello.plain". There's no file with that name here."** Terminal or PowerShell is in a different folder from your file, or the file has a different name. Type `ls` (Mac) or `dir` (Windows) to list the files in the folder. If you see `hello.plain.txt`, your editor added `.txt` to the name. Rename it with `mv hello.plain.txt hello.plain` (Mac) or `ren hello.plain.txt hello.plain` (Windows).
- **Plain's message mentions words like "rtf1" or "fonttbl".** TextEdit saved your file as rich text. In TextEdit, choose **Make Plain Text** from the **Format** menu, then save again.
- **"Save "hello.plain" as plain text (UTF-8), then try again."** Save the file again, and choose **UTF-8** as the encoding.
- **"Install your computer's web certificates, then run this again."** On a Mac, open your **Applications** folder, open the **Python** folder in it, and double-click **Install Certificates.command**.

If you're still stuck, see [Get help](/help/).

## Ask Claude for ideas (optional)

Plain can ask Claude, an AI made by Anthropic, for ideas when it can't follow a line. You don't need this to use Plain. Without it, Plain still offers its own ideas.

You need two things:

- **An Anthropic account.** Sign up at [platform.claude.com](https://platform.claude.com). Anthropic charges your account a small amount for each request, so set up billing in your account first.
- **A key.** A key is a secret code that lets Plain use your account. In your account, go to **Settings**, then **API keys**, and create a key. Copy it right away: it starts with `sk-ant-`, and Anthropic shows it only once. Keep it secret, like a password.

Then follow these steps.

**1. Install Plain with Claude's help included.** Type:

```bash
pipx install "plainlang[ai]"
```

If you've already installed Plain, add `--force` so pipx replaces it:

```bash
pipx install --force "plainlang[ai]"
```

**2. Save your key where Plain looks for it.** Plain looks for your key in a setting called `ANTHROPIC_API_KEY`. In the command below, put your key in place of `paste-your-key-here`, and keep the quotes.

On a Mac, type:

```bash
echo 'export ANTHROPIC_API_KEY="paste-your-key-here"' >> ~/.zshrc
```

On Windows, type:

```bash
setx ANTHROPIC_API_KEY "paste-your-key-here"
```

**3. Close Terminal or PowerShell and open it again.** Now, when you use `plain run` or `plain fix` and Plain can't follow a line, it tells you it's asking Claude:

```text
Asking Claude for ideas. This sends hello.plain to Anthropic, which charges your account a small amount for each request.
```

Claude's ideas come after Plain's own, marked `(from Claude)`.

Here's what Plain does to keep you in charge:

- Plain checks every idea from Claude before it shows it to you, and leaves out any idea that doesn't work.
- Plain changes your file only when you choose an idea, and keeps your old file in a copy that ends in `.bak`.
- Plain sends the lines of your program, after hiding anything that looks like a password or a key. It never sends your data files or the answers you type.
- Plain asks Claude only when you run it in Terminal or PowerShell. It never asks in `plain check` or in the playground.

**To turn it off for one run,** add `--no-ai`:

```bash
plain run hello.plain --no-ai
```

**To turn it off every time,** set `PLAIN_AI` to `off`, then close the window and open it again. On a Mac, type:

```bash
echo 'export PLAIN_AI=off' >> ~/.zshrc
```

On Windows, type:

```bash
setx PLAIN_AI off
```

## Choose a text editor

Any text editor works. Save each program as plain text, with a name that ends in `.plain`.

- **On a Mac,** TextEdit works. Choose **Make Plain Text** from the **Format** menu for each new file. To make every new file plain text, choose **Settings** from the **TextEdit** menu, and under **Format** choose **Plain text**.
- **On Windows,** Notepad works. When you save, set **Save as type** to **All files**, or Notepad may add `.txt` to the name.
- **A free code editor,** such as Visual Studio Code, shows line numbers. They match the line numbers in Plain's messages.

Don't write programs in Word, Pages or Google Docs: they save hidden formatting that Plain can't read. Text you copy from them is fine. Plain reads “curly quotes” the same as "straight quotes".

To move a line to the right, under an `if` or a `repeat`, type 4 spaces or press **Tab**. Plain treats a Tab the same as 4 spaces.

## If plain starts a different program

Another program called Plain, a tool programmers use to build websites, also installs a command named `plain`. If you have it, `plain` may start that program instead of this one, or pipx may say a file named `plain` already exists.

You can still use this Plain. Install it straight into Python, then type `python3 -m plainlang` (Mac) or `python -m plainlang` (Windows) wherever this site says `plain`. On a Mac:

```bash
python3 -m pip install --user plainlang
python3 -m plainlang run hello.plain
```

On Windows:

```bash
python -m pip install --user plainlang
python -m plainlang run hello.plain
```

## Update or remove Plain

To get the newest version of Plain, type:

```bash
pipx upgrade plainlang
```

To remove Plain from your computer, type:

```bash
pipx uninstall plainlang
```
