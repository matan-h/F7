from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence


class KeySequenceConverter:
    """Handles conversions between QKeySequence and custom <mod>+<key> strings."""

    _MOD_MAP = {
        Qt.KeyboardModifier.ControlModifier: ("<ctrl>", "Ctrl"),
        Qt.KeyboardModifier.ShiftModifier: ("<shift>", "Shift"),
        Qt.KeyboardModifier.AltModifier: ("<alt>", "Alt"),
        Qt.KeyboardModifier.MetaModifier: ("<meta>", "Meta")
    }

    @staticmethod
    def _get_mods(modifiers: Qt.KeyboardModifier, native: bool = False) -> list[str]:
        """Returns modifier names (custom or native)."""
        idx = 1 if native else 0
        return [names[idx] for mod, names in KeySequenceConverter._MOD_MAP.items() if modifiers & mod]

    @staticmethod
    def _format_key(key_str: str) -> str:
        """Formats a key string for custom format."""
        key_str = key_str.lower()
        if len(key_str) == 1:
            return key_str
        else:
            return f"<{key_str}>"


    @staticmethod
    def _parse_key(key_str: str) -> str:
        """Parses a custom key string to native format."""
        if key_str.startswith("<") and key_str.endswith(">"):
            key_str = key_str[1:-1]
        return key_str.upper() if (len(key_str) == 1 and key_str.isalpha()) or key_str.startswith("f") else key_str.capitalize()

    @classmethod
    def to_custom_str(cls, qks: QKeySequence) -> str | None:
        """Converts a QKeySequence to a custom <mod>+<key> string, e.g., 'Ctrl+Shift+A' -> '<ctrl>+<shift>+a'."""
        if qks.isEmpty():
            return None

        combo = qks[0]
        mods = combo.keyboardModifiers()
        key_val = combo.key()

        mod_parts = cls._get_mods(mods)


        temp_seq = QKeySequence(key_val)

        key_str = temp_seq.toString(QKeySequence.SequenceFormat.PortableText).lower()

        key_text = cls._format_key(key_str)
        if not key_text:
            return None

        return "+".join(mod_parts + [key_text]) if mod_parts else key_text

    @classmethod
    def to_qkeysequence(cls, custom_str: str | None) -> QKeySequence:
        """Converts a custom <mod>+<key> string to a QKeySequence, e.g., '<ctrl>+<shift>+a' -> 'Ctrl+Shift+A'."""
        if not custom_str:
            return QKeySequence()

        parts = custom_str.lower().split("+")
        key_str = parts[-1].strip("<>")
        mods = Qt.KeyboardModifier.NoModifier

        for part in parts[:-1]:
            for mod, (custom, _) in cls._MOD_MAP.items():
                if part == custom:
                    mods |= mod

        mod_strs = cls._get_mods(mods, native=True)
        final_key = key_str.upper() if len(key_str) == 1 and key_str.isalpha() else key_str.capitalize()
        sequence_str = "+".join(mod_strs + [final_key]) if mod_strs else final_key

        return QKeySequence.fromString(sequence_str, QKeySequence.SequenceFormat.PortableText)