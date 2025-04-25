# settingsUI.py
from PyQt6.QtWidgets import (
    QDialog, QTabWidget, QWidget, QFormLayout, QLabel,
    QCheckBox, QLineEdit, QComboBox, QSpinBox,
    QDialogButtonBox, QMessageBox, QVBoxLayout,QDoubleSpinBox,QPushButton,QColorDialog,QApplication,
)
import sys
from PyQt6.QtGui import QColor, QColorConstants

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QScreen, QValidator # Import QValidator

from PyQt6.QtCore import pyqtSignal
from .settings import Settings,Color

from qt_material import apply_stylesheet

# Custom validator for hex colors
class HexColorValidator(QValidator):
    def validate(self, input_string, pos):
        # Empty string is acceptable (e.g., for nullable)
        if not input_string:
            return QValidator.State.Acceptable, input_string, pos

        # Must start with #
        if not input_string.startswith("#"):
            return QValidator.State.Invalid, input_string, pos

        # Remaining characters must be hex digits
        hex_digits = "0123456789abcdefABCDEF"
        hex_part = input_string[1:]
        for char in hex_part:
            if char not in hex_digits:
                return QValidator.State.Invalid, input_string, pos

        # Valid lengths are 3, 4, 6, 8 (for #RGB, #RGBA, #RRGGBB, #RRGGBBAA)
        # Common lengths are 6 and 8 for #RRGGBB and #RRGGBBAA
        # Length 7 (#RRGGBB) or 9 (#RRGGBBAA) is complete
        if len(input_string) == 7 or len(input_string) == 9:
             return QValidator.State.Acceptable, input_string, pos
        # Lengths like #1, #12, #123, #1234, #12345, #1234567 are Intermediate if valid chars so far
        elif len(input_string) > 1 and len(input_string) < 9:
             return QValidator.State.Intermediate, input_string, pos
        else:
            return QValidator.State.Invalid, input_string, pos # Too long or just '#'

def color2h(color: QColor) -> str:
    """
    Convert a QColor to a hex string.
    - If alpha is 255 (fully opaque), returns "#RRGGBB".
    - Otherwise, returns "#AARRGGBB".
    """
    # Get the integer alpha (0–255)
    alpha = color.alpha()  

    if alpha == 255:
        # name() default is HexRgb => "#RRGGBB"
        return color.name(QColor.NameFormat.HexRgb).lower() 
    else:
        # explicitly ask for HexArgb => "#AARRGGBB"
        return color.name(QColor.NameFormat.HexArgb).lower()


class SettingsDialog(QDialog):
    settingsApplied = pyqtSignal()  # Signal to notify the main app of changes

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        # We work with a *copy* of the settings object to allow "Cancel" to discard changes easily
        # Or, we modify the original and rely on "Cancel" reverting.
        # Let's modify the original directly for "Apply" and handle "Cancel" separately.
        # This means the self.settings object passed in will be modified by "Apply".
        self.settings = settings # Keep reference to the main app's settings object
        self._original_values = settings._values.copy() # Store original values for Cancel

        self.widget_map = {}  # Maps (section, name) to {'enabled': widget, 'value': widget, 'meta': meta}
        self.setWindowTitle("Slick Launcher Settings")

        # Set size to ~80% of screen size, capped at 800x600
        screen = QScreen.availableGeometry(QApplication.primaryScreen())
        width = min(int(screen.width() * 0.8), 800)
        height = min(int(screen.height() * 0.8), 600)
        self.resize(width, height)

        # Create tab widget for sections
        self.tab_widget = QTabWidget()

        # Generate tabs and widgets
        for section in settings._registry:
            print(f"Building settings tab for: {section}")
            tab = QWidget()
            layout = QFormLayout()
            layout.setVerticalSpacing(10)
            for name, meta in settings._registry[section].items():
                # Main label
                label = QLabel(name.replace('_', ' ').title())
                label.setStyleSheet("font-weight: bold; font-size: 14px;")

                # Description label
                desc_label = QLabel(meta['description'])
                desc_label.setStyleSheet("color: #7f8c8d; font-size: 12px; margin-left: 20px;")
                desc_label.setWordWrap(True)

                # Get the current value from the shared settings object
                value = self.settings._values.get(section, {}).get(name, meta.get('default'))

                enabled_widget = None
                value_widget = None

                # Handle nullable settings with a checkbox
                if meta.get('nullable'):
                    enabled_widget = QCheckBox("Enable")
                    # Initial state based on whether the current value is None
                    enabled_widget.setChecked(value is not None)

                # Choose widget based on type
                if meta['type'] == bool:
                    value_widget = QCheckBox()
                    # Set initial state, default to False if value is None
                    value_widget.setChecked(value if isinstance(value, bool) else False)
                elif meta['type'] == str and meta.get('options'):
                    value_widget = QComboBox()
                    value_widget.addItems(meta['options'])
                     # Set initial text, default to first option if value is None or not in options
                    initial_text = value if isinstance(value, str) and value in meta['options'] else meta['options'][0]
                    value_widget.setCurrentText(initial_text)

                elif meta['type'] == str:
                    value_widget = QLineEdit()
                     # Set initial text, default to empty string if value is None or not a string
                    value_widget.setText(value if isinstance(value, str) else "")
                elif meta['type'] == int:
                    value_widget = QSpinBox()
                    value_widget.setMinimum(-1000 - 1) # Use system max size for robustness
                    value_widget.setMaximum(1000)
                    # Set initial value, default to 0 if value is None or not an int
                    value_widget.setValue(value if isinstance(value, int) else 0)
                elif meta['type'] == float:
                    value_widget = QDoubleSpinBox()
                    value_widget.setMinimum(-1000) # Use system max float
                    value_widget.setMaximum(1000)
                    value_widget.setDecimals(3) # Default decimals, could be configurable
                     # Set initial value, default to 0.0 if value is None or not a float/int
                    value_widget.setValue(float(value) if isinstance(value, (int, float)) else 0.0)
                elif meta['type'] == Color:
                        # Create a QPushButton that shows the current color and stores its QColor
                    color_button = QPushButton()

                    # Determine initial color (with alpha) or use opaque white
                    try:
                        q_color = QColor(value)
                    except Exception:
                        q_color = QColor()
                    if not q_color.isValid():
                        q_color = QColor('#ffffffff')  # default to white with full opacity

                    # Display as #AARRGGBB
                    hex_argb = color2h(q_color)
                    color_button.setStyleSheet(
                        f"background-color: {hex_argb}; border-radius: 4px; padding: 8px; min-width: 30px;"
                    )
                    color_button.setProperty('currentColor', q_color)
                    color_button.setToolTip('Click to select color (with alpha)')

                    # Open alpha-enabled color dialog on click
                    color_button.clicked.connect(lambda _, btn=color_button: self.pick_color(btn))

                    value_widget = color_button


                else:
                    print("WARN: unknown type in settings", section, name, meta)
                    continue # Skip this setting if type is unknown


                # Connect enabled checkbox to value widget
                if enabled_widget and value_widget:
                    # Initial state based on enabled_widget
                    value_widget.setEnabled(enabled_widget.isChecked())
                    enabled_widget.toggled.connect(value_widget.setEnabled)

                # Add to layout
                widget_layout = QVBoxLayout()
                widget_layout.setContentsMargins(0, 0, 0, 0) # No extra margins
                widget_layout.setSpacing(5) # Small spacing between enable/value widget
                if enabled_widget:
                    widget_layout.addWidget(enabled_widget)
                if value_widget:
                     widget_layout.addWidget(value_widget)

                form_widget = QWidget()
                form_widget.setLayout(widget_layout)
                layout.addRow(label, form_widget)
                layout.addRow("", desc_label)  # Description below

                # Store widget references and meta information
                self.widget_map[(section, name)] = {
                    'enabled': enabled_widget,
                    'value': value_widget,
                    'meta': meta
                }

            tab.setLayout(layout)
            self.tab_widget.addTab(tab, section.capitalize())

        # Add dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )

        # Manually create and add the Apply button
        apply_button = QPushButton("Apply")
        button_box.addButton(apply_button, QDialogButtonBox.ButtonRole.ApplyRole)

        # Connect the Apply button
        apply_button.clicked.connect(self.apply_changes_to_settings)

        # Connect standard signals to our custom slots
        button_box.accepted.connect(self.accept_settings) # OK button
        button_box.rejected.connect(self.reject_settings) # Cancel button


        # Set up main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tab_widget)
        main_layout.addWidget(button_box)
        self.setLayout(main_layout)

        # Apply modern, high-contrast styling (kept from your code)
        extra =     {
            'density_scale': '-2',
        }
        return apply_stylesheet(self, theme='dark_teal.xml',extra=extra)
        
    def pick_color(self, button: QPushButton):
        """Show a QColorDialog with alpha channel and update the button."""
        initial = button.property('currentColor') or QColor('#ffffffff')
        dialog = QColorDialog(initial, self)
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        
        dialog.setWindowTitle('Select Color and Alpha')

        if dialog.exec() == QDialog.DialogCode.Accepted:
            color = dialog.currentColor()
            # Store and display as ARGB hex
            hex_argb = color2h(color)
            button.setProperty('currentColor', color)
            button.setStyleSheet(
                f"background-color: {hex_argb}; border-radius: 4px; padding: 8px; min-width: 30px;"
            )


    def open_color_dialog(self, button: QPushButton, hex_edit: QLineEdit):
        """Open a QColorDialog with alpha channel support and update the UI"""
        # Parse existing hex, fallback to white
        current_hex = hex_edit.text() or button.styleSheet().split('background-color: ')[-1].split(';')[0]
        q_color = QColor(current_hex)
        if not q_color.isValid():
            q_color = QColor("#ffffffff")

        # Create dialog with alpha channel enabled
        dialog = QColorDialog(q_color, self)
        dialog.setOption(
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
            True
        )
        dialog.setWindowTitle("Select Color and Alpha")

        if dialog.exec() == QDialog.DialogCode.Accepted:
            color = dialog.currentColor()
            # Use ARGB hex format to include alpha
            new_hex = color2h(color)
            hex_edit.setText(new_hex)
            button.setStyleSheet(
                f"background-color: {new_hex}; border-radius: 4px; padding: 8px; min-width: 30px;"
            )

    def update_color_preview(self, button: QPushButton, text: str):
        q_color = QColor(text)
        if q_color.isValid():
            hex_with_alpha = q_color.name(QColor.NameFormat.HexArgb).lower()
            button.setStyleSheet(
                f"background-color: {hex_with_alpha}; border-radius: 4px; padding: 8px; min-width: 30px;"
            )
        elif not text:
            # Reset to default UI background if empty
            button.setStyleSheet(
                f"background-color: #22252d; border-radius: 4px; padding: 8px; min-width: 30px;"
            )


    def apply_changes_to_settings(self):
        """Reads values from widgets and applies them to the shared settings object."""
        print("Applying settings changes...")
        try:
            for (section, name), widgets in self.widget_map.items():
                enabled_widget = widgets.get('enabled')
                value_widget = widgets['value']
                meta = widgets['meta']

                new_value = None # Assume nullable unless enabled or not nullable

                if enabled_widget and not enabled_widget.isChecked():
                    new_value = None # Setting is disabled, value is None
                else:
                    # Read value based on widget type
                    widget_type = type(value_widget)
                    setting_type = meta['type'] # The expected type (bool, str, int, float, Color)

                    if setting_type == bool and widget_type == QCheckBox:
                        new_value = value_widget.isChecked()
                    elif setting_type == str and widget_type == QComboBox:
                         new_value = value_widget.currentText()
                    elif setting_type == str and widget_type == QLineEdit:
                         new_value = value_widget.text()
                    elif setting_type == int and widget_type == QSpinBox:
                         new_value = value_widget.value()
                    elif setting_type == float and widget_type == QDoubleSpinBox:
                         new_value = value_widget.value()
                    elif setting_type == Color and isinstance(value_widget, QPushButton):
                            q_color = value_widget.property('currentColor')
                            if isinstance(q_color, QColor) and q_color.isValid():
                                new_value = Color(color2h(q_color))

                    # Handle other types if needed...

                # Update the value in the actual settings object passed from the main window
                # Ensure the section and name exist in the settings object's values dict
                if section in self.settings._values and name in self.settings._values[section]:
                     # Only update if the new_value is valid based on its type
                     is_nullable = meta.get('nullable')
                     expected_type = meta['type']

                     if new_value is None and is_nullable:
                         self.settings._values[section][name] = None
                     elif new_value is not None:
                          # Basic type check before assigning
                          if expected_type == Color and isinstance(new_value, Color):
                               self.settings._values[section][name] = new_value
                          elif expected_type != Color and isinstance(new_value, expected_type):
                               self.settings._values[section][name] = new_value
                          else:
                               # This case should ideally be caught by widget type/validation
                               # but is a final safeguard.
                               print(f"Warning: Type mismatch for {section}.{name}. Expected {expected_type}, got {type(new_value)}. Not updating.", file=sys.stderr)
                     # If new_value is None but not nullable, the setting is unchanged.
                     # This relies on the initial load providing a default, which it does.


            # Emit the signal after applying changes to the in-memory object
            self.settingsApplied.emit()
            print("Settings changes applied to in-memory object and signal emitted.")

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to apply settings changes: {e}")

    def accept_settings(self):
        """Apply settings changes to the shared object, save to TOML, and close."""
        self.apply_changes_to_settings() # First, apply changes to the in-memory object
        try:
            self.settings.save_to_toml() # Then, save the updated object to file
            print("Settings saved to TOML.")
            super().accept() # Close the dialog with Accepted result
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to save settings to file: {e}")
            # Do not close the dialog on save error
            # super().reject() # Or reject? Depending on desired behavior on save failure


    def reject_settings(self):
        """Discard changes and close the dialog."""
        print("Discarding settings changes and closing.")
        # Revert the settings object back to its original state
        self.settings._values = self._original_values
        # Optionally, you might want to re-apply the *original* settings to the main window's UI
        # by emitting the signal, but this might be confusing. Let's skip this for now.
        # self.settingsApplied.emit() # This would re-apply original state visually

        super().reject() # Close the dialog with Rejected result

    # The original accept method is no longer needed, replaced by accept_settings
    # def accept(self):
    #     self.save_settings() # This now only saves and emits. We need more for OK.
    #     super().accept() # This closes the dialog.