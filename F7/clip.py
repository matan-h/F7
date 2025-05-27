# created by gemini-exp

import os
import platform
import shutil
import subprocess
import sys
import time

# --- Dependencies ---
# This library requires:
# - pyperclip: `pip install pyperclip`
# - pyautogui: `pip install pyautogui`
#
# On Linux, it also works best if the user has:
# - wl-clipboard: (Provides wl-paste) `sudo apt install wl-clipboard` or equivalent
# - xsel: `sudo apt install xsel` or equivalent

try:
    import pyperclip
except ImportError:
    print(
        "Warning: pyperclip library not found. Clipboard operations (including fallback method) will fail.",
        file=sys.stderr,
    )
    print("Install it using: pip install pyperclip", file=sys.stderr)
    pyperclip = None  # Set to None to check availability later

try:
    import pyautogui
except ImportError:
    print(
        "Warning: pyautogui library not found. Clipboard simulation fallback method will fail.",
        file=sys.stderr,
    )
    print("Install it using: pip install pyautogui", file=sys.stderr)
    pyautogui = None  # Set to None to check availability later

# --- Platform-Specific Implementations ---


def _get_selected_text_linux_direct():
    """
    Tries to get selected text on Linux using native tools (wl-paste, xsel)
    for the primary selection buffer without modifying the clipboard.
    Returns the selected text or None if unsuccessful.
    """
    # Check for Wayland first
    is_wayland = (
        "WAYLAND_DISPLAY" in os.environ
        or os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    )

    if is_wayland:
        # Try Wayland's wl-paste for primary selection
        wl_paste_path = shutil.which("wl-paste")
        if wl_paste_path:
            try:
                # --no-newline prevents adding an extra newline
                # --primary selects the primary selection buffer
                result = subprocess.run(
                    [wl_paste_path, "--primary", "--no-newline"],
                    capture_output=True,
                    text=True,
                    check=True,  # Raise error on non-zero exit
                    timeout=0.5,  # Short timeout
                )
                # Check if stdout is not empty, as empty selection is possible
                if result.stdout:
                    return result.stdout
                else:
                    # print("wl-paste succeeded but returned empty (no primary selection?).", file=sys.stderr)
                    return ""  # Return empty string for empty selection
            except FileNotFoundError:
                # Should not happen due to shutil.which, but belt and suspenders
                print(
                    "wl-paste command not found despite initial check.", file=sys.stderr
                )
            except subprocess.TimeoutExpired:
                print("wl-paste command timed out.", file=sys.stderr)
            except subprocess.CalledProcessError as e:
                # wl-paste might fail if compositor doesn't support primary selection,
                # or if no selection exists. Error code might vary.
                # print(f"wl-paste failed (is primary selection supported/active?): {e}", file=sys.stderr)
                # Treat failure as "no selection retrievable this way"
                pass
            except Exception as e:
                print(
                    f"An unexpected error occurred with wl-paste: {e}", file=sys.stderr
                )
        # else:
        #     print("Wayland session detected, but wl-paste command not found. Install wl-clipboard.", file=sys.stderr)

    # If not Wayland, or wl-paste failed/not found, try X11's xsel
    # Check if DISPLAY is set, indicating an X11 context (could be XWayland)
    if "DISPLAY" in os.environ:
        xsel_path = shutil.which("xsel")
        if xsel_path:
            try:
                # -p selects primary, -o outputs
                result = subprocess.run(
                    [xsel_path, "-p", "-o"],
                    capture_output=True,
                    text=True,
                    check=True,  # Raise error on non-zero exit
                    timeout=0.5,  # Short timeout
                )
                # Check if stdout is not empty
                if result.stdout:
                    return result.stdout
                else:
                    # print("xsel succeeded but returned empty (no primary selection?).", file=sys.stderr)
                    return ""  # Return empty string for empty selection
            except FileNotFoundError:
                print("xsel command not found despite initial check.", file=sys.stderr)
            except subprocess.TimeoutExpired:
                print("xsel command timed out.", file=sys.stderr)
            except subprocess.CalledProcessError as e:
                # xsel commonly fails if no primary selection exists.
                # print(f"xsel failed (is primary selection active?): {e}", file=sys.stderr)
                # Treat failure as "no selection retrievable this way"
                pass
            except Exception as e:
                print(f"An unexpected error occurred with xsel: {e}", file=sys.stderr)
        # else:
        #    print("X11/XWayland context detected, but xsel command not found. Install xsel.", file=sys.stderr)

    # If both methods failed or weren't applicable
    return None  # Indicate failure to retrieve directly


def _get_selected_text_clipboard_hack():
    """
    Gets selected text by simulating Ctrl+C (Cmd+C on Mac)
    and reading the clipboard.

    WARNING: This modifies the user's clipboard content temporarily!
    Returns the selected text or None if unsuccessful.
    """
    if not pyperclip or not pyautogui:
        print(
            "Error: Clipboard hack requires 'pyperclip' and 'pyautogui'.",
            file=sys.stderr,
        )
        return None

    original_clipboard = None
    selected_text = None
    system = platform.system()

    try:
        # 1. Store original clipboard content
        try:
            original_clipboard = pyperclip.paste()
        except Exception as e:
            # Pyperclip can raise various errors depending on backend issues
            print(
                f"Warning: Could not read initial clipboard content: {e}",
                file=sys.stderr,
            )
            original_clipboard = None  # Treat as unknown
        try:
            # 2. Simulate the copy command
            if system == "Darwin":  # macOS
                pyautogui.hotkey("command", "c")
            elif system == "Windows" or system == "Linux":
                pyautogui.hotkey("ctrl", "c")
            else:
                print(
                    f"Unsupported system for copy simulation: {system}", file=sys.stderr
                )
                return None  # Cannot simulate copy
        except KeyboardInterrupt:  # TODO:option add ctrl+shift+c option to settings?
            raise Exception(
                "you are likely running shift from the terminal. to copy on windows/macOS it does ctrl+c. Unfortunately, its the same shortcut to quit in the terminal. "
            )

        # 3. Wait briefly for clipboard to update (crucial, might need tuning)
        time.sleep(0.3)

        # 4. Read the new clipboard content
        try:
            selected_text = pyperclip.paste()
        except Exception as e:
            print(
                f"Error: Could not read clipboard after copy simulation: {e}",
                file=sys.stderr,
            )
            selected_text = None  # Failed to read

    except pyautogui.PyAutoGUIException as e:
        print(f"Error during pyautogui operation: {e}", file=sys.stderr)
        selected_text = None  # Indicate failure
    finally:
        # 5. Restore original clipboard content *if* we read it successfully
        #    Only restore if the content actually changed, or if reading failed after copy
        if original_clipboard is not None:
            current_clipboard_after_read = selected_text  # May be None if read failed
            if current_clipboard_after_read != original_clipboard:
                try:
                    pyperclip.copy(original_clipboard)
                    # Short pause after restore might sometimes help, but usually not needed
                    # time.sleep(0.05)
                except Exception as restore_e:
                    print(
                        f"Error: Failed to restore original clipboard content: {restore_e}",
                        file=sys.stderr,
                    )
            # else:
            #     print("Clipboard content unchanged or initial read failed, no restore needed.", file=sys.stderr)
        # else:
        #     print("Could not read initial clipboard, skipping restore.", file=sys.stderr)

    # If clipboard content didn't change from original *and* we read both successfully,
    # it likely means no text was selected or the copy failed silently.
    if (
        original_clipboard is not None
        and selected_text is not None
        and selected_text == original_clipboard
    ):
        print(
            "Clipboard content unchanged after copy simulation. maybe copy failed.",
            file=sys.stderr,
        )
    #  return "" # Return empty string in this ambiguous case

    # Return the text read (which might be None if reading failed)
    # If selected_text is None here, it means an error occurred during the process
    return selected_text


# --- Public API ---
def get_selected_text(allow_clipboard_hack=True):
    """
    Attempts to get the currently selected text in a cross-platform manner.

    On Linux, it first tries to read the primary selection directly using
    'wl-paste' (Wayland) or 'xsel' (X11/XWayland) without modifying the clipboard.

    If the direct method fails on Linux, or on Windows/macOS, and if
    `allow_clipboard_hack` is True (default), it falls back to simulating
    a copy command (Ctrl+C or Cmd+C) and reading the clipboard content.

    Args:
        allow_clipboard_hack (bool): If True, allows falling back to the
            clipboard simulation method which temporarily modifies the
            user's clipboard. Defaults to True.

    Returns:
        str: The selected text, or an empty string if no text is selected
             or if retrieval failed (and hack wasn't allowed or also failed).
        None: If a critical error occurred (e.g., missing dependencies for
              the only available method).

    WARNING:
        The clipboard hack method modifies the user's clipboard. While this
        function attempts to restore the original content, it's not guaranteed
        in all scenarios (e.g., if the script crashes). Use with caution.
    """
    system = platform.system()
    selected_text = None

    # 1. Try direct method on Linux
    if system == "Linux":
        selected_text = _get_selected_text_linux_direct()
        if selected_text is not None:
            # print("Retrieved text using Linux direct method.", file=sys.stderr)
            return selected_text  # Success!

    # 2. If direct method failed (returned None) or not on Linux,
    #    try clipboard hack if allowed.
    if selected_text is None and allow_clipboard_hack:
        # print("Direct method failed or not applicable. Trying clipboard hack...", file=sys.stderr)
        selected_text = _get_selected_text_clipboard_hack()
        if selected_text is not None:
            # print("Retrieved text using clipboard hack method.", file=sys.stderr)
            return selected_text  # Hack succeeded (returned string, possibly empty)
        else:
            # Hack failed (returned None)
            print("Clipboard hack method failed.", file=sys.stderr)
            return None  # Indicate critical failure of the hack method itself

    # 3. If direct method failed and hack wasn't allowed or also failed
    elif selected_text is None and not allow_clipboard_hack:
        print(
            "Direct method failed or not applicable, and clipboard hack is disallowed.",
            file=sys.stderr,
        )
        return ""  # Return empty string, as we couldn't get text but didn't critically fail

    # Should theoretically not be reached if logic is sound, but as a safeguard:
    return selected_text if selected_text is not None else ""


# --- Example Usage ---
if __name__ == "__main__":
    print("Attempting to get selected text...")
    print("Please select some text in another window within the next 5 seconds.")
    time.sleep(5)

    # Example 1: Try direct method first, fallback to hack if needed (default)
    print("\n--- Test 1: Default behavior (allow_clipboard_hack=True) ---")
    text1 = get_selected_text()
    if text1 is not None:
        print(f"Selected Text: >>>\n{text1}\n<<<")
        if platform.system() != "Linux":
            print("(Used clipboard hack method)")
    else:
        print("Failed to retrieve selected text (critical error).")

    # Example 2: Only allow direct method (relevant on Linux)
    if platform.system() == "Linux":
        print("\n--- Test 2: Direct method only (allow_clipboard_hack=False) ---")
        print("Select text again if needed (5 seconds)...")
        time.sleep(5)
        text2 = get_selected_text(allow_clipboard_hack=False)
        if text2 is not None:  # Will be "" if direct failed but hack disallowed
            print(f"Selected Text (Direct Only): >>>\n{text2}\n<<<")
            if not text2:
                print("(Direct method failed or returned empty, hack disallowed)")
        else:
            # This case should not happen with allow_clipboard_hack=False
            print("Failed to retrieve selected text (unexpected None).")

    print("\n--- Finished ---")
