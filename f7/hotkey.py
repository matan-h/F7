import platform

os_name = platform.system()
if os_name == "Windows":
    from pynput import keyboard

    class HotkeyListener:
        def __init__(self, hotkey_str: str, callback):
            self.hotkey = keyboard.HotKey(keyboard.HotKey.parse(hotkey_str), callback)
            self.listener = keyboard.Listener(
                on_press=self.for_canonical(self.hotkey.press),
                on_release=self.for_canonical(self.hotkey.release),
            )

        def for_canonical(self, f):
            return lambda k: f(self.listener.canonical(k))

        def start(self):
            self.listener.start()

        def stop(self):
            self.listener.stop()

else:

    class HotkeyListener:
        def __init__(self, hotkey_str, callback):
            pass

        def start(self):
            pass

        def stop(self):
            pass
