# slick_window.py
import os
import sys
import traceback
from contextlib import contextmanager

from PyQt6.QtCore import QMetaObject, QStringListModel, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QFontMetrics, QGuiApplication, QIcon, QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QCompleter,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QSystemTrayIcon,
    QTextEdit,
    QWidget,
)

from slick_launcher.hotkey import HotkeyListener
from slick_launcher.types import QInstance

from .api import API
from .core import CoreLogic
from .plugins.base_plugin import PluginInterface  # For type hinting
from .settingsUI import SettingsDialog  # For opening settings
from .singleInstance import singleInstance  # Base class for single instance app
from .ui import SlickUIFactory
from .utils import WORD_BOUNDARY_RE  # For autocompletion prefix detection


class SlickLauncherWindow(singleInstance):  # Inherits from singleInstance
    """
    The main application window for Slick Launcher.
    It handles UI events, interacts with CoreLogic for business logic,
    and uses SlickUIFactory to build its user interface.
    """

    # Signal to notify plugins about cleanup (e.g., before application quits)
    aboutToQuitSignal = (
        pyqtSignal()
    )  # Renamed from 'aboutToQuit' to avoid potential clashes
    # Signal emitted when settings (especially visual ones) are reloaded and applied
    settings_reloaded_signal = pyqtSignal()

    def __init__(self):
        """
        Initializes the main window, core logic, UI elements, and connects signals.
        """
        super().__init__()  # Call parent constructor (singleInstance)
        self.core = CoreLogic()
        self.api = API(self)
        self.hotkey_listener = None

        # --- Initialization Steps ---
        # 1. Register settings definitions (before loading them)
        self.core.register_main_settings()
        # 2. Load plugins (plugins might register their own settings)
        self.core.load_plugins(self.api, self.core.settings)
        # 3. Load all settings from TOML file
        self.core.load_settings_from_file()
        # 4. Initialize command history
        self.core.init_history()

        # --- Window State ---
        self.selected_text: str = ""  # Stores currently OS-selected text
        self.active_plugin: PluginInterface | None = None  # Currently active plugin
        self.do_not_trigger_AC_flag = False  # Prevents autocomplete re-triggering
        self._focus_changed_connection = (
            None  # Manages focus change connection for closeOnBlur
        )

        # --- UI Setup ---
        self._init_ui_elements()  # Create UI using SlickUIFactory
        self._connect_signals_and_handlers()  # Connect event handlers

        # --- Post-UI Setup ---
        self.update_status_bar()  # Set initial status bar message
        if self.core.settings.system.rememberLast and self.core.history:
            last_command = self.core.history[-1] if self.core.history else ""
            self.api.set_input_text(last_command)
            self.core.reset_history_index_to_latest()

        # Connect to application's global aboutToQuit signal for cleanup
        QApplication.instance().aboutToQuit.connect(self._handle_application_quit)

    def _init_ui_elements(self):
        """
        Initializes the window's appearance and creates UI widgets using SlickUIFactory.
        """
        self.setWindowTitle("Slick Launcher")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )  # Standard flags for this type of launcher
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )  # For custom rounded look

        # Create UI widgets using the factory
        ui_elements = SlickUIFactory.create_launcher_widgets(parent_widget=self)
        self.main_widget: QWidget = ui_elements["main_widget"]
        self.input_field: QLineEdit = ui_elements["input_field"]
        self.preview_output: QTextEdit = ui_elements["preview_output"]
        self.status_bar: QLabel = ui_elements["status_bar"]
        self.completer: QCompleter = ui_elements["completer"]
        self.completion_model: QStringListModel = ui_elements["completion_model"]

        self.setCentralWidget(self.main_widget)  # Set the main container widget

        # Apply stylesheet based on loaded settings
        self.apply_current_stylesheet()

        # Initial window sizing and positioning
        self.setFixedWidth(500)  # Fixed width for the launcher
        self.resize(500, 1)  # Start with minimal height, will adjust
        self._center_window()

    def _connect_signals_and_handlers(self):
        """
        Connects Qt signals from UI elements to their respective handler methods.
        """
        self.input_field.installEventFilter(self)  # For key press handling in input
        self.input_field.textChanged.connect(lambda: self._handle_input_change(False))
        self.completer.activated[str].connect(
            self._insert_completion_from_popup
        )  # Item selected from completer

        if self.core.settings.system.closeOnBlur:
            # Store the connection object to manage it (disconnect/reconnect)
            # when modal dialogs like settings are open.
            app_instance = QInstance()
            if app_instance:
                # It's good practice to check if already connected if this could be called multiple times
                try:
                    app_instance.focusChanged.disconnect(self._on_focus_changed)
                except TypeError:
                    pass  # Was not connected
                app_instance.focusChanged.connect(self._on_focus_changed)

    def apply_current_stylesheet(self):
        """
        Generates and applies the stylesheet based on current settings.
        Emits a signal indicating that visual settings have been reloaded.
        """
        qcss = SlickUIFactory.generate_stylesheet(self.core.settings)
        self.setStyleSheet(qcss)
        self.settings_reloaded_signal.emit()  # Notify interested components (e.g., plugins)

    def _center_window(self):
        """Centers the window on the screen where it appears."""
        try:
            screen_geometry = (
                self.screen().availableGeometry()
            )  # Get available geometry of the current screen
            self.move(screen_geometry.center() - self.frameGeometry().center())
        except Exception as e:
            # This can happen in some environments or if screen is not yet available
            print(f"Warning: Could not center window: {e}", file=sys.stderr)
            # Fallback: just move to a default position if screen info fails
            self.move(100, 100)

    def _capture_initial_os_selection(self):
        """
        Captures the currently selected text from the OS when the window is shown.
        Updates the status bar accordingly.
        """
        # Use a short delay if direct capture is problematic on some systems
        # QTimer.singleShot(50, lambda: self._update_selected_text_and_status())
        self._update_selected_text_and_status()

    def _update_selected_text_and_status(self):
        """Helper to get selected text and update status."""
        self.selected_text = self.core.get_os_selected_text()
        self.update_status_bar(
            self.active_plugin or self.core.find_plugin(is_default=True)
        )

    def update_status_bar(self, plugin: PluginInterface | None = None):
        """
        Updates the status bar text based on selected text length and current plugin.

        Args:
            plugin (PluginInterface | None): The plugin to get status message from.
                                            If None, uses the default plugin.
        """
        if plugin is None:
            plugin = self.core.find_plugin(is_default=True)

        status_message = (
            plugin.get_status_message()
            if plugin and hasattr(plugin, "get_status_message")
            else "Ready"
        )
        char_count = len(self.selected_text)
        self.status_bar.setText(f"✂️ ({char_count} chars) | {status_message}")

    def _reload_visual_settings(self):
        """
        Called after settings are changed (e.g., from SettingsDialog).
        Reloads settings from memory (assuming SettingsDialog updated them) and applies stylesheet.
        """
        print("Window: Reloading visual settings...")
        self.apply_current_stylesheet()

    def open_settings_dialog(self):
        """
        Opens the settings dialog. Manages focus change connection to prevent
        the main window from closing if 'closeOnBlur' is active.
        """
        app_instance = QInstance()
        was_connected = False
        if self.core.settings.system.closeOnBlur and app_instance:
            try:
                app_instance.focusChanged.disconnect(self._on_focus_changed)
                was_connected = True  # Successfully disconnected
            except TypeError:  # Was not connected or already disconnected
                was_connected = False

        dialog = SettingsDialog(
            self.core.settings, self
        )  # Pass current settings and parent

        dialog.settingsApplied.connect(self._reload_visual_settings)

        dialog.exec()
        # Reconnect focus logic if it was disconnected
        if self.core.settings.system.closeOnBlur and was_connected and app_instance:
            try:  # Ensure not to connect multiple times if logic changes
                app_instance.focusChanged.disconnect(self._on_focus_changed)
            except TypeError:
                pass
            app_instance.focusChanged.connect(self._on_focus_changed)

        # After dialog closes, visual settings might have changed (e.g. user hit OK/Apply)
        # The dialog.settingsApplied signal should handle this, but as a fallback:
        self._reload_visual_settings()

    @contextmanager
    def _suppress_autocomplete_retrigger(self):
        """
        Context manager to temporarily disable autocomplete re-triggering,
        useful when a completion is inserted programmatically.
        """
        self.do_not_trigger_AC_flag = True
        try:
            yield
        finally:
            self.do_not_trigger_AC_flag = False

    def _handle_input_change(self, manual_trigger_for_completion=False):
        """
        Handles text changes in the input field.
        Updates active plugin, triggers autocompletion, and updates preview.
        """
        if (
            self.core.ignore_text_changed_for_history
        ):  # If history navigation is happening, skip
            return

        self.core.reset_history_index_to_latest()  # User is typing, so reset history nav index
        command = self.input_field.text()
        cursor_pos = self.input_field.cursorPosition()

        # Special command to open settings
        if command == "/settings":
            self.open_settings_dialog()
            # self.input_field.clear() # Optional: clear input after opening settings
            self._hide_preview_output()  # Hide preview as it's likely irrelevant
            return

        # Determine the active plugin based on the command
        new_active_plugin = self.core.find_plugin(command)

        # If plugin context changes, reset completions
        if new_active_plugin != self.active_plugin:
            self.completion_model.setStringList([])  # Clear old completions
            if self.completer:
                self.completer.popup().hide()  # Hide popup
            self.active_plugin = new_active_plugin

        if not self.active_plugin:
            self.status_bar.setText("No matching plugin found!")
            self._hide_preview_output()
            self._adjust_main_window_height()
            return

        self.update_status_bar(self.active_plugin)  # Update status for the new plugin

        # --- Autocomplete Handling ---
        self._process_autocomplete(command, cursor_pos, manual_trigger_for_completion)

        # --- Preview Update ---
        if hasattr(self.active_plugin, "update_preview"):
            self.active_plugin.update_preview(command, self.selected_text, manual=False)
        self._adjust_main_window_height()  # Adjust height after preview content might have changed

    def _process_autocomplete(
        self, command: str, cursor_pos: int, manual_trigger: bool
    ):
        """Handles the logic for autocompletion."""
        if (
            self.do_not_trigger_AC_flag
            or not command
            or not self.active_plugin
            or not self.active_plugin.HAS_AUTOCOMPLETE
        ):
            if self.completer:
                self.completer.popup().hide()
            return

        # Determine if completion should be triggered
        should_trigger_completion_popup = manual_trigger or (
            self.core.settings.system.alwaysComplete
            or (cursor_pos > 0 and command[cursor_pos - 1] == ".")
        )  # Common trigger chars

        completions_were_updated = False
        if self.core.settings.system.doComplete:
            if should_trigger_completion_popup:
                try:
                    # Plugin is responsible for updating the completion_model and setting completionPrefix
                    if hasattr(self.active_plugin, "update_completions"):
                        self.active_plugin.update_completions(command, cursor_pos)

                    if self.completion_model.rowCount() > 0:
                        completions_were_updated = True
                        if not self.completer.popup().isVisible():
                            self.completer.complete()  # Show the popup
                        self._select_first_completion_item()  # Auto-select first item
                except Exception as e:
                    print(
                        f"Error during completion update by plugin {self.active_plugin.NAME}: {e}",
                        file=sys.stderr,
                    )
                    traceback.print_exc()
                    if self.completer:
                        self.completer.popup().hide()
            elif (
                self.completer.popup().isVisible()
            ):  # Popup is visible, but not explicitly triggered now
                # Update prefix for filtering if user is typing with popup open
                text_before_cursor = command[:cursor_pos]
                match = WORD_BOUNDARY_RE.search(
                    text_before_cursor
                )  # Use regex from utils
                if match:
                    prefix = match.group(1)
                    self.completer.setCompletionPrefix(prefix)
                    if not prefix:  # If prefix becomes empty, hide popup
                        self.completer.popup().hide()
                    else:
                        self._select_first_completion_item()  # Re-select after prefix change
                else:  # No valid prefix found
                    self.completer.popup().hide()

        # If no completions were generated/updated this cycle, and not manually triggered, hide popup
        if (
            not completions_were_updated
            and not self.completer.popup().isVisible()
            and not manual_trigger
        ):
            if self.completer:
                self.completer.popup().hide()

    def _select_first_completion_item(self):
        """Selects the first item in the completion popup if it's visible and has items."""
        if not self.completer or not self.completer.popup().isVisible():
            return

        popup_view = self.completer.popup()
        model = popup_view.model()  # Should be self.completion_model
        if model and model.rowCount() > 0:
            # Use QTimer.singleShot to ensure selection happens after Qt has processed events
            QTimer.singleShot(
                0,
                lambda: (
                    popup_view.setCurrentIndex(model.index(0, 0))
                    if popup_view.isVisible()
                    else None
                ),
            )

    def _insert_completion_from_popup(self, completion_text: str):
        """
        Inserts the selected completion text from the popup into the input field.
        This is connected to the completer's 'activated' signal.
        """
        if not self.active_plugin or not self.active_plugin.HAS_AUTOCOMPLETE:
            return  # Should not happen if completer is only active for such plugins

        current_text = self.input_field.text()
        cursor_pos = self.input_field.cursorPosition()
        prefix_to_replace = (
            self.completer.completionPrefix()
        )  # Get what the completer thinks is the prefix

        start_pos = cursor_pos - len(prefix_to_replace)

        # Construct new text and cursor position
        new_text = (
            current_text[:start_pos] + completion_text + current_text[cursor_pos:]
        )
        new_cursor_pos = start_pos + len(completion_text)

        with self._suppress_autocomplete_retrigger():  # Prevent immediate re-completion
            self.input_field.setText(new_text)
            self.input_field.setCursorPosition(new_cursor_pos)

        if self.completer:
            self.completer.popup().hide()  # Hide popup after inserting

    def eventFilter(self, obj, event: QKeyEvent):
        """
        Filters events for the input field, primarily for handling key presses
        like Enter, Escape, Tab, Up/Down arrows for history and completion.
        """
        if obj is self.input_field and event.type() == QKeyEvent.Type.KeyPress:
            key = event.key()
            modifiers = event.modifiers()
            is_completer_visible = self.completer.popup().isVisible()

            # --- History Navigation (Up/Down arrows) ---
            # Only if completer is not visible and history is enabled
            if not is_completer_visible and self.core.settings.system.history:
                text_from_history = None
                self.core.ignore_text_changed_for_history = (
                    True  # Suppress input_change during history nav
                )
                if key == Qt.Key.Key_Up:
                    text_from_history = self.core.get_history_previous()
                elif key == Qt.Key.Key_Down:
                    text_from_history = self.core.get_history_next()

                if (
                    text_from_history is not None
                ):  # Includes empty string from get_history_next
                    self.input_field.setText(text_from_history)
                    self.input_field.setCursorPosition(
                        len(text_from_history)
                    )  # Move cursor to end
                    self.core.ignore_text_changed_for_history = False
                    return True  # Event handled
                self.core.ignore_text_changed_for_history = False

            # --- Manual Completion Trigger (Ctrl+Space) ---
            if (
                modifiers == Qt.KeyboardModifier.ControlModifier
                and key == Qt.Key.Key_Space
            ):
                self._handle_input_change(manual_trigger_for_completion=True)
                event.accept()
                return True

            # --- Completer Interaction (Tab, Enter, Escape when popup is visible) ---
            if is_completer_visible:
                current_completion = (
                    self.completer.currentCompletion()
                )  # Highlighted item
                if (
                    key == Qt.Key.Key_Tab
                    or key == Qt.Key.Key_Return
                    or key == Qt.Key.Key_Enter
                ):
                    if current_completion:
                        self._insert_completion_from_popup(current_completion)
                        event.accept()
                        return True
                    else:  # No item selected, but popup is visible (e.g., Enter to dismiss?)
                        self.completer.popup().hide()
                        event.accept()
                        return (
                            True  # Or potentially execute if Enter, for now, just hide
                        )
                elif key == Qt.Key.Key_Escape:
                    self.completer.popup().hide()
                    event.accept()
                    return True
                # Let Up/Down arrow keys pass through to QCompleter's default handling
                elif key in [Qt.Key.Key_Up, Qt.Key.Key_Down]:
                    return super().eventFilter(
                        obj, event
                    )  # Allow completer to handle navigation

            # --- Standard Command Execution / Window Close (Return/Enter, Escape) ---
            # Only if completer is NOT visible
            if not is_completer_visible:
                if key in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
                    if modifiers == Qt.KeyboardModifier.ShiftModifier:
                        # QLineEdit doesn't directly support multiline, this might be for future
                        # For now, Shift+Enter could be an alternative execute or do nothing
                        pass  # Or self._execute_command(alternative_mode=True)
                    elif (
                        modifiers == Qt.KeyboardModifier.ControlModifier
                    ):  # Ctrl+Enter for manual preview
                        if self.active_plugin and hasattr(
                            self.active_plugin, "update_preview"
                        ):
                            self.active_plugin.update_preview(
                                self.input_field.text(), self.selected_text, manual=True
                            )
                            self._adjust_main_window_height()
                    else:  # Normal Enter executes the command
                        self._execute_command()
                    event.accept()
                    return True

                elif key == Qt.Key.Key_Escape:
                    self.close_launcher_window()  # Close/hide the launcher
                    event.accept()
                    return True

        return super().eventFilter(obj, event)  # Pass unhandled events to base class

    def _adjust_main_window_height(self):
        """
        Adjusts the main window's height based on the visibility and content
        of the preview output area. Uses QTimer for deferred execution.
        """
        QTimer.singleShot(0, self._perform_height_adjustment)

    def _perform_height_adjustment(self):
        """The actual logic for adjusting preview and window height."""
        document = self.preview_output.document()
        # Check if there's text content to decide whether to show or hide preview
        if not document.isEmpty():
            font_metrics = QFontMetrics(self.preview_output.font())
            line_height = font_metrics.lineSpacing()
            # Calculate content height (document.size().height() is more accurate for wrapped text)
            content_height = document.size().height()

            # Define padding and frame space (these are approximations, might need fine-tuning)
            padding_vertical = (
                self.preview_output.contentsMargins().top()
                + self.preview_output.contentsMargins().bottom()
                + 4
            )  # Approx
            frame_vertical_thickness = self.preview_output.frameWidth() * 2

            required_total_height = (
                content_height + padding_vertical + frame_vertical_thickness
            )
            # Max height for preview (e.g., 5 lines)
            max_height_for_5_lines = (
                (5 * line_height) + padding_vertical + frame_vertical_thickness
            )

            final_preview_height = min(required_total_height, max_height_for_5_lines)
            self.preview_output.setFixedHeight(int(final_preview_height))
            self.preview_output.show()
        else:
            self._hide_preview_output()  # Hide if no content

        # Adjust the main window size after showing/hiding/resizing preview
        # This ensures the main window shrinks or grows to fit its contents.
        self.adjustSize()

    def _hide_preview_output(self):
        """Utility to hide the preview output and trigger a window height adjustment."""
        self.preview_output.hide()
        QTimer.singleShot(0, self.adjustSize)  # Adjust main window size after hiding

    def _execute_command(self):
        """
        Executes the current command using the active plugin.
        Adds command to history and handles results (e.g., copying to clipboard).
        """
        command_raw = self.input_field.text()

        if not self.active_plugin:
            self.status_bar.setText("No plugin active to execute command.")
            return

        # Add to history before execution
        self.core.add_to_history(command_raw)

        # Determine the actual command text to pass to the plugin
        # (strip prefix/suffix if they match the active plugin's definition)
        command_to_execute = command_raw
        if self.active_plugin.PREFIX and command_raw.startswith(
            self.active_plugin.PREFIX
        ):
            command_to_execute = command_raw[len(self.active_plugin.PREFIX) :]
        elif self.active_plugin.SUFFIX and command_raw.endswith(
            self.active_plugin.SUFFIX
        ):
            command_to_execute = command_raw[: -len(self.active_plugin.SUFFIX)]
        # Note: Default plugins (without prefix/suffix) receive the raw command

        print(
            f"Window: Executing with plugin '{self.active_plugin.NAME}': '{command_to_execute}'"
        )
        try:
            # Execute and get potential result for clipboard
            if hasattr(self.active_plugin, "execute"):
                result = self.active_plugin.execute(
                    command_to_execute, self.selected_text
                )
                if (
                    result is not None
                ):  # Plugin returned something synchronously for clipboard
                    self._copy_to_clipboard_and_close(result)
            else:
                print(
                    f"Warning: Plugin {self.active_plugin.NAME} has no execute method.",
                    file=sys.stderr,
                )
                self.status_bar.setText(
                    f"Plugin {self.active_plugin.NAME} cannot execute."
                )

        except Exception as e:
            error_message = (
                f"Error during execution by plugin {self.active_plugin.NAME}: {e}"
            )
            print(error_message, file=sys.stderr)
            traceback.print_exc()
            self.status_bar.setText(
                f"💥 Plugin Error: {str(e)[:50]}..."
            )  # Show truncated error

    def _copy_to_clipboard_and_close(self, result_text: str):
        """Copies the given text to clipboard and closes the launcher window."""
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(str(result_text))  # Ensure it's a string
            result_preview = (
                str(result_text).replace("\n", " ").strip()[:50]
            )  # Truncate for status
            self.status_bar.setText(f"📋 Result copied: {result_preview}...")
            # Close after a short delay to allow user to see the status message
            QTimer.singleShot(200, self.close_launcher_window)
        else:
            self.status_bar.setText("INTERNAL Error: Could not access clipboard.")

    def _on_focus_changed(self, old_widget: QWidget | None, new_widget: QWidget | None):
        """
        Handles application focus changes. If 'closeOnBlur' is enabled,
        this will close the launcher if it loses focus to a non-child widget.
        """
        # Quit if focus is lost (unless a child widget like preview or completer popup gained focus)
        # IMPORTANT: Check if new_widget is None (happens during shutdown)
        # Also check if 'new_widget' is a Qt object before calling isAncestorOf
        if new_widget is None or (
            not self.isAncestorOf(new_widget) and new_widget is not self
        ):
            # Add a small delay to prevent quitting if focus briefly shifts during interaction
            # (e.g., clicking on a menu item of the launcher itself if it had one)
            QTimer.singleShot(150, self._check_and_close_if_focus_lost)

    def _check_and_close_if_focus_lost(self):
        """
        Performs the actual check and closes the window if it's still not active.
        This is called after a short delay from _on_focus_changed.
        """
        # Check isActiveWindow AND ensure the application is not in the process of shutting down
        app_instance = QInstance()
        if app_instance and not self.isActiveWindow():
            # Also check if any modal dialogs owned by this window are active
            # (e.g. settings dialog). If so, don't close.
            for widget in app_instance.topLevelWidgets():
                if (
                    isinstance(widget, QMainWindow)
                    and widget.isModal()
                    and widget.parent() is self
                ):  # Crude check
                    return  # Don't close if a modal child is active
            self.close_launcher_window()

    def _reset_ui_and_state(self):
        """Resets the UI elements and internal state to default."""
        self.input_field.clear()
        self.preview_output.clear()
        self._hide_preview_output()
        self.selected_text = ""  # Clear captured OS selection
        self.active_plugin = self.core.find_plugin(
            is_default=True
        )  # Reset to default plugin
        self.update_status_bar(self.active_plugin)
        self.core.reset_history_index_to_latest()
        self._adjust_main_window_height()  # Recalculate height for clean state

    def close_launcher_window(self):  # Renamed from 'close' to be more specific
        """Closes or hides the launcher window based on 'startInTray' setting."""
        if (
            self.core.settings.system.startInTray
            and self.tray_icon
            and self.tray_icon.isVisible()
        ):
            self._reset_ui_and_state()  # Clear content before hiding
            self.hide()  # Hide the window, it remains in tray
        else:
            self.quit_application()  # No tray or not set to start in tray, so quit

    def quit_application(self):
        """Initiates the application quit sequence."""
        # Cleanup is handled by _handle_application_quit via app.aboutToQuit signal
        QApplication.instance().quit()

    def _handle_application_quit(self):
        """
        Called when QApplication.instance().aboutToQuit is emitted.
        Ensures plugins are cleaned up and history is saved.
        """
        self.aboutToQuitSignal.emit()  # Notify internal components/plugins
        self.core.cleanup_plugins()  # Call core logic for plugin cleanup
        self.core.save_history()  # Ensure history is saved on exit
        if self.hotkey_listener:
            self.hotkey_listener.stop()

        if hasattr(self, "tray_icon") and self.tray_icon:  # Clean up tray icon
            self.tray_icon.hide()

    def _handle_hotkey(self):
        # Safely call the show_window slot in the main thread
        QMetaObject.invokeMethod(
            self, "show_window_signal", Qt.ConnectionType.QueuedConnection
        )

    @pyqtSlot()
    def show_window_signal(self):
        self.show_window_from_tray_or_socket()

    # --- System Tray Icon Functionality ---
    def setup_tray_icon(self):
        """Sets up the system tray icon and its context menu."""
        if not self.hotkey_listener and self.core.settings.system.hotkey:
            self.hotkey_listener = HotkeyListener(
                self.core.settings.system.hotkey, self._handle_hotkey
            )
            self.hotkey_listener.start()

        if not QSystemTrayIcon.isSystemTrayAvailable():
            print("Warning: System tray not available on this system.", file=sys.stderr)
            self.tray_icon = None
            return
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.png")
        icon = QIcon(icon_path)
        if icon.isNull():  # If themed icon not found and fallback also fails
            print("Warning: Could not load tray icon.", file=sys.stderr)

        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("Slick Launcher")

        tray_menu = QMenu(self)  # Parent menu to self for proper lifetime management
        show_action = QAction(
            "Show Launcher", self, triggered=self.show_window_from_tray_or_socket
        )
        settings_action = QAction("Settings", self, triggered=self.open_settings_dialog)
        tray_menu.addSeparator()
        quit_action = QAction(
            "Quit Slick Launcher", self, triggered=self.quit_application
        )

        tray_menu.addAction(show_action)
        tray_menu.addAction(settings_action)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        # Connect activation signal (e.g., left-click on tray icon)
        self.tray_icon.activated.connect(self._on_tray_icon_activated)
        self.tray_icon.show()
        print("Window: System tray icon setup complete.")

    def _on_tray_icon_activated(self, reason: QSystemTrayIcon.ActivationReason):
        """Handles activation of the tray icon (e.g., click)."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # Typically a left-click
            self.show_window_from_tray_or_socket()
        # Can also handle QSystemTrayIcon.ActivationReason.Context for right-click if menu not enough

    def show_window_from_tray_or_socket(self):  # Unified method for showing
        """
        Shows the main launcher window, captures OS selection, and sets focus.
        Called from tray or when a 'show' socket command is received.
        """
        self._reset_ui_and_state()  # Ensure clean state when shown
        self._capture_initial_os_selection()  # Get current OS selected text
        self.showNormal()  # Show the window normally (not maximized or minimized)
        self.activateWindow()  # Bring to front and give focus
        self.raise_()  # Ensure it's on top of other windows
        self.input_field.setFocus()  # Set focus to the input field

    # --- Overridden from singleInstance base class ---
    def process_socket_command(self, command_data: str):
        """
        Handles commands received via socket from another instance (if using singleInstance).
        Overrides the method from the `singleInstance` base class.

        Args:
            command_data (str): The command string received.
        """
        command_data = command_data.strip().lower()
        print(f"Window: Received socket command: '{command_data}'")
        if command_data == "show":
            # Ensure this is run in the GUI thread if socket handling is on another thread
            QTimer.singleShot(0, self.show_window_from_tray_or_socket)
        elif command_data == "settings":
            QTimer.singleShot(
                0,
                lambda: [
                    self.show_window_from_tray_or_socket(),
                    self.open_settings_dialog(),
                ],
            )
        else:
            print(f"Window: Unknown socket command received: {command_data}")
        # Call super if singleInstance has its own processing logic you want to preserve
        # super().process_socket_command(command_data)

    # Override closeEvent to handle tray icon logic if window is closed by user (e.g., 'X' button)
    def closeEvent(self, event):
        """
        Overrides QWidget.closeEvent. Called when the user attempts to close the window.
        If configured to run in tray, this will hide the window instead of quitting.
        """
        if (
            self.core.settings.system.startInTray
            and self.tray_icon
            and self.tray_icon.isVisible()
        ):
            self._reset_ui_and_state()
            self.hide()  # Hide the window, don't accept the close event which would quit
            event.ignore()  # Important: ignore the event to prevent actual closing
        else:
            # Not in tray mode or no tray icon, so proceed with normal close (which leads to quit)
            event.accept()
            self.quit_application()  # Ensure quit sequence is initiated
