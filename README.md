# F7
> stop using `clipaste | <your python/command here> | clipcopy`

<!-- TODO: screenshot -->

`F7` is a app to help you manipulate strings fast and easily using either python,command line,or local LLM

## Installation
Install using pip:
```bash
pip install f7
```
or using [pipx](https://github.com/pypa/pipx):
```bash
pipx install f7
```

<!-- in the future, maybe gh releases -->

## Setup
### Linux
requirements: `xsel` on X,`wl-clipboard` on wayland.

to create desktop files, run
```bash
f7 register
```
That will create the main application desktop file and optionally register a startup file.

the next step is to go the `Shortcuts` settings (`Settings > Keyboard > Shortcuts > Add Application` on KDE and Gnome), and register the `f7` application with your custom shortcut (such as `F7` key)

you could also try to register the command `<f7 path> show` instead

### Windows
run
```bash
f7 register
```
That will register the startup registry key. The app itself would listen to shortcut. you can change the shortcut using the `F7` settings (on the tray menu)

### Macos
currently no support, but maybe possible with MacOS `Shortcuts` app: `Shortcuts > + > shell script` or using `Automator` app.
If you know any way to do that, please reach out or open a PR

## Usage
1.  **Select the Text:** Highlight the list of names in whatever application you're using.
    <!-- ![Screenshot of text selection](https://placehold.co/400x100/eee/333?text=1.+Select+Text+in+App) -->

2.  **Activate the Tool using the shortcut:**
    <!-- ![Screenshot of the utility window appearing](https://placehold.co/500x150/ddd/333?text=2.+Utility+Appears) -->

3.  **Type Your Transformation:** In the input field, you can use a bit of Python (python is the default,There are multiple plugins such as local LLM, with `!` prefix or suffix, command line with `$` prefix). For this task, you'd type:
    ```python
    [name.split()[0] for name in lines]
    ```
    *(This tells the tool: "For each line of the selected text, split it into words, and give me the first word.")*
    (without the `print` it would just join the list by `\n`)

    As you type, you'll see a **live preview** of what the result will be:
    ```
    Laura
    Dale
    Audrey
    Harry
    ```
    <!-- ![Screenshot of the utility with input and preview](https://placehold.co/500x200/ccc/333?text=3.+Type+Command+&+See+Preview) -->

4.  **Hit Enter:** Press the `Enter` key.

5.  **Done!** The list `['Laura', 'Dale', 'Audrey', 'Harry']` is now copied to your clipboard. The application window will disappear. You can now paste your extracted first names wherever you need them!
    <!-- ![Animation/icon of pasting text](https://placehold.co/300x80/eee/333?text=4.+Result+Copied!+Paste+it!) -->

## Setting Up Local AI (LLM)

This application supports two main backends: **Ollama** and **Llama.cpp**.

**1. Ollama Setup:**

* **Install Ollama:** If you haven't already, download and install Ollama from [ollama.com](https://ollama.com/).
* **Pull a Model:** Open your terminal or command prompt and pull a model that you want to use. For example, to get the `phi3` model (a good general-purpose small model):
    ```bash
    ollama pull phi3
    ```
    You can find other available models on the Ollama library website.
* **Configure in the App:**
    1.  Open the application's settings (type `/settings` or use the tray menu).
    2.  Go to the "Ai" (or similarly named) settings tab.
    3.  Set "Backend" to `ollama` (its default).
    4.  In "Ollama Model," enter the name of the model you pulled (e.g., `phi3`).

**2. Llama.cpp Setup:**
* **Get a Llama.cpp Compatible Model:** You'll need a GGUF file. You can find [these](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/tree/main) on platforms like Hugging Face. (usually you want to pick the `Q4_K_M` file)
* **Install Llama.cpp Python Bindings:** If the application doesn't bundle it, you might need to install the `llama-cpp-python` library. Usually, this is handled by the application's dependencies.
* **Configure in the App:**
    1.  Open the application's settings.
    2.  Go to the Ai settings tab.
    3.  Set "Backend" to `llama_cpp`.
    4.  In "Llama.cpp Model Path," provide the full path to your downloaded GGUF model file on your computer.
    5.  Configure `llama_cpp_n_threads` (number of CPU threads) and `llama_cpp_use_GPU` (if you have a compatible GPU and Llama.cpp build).
    6.  Adjust other settings as needed.

## FAQ
<!-- TODO: add FAQ  -->
### How to report errors/problems/suggestions

please open a [GitHub issue](https://github.com/matan-h/F7/issues)

### How can I donate you

If you found this tool/library useful, it would be great if you could buy me a coffee:

<a href="https://www.buymeacoffee.com/matanh" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-blue.png" alt="Buy Me A Coffee" height="47" width="200"></a>