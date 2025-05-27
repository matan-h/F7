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


class UIFactory:
    """
    Factory class responsible for creating and styling UI elements for F7.
    This class does not handle event logic, only UI construction and appearance.
    """

    @staticmethod
    def create_F7_widgets(parent_widget=None) -> dict:
        """
        Creates the primary UI widgets for the F7 window.

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
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)
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
        colors = settings_instance.colors

        # Define QSS using f-string and pulling colors from settings
        qcss = f"""
        #MainWidget {{
            background: {colors.main_widget_bg};
            border: 1px solid {colors.main_widget_border};
            border-radius: 6px;
        }}
        #InputField {{
            background: {colors.input_bg};
            border: 1px solid {colors.input_border};
            border-radius: 4px;
            color: {colors.input_text};
            padding: 8px 12px;
            font-size: 16px;
        }}
        #InputField:focus {{
            border: 1px solid {colors.input_focus_border};
        }}
        #PreviewOutput {{
            background: {colors.preview_bg};
            border: 1px solid {colors.preview_border};
            border-radius: 4px;
            color: {colors.preview_text};
            font-family: 'Fira Code', 'Consolas', monospace;
            font-size: 13px;
            padding: 4px 8px;
        }}
        #StatusBar {{
            color: {colors.status_bar_text};
            font-size: 11px;
            padding: 2px 4px;
        }}
        #CompletionPopup {{
            background: {colors.completion_popup_bg};
            border: 1px solid {colors.completion_popup_border};
            border-radius: 4px;
            color: {colors.completion_popup_text};
            font-size: 13px;
            padding: 2px;
        }}
        #CompletionPopup::item {{
            padding: 4px 8px;
            border-radius: 3px;
        }}
        #CompletionPopup::item:selected {{
            background-color: {colors.completion_item_selected_bg};
            color: {colors.completion_item_selected_text};
        }}
    """

        return qcss
