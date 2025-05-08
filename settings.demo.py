# Example Usage (for testing purposes, if run directly)
import sys
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication, QDialog
from slick_launcher.converters import KeySequenceConverter
from slick_launcher.settings import Color, HotKeyType
from slick_launcher.settingsUI import SettingsDialog


if __name__ == '__main__':
    # Mock Settings class and registry for testing
    class MockSettings:
        def __init__(self):
            self._registry = {
                "General": {
                    "username": {"type": str, "default": "User", "description": "Your username."},
                    "dark_mode": {"type": bool, "default": True, "description": "Enable dark mode theme."},
                    "launch_hotkey": {"type": HotKeyType, "default": "<ctrl>+<alt>+s", "description": "Global hotkey to launch the app."}, # Custom format
                    "nullable_hotkey": {"type": HotKeyType, "default": None, "description": "Optional hotkey, can be empty."},
                    "f_key_hotkey": {"type": HotKeyType, "default": "<shift>+<f11>", "description": "Shortcut with an F-key."},
                    "just_key_hotkey": {"type": HotKeyType, "default": "<space>", "description": "Shortcut with just space key."}
                },
                "Appearance": {
                    "theme_color": {"type": Color, "default": "#ff0000", "description": "Main theme color."},
                    "font_size": {"type": int, "default": 12, "description": "Default font size."},
                    "ignored_files": {"type": list, "default": [".git", "*.tmp", "__pycache__"], "description": "Comma-separated list of files/patterns to ignore."},
                     "nullable_list": {"type": list, "default": None, "description": "Optional comma-separated list."},
                },
                "Advanced": {
                    "timeout": {"type": float, "default": 5.0, "description": "Network timeout in seconds."},
                    "log_level": {"type": str, "options": ["DEBUG", "INFO", "WARNING", "ERROR"], "default": "INFO", "description": "Logging verbosity."},
                    "multiline_text": {"type": str, "default": "Hello\nWorld\nThis is a test.", "description": "A multiline text setting."},
                }
            }
            self._values = {
                "General": {
                    "username": "TestUser",
                    "dark_mode": False,
                    "launch_hotkey": "<ctrl>+<alt>+x", # Custom format
                    "nullable_hotkey": None,
                    "f_key_hotkey": "<f12>",
                    "just_key_hotkey": "a" # Test single key
                },
                "Appearance": {
                    "theme_color": Color("#00ff0080"),
                    "font_size": 10,
                    "ignored_files": ["node_modules", ".env"],
                    "nullable_list": None,
                },
                 "Advanced": {
                    "timeout": 2.5,
                    "log_level": "DEBUG",
                    "multiline_text": "Custom\nText.",
                }
            }
            for section, items in self._registry.items():
                if section not in self._values:
                    self._values[section] = {}
                for name, meta in items.items():
                    if name not in self._values[section]:
                        self._values[section][name] = meta['default']


        def save_to_toml(self):
            print("MockSettings: save_to_toml() called. Current values:")
            import json
            print(json.dumps(self._values, indent=2, default=str))

        def __str__(self):
            import json
            return json.dumps(self._values, indent=2, default=str)


    app = QApplication(sys.argv)
    mock_settings_instance = MockSettings()

    print("Initial settings state:")
    print(mock_settings_instance)

    # Test conversion functions
    print("\n--- Testing Hotkey Conversions ---")
    test_custom_strs = ["<ctrl>+a", "<alt>+<shift>+b", "<meta>+<f1>", "<f12>", "c", "<space>", None, ""]
    for cs in test_custom_strs:
        qks =  KeySequenceConverter.to_qkeysequence(cs)

        cs_back = KeySequenceConverter.to_custom_str(qks)
        match = cs == cs_back if cs else cs_back is None # Handle None case
        if not cs and not cs_back: match = True # "" -> QKeySequence() -> None, consider match for empty

        print(f"Custom: '{cs}' -> QKS: '{qks.toString(QKeySequence.SequenceFormat.PortableText)}' -> Custom Back: '{cs_back}' (Match: {match})")

    test_qks_strs = ["Ctrl+A", "Alt+Shift+B", "Meta+F1", "F12", "C", "Space"]
    for qks_str in test_qks_strs:
        qks = QKeySequence.fromString(qks_str, QKeySequence.SequenceFormat.PortableText)
        cs = KeySequenceConverter.to_custom_str(qks)
        qks_back =  KeySequenceConverter.to_qkeysequence(cs)
        match = qks == qks_back
        print(f"QKS: '{qks_str}' -> Custom: '{cs}' -> QKS Back: '{qks_back.toString(QKeySequence.SequenceFormat.PortableText)}' (Match: {match})")
    print("----------------------------------\n")


    dialog = SettingsDialog(mock_settings_instance)
    dialog.settingsApplied.connect(lambda: print(f"SettingsApplied signal received! Current settings:\n{mock_settings_instance}"))

    result = dialog.exec()

    if result == QDialog.DialogCode.Accepted:
        print("\nDialog accepted. Final settings state:")
        print(mock_settings_instance)
    else:
        print("\nDialog rejected or closed. Final settings state (should be original or last applied if any):")
        print(mock_settings_instance)

    sys.exit()
