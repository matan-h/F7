# settingsUI.py
import sys

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QKeySequence, QScreen, QValidator  # Added QKeySequence
from PyQt6.QtWidgets import (  # Added QKeySequenceEdit
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from qt_material import apply_stylesheet

from .converters import KeySequenceConverter
from .settings import Color, HotKeyType, Settings


def color2h(color: QColor) -> str:
    alpha = color.alpha()
    if alpha == 255:
        return color.name(QColor.NameFormat.HexRgb).lower()
    else:
        return color.name(QColor.NameFormat.HexArgb).lower()


class SettingsDialog(QDialog):
    settingsApplied = pyqtSignal()

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._original_values = {
            sec: data.copy() for sec, data in settings._values.items()
        }

        self.widget_map = {}
        self.setWindowTitle("Slick Launcher Settings")
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)

        screen = QScreen.availableGeometry(QApplication.primaryScreen())
        width = min(int(screen.width() * 0.8), 900)
        height = min(int(screen.height() * 0.8), 700)
        self.resize(width, height)

        self.tab_widget = QTabWidget()

        for section in settings._registry:
            tab_content_widget = QWidget()
            layout = QFormLayout()
            layout.setVerticalSpacing(15)
            layout.setContentsMargins(10, 10, 10, 10)

            for name, meta in settings._registry[section].items():
                label = QLabel(name.replace("_", " ").title())
                label.setStyleSheet("font-weight: bold; font-size: 14px;")

                desc_label = QLabel(meta["description"])
                desc_label.setStyleSheet(
                    "color: #7f8c8d; font-size: 12px; margin-left: 5px; margin-top: -5px;"
                )
                desc_label.setWordWrap(True)

                current_value = self.settings._values.get(section, {}).get(
                    name, meta.get("default")
                )

                enabled_widget = None
                value_widget = None
                widget_to_add_to_layout = None

                if meta.get("default") is None and meta["type"] != bool:
                    enabled_widget = QCheckBox("Enable")
                    enabled_widget.setChecked(current_value is not None)

                setting_type = meta["type"]

                if setting_type == bool:
                    value_widget = QCheckBox()
                    value_widget.setChecked(
                        current_value if isinstance(current_value, bool) else False
                    )
                    widget_to_add_to_layout = value_widget
                elif setting_type == str and meta.get("options"):
                    value_widget = QComboBox()
                    value_widget.addItems(meta["options"])
                    initial_text = (
                        current_value
                        if isinstance(current_value, str)
                        and current_value in meta["options"]
                        else (meta["options"][0] if meta["options"] else "")
                    )
                    value_widget.setCurrentText(initial_text)
                    widget_to_add_to_layout = value_widget
                elif setting_type == str:
                    default_text = meta.get("default", "")
                    if isinstance(default_text, str) and "\n" in default_text:
                        value_widget = QTextEdit()
                        value_widget.setPlainText(
                            current_value if isinstance(current_value, str) else ""
                        )
                    else:
                        value_widget = QLineEdit()
                        value_widget.setText(
                            current_value if isinstance(current_value, str) else ""
                        )
                    widget_to_add_to_layout = value_widget
                elif setting_type == int:
                    value_widget = QSpinBox()
                    value_widget.setMinimum(meta.get("min", -1000))
                    value_widget.setMaximum(meta.get("max", 1000))
                    value_widget.setValue(
                        current_value if isinstance(current_value, int) else 0
                    )
                    widget_to_add_to_layout = value_widget
                elif setting_type == float:
                    value_widget = QDoubleSpinBox()
                    value_widget.setMinimum(meta.get("min", -1000.0))
                    value_widget.setMaximum(meta.get("max", 1000.0))
                    value_widget.setDecimals(meta.get("decimals", 3))
                    value_widget.setValue(
                        float(current_value)
                        if isinstance(current_value, (int, float))
                        else 0.0
                    )
                    widget_to_add_to_layout = value_widget
                elif setting_type == Color:
                    color_button = QPushButton()
                    try:
                        q_color = QColor(
                            current_value
                            if isinstance(current_value, str)
                            else "#ffffffff"
                        )
                    except Exception:
                        q_color = QColor("#ffffffff")
                    if not q_color.isValid():
                        q_color = QColor("#ffffffff")

                    hex_argb = color2h(q_color)
                    color_button.setStyleSheet(
                        f"background-color: {hex_argb}; border-radius: 4px; padding: 8px; min-width: 30px;"
                    )
                    color_button.setProperty("currentColor", q_color)
                    color_button.setToolTip("Click to select color (with alpha)")
                    color_button.clicked.connect(
                        lambda _, btn=color_button: self.pick_color(btn)
                    )
                    value_widget = color_button
                    widget_to_add_to_layout = value_widget
                elif setting_type == HotKeyType:
                    key_sequence_edit = QKeySequenceEdit()
                    key_sequence_edit.setMaximumSequenceLength(1)

                    if isinstance(current_value, str):
                        qks = KeySequenceConverter.to_qkeysequence(current_value)
                        key_sequence_edit.setKeySequence(qks)

                    clear_btn = QPushButton("Clear")
                    clear_btn.setToolTip("Clear the shortcut")
                    clear_btn.clicked.connect(
                        key_sequence_edit.clear
                    )  # Use QKeySequenceEdit's clear
                    clear_btn.setFixedWidth(
                        clear_btn.fontMetrics().horizontalAdvance(" Clear ") + 10
                    )

                    container = QWidget()
                    h_layout = QHBoxLayout(container)
                    h_layout.setContentsMargins(0, 0, 0, 0)
                    h_layout.setSpacing(5)
                    h_layout.addWidget(key_sequence_edit, 1)
                    h_layout.addWidget(clear_btn)

                    value_widget = key_sequence_edit  # The QKeySequenceEdit is the source of the value
                    widget_to_add_to_layout = container
                elif setting_type == list:
                    value_widget = QLineEdit()
                    if isinstance(current_value, list):
                        value_widget.setText(", ".join(map(str, current_value)))
                    elif isinstance(current_value, str):
                        value_widget.setText(current_value)
                    else:
                        value_widget.setText("")
                    value_widget.setPlaceholderText("e.g., item1, item2, item3")
                    widget_to_add_to_layout = value_widget
                else:
                    print(
                        f"WARN: unknown type in settings: {section}.{name} ({meta['type']})",
                        file=sys.stderr,
                    )
                    widget_to_add_to_layout = QLabel(
                        f"Unsupported type: {meta['type']}"
                    )

                if enabled_widget and value_widget:
                    value_widget.setEnabled(enabled_widget.isChecked())
                    enabled_widget.toggled.connect(value_widget.setEnabled)
                    if setting_type == HotKeyType and widget_to_add_to_layout:
                        clear_button_in_container = widget_to_add_to_layout.findChild(
                            QPushButton
                        )
                        if clear_button_in_container:
                            clear_button_in_container.setEnabled(
                                enabled_widget.isChecked()
                            )
                            enabled_widget.toggled.connect(
                                clear_button_in_container.setEnabled
                            )

                field_layout = QVBoxLayout()
                field_layout.setSpacing(2)
                field_layout.addWidget(label)

                if enabled_widget:
                    layout.addRow(label, enabled_widget)
                    indented_widget_layout = QHBoxLayout()
                    indented_widget_layout.addSpacing(20)
                    indented_widget_layout.addWidget(widget_to_add_to_layout)
                    layout.addRow("", indented_widget_layout)
                else:
                    layout.addRow(label, widget_to_add_to_layout)

                layout.addRow("", desc_label)

                self.widget_map[(section, name)] = {
                    "enabled": enabled_widget,
                    "value": value_widget,
                    "meta": meta,
                }

            tab_content_widget.setLayout(layout)

            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setWidget(tab_content_widget)
            scroll_area.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

            self.tab_widget.addTab(scroll_area, section.capitalize())

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        apply_button = QPushButton("Apply")
        button_box.addButton(apply_button, QDialogButtonBox.ButtonRole.ApplyRole)

        apply_button.clicked.connect(self.apply_changes_to_settings)
        button_box.accepted.connect(self.accept_settings)
        button_box.rejected.connect(self.reject_settings)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.tab_widget)
        main_layout.addWidget(button_box)

        extra = {"density_scale": "-2"}
        try:
            apply_stylesheet(self, theme="dark_teal.xml", extra=extra)
            css = "QComboBox::item:selected { background-color: grey; }"
            self.setStyleSheet(self.styleSheet() + css)
        except Exception as e:
            print(f"Failed to apply stylesheet: {e}", file=sys.stderr)

    def pick_color(self, button: QPushButton):
        initial = button.property("currentColor") or QColor("#ffffffff")
        dialog = QColorDialog(initial, self)
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        dialog.setWindowTitle("Select Color and Alpha")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            color = dialog.currentColor()
            hex_argb = color2h(color)
            button.setProperty("currentColor", color)
            button.setStyleSheet(
                f"background-color: {hex_argb}; border-radius: 4px; padding: 8px; min-width: 30px;"
            )

    def apply_changes_to_settings(self):
        print("Applying settings changes...")
        try:
            for (section, name), widget_data in self.widget_map.items():
                enabled_widget = widget_data.get("enabled")
                value_widget = widget_data[
                    "value"
                ]  # This is QKeySequenceEdit for HotKeyType
                meta = widget_data["meta"]

                setting_type = meta["type"]
                is_nullable = meta.get("default") is None

                new_value = None

                if enabled_widget and not enabled_widget.isChecked():
                    if is_nullable:
                        new_value = None
                    else:
                        new_value = None
                else:
                    if setting_type == bool:
                        new_value = value_widget.isChecked()
                    elif setting_type == str and isinstance(value_widget, QComboBox):
                        new_value = value_widget.currentText()
                    elif setting_type == str and isinstance(value_widget, QLineEdit):
                        new_value = value_widget.text()
                    elif setting_type == str and isinstance(value_widget, QTextEdit):
                        new_value = value_widget.toPlainText()
                    elif setting_type == int:
                        new_value = value_widget.value()
                    elif setting_type == float:
                        new_value = value_widget.value()
                    elif setting_type == Color:
                        q_color = value_widget.property("currentColor")
                        if isinstance(q_color, QColor) and q_color.isValid():
                            new_value = Color(color2h(q_color))
                        elif is_nullable:
                            new_value = None
                        else:
                            new_value = Color("") if not is_nullable else None
                    elif setting_type == HotKeyType:
                        qks = (
                            value_widget.keySequence()
                        )  # value_widget is QKeySequenceEdit
                        custom_str = KeySequenceConverter.to_custom_str(qks)
                        if custom_str:
                            new_value = HotKeyType(custom_str)
                        elif is_nullable:
                            new_value = None
                        else:
                            new_value = HotKeyType("")
                    elif setting_type == list:
                        text_val = value_widget.text()
                        if text_val.strip():
                            new_value = [
                                item.strip()
                                for item in text_val.split(",")
                                if item.strip()
                            ]
                        else:
                            new_value = []

                if section not in self.settings._values:
                    self.settings._values[section] = {}

                if new_value is None and is_nullable:
                    self.settings._values[section][name] = None
                elif new_value is not None:
                    is_correct_type = False
                    if setting_type == Color:
                        is_correct_type = isinstance(new_value, Color)
                    elif setting_type == HotKeyType:
                        is_correct_type = isinstance(new_value, HotKeyType)
                    elif setting_type == list:
                        is_correct_type = isinstance(new_value, list)
                    else:
                        is_correct_type = isinstance(new_value, setting_type)

                    if is_correct_type:
                        self.settings._values[section][name] = new_value
                    else:
                        print(
                            f"Warning: Type mismatch for {section}.{name}. Expected {setting_type}, got {type(new_value)} with value '{new_value}'. Not updating.",
                            file=sys.stderr,
                        )
                elif not is_nullable and new_value is None:
                    if setting_type == str:
                        self.settings._values[section][name] = ""
                    elif setting_type == HotKeyType:
                        self.settings._values[section][name] = HotKeyType("")
                    elif setting_type == Color:
                        self.settings._values[section][name] = Color("")
                    elif setting_type == list:
                        self.settings._values[section][name] = []
                    print(
                        f"Info: Non-nullable field {section}.{name} got None. Setting to empty/default if possible.",
                        file=sys.stderr,
                    )

            self.settingsApplied.emit()
            print("Settings changes applied to in-memory object and signal emitted.")

        except Exception as e:
            import traceback

            traceback.print_exc()
            QMessageBox.critical(
                self, "Error", f"Failed to apply settings changes: {e}"
            )

    def accept_settings(self):
        self.apply_changes_to_settings()
        try:
            self.settings.save_to_toml()
            print("Settings saved to TOML.")
            super().accept()
        except Exception as e:
            import traceback

            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to save settings to file: {e}")

    def reject_settings(self):
        print("Discarding settings changes and closing.")
        self.settings._values = {
            sec: data.copy() for sec, data in self._original_values.items()
        }
        super().reject()
