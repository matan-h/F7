# slick_ui.py
import sys
from PyQt6.QtCore import Qt, QStringListModel
# QColor is used by generate_stylesheet, settings.Color should be used
from PyQt6.QtWidgets import (QLineEdit, QTextEdit, QVBoxLayout, QWidget,
                             QLabel, QFrame, QCompleter)

# Local import from your project structure
from .settings import Color # For type hinting and default values in stylesheet

class SlickUIFactory:
    """
    Factory class responsible for creating and styling UI elements for Slick Launcher.
    This class does not handle event logic, only UI construction and appearance.
    """

    @staticmethod
    def create_launcher_widgets(parent_widget=None) -> dict:
        """
        Creates the primary UI widgets for the launcher.

        Args:
            parent_widget: The parent widget for the created UI elements.

        Returns:
            dict: A dictionary containing the created widgets, keyed by name
                  (e.g., "main_widget", "input_field", "completer").
        """
        main_widget = QWidget(parent=parent_widget)
        main_widget.setObjectName("MainWidget") # For styling via QSS

        layout = QVBoxLayout(main_widget) # Set layout directly on main_widget
        layout.setContentsMargins(8, 8, 8, 8) # Consistent padding
        layout.setSpacing(4) # Spacing between widgets

        # Input field for commands
        input_field = QLineEdit(parent=main_widget)
        input_field.setPlaceholderText("Enter text or command...")
        input_field.setObjectName("InputField") # For styling
        layout.addWidget(input_field)

        # Autocompleter setup
        completion_model = QStringListModel(parent=input_field) # Parent to input_field for lifetime
        completer = QCompleter(completion_model, parent=input_field) # Parent to input_field
        completer.setWidget(input_field) # Associate completer with the input field
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive) # Python is case-sensitive
        completer.setFilterMode(Qt.MatchFlag.MatchStartsWith) # Standard completion filter
        completer.popup().setObjectName("CompletionPopup") # For styling the popup

        # Preview output area
        preview_output = QTextEdit(parent=main_widget)
        preview_output.setObjectName("PreviewOutput") # For styling
        preview_output.setReadOnly(True)
        preview_output.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        preview_output.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        preview_output.setFrameStyle(QFrame.Shape.NoFrame) # No border for seamless look
        preview_output.setMaximumHeight(200) # Default max height, can be adjusted dynamically
        preview_output.setFocusPolicy(Qt.FocusPolicy.NoFocus) # Prevent tabbing into read-only preview
        preview_output.hide() # Initially hidden
        layout.addWidget(preview_output)

        # Status bar for messages
        status_bar = QLabel(parent=main_widget)
        status_bar.setObjectName("StatusBar") # For styling
        layout.addWidget(status_bar)

        return {
            "main_widget": main_widget,
            "input_field": input_field,
            "preview_output": preview_output,
            "status_bar": status_bar,
            "completer": completer,
            "completion_model": completion_model,
            "layout": layout
        }

    @staticmethod
    def generate_stylesheet(settings_instance) -> str:
        """
        Generates the QSS (Qt Style Sheets) string based on the current settings.

        Args:
            settings_instance: The loaded Settings object containing color definitions.

        Returns:
            str: A QSS string for styling the application.
        """
        colors = settings_instance.colors # Access the 'colors' section from settings

        def get_hex(color_setting_value, default_hex="#ffffff") -> str:
            """Safely gets a hex string from a setting, defaulting if invalid."""
            if isinstance(color_setting_value, Color): # settings.Color object
                hex_str = str(color_setting_value) # Assuming Color object has __str__ returning hex
            elif isinstance(color_setting_value, str):
                hex_str = color_setting_value
            else:
                hex_str = default_hex

            # Basic validation for hex string
            if not (isinstance(hex_str, str) and hex_str.startswith("#") and len(hex_str) in [7, 9]):
                print(f"Warning: Invalid color format '{hex_str}' for setting. Using default '{default_hex}'.", file=sys.stderr)
                return default_hex
            return hex_str

        # Define QSS using f-string and pulling colors from settings
        # Fallback values are provided in case a setting is missing or malformed
        qcss = f"""
            #MainWidget {{
                background: {get_hex(colors.main, '#282c34')};
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.12);
            }}
            #InputField {{
                font-size: 16px;
                padding: 8px 12px;
                background: {get_hex(colors.input, '#1e222a')};
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                color: #abb2bf; /* Consider making text colors configurable too */
                margin-bottom: 4px;
            }}
            #PreviewOutput {{
                font-family: 'Fira Code', 'Consolas', monospace; /* Monospaced font for previews */
                font-size: 13px;
                background: {get_hex(colors.preview, '#1e222a')};
                color: #abb2bf;
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 4px;
                padding: 4px 8px;
            }}
            #StatusBar {{
                color: #5c6370;
                font-size: 11px;
                padding: 2px 4px;
                margin-top: 4px;
            }}
            #CompletionPopup {{ /* Style the completer's popup window */
                background: {get_hex(colors.completion_popup, '#32363e')};
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                color: #abb2bf; /* Text color for completion items */
                font-size: 13px;
                padding: 2px; /* Padding around the list of items */
                margin: 0px; /* Important for positioning relative to input field */
            }}
            #CompletionPopup QAbstractItemView::item {{ /* Style individual items in the popup */
                 padding: 4px 8px; /* Padding within each item */
                 border-radius: 3px; /* Slightly rounded corners for items */
            }}
            #CompletionPopup QAbstractItemView::item:selected {{ /* Style for the selected item */
                background-color: {get_hex(colors.completion_selected, '#4682b4')};
                color: #ffffff; /* White text for selected item for contrast */
            }}
        """
        return qcss
