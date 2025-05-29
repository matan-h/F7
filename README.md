# F7
> I know a command that could do that

![Screenshot of the app with grep() python command to find https links](./screenshots/hyperland-pygrep.png)

`F7` is an app to help you manipulate strings fast and easily using Python, the command line, or a local LLM.

## Installation
Install using pip:
```bash
pip install f7
```

Or using [pipx](https://github.com/pypa/pipx):

```bash
pipx install f7
```

<!-- In the future, maybe GitHub Releases -->

## Setup
### Linux

Requirements: `xsel` on X, `wl-clipboard` on Wayland.

To create desktop files, run:

```bash
f7 register
```

That will create the main application desktop file and optionally register a startup file.

Next, go to your system's keyboard shortcuts settings (e.g., `Settings > Keyboard > Shortcuts > Add Application` on KDE or GNOME), and bind the `f7` *application* to your preferred shortcut (e.g., `F7` or `F4`).

You can also try registering the command `<f7 path> show` instead.

### Windows

Run:

```bash
f7 register
```

That will register the startup registry key. The app listens for your configured shortcut. You can change the shortcut using the F7 settings in the tray menu.

### macOS

Currently not supported, but may be possible using macOS's Shortcuts app (`Shortcuts > + > Shell Script`) or Automator.

If you find a way to make it work, feel free to open a PR or reach out!

## Usage

1. **Select the Text:** Highlight any text from any app.

2. **Activate F7:** Hit your shortcut key.
   ![Screenshot of the F7 window appearing on todepond website](./screenshots/f7-opening.png)

3. **Type Your Transformation:**

   In the input field, use Python (default), command-line (`$` prefix), or LLM (`!` prefix or suffix).

   Example using Python:

   ```python
   [l.split()[0] for l in lines]
   ```

   *(This tells the app: for each line, split it into words, and give me the first one.)*

   Or using Bash:

   ```bash
   $cut -f1
   ```

   (Use `$$cut -f1` for live preview.)

   Live preview will show up as you type:

   ```
   18109
   8679
   ...
   ```

   ![Screenshot of the F7 window appearing](./screenshots/f7-todepond-python.png)

4. **Hit Enter:** Result is copied to your clipboard.

5. **Done!** Paste it wherever you want.

## Command Line Mode

You can also run F7 in command-line mode directly:

```bash
f7 show --cli
```

This allows using the same transformation interface from your terminal.

![Command mode screenshot](./screenshots/f7-command-mode.png)

## Local AI (LLM) Setup

Supports two backends: **Ollama** and **Llama.cpp**.

### 1. Ollama Setup

* **Install Ollama:** [ollama.com](https://ollama.com/)
* **Pull a model:** For example:

```bash
ollama pull phi3
```

You can find other available models on the Ollama library website.

* **Configure in App:**

  1. Open F7 settings (`/settings` or tray menu)
  2. Go to **AI** tab
  3. Set **Backend** to `ollama`
  4. Set **Model Name** (e.g., `phi3`)

**2. Llama.cpp Setup:**
### 2. Llama.cpp Setup

* **Download a GGUF model:** e.g., from [Hugging Face](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/tree/main)

  * Recommended: `Q4_K_M`

* **Configure in App:**

  1. Open F7 settings
  2. Go to **AI** tab
  3. Set **Backend** to `llama_cpp`
  4. Set path to the GGUF model
  5. Enable GPU if you have one (`llama_cpp_use_GPU`)

## F7 python
## what is this grep() function, that's not python builtin
F7 adds a few helpful twists to regular Python to speed things up:
* Predefined variables: `text` (alias:`s`), `lines`, `words`
* Auto-parsed content: `_` var will try to parse the text as JSON, Python literal, CSV or base64.

* Forgiving syntax: complete `({[` so half-written code like `[ l for l in lines` works!

- List display: Lists show as joined lines (`"\n".join(...)`) instead of `repr(...)`, so it easier to work with lines.

- Auto-display: Typing `text.upper` or `urldecode` get output automatically if they match `(str) → str`, or a method of `text`.
- Useful built-ins:
  - `grep("foo")` → like `re.search(...)` over `lines`
  - `sub("a", "b")` → like `re.sub(...)` on `text`
  - Other helpers: `entropy`, `from_base64`, `from_tsv`, etc.
- Preloaded utils: Things like `lnjoin = "\n".join`, `urlencode = quote_plus`. also there are string formatters like `snake_case`, `camel_case` that came from [`string_utils`](https://pypi.org/project/python-string-utils)

## FAQ

### F7 key triggers "caret browsing" in Chrome/uim

Unfortunately, Chrome doesn’t let you disable F7. Options:
* Remap shortcut to something else (e.g. `F4`)

  * Windows: `F7 settings > System > Hotkey`
  * Linux: System Settings > Keyboard Shortcuts
  * Use a browser that allows shortcut customization (e.g., Brave, Vivaldi)
  * Remap `F7` key to something else (e.g. using PowerToys on Windows bind F7 to alt+F7)

### F7 key triggers `caret browsing` in Firefox
If you use caret browsing, consider remapping the shortcut. Otherwise, just click "Do not ask me again" and choose "No".
Firefox will remember your choice.

### How to report errors/problems/suggestions

please open a [GitHub issue](https://github.com/matan-h/F7/issues)

### How can I donate you

If you found this app useful, you can buy me a coffee:

<a href="https://www.buymeacoffee.com/matanh" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-blue.png" alt="Buy Me A Coffee" height="47" width="200"></a>