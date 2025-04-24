
import sys
# Prevent PyAutoGUI and pywinctl from setting Process DPI Awareness, which Qt tries to do then throws warnings about it.
# The unittest workaround significantly increases build time, boot time and build size with PyInstaller.
# https://github.com/asweigart/pyautogui/issues/663#issuecomment-2171881720
# QT doesn't call those from Python/ctypes, meaning we can stop other programs from setting it.
if sys.platform == "win32":
    import ctypes
    # pyautogui._pyautogui_win.py
    ctypes.windll.user32.SetProcessDPIAware = lambda: None  # pyright: ignore[reportAttributeAccessIssue]
    # pymonctl._pymonctl_win.py
    # pywinbox._pywinbox_win.py
    ctypes.windll.shcore.SetProcessDpiAwareness = (  # pyright: ignore[reportAttributeAccessIssue]
        lambda _: None  # pyright: ignore[reportUnknownLambdaType]
    )
