# base_plugin.py
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List, Optional

from PyQt6.QtCore import QThread

# Assuming types.py defines pyqtSignal, if not, import from QtCore
# from PyQt6.QtCore import pyqtSignal

if TYPE_CHECKING:
    from ..api import API
    from ..settings import Settings

    # If your project has a common types.py for pyqtSignal, use this:
    # from ..types import pyqtSignal
    # Otherwise, for standard Qt, you'd import pyqtSignal from QtCore in worker threads.


class Thread(QThread):
    """
    Base class for worker threads used by plugins.
    Ensures a stop method is declared.
    """

    @abstractmethod
    def stop(self):
        """Signals the thread to stop its operation."""
        raise NotImplementedError("Subclasses of Thread must implement stop()")


class PluginInterface(ABC):
    """
    Abstract Base Class for Slick Launcher plugins.
    Plugins interact with the launcher via the provided API instance.
    """

    NAME: str = "Base Plugin"
    PREFIX: Optional[str] = None
    SUFFIX: Optional[str] = None
    IS_DEFAULT: bool = False
    PRIORITY: int = 99
    HAS_AUTOCOMPLETE: bool = False

    def __init__(self, api_instance: "API", settings: "Settings"):
        """
        Initialize the plugin.

        Args:
            api_instance: An instance of the API class for interacting with the launcher.
            settings: The application settings object.
        """
        self.api = api_instance
        self.settings = settings  # Store settings instance as requested
        self.active_workers: List[Thread] = []

    @abstractmethod
    def get_status_message(self) -> str:
        """
        Return a short status message to display when this plugin is potentially active.
        This message is used by `api.reset_status()` or can be part of `api.set_status()`.
        """
        pass

    @abstractmethod
    def update_preview(self, command: str, selected_text: str, manual: bool) -> None:
        """
        Update the preview based on the current command and selected text.
        Plugins should use `self.api.update_preview_content()` and `self.api.set_status()`.

        Args:
            command: The current text in the input field (obtained via `self.api.get_input_text()`).
            selected_text: The text currently selected in the system (obtained via `self.api.get_selected_os_text()`).
            manual: True if the preview was triggered by a manual action (e.g., Ctrl+Enter).
        """
        pass

    @abstractmethod
    def execute(self, command: str, selected_text: str) -> Optional[str]:
        """
        Execute the main action of the plugin.

        Args:
            command: The final command text (stripped of prefix/suffix by the core).
            selected_text: The text currently selected in the system.

        Returns:
            A string containing the result to be copied to the clipboard.
            If a string is returned, `self.api.close_launcher(result)` will be called.
            If None is returned, the plugin is responsible for any further actions,
            including calling `self.api.close_launcher()` or `self.api.quit_application()`
            if needed, or updating status/preview for errors or async operations.
        """
        pass

    @abstractmethod
    def register_settings(self, settings_manager: "Settings") -> None:
        """
        Register plugin-specific settings with the application's settings manager.
        The `settings_manager` is the main application's settings object (self.settings).
        This method is called by CoreLogic during plugin loading.

        Example:
            # In your plugin's register_settings:
            # plugin_section = settings_manager.section(f"plugin_{self.NAME.lower().replace(' ', '_')}")
            # plugin_section.add('my_option', 'Description of my option', 'default_val', str)
        """
        pass

    def update_completions(self, command: str, cursor_pos: int) -> None:
        """
        Optional: Update autocomplete suggestions.
        Plugins should use:
        - `model = self.api.get_completion_model()`
        - `completer = self.api.get_completer()`
        - `model.setStringList([...])`
        - `completer.setCompletionPrefix("...")`
        - `self.api.show_completion_popup()` or `self.api.hide_completion_popup()`

        Args:
            command: The full text currently in the input field.
            cursor_pos: The current position of the text cursor.
        """
        # Default implementation does nothing.
        # Plugins with HAS_AUTOCOMPLETE = True should override this.
        pass

    def cleanup(self) -> None:
        """Optional: Clean up resources, including stopping any active workers."""
        for worker in self.active_workers[:]:
            if isinstance(worker, Thread) and worker.isRunning():
                try:
                    worker.stop()
                    worker.quit()
                    if not worker.wait(1000):
                        print(
                            f"Plugin {self.NAME}: Worker thread did not stop gracefully, terminating."
                        )
                        worker.terminate()
                        worker.wait()
                except Exception as e:
                    print(f"Plugin {self.NAME}: Error stopping worker thread: {e}")
            if worker in self.active_workers:
                self.active_workers.remove(worker)

        # print(f"Plugin {self.NAME}: Cleanup complete. Active workers left: {len(self.active_workers)}")
