# plugins/base_plugin.py
from abc import ABC, abstractmethod
from PyQt6.QtWidgets import QTextEdit, QLabel

class PluginInterface(ABC):
    """
    Abstract Base Class for Slick Launcher plugins.

    Defines the interface that all plugins must implement.
    """

    # --- Configuration ---
    # Set these in your plugin implementation

    NAME = "Base Plugin" # Human-readable name
    PREFIX = None        # String prefix to trigger this plugin (e.g., "!")
    SUFFIX = None        # String suffix to trigger this plugin
    IS_DEFAULT = False   # True if this plugin handles input without matching prefix/suffix
    PRIORITY = 99        # Lower number means higher priority for matching

    # --- Methods ---

    @abstractmethod
    def __init__(self, launcher_instance):
        """
        Initialize the plugin.
        Args:
            launcher_instance: Reference to the main SlickLauncher instance.
                               Allows access to UI elements or core methods if needed,
                               but use sparingly to maintain decoupling.
        """
        self.launcher = launcher_instance
        pass

    @abstractmethod
    def get_status_message(self) -> str:
        """
        Return a short status message to display when this plugin is potentially active.
        """
        pass

    @abstractmethod
    def update_preview(self, command: str, selected_text: str, preview_widget: QTextEdit, status_widget: QLabel,manual:bool) -> None:
        """
        Update the preview widget based on the current command and selected text.
        This method handles how the preview is displayed (e.g., static text, streaming).

        Args:
            command: The current text in the input field (potentially including prefix/suffix).
            selected_text: The text currently selected in the system.
            preview_widget: The QTextEdit widget used for displaying the preview.
            status_widget: The QLabel widget for status updates.
            manual: true if the operation was triggered by ctrl+Enter.
        """
        pass

    @abstractmethod
    def execute(self, command: str, selected_text: str) -> str | None:
        """
        Execute the main action of the plugin.

        Args:
            command: The final command text (potentially stripped of prefix/suffix).
            selected_text: The text currently selected in the system.

        Returns:
            A string containing the result to be copied to the clipboard,
            or None if the execution is asynchronous or doesn't produce clipboard output.
            The launcher will handle copying the returned string and quitting.
            If None is returned, the plugin is responsible for any further actions
            (like async handling and quitting via self.launcher.quit()).
        """
        pass

    def cleanup(self) -> None:
        """
        Optional method to clean up resources (e.g., stop threads) when the launcher quits
        or the plugin is deactivated.
        """
        pass # Default implementation does nothing