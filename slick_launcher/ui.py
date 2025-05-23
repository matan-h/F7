# ui.py

from PyQt6.QtCore import QStringListModel, Qt
from PyQt6.QtWidgets import (
    QCompleter,
    QFrame,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


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
        main_widget.setObjectName("MainWidget")  # For styling via QSS

        layout = QVBoxLayout(main_widget)  # Set layout directly on main_widget
        layout.setContentsMargins(8, 8, 8, 8)  # Consistent padding
        layout.setSpacing(4)  # Spacing between widgets

        # Input field for commands
        input_field = QLineEdit(parent=main_widget)
        input_field.setPlaceholderText("Enter text or command...")
        input_field.setObjectName("InputField")  # For styling
        layout.addWidget(input_field)

        # Autocompleter setup
        completion_model = QStringListModel(
            parent=input_field
        )  # Parent to input_field for lifetime
        completer = QCompleter(
            completion_model, parent=input_field
        )  # Parent to input_field
        completer.setWidget(input_field)  # Associate completer with the input field
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setCaseSensitivity(
            Qt.CaseSensitivity.CaseSensitive
        )  # Python is case-sensitive
        completer.setFilterMode(
            Qt.MatchFlag.MatchStartsWith
        )  # Standard completion filter
        completer.popup().setObjectName("CompletionPopup")  # For styling the popup

        # Preview output area
        preview_output = QTextEdit(parent=main_widget)
        preview_output.setObjectName("PreviewOutput")  # For styling
        preview_output.setReadOnly(True)
        preview_output.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        preview_output.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        preview_output.setFrameStyle(
            QFrame.Shape.NoFrame
        )  # No border for seamless look
        preview_output.setMaximumHeight(
            200
        )  # Default max height, can be adjusted dynamically
        preview_output.setFocusPolicy(
            Qt.FocusPolicy.NoFocus
        )  # Prevent tabbing into read-only preview
        preview_output.hide()  # Initially hidden
        layout.addWidget(preview_output)

        # Status bar for messages
        status_bar = QLabel(parent=main_widget)
        status_bar.setObjectName("StatusBar")  # For styling
        layout.addWidget(status_bar)

        return {
            "main_widget": main_widget,
            "input_field": input_field,
            "preview_output": preview_output,
            "status_bar": status_bar,
            "completer": completer,
            "completion_model": completion_model,
            "layout": layout,
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
        colors = settings_instance.colors  # Access the 'colors' section from settings

        def get_hex(
            color_setting_value, default_hex="#ffffff"
        ) -> str:  # TODO: remove this function
            """Safely gets a hex string from a setting, defaulting if invalid."""
            return color_setting_value

        # Define QSS using f-string and pulling colors from settings
        # Fallback values are provided in case a setting is missing or malformed
        qcss = f"""
        #MainWidget {{
            background: {get_hex(colors.main_widget_bg, '#282c34')};
            border: 1px solid {get_hex(colors.main_widget_border, '#ffffff1a')};
            border-radius: 6px;
        }}
        #InputField {{
            background: {get_hex(colors.input_bg, '#1e222a')};
            border: 1px solid {get_hex(colors.input_border, '#ffffff14')};
            border-radius: 4px;
            color: {get_hex(colors.input_text, '#abb2bf')};
            padding: 8px 12px;
            font-size: 16px;
        }}
        #InputField:focus {{
            border: 1px solid {get_hex(colors.input_focus_border, '#4682b4')};
        }}
        #PreviewOutput {{
            background: {get_hex(colors.preview_bg, '#1e222a')};
            border: 1px solid {get_hex(colors.preview_border, '#ffffff0d')};
            border-radius: 4px;
            color: {get_hex(colors.preview_text, '#abb2bf')};
            font-family: 'Fira Code', 'Consolas', monospace;
            font-size: 13px;
            padding: 4px 8px;
        }}
        #StatusBar {{
            color: {get_hex(colors.status_bar_text, '#5c6370')};
            font-size: 11px;
            padding: 2px 4px;
        }}
        #CompletionPopup {{
            background: {get_hex(colors.completion_popup_bg, '#32363e')};
            border: 1px solid {get_hex(colors.completion_popup_border, '#ffffff26')};
            border-radius: 4px;
            color: {get_hex(colors.completion_popup_text, '#abb2bf')};
            font-size: 13px;
            padding: 2px;
        }}
        #CompletionPopup::item {{
            padding: 4px 8px;
            border-radius: 3px;
        }}
        #CompletionPopup::item:selected {{
            background-color: {get_hex(colors.completion_item_selected_bg, '#4682b4')};
            color: {get_hex(colors.completion_item_selected_text, '#ffffff')};
        }}
    """

        return qcss
