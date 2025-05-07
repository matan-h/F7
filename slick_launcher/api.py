# api.py
from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional
from PyQt6.QtWidgets import QTextEdit, QLabel, QCompleter
from PyQt6.QtCore import QStringListModel, QTimer
from PyQt6.QtGui import QGuiApplication

if TYPE_CHECKING:
    from window import SlickLauncherWindow 
    from .settings import Settings

class API:
    """
    API class for plugins to interact with the SlickLauncher window and core functionalities.
    """
    def __init__(self, window_instance: SlickLauncherWindow):
        """
        Initializes the API with a reference to the main launcher window.

        Args:
            window_instance: The instance of SlickLauncherWindow.
        """
        self._window = window_instance

    def _adjust_window_height(self) -> None:
        """
        PRIVATE: Triggers an adjustment of the main window's height to fit its contents.
        This is called internally by methods that change content affecting window size.
        """
        self._window._adjust_main_window_height()

    def set_status(self, text: str, plugin_name: Optional[str] = None) -> None:
        """
        Sets the text of the status bar.

        Args:
            text: The text to display.
            plugin_name: Optional name of the plugin to include in the status.
                         If None, tries to use the current active plugin's name.
        """
        current_plugin = self._window.active_plugin
        base_message = text
        if plugin_name:
            base_message = f"[{plugin_name}] {text}"
        elif current_plugin and hasattr(current_plugin, 'NAME'):
            base_message = f"[{current_plugin.NAME}] {text}"
        
        char_count = len(self._window.selected_text) 
        self._window.status_bar.setText(f"✂️ ({char_count} chars) | {base_message}")

    def reset_status(self) -> None:
        """
        Resets the status bar to the default message for the current active plugin.
        """
        plugin_to_use = self._window.active_plugin
        if plugin_to_use is None: # If no plugin is active yet, find the default
            plugin_to_use = self._window.core.find_plugin(is_default=True)
        
        self._window.update_status_bar(plugin_to_use) # Relies on window's method

    def copy_text_to_clipboard(self, text: str) -> None:
        """
        Copies the given text to the system clipboard.

        Args:
            text: The text to copy.
        """
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(str(text))
        else:
            self.set_status("Error: Could not access clipboard.")

    def get_selected_os_text(self) -> str:
        """
        Returns the text currently selected in the operating system.
        Relies on the window to keep its `selected_text` attribute updated.
        """
        return self._window.selected_text

    def get_input_text(self) -> str:
        """
        Returns the current text from the launcher's input field.
        """
        return self._window.input_field.text()

    def set_input_text(self, text: str, cursor_to_end: bool = True) -> None:
        """
        Sets the text of the launcher's input field.
        This action might trigger the window's input change handlers.

        Args:
            text: The text to set.
            cursor_to_end: If True, moves the cursor to the end of the text.
        """
        # Use window's context manager to prevent re-triggering autocomplete/input handling loops
        with self._window._suppress_autocomplete_retrigger(): 
            self._window.input_field.setText(text)
            if cursor_to_end:
                self._window.input_field.setCursorPosition(len(text))

    def update_preview_content(self, content: str, is_html: bool = False) -> None:
        """
        Updates the content of the preview area.
        Automatically shows the preview if there is content, hides it if content is empty,
        and adjusts the main window's height accordingly.

        Args:
            content: The text or HTML content to display.
            is_html: Set to True if the content is HTML.
        """
        if is_html:
            self._window.preview_output.setHtml(content)
        else:
            self._window.preview_output.setPlainText(content)
        
        # Show preview only if there's actual non-whitespace content
        if content and content.strip(): 
            self._window.preview_output.show()
        else:
            # Clear content and hide if effectively empty, ensuring consistent state
            if not (content and content.strip()) and self._window.preview_output.toPlainText(): # if it was hidden due to whitespace
                self._window.preview_output.setPlainText("") # ensure it's truly empty
            self._window.preview_output.hide()
        
        self._adjust_window_height() # Adjust height after content change and visibility change

    def close_launcher(self, copy_and_close_text: Optional[str] = None) -> None:
        """
        Closes/hides the launcher window.
        If text is provided, it's copied to clipboard before closing, 
        and a status message confirms the copy.

        Args:
            copy_and_close_text: Optional text to copy to clipboard before closing.
        """
        if copy_and_close_text is not None:
            self.copy_text_to_clipboard(copy_and_close_text)
            result_preview = str(copy_and_close_text).replace('\n', ' ').strip()[:50]
            self.set_status(f"📋 Copied: {result_preview}...")
            # Delay closing to allow user to see the status message
            QTimer.singleShot(250, self._window.close_launcher_window) 
        else:
            self._window.close_launcher_window()

    def quit_application(self) -> None:
        """
        Quits the entire SlickLauncher application.
        """
        self._window.quit_application()

    def get_settings(self) -> Settings:
        """
        Provides read-only access to the application's settings object.
        """
        return self._window.core.settings

    # --- Methods for advanced plugins needing direct widget access (use with caution) ---
    def get_preview_widget(self) -> QTextEdit:
        """
        Returns the QTextEdit widget used for the preview.
        Prefer `update_preview_content` for managing preview. Use this for highly custom interactions.
        """
        return self._window.preview_output

    def get_status_bar_widget(self) -> QLabel:
        """
        Returns the QLabel widget used for the status bar.
        Prefer `set_status` or `reset_status`. Use this for highly custom interactions.
        """
        return self._window.status_bar

    # --- Autocompletion related methods ---
    def get_completion_model(self) -> QStringListModel:
        """Returns the QStringListModel used by the completer for plugins to populate."""
        return self._window.completion_model

    def get_completer(self) -> QCompleter:
        """
        Returns the QCompleter instance for plugins to configure (e.g., setCompletionPrefix).
        """
        return self._window.completer

    def show_completion_popup(self) -> None:
        """
        Requests the completion popup to be shown if completions are available in the model.
        Also ensures the first item is selected.
        """
        # Check if completer exists and model has items
        if self._window.completer and self._window.completion_model.rowCount() > 0:
            if not self._window.completer.popup().isVisible(): # Show only if not already visible
                 self._window.completer.complete() # This triggers the popup
            # Ensure the first item is selected/highlighted after showing
            self._window._select_first_completion_item() 

    def hide_completion_popup(self) -> None:
        """Hides the completion popup if it's currently visible."""
        if self._window.completer and self._window.completer.popup().isVisible():
            self._window.completer.popup().hide()
