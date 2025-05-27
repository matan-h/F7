# settingsUI.py
import sys

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QKeySequence, QScreen, QValidator
from PyQt6.QtWidgets import (
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
    """Converts a QColor to a hex string (with alpha if not fully opaque)."""
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
        # Store original values to revert on cancel
        self._original_values = {
            sec: data.copy() for sec, data in settings._values.items()
        }

        # Map to store widgets for easy access
        self.widget_map = {}
        self.setWindowTitle("Slick Launcher Settings")
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setWindowFlag(Qt.WindowType.WindowMinimizeButtonHint, True)

        # Resize dialog based on screen size
        screen = QScreen.availableGeometry(QApplication.primaryScreen())
        width = min(int(screen.width() * 0.8), 900)
        height = min(int(screen.height() * 0.8), 700)
        self.resize(width, height)

        self.tab_widget = QTabWidget()

        # Build the UI dynamically based on settings registry
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
                widget_container = (
                    QWidget()
                )  # Use a container for value widget and reset button
                h_layout = QHBoxLayout(widget_container)
                h_layout.setContentsMargins(0, 0, 0, 0)
                h_layout.setSpacing(5)

                setting_type = meta["type"]

                # Create the appropriate widget based on setting type
                if setting_type == bool:
                    value_widget = QCheckBox()
                    value_widget.setChecked(
                        current_value if isinstance(current_value, bool) else False
                    )
                    h_layout.addWidget(value_widget)
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
                    h_layout.addWidget(value_widget, 1)
                elif setting_type == str:
                    default_text = meta.get("default", "")
                    if isinstance(default_text, str) and "\n" in default_text:
                        value_widget = QTextEdit()
                        value_widget.setPlainText(
                            current_value if isinstance(current_value, str) else ""
                        )
                        h_layout.addWidget(value_widget, 1)
                    else:
                        value_widget = QLineEdit()
                        value_widget.setText(
                            current_value if isinstance(current_value, str) else ""
                        )
                        h_layout.addWidget(value_widget, 1)
                elif setting_type == int:
                    value_widget = QSpinBox()
                    value_widget.setMinimum(meta.get("min", -1000))
                    value_widget.setMaximum(meta.get("max", 1000))
                    value_widget.setValue(
                        current_value if isinstance(current_value, int) else 0
                    )
                    h_layout.addWidget(value_widget)
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
                    h_layout.addWidget(value_widget)
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
                    h_layout.addWidget(value_widget)
                elif setting_type == HotKeyType:
                    key_sequence_edit = QKeySequenceEdit()
                    key_sequence_edit.setMaximumSequenceLength(1)

                    if isinstance(current_value, str):
                        qks = KeySequenceConverter.to_qkeysequence(current_value)
                        key_sequence_edit.setKeySequence(qks)

                    clear_btn = QPushButton("Clear")
                    clear_btn.setToolTip("Clear the shortcut")
                    clear_btn.clicked.connect(key_sequence_edit.clear)
                    clear_btn.setFixedWidth(
                        clear_btn.fontMetrics().horizontalAdvance(" Clear ") + 10
                    )

                    h_layout.addWidget(key_sequence_edit, 1)
                    h_layout.addWidget(clear_btn)
                    value_widget = key_sequence_edit  # The QKeySequenceEdit is the source of the value
                elif setting_type == list:
                    value_widget = QLineEdit()
                    if isinstance(current_value, list):
                        value_widget.setText(", ".join(map(str, current_value)))
                    elif isinstance(current_value, str):
                        value_widget.setText(current_value)
                    else:
                        value_widget.setText("")
                    value_widget.setPlaceholderText("e.g., item1, item2, item3")
                    h_layout.addWidget(value_widget, 1)
                else:
                    print(
                        f"WARN: unknown type in settings: {section}.{name} ({meta['type']})",
                        file=sys.stderr,
                    )
                    widget_container = (
                        QLabel(  # No container needed for unsupported type label
                            f"Unsupported type: {meta['type']}"
                        )
                    )
                    value_widget = None  # No value widget for unsupported type

                # Add enable checkbox for nullable settings
                if meta.get("default") is None and meta["type"] != bool:
                    enabled_widget = QCheckBox("Enable")
                    enabled_widget.setChecked(current_value is not None)
                    if value_widget:  # Ensure value_widget exists before connecting
                        value_widget.setEnabled(enabled_widget.isChecked())
                        enabled_widget.toggled.connect(value_widget.setEnabled)
                        # Also disable clear button for HotKeyType if enabled is unchecked
                        if setting_type == HotKeyType:
                            clear_button_in_container = widget_container.findChild(
                                QPushButton
                            )
                            if clear_button_in_container:
                                clear_button_in_container.setEnabled(
                                    enabled_widget.isChecked()
                                )
                                enabled_widget.toggled.connect(
                                    clear_button_in_container.setEnabled
                                )

                # Add Reset button
                reset_button = QPushButton("Reset")
                reset_button.setToolTip(
                    f"Reset {name.replace('_', ' ').title()} to default"
                )
                # Use lambda to pass section and name to the reset handler
                reset_button.clicked.connect(
                    lambda _, s=section, n=name: self.reset_setting(s, n)
                )
                reset_button.setFixedWidth(
                    reset_button.fontMetrics().horizontalAdvance(" Reset ") + 10
                )
                if value_widget is not None:
                    h_layout.addWidget(reset_button)

                field_layout = QVBoxLayout()
                field_layout.setSpacing(2)
                field_layout.addWidget(label)

                if enabled_widget:
                    layout.addRow(label, enabled_widget)
                    indented_widget_layout = QHBoxLayout()
                    indented_widget_layout.addSpacing(20)
                    indented_widget_layout.addWidget(widget_container)
                    layout.addRow("", indented_widget_layout)
                else:
                    layout.addRow(
                        label, widget_container
                    )  # Add the container with value widget and reset button

                layout.addRow("", desc_label)

                self.widget_map[(section, name)] = {
                    "enabled": enabled_widget,
                    "value": value_widget,  # This is the actual input widget
                    "reset_button": reset_button,
                    "meta": meta,
                }

                # Connect signals for automatic applying of changes
                if value_widget:
                    if setting_type == bool and isinstance(value_widget, QCheckBox):
                        value_widget.toggled.connect(self.apply_changes_to_settings)
                    elif setting_type == str and isinstance(value_widget, QComboBox):
                        value_widget.currentIndexChanged.connect(
                            self.apply_changes_to_settings
                        )
                    elif setting_type == str and isinstance(
                        value_widget, (QLineEdit, QTextEdit)
                    ):
                        # Use textChanged for QLineEdit and textChanged for QTextEdit (signal is the same name)
                        value_widget.textChanged.connect(self.apply_changes_to_settings)
                    elif setting_type == int and isinstance(value_widget, QSpinBox):
                        value_widget.valueChanged.connect(
                            self.apply_changes_to_settings
                        )
                    elif setting_type == float and isinstance(
                        value_widget, QDoubleSpinBox
                    ):
                        value_widget.valueChanged.connect(
                            self.apply_changes_to_settings
                        )
                    elif setting_type == Color and isinstance(
                        value_widget, QPushButton
                    ):
                        value_widget.clicked.connect(
                            self.apply_changes_to_settings
                        )  # Apply after color is picked
                    elif setting_type == HotKeyType and isinstance(
                        value_widget, QKeySequenceEdit
                    ):
                        value_widget.keySequenceChanged.connect(
                            self.apply_changes_to_settings
                        )
                    elif setting_type == list and isinstance(value_widget, QLineEdit):
                        value_widget.textChanged.connect(self.apply_changes_to_settings)

            tab_content_widget.setLayout(layout)

            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setWidget(tab_content_widget)
            scroll_area.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

            self.tab_widget.addTab(scroll_area, section.capitalize())

        # Use only OK and Cancel buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        button_box.accepted.connect(self.accept_settings)
        button_box.rejected.connect(self.reject_settings)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.tab_widget)
        main_layout.addWidget(button_box)

        # Apply stylesheet
        extra = {"density_scale": "-2"}
        try:
            apply_stylesheet(self, theme="dark_teal.xml", extra=extra)
            css = "QComboBox::item:selected { background-color: grey; }"
            self.setStyleSheet(self.styleSheet() + css)
        except Exception as e:
            print(f"Failed to apply stylesheet: {e}", file=sys.stderr)

    def pick_color(self, button: QPushButton):
        """Opens a color dialog to pick a color."""
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
            # Trigger apply after color selection
            self.apply_changes_to_settings()

    def reset_setting(self, section: str, name: str):
        """Resets a specific setting to its default value."""
        widget_data = self.widget_map.get((section, name))
        if not widget_data:
            print(
                f"WARN: Could not find widget for {section}.{name} to reset.",
                file=sys.stderr,
            )
            return

        value_widget = widget_data["value"]
        meta = widget_data["meta"]
        default_value = meta.get("default")
        setting_type = meta["type"]
        enabled_widget = widget_data.get("enabled")

        # Update the widget with the default value
        if enabled_widget:
            enabled_widget.setChecked(default_value is not None)

        # Temporarily block signals to prevent recursive apply calls during reset
        if value_widget:
            blocker = QSignalBlocker(value_widget)
        if enabled_widget:
            blocker_enabled = QSignalBlocker(enabled_widget)

        if setting_type == bool and isinstance(value_widget, QCheckBox):
            value_widget.setChecked(
                default_value if isinstance(default_value, bool) else False
            )
        elif setting_type == str and isinstance(value_widget, QComboBox):
            # Find the index of the default value in the options
            index = value_widget.findText(
                default_value if isinstance(default_value, str) else ""
            )
            if index != -1:
                value_widget.setCurrentIndex(index)
        elif setting_type == str and isinstance(value_widget, QLineEdit):
            value_widget.setText(
                default_value if isinstance(default_value, str) else ""
            )
        elif setting_type == str and isinstance(value_widget, QTextEdit):
            value_widget.setPlainText(
                default_value if isinstance(default_value, str) else ""
            )
        elif setting_type == int and isinstance(value_widget, QSpinBox):
            value_widget.setValue(
                default_value if isinstance(default_value, int) else 0
            )
        elif setting_type == float and isinstance(value_widget, QDoubleSpinBox):
            value_widget.setValue(
                float(default_value) if isinstance(default_value, (int, float)) else 0.0
            )
        elif setting_type == Color and isinstance(value_widget, QPushButton):
            q_color = QColor(
                default_value if isinstance(default_value, str) else "#ffffffff"
            )
            if not q_color.isValid():
                q_color = QColor("#ffffffff")
            hex_argb = color2h(q_color)
            value_widget.setProperty("currentColor", q_color)
            value_widget.setStyleSheet(
                f"background-color: {hex_argb}; border-radius: 4px; padding: 8px; min-width: 30px;"
            )
        elif setting_type == HotKeyType and isinstance(value_widget, QKeySequenceEdit):
            qks = KeySequenceConverter.to_qkeysequence(
                default_value if isinstance(default_value, str) else ""
            )
            value_widget.setKeySequence(qks)
        elif setting_type == list and isinstance(value_widget, QLineEdit):
            if isinstance(default_value, list):
                value_widget.setText(", ".join(map(str, default_value)))
            elif isinstance(default_value, str):
                value_widget.setText(default_value)
            else:
                value_widget.setText("")

        # Unblock signals
        if value_widget:
            del blocker
        if enabled_widget:
            del blocker_enabled

        # Automatically apply the reset change
        self.apply_changes_to_settings()

    def apply_changes_to_settings(self):
        """Applies changes from the UI widgets to the settings object."""
        print("Applying settings changes automatically...")
        try:
            for (section, name), widget_data in self.widget_map.items():
                enabled_widget = widget_data.get("enabled")
                value_widget = widget_data["value"]
                meta = widget_data["meta"]

                setting_type = meta["type"]
                is_nullable = meta.get("default") is None

                new_value = None

                # Determine the new value based on the widget state
                if enabled_widget and not enabled_widget.isChecked():
                    if is_nullable:
                        new_value = None
                    else:
                        # If not nullable and disabled, we might set to a default/empty state
                        if setting_type == str:
                            new_value = ""
                        elif setting_type == HotKeyType:
                            new_value = HotKeyType("")
                        elif setting_type == Color:
                            new_value = Color("")
                        elif setting_type == list:
                            new_value = []

                        else:
                            new_value = meta.get(
                                "default"
                            )  # Fallback to default if no specific empty state
                        print(
                            f"Info: Non-nullable field {section}.{name} disabled. Setting to {new_value}.",
                            file=sys.stderr,
                        )

                else:  # Widget is enabled or not nullable
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
                            new_value = Color("")  # Default for non-nullable color
                    elif setting_type == HotKeyType:
                        qks = value_widget.keySequence()
                        custom_str = KeySequenceConverter.to_custom_str(qks)
                        if custom_str:
                            new_value = HotKeyType(custom_str)
                        elif is_nullable:
                            new_value = None
                        else:
                            new_value = HotKeyType(
                                ""
                            )  # Default for non-nullable hotkey
                    elif setting_type == list:
                        text_val = value_widget.text()
                        if text_val.strip():
                            new_value = [
                                item.strip()
                                for item in text_val.split(",")
                                if item.strip()
                            ]
                        else:
                            new_value = []  # Default for non-nullable list

                # Update the settings object
                if section not in self.settings._values:
                    self.settings._values[section] = {}

                # Perform type checking before assigning the value
                is_correct_type = False
                if new_value is None and is_nullable:
                    is_correct_type = True  # None is valid for nullable fields
                elif new_value is not None:
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

            self.settingsApplied.emit()
            print("Settings changes applied to in-memory object and signal emitted.")
            # Save changes to file immediately after applying
            self.settings.save_to_toml()
            print("Settings saved to TOML.")

        except Exception as e:
            import traceback

            traceback.print_exc()
            # Show a non-blocking message box for automatic apply errors
            QMessageBox.warning(
                self,
                "Error Applying Settings",
                f"Failed to apply settings changes: {e}",
            )

    def accept_settings(self):
        """Accepts settings and closes the dialog."""
        # Changes are already applied and saved automatically
        super().accept()

    def reject_settings(self):
        """Discards changes and closes the dialog."""
        print("Discarding settings changes and closing.")
        # Revert to original values
        self.settings._values = {
            sec: data.copy() for sec, data in self._original_values.items()
        }
        # Save the original settings back to the file
        try:
            self.settings.save_to_toml()
            print("Original settings restored and saved to TOML.")
        except Exception as e:
            import traceback

            traceback.print_exc()
            QMessageBox.critical(
                self, "Error", f"Failed to revert settings to file: {e}"
            )

        super().reject()
