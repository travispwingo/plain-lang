# Install Plain

You can try Plain in your browser with nothing to install: [open the playground](/). Install it on your computer to keep your programs there.

Copy each command on this page into Terminal (Mac and Linux) or PowerShell (Windows), then press **Return** or **Enter**.

## On a Mac

Open Terminal: press **Command+Space**, type `Terminal` and press **Return**. Then type:

```bash
brew install travispwingo/tap/plain
```

This installs Plain and everything it needs.

**No Homebrew yet?** It's a free helper that installs programs. Paste the line from [brew.sh](https://brew.sh) into Terminal first. Press **Return** when it asks, and type your Mac password if it asks for it. Nothing shows as you type. When it's done, type the lines it shows under **Next steps**, and then the line above.

**Older Mac?** If **About This Mac**, in the Apple menu, shows an Intel chip or macOS 14 or earlier, Homebrew is slow there. Follow the [Linux steps](#on-linux) in Terminal instead.

## On Windows

Open PowerShell: press the **Windows** key, type `PowerShell` and press **Enter**. Then type:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

This installs uv, a free helper that installs programs. Close PowerShell, open it again and type:

```bash
uv tool install plainlang
```

## On Linux

Open a terminal. On most Linux computers, press **Ctrl+Alt+T**. Then type:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

If it says `curl` isn't found, type `wget -qO- https://astral.sh/uv/install.sh | sh` instead. This installs uv, a free helper that installs programs. Close the terminal, open it again and type:

```bash
uv tool install plainlang
```

If you use Homebrew, the Mac command works on Linux too.

## Run your first program

**1. Check Plain.** Type `plain --version`. You should see a version number, like `Plain 0.1.0`.

**2. Write a program.** Open TextEdit (Mac), Notepad (Windows) or Text Editor (Linux), and type:

```plain fragment
show "Hello there!"
```

**3. Save it** in **Documents** as `hello.plain`. In TextEdit, first choose **Make Plain Text** from the **Format** menu, and click **Use .plain** if it asks. In Notepad, set **Save as type** to **All files**.

**4. Run it.** On a Mac or Linux, type these one at a time:

```bash
cd Documents
plain run hello.plain
```

On Windows, open **Documents** in File Explorer, type `powershell` in the address bar and press **Enter**. Then type `plain run hello.plain`.

You should see:

```text
Hello there!
```

You've written and run a program. Next, try the [lessons](/learn/).

## If something goes wrong

- **"command not found: brew"** on a Mac: type `echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile`, then close Terminal and open it again.
- **"command not found"** or **"is not recognized"**: close Terminal or PowerShell and open it again. On Windows, restart your computer if that doesn't help.
- **"There's no file with that name here."** Type `ls` to see the files in this folder. If you see `hello.plain.txt`, type `mv hello.plain.txt hello.plain`.
- **"Save "hello.plain" as plain text (UTF-8)"**: save the file again, with **UTF-8** as the encoding.
- **"Update your computer's web certificates"**: the rest of Plain's message says how. See also [Fix web certificate problems](/help/#certificates).

If you're still stuck, see [Get help](/help/).

## Choose a text editor

Any text editor works. Save each program as plain text, with a name that ends in `.plain`. A free code editor, such as Visual Studio Code, shows line numbers that match the ones in Plain's messages.

Don't write programs in Word, Pages or Google Docs: they save hidden formatting that Plain can't read. Text you copy from them is fine.

To move a line to the right, under an `if` or a `repeat`, type 4 spaces or press **Tab**.

## If plain starts a different program

Another Plain, a tool programmers use to build websites, also has a `plain` command. If you have it, `plain` may start that program, or uv may say `Executable already exists: plain`.

You can still use this Plain. Where this site says `plain`, type `"$(brew --prefix plain)/bin/plain"` if you used Homebrew, or `uvx --from plainlang plain` if you used uv. For example:

```bash
uvx --from plainlang plain run hello.plain
```

## Update or remove Plain

To get the newest version, type `brew upgrade plain` if you used Homebrew, or `uv tool upgrade plainlang` if you used uv. To remove Plain, type `brew uninstall plain` or `uv tool uninstall plainlang`.
