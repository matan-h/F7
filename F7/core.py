import os
import sys
import traceback
from typing import Optional

from appdirs import user_config_dir

from .api import API
from .clip import get_selected_text
from .plugins import plugins as plugins_registry
from .plugins.base_plugin import PluginInterface
from .settings import Color, HotKeyType, Settings


class CoreLogic:
    """
    Handles non-QT UI related logic for F7, including:
    - Settings management (loading, saving, registration)
    - Plugin loading and management
    - Command history
    - Accessing OS-level selected text
    """

    def __init__(self):
        self.config_dir = user_config_dir("F7")
        os.makedirs(self.config_dir, exist_ok=True)

        self.settings = Settings()
        self.plugins: list[PluginInterface] = []
        self.history_path = os.path.join(self.config_dir, "history.txt")
        self.history: list[str] = []
        self.current_history_index = 0  # Index for navigating history
        self.ignore_text_changed_for_history = False
        self.default_plugin: Optional[PluginInterface] = None

    def register_main_settings(self):
        # In Qt’s QSS you can use 8‑digit hex in the #AARRGGBB format, where the first two hex digits are the alpha channel.

        # [colors] section
        colors_section = self.settings.section(
            "colors"
        )  # Use a different variable name
        colors_section.add(
            "main_widget_bg", "Main widget background color", "#282c34", Color
        )
        colors_section.add(
            "main_widget_border", "Main widget border color", "#1f1f1f", Color
        )

        # Input field settings
        colors_section.add("input_bg", "Input field background color", "#1e222a", Color)
        colors_section.add(
            "input_border", "Input field border color", "#14ffffff", Color
        )
        colors_section.add("input_text", "Input field text color", "#abb2bf", Color)
        colors_section.add(
            "input_focus_border", "Input field focus border color", "#4682b4", Color
        )

        # Preview settings
        colors_section.add("preview_bg", "Preview background color", "#1e222a", Color)
        colors_section.add("preview_border", "Preview border color", "#0fffffff", Color)
        colors_section.add("preview_text", "Preview text color", "#abb2bf", Color)

        # Completion popup settings
        colors_section.add(
            "completion_popup_bg", "Completion popup background color", "#32363e", Color
        )
        colors_section.add(
            "completion_popup_border",
            "Completion popup border color",
            "#25ffffff",
            Color,
        )
        colors_section.add(
            "completion_popup_text", "Completion popup text color", "#abb2bf", Color
        )
        colors_section.add(
            "completion_item_selected_bg",
            "Selected completion item background color",
            "#4682b4",
            Color,
        )
        colors_section.add(
            "completion_item_selected_text",
            "Selected completion item text color",
            "#ffffff",
            Color,
        )

        # Status bar settings
        colors_section.add("status_bar_text", "Status bar text color", "#5c6370", Color)

        # [system] section
        system_section = self.settings.section(
            "system"
        )  # Use a different variable name
        system_section.add("startInTray", "Start minimized in system tray", True, bool)
        system_section.add(
            "closeOnBlur", "Close window when it loses focus", True, bool
        )
        system_section.add("doComplete", "Enable autocompletion", True, bool)
        system_section.add(
            "alwaysComplete", "Show completions without waiting for '.'", False, bool
        )
        system_section.add("rememberLast", "Remember the last command", False, bool)
        system_section.add("history", "Enable command history", True, bool)
        system_section.add("history_limit", "Max number of history items", 100, int)
        system_section.add(
            "hotkey",
            "the keyboard shortcut to start the app from tray in windows/macos",
            "<F7>",
            HotKeyType,
        )

    def load_settings_from_file(self):
        toml_path = os.path.join(self.config_dir, "settings.toml")
        self.settings.load_from_toml(toml_path)

    def load_plugins(
        self, api_instance: API, app_settings: Settings
    ):  # Changed signature
        """
        Dynamically loads and initializes plugins from the plugins_registry.
        Plugins are sorted by priority.

        Args:
            api_instance: The API instance for plugins to use.
            app_settings: The main application settings object.
        """
        # TODO: write a list of each plugin and its startup speed.
        loaded_plugins_temp = []
        for plugin_class in plugins_registry:
            try:
                # Pass the api_instance and the global settings object to the plugin
                plugin_instance = plugin_class(api_instance, app_settings)

                # Let plugins register their specific settings using the passed global settings
                if hasattr(plugin_instance, "register_settings") and callable(
                    plugin_instance.register_settings
                ):
                    plugin_instance.register_settings(
                        app_settings
                    )  # Pass the main settings manager

                loaded_plugins_temp.append(plugin_instance)
            except Exception as e:
                print(
                    f"Core: Failed to load or initialize plugin {getattr(plugin_class, 'NAME', plugin_class.__name__)}: {e}",
                    file=sys.stderr,
                )
                traceback.print_exc()

        # Sort plugins: Prefix/Suffix matching first, then by priority (lower first), then default
        loaded_plugins_temp.sort(
            key=lambda p: (not (p.PREFIX or p.SUFFIX), p.PRIORITY, not p.IS_DEFAULT)
        )
        # TODO: load external plugins too (maybe from ~/.config/F7/plugins)
        self.plugins = loaded_plugins_temp

        # Identify the default plugin after sorting
        self.default_plugin = next((p for p in self.plugins if p.IS_DEFAULT), None)
        if not self.default_plugin and self.plugins:
            self.default_plugin = self.plugins[
                -1
            ]  # Fallback: last by priority if no explicit default
            if self.default_plugin:
                print(
                    f"Core: No explicit default plugin. Using '{self.default_plugin.NAME}' as fallback default.",
                    file=sys.stderr,
                )

        if not self.plugins:
            print("Core: Warning: No valid plugins were loaded.", file=sys.stderr)

    def init_history(self):
        self.history = []
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    self.history = [line.strip() for line in f if line.strip()]
            except Exception as e:
                print(f"Core: Error loading history: {e}", file=sys.stderr)
        self.current_history_index = len(self.history)

    def save_history(self):
        if not self.settings.system.history:
            return
        try:
            # Apply history limit
            history_limit = self.settings.system.history_limit
            if len(self.history) > history_limit:
                self.history = self.history[-history_limit:]

            with open(self.history_path, "w", encoding="utf-8") as f:
                for cmd in self.history:
                    f.write(f"{cmd}\n")
        except Exception as e:
            print(f"Core: Error saving history: {e}", file=sys.stderr)

    def add_to_history(self, command_raw: str):
        if self.settings.system.history and command_raw and command_raw.strip():
            stripped_command = command_raw.strip()
            if not self.history or self.history[-1] != stripped_command:
                self.history.append(stripped_command)
            # current_history_index should point to one position *after* the last item,
            # effectively representing the "new command" line.
            self.current_history_index = len(self.history)

    def get_history_previous(self):
        if not self.history:
            return None
        if self.current_history_index > 0:
            self.current_history_index -= 1
            return self.history[self.current_history_index]
        # If already at the oldest (index 0), keep returning it
        return self.history[0] if self.history else None

    def get_history_next(self):
        if not self.history or self.current_history_index >= len(self.history):
            # If index is already at or past the "new command" line, nothing "next"
            return ""  # Signal to clear input

        if self.current_history_index < len(self.history) - 1:
            self.current_history_index += 1
            return self.history[self.current_history_index]
        elif self.current_history_index == len(self.history) - 1:
            # We are at the last actual history item, moving "next" goes to the "new command" line
            self.current_history_index += 1
            return ""  # Signal to clear input
        return ""  # Should not be reached

    def reset_history_index_to_latest(self):
        if (
            not self.ignore_text_changed_for_history
        ):  # Only reset if not actively navigating
            self.current_history_index = len(self.history)

    def find_plugin(
        self, command: str = "", is_default: bool = False
    ) -> Optional[PluginInterface]:
        if is_default:
            return self.default_plugin

        if not command:  # If command is empty, usually the default plugin handles it
            return self.default_plugin

        for plugin in self.plugins:
            if plugin.PREFIX and command.startswith(plugin.PREFIX):
                return plugin

            if plugin.SUFFIX and command.endswith(plugin.SUFFIX):
                return plugin

        return self.default_plugin  # Fallback to default if no specific match

    def cleanup_plugins(self):
        for plugin in self.plugins:
            try:
                if hasattr(plugin, "cleanup") and callable(plugin.cleanup):
                    plugin.cleanup()
            except Exception as e:
                print(
                    f"Core: Error cleaning up plugin {getattr(plugin, 'NAME', 'UnknownPlugin')}: {e}",
                    file=sys.stderr,
                )
                traceback.print_exc()
        self.plugins = []  # Clear the list of plugins

    def get_os_selected_text(self) -> str:
        try:
            return get_selected_text()
        except Exception as e:
            print(f"Core: Error getting selected text from OS: {e}", file=sys.stderr)
            return ""
