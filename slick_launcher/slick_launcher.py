# slick_launcher.py
import os
import sys,traceback

from PyQt6.QtCore import Qt, QTimer, pyqtSignal,QStringListModel
from PyQt6.QtGui import QKeyEvent, QFont, QGuiApplication,QFontMetrics, QColor
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLineEdit,
                             QTextEdit, QVBoxLayout, QWidget, QLabel,
                             QFrame,QCompleter,QMessageBox)


from .settingsUI import SettingsDialog # Corrected import name
from . import workaround as _
# Local imports
from .clip import get_selected_text
from .plugins.base_plugin import PluginInterface # For type hinting
from .plugins import plugins
# exit(0) # 258.18ms to this point
from .utils import WORD_BOUNDARY_RE
from .settings import Settings,Color # Assuming Color class exists
from appdirs import user_config_dir


# --- Constants ---
class SlickLauncher(QMainWindow):
    # Signal to notify plugins about cleanup
    aboutToQuit = pyqtSignal()
    # Signal emitted by main window when settings are applied (e.g., colors reloaded)
    # This can be useful for plugins if they also use colors or settings that need dynamic updates
    settings_reloaded = pyqtSignal()


    def __init__(self):
        super().__init__()
        self.selected_text = ""
        self.plugins = []
        self.active_plugin = None
        self.completer = None
        self.completion_model = None

        # Initialize settings before anything else
        self.settings = Settings()
        self.register_main_settings()  # Register core settings

        self.load_plugins()
        for plugin in self.plugins:
            plugin.register_settings(self.settings)  # Let plugins register their settings

        self.load_settings()    # Load from TOML after all registrations
        self.initUI()
        self.capture_initial_selection() # Get text immediately
        self.resetStatus() # Set initial status based on default plugin

        # The connection for reloading visual settings will be made
        # when the SettingsDialog is opened.

    def register_main_settings(self):
        """Register the core settings for Slick Launcher."""
        # [colors] section
        colors = self.settings.section("colors")
        colors.add("main", "Main background color", "#282c34", Color)
        colors.add("input", "Input field background color", "#1e222a", Color)
        colors.add("preview", "Preview background color", "#1e222a", Color)
        colors.add("completion_popup", "Completion popup background color", "#32363e", Color)
        colors.add("completion_selected", "Selected completion item background color", "#4682b4", Color)

        # [system] section
        system = self.settings.section("system")
        system.add("closeOnBlur", "Close launcher when it loses focus", True, bool)
        system.add("doComplete", "Enable autocompletion", True, bool)
        system.add("alwaysComplete", "Always show completions without waiting for '.'", False, bool)
        system.add("rememberLast", "Remember the last command", True, bool)
        system.add("history", "Enable command history", True, bool)

    def load_settings(self):
        """Load settings from the TOML file in the OS-appropriate directory."""
        config_dir = user_config_dir("slick_launcher", "your_company_name")
        os.makedirs(config_dir, exist_ok=True)
        toml_path = os.path.join(config_dir, "settings.toml")
        self.settings.load_from_toml(toml_path)

    def load_plugins(self):
        """Dynamically loads plugins from the PLUGIN_DIR directory."""
        self.plugins = list(map(lambda x:x(self),plugins))


        # Sort plugins: Prefix/Suffix matching first, then by priority (lower first), then default
        self.plugins.sort(key=lambda p: (
            not (p.PREFIX or p.SUFFIX), # Plugins with prefix/suffix come first (False < True)
            p.PRIORITY,                 # Then sort by priority number
            not p.IS_DEFAULT            # Ensure default is considered last among equals
        ))

        if not self.plugins:
             print("Warning: No valid plugins were loaded.", file=sys.stderr)


    def initUI(self):
        self.setWindowTitle("Slick Launcher")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                           Qt.WindowType.WindowStaysOnTopHint |
                           Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.main_widget = QWidget()
        self.main_widget.setObjectName("MainWidget")
        self.setCentralWidget(self.main_widget)

        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        self.main_widget.setLayout(layout)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter text or command...") # Generic placeholder
        self.input_field.setObjectName("InputField")
        self.input_field.installEventFilter(self)
        layout.addWidget(self.input_field)
                # --- Setup Autocompleter ---
        self.completion_model = QStringListModel()
        self.completer = QCompleter(self.completion_model, self)
        self.completer.setWidget(self.input_field)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        # self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive) # Often desired
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive) # Python is case-sensitive
        self.completer.setFilterMode(Qt.MatchFlag.MatchStartsWith) # Standard completion filter
        # self.completer.setPopup(QFrame()) # Use a QFrame for custom styling if needed
        self.completer.popup().setObjectName("CompletionPopup") # For styling
        self.completer.activated[str].connect(self.insert_completion) # Signal when item selected


        self.preview_output = QTextEdit()
        self.preview_output.setObjectName("PreviewOutput")
        self.preview_output.setReadOnly(True)
        self.preview_output.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.preview_output.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.preview_output.setFrameStyle(QFrame.Shape.NoFrame)
        self.preview_output.setMaximumHeight(200) # Increased max height a bit
        self.preview_output.setFocusPolicy(Qt.FocusPolicy.NoFocus) # Prevent Tab focusing read-only preview

        self.hide_preview()
        layout.addWidget(self.preview_output)

        self.status_bar = QLabel()
        self.status_bar.setObjectName("StatusBar")
        layout.addWidget(self.status_bar)

        # Apply initial stylesheet based on loaded settings
        self.apply_stylesheet()

        self.resize(500, 1) # Start minimal height
        self.setFixedWidth(500)

        self.centerWindow()

        # Signals
        self.input_field.textChanged.connect(lambda: self.handle_input_change())
        if self.settings.system.closeOnBlur:
            QApplication.instance().focusChanged.connect(self.on_focus_changed)
        # Connect the application's aboutToQuit signal to our cleanup handler
        QApplication.instance().aboutToQuit.connect(self.cleanup_plugins)

    def generate_stylesheet(self) -> str:
        """Generates the QSS string based on the current settings."""
        # Access colors directly from the loaded settings object
        colors = self.settings.colors # Assuming self.settings.colors is the 'colors' section

        # Ensure color values are valid hex strings, default if not
        def get_valid_hex(color_setting, default="#ffffff"):
            if isinstance(color_setting, Color):
                 # Use the Color object's hex attribute
                 hex_str = color_setting
            elif isinstance(color_setting, str):
                 # Assume string is a potential hex code
                 hex_str = color_setting
            else:
                 # Fallback if type is unexpected
                 return default

            # Basic validation (e.g., #RRGGBB or #RRGGBBAA)
            if not isinstance(hex_str, str) or not (hex_str.startswith("#") and len(hex_str) in [7, 9]):
                 print(f"Warning: Invalid color format '{hex_str}', using default '{default}'", file=sys.stderr)
                 return default
            return hex_str


        qcss = f"""
            #MainWidget {{
                background: {get_valid_hex(colors.main, '#282c34')};
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.12);
            }}
            #InputField {{
                font-size: 16px;
                padding: 8px 12px;
                background: {get_valid_hex(colors.input, '#1e222a')};
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                color: #abb2bf; /* Keep static text color unless you add it to settings */
                margin-bottom: 4px;
            }}
            #PreviewOutput {{
                font-family: 'Fira Code', 'Consolas', monospace; /* Add fallback fonts */
                font-size: 13px;
                background: {get_valid_hex(colors.preview, '#1e222a')};
                color: #abb2bf; /* Keep static text color unless you add it to settings */
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 4px;
                padding: 4px 8px;
            }}
            #StatusBar {{
                color: #5c6370; /* Keep static text color unless you add it to settings */
                font-size: 11px;
                padding: 2px 4px;
                margin-top: 4px;
            }}

            #CompletionPopup {{ /* Style the completer popup */
                background: {get_valid_hex(colors.completion_popup, '#32363e')};
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 4px;
                color: #abb2bf; /* Text color */
                font-size: 13px; /* Match preview font size? */
                padding: 2px;
                margin: 0px; /* Important for positioning */
            }}
            #CompletionPopup QAbstractItemView::item {{ /* Style individual items */
                 padding: 4px 8px;
                 border-radius: 3px; /* Rounded corners for items */
            }}
            #CompletionPopup QAbstractItemView::item:selected {{ /* Highlight selected item */
                background-color: {get_valid_hex(colors.completion_selected, '#4682b4')};
                color: #ffffff;
            }}
        """
        return qcss

    def apply_stylesheet(self):
        """Generates and applies the stylesheet based on current settings."""
        qcss = self.generate_stylesheet()
        # print(qcss) # Uncomment to debug CSS
        self.setStyleSheet(qcss)
        # Emit signal after applying visual settings
        self.settings_reloaded.emit()


    def centerWindow(self):
        frame = self.frameGeometry()
        center = self.screen().availableGeometry().center()
        frame.moveCenter(center)
        self.move(frame.topLeft())

    def capture_initial_selection(self):
        # Use a short delay to allow the clipboard/selection mechanism to catch up
        # when the window is first shown.
        self._update_selected_text()
        # QTimer.singleShot(50, self._update_selected_text)

    def _update_selected_text(self):
        self.selected_text = get_selected_text()
        self.resetStatus() # Update status after getting text

    def resetStatus(self,plugin=None):
        """Sets the status bar based on selected text and the default plugin."""
        if plugin is None:
            plugin = self.find_plugin(is_default=True)
        status_text = plugin.get_status_message() if plugin else "No default plugin"
        self.status_bar.setText(f"✂️ ({len(self.selected_text)} chars) | {status_text}")


    def find_plugin(self, command: str = "", is_default: bool = False) -> PluginInterface | None:
        """Finds the highest priority plugin that matches the command or the default."""
        # default - 0. prefix - 1. suffix - 2
        if is_default:
            # Find the first plugin marked as default
            for plugin in self.plugins:
                if plugin.IS_DEFAULT:
                    return plugin
            return None # Should not happen if sorting is correct and one IS_DEFAULT=True exists

        # Find by prefix/suffix based on priority
        for plugin in self.plugins:
            if plugin.PREFIX and command.startswith(plugin.PREFIX):
                return plugin
            if plugin.SUFFIX and command.endswith(plugin.SUFFIX):
                return plugin

        # If no prefix/suffix match, return the default plugin
        return self.find_plugin(is_default=True)


    def reload_visual_settings(self):
        """Applies the stylesheet based on the current in-memory settings."""
        print("Reloading visual settings based on current in-memory state...")
        # Removed load_settings() - we want to use the settings modified by the dialog directly
        self.apply_stylesheet() # Apply the stylesheet using the current values


    def open_settings(self):
        """Open the settings dialog."""
        # Disconnect focus logic temporarily to prevent unintended quitting
        if self.settings.system.closeOnBlur:
            try:
                 # Store the signal connection object to safely disconnect
                 self._focus_changed_connection = QApplication.instance().focusChanged.disconnect(self.on_focus_changed)
            except (TypeError, RuntimeError): # Handle case where it might not have been connected yet or already disconnected
                 self._focus_changed_connection = None # Ensure it's None if disconnection fails


        dialog = SettingsDialog(self.settings, self)

        # --- Connect the signal from the dialog ---
        # We assume SettingsDialog has a signal named 'settingsApplied'
        # that it emits AFTER successfully updating the in-memory settings.
        try:
            dialog.settingsApplied.connect(self.reload_visual_settings)
        except AttributeError:
            print("Warning: SettingsDialog does not have a 'settingsApplied' signal. Auto-reload won't work.", file=sys.stderr)


        dialog.exec() # Show the dialog modally

        # Reconnect focus logic after the dialog is closed
        if self.settings.system.closeOnBlur:
            # Use the stored connection object if available, otherwise reconnect directly
            if self._focus_changed_connection is None:
                 QApplication.instance().focusChanged.connect(self.on_focus_changed)
            else:
                 # Reconnect using the stored connection object's connect method
                 self._focus_changed_connection.connect(self.on_focus_changed)
            self._focus_changed_connection = None # Clear the stored object


    def handle_input_change(self,manual_trigger=False): # Removed manual=False, not needed here now
        """Called when text in the input field changes."""
        command = self.input_field.text()
        if (command=="/settings"):
            self.open_settings()
            # Clear the input field after opening settings? Or let user delete?
            # self.input_field.clear()
            # self.hide_preview() # Hide preview after opening settings
            # self.adjustHeight()
            return # Stop processing input if opening settings

        cursor_pos = self.input_field.cursorPosition()
        new_active_plugin = self.find_plugin(command)

        # --- Handle Plugin Change ---
        if new_active_plugin != self.active_plugin:
            # Plugin changed, clear old completions immediately
            if self.completion_model:
                self.completion_model.setStringList([])
            if self.completer:
                self.completer.popup().hide()
            # Update active plugin reference
            self.active_plugin = new_active_plugin

        # --- Plugin Logic ---
        if not self.active_plugin:
            self.status_bar.setText("No matching plugin found!")
            self.hide_preview()
            self.adjustHeight()
            return # No plugin, no preview or completion

        self.resetStatus(self.active_plugin)

        # --- Autocomplete Handling ---
        should_trigger_completion = manual_trigger or (
            self.settings.system.alwaysComplete or
            (command and cursor_pos > 0 and command[cursor_pos - 1] == '.')
        )

        completions_updated = False # Flag to know if plugin provided new list
        if self.settings.system.doComplete and self.active_plugin.HAS_AUTOCOMPLETE:
             if should_trigger_completion:
                 try:
                     # --- Let plugin update completions ---
                     # We assume plugin calls setStringList and setCompletionPrefix
                     self.active_plugin.update_completions(command, cursor_pos)
                     # Check if completions were actually generated after the update
                     if self.completion_model.rowCount() > 0:
                          completions_updated = True
                          # Trigger the popup if not visible, handled by plugin now?
                          # Let's ensure popup logic remains robust.
                          # If plugin didn't show popup, maybe we should?
                          if not self.completer.popup().isVisible():
                              self.completer.complete() # Ensure popup shows
                          # --- Call centralized select_first ---
                          self.select_first_completion()

                 except Exception as e:
                     print(f"Error during completion update by plugin {self.active_plugin.NAME}: {e}", file=sys.stderr)
                     traceback.print_exc()
                     if self.completer: self.completer.popup().hide()
             else:
                 # Update prefix for filtering if popup already visible
                 if self.completer.popup().isVisible():
                      text_before_cursor = command[:cursor_pos]
                      match = WORD_BOUNDARY_RE.search(text_before_cursor)
                      if match:
                          prefix = match.group(1)
                          self.completer.setCompletionPrefix(prefix)
                          # If prefix is now empty, maybe hide?
                          if not prefix:
                              self.completer.popup().hide()
                          else:
                              # Model might need filtering, ensure first item is selected again?
                              # QCompleter handles filtering based on prefix, but selection might reset.
                              self.select_first_completion() # Reselect first after prefix change
                      else:
                          self.completer.popup().hide() # Hide if prefix is broken)

        # If no completions were generated this time, hide the popup
        if not completions_updated and not self.completer.popup().isVisible() and not manual_trigger:
             # Don't hide if manually triggered and no completions found? Maybe show status?
             if self.completer: self.completer.popup().hide()


        # --- Preview Update ---
        # Let the active plugin handle the preview update
        # We can still use the manual flag concept here if needed (Ctrl+Enter)
        is_manual_preview = False # Determine if Ctrl+Enter triggered this somehow if needed
        self.active_plugin.update_preview(
            command,
            self.selected_text,
            self.preview_output,
            self.status_bar,
            manual=is_manual_preview # Pass appropriate value
        )

        # Adjust height *after* plugin updates preview/completions
        self.adjustHeight()

    def select_first_completion(self):
        """Selects the first item in the completion popup if available."""
        if not self.completer or not self.completer.popup().isVisible():
             return # Don't try if completer/popup not ready

        popup = self.completer.popup()
        model = popup.model()
        if model and model.rowCount() > 0:
             # Use QTimer.singleShot to ensure it runs after Qt updates the view
             def do_select():
                 # Re-check visibility in case it was hidden before timer fired
                 if popup.isVisible():
                     index = model.index(0, 0)
                     popup.setCurrentIndex(index)
             QTimer.singleShot(0, do_select)


    def insert_completion(self, completion):
        """Inserts the selected completion into the input field."""
        if not self.active_plugin or not self.active_plugin.HAS_AUTOCOMPLETE:
            return # Should not happen if completer is only active for Python plugin

        current_text = self.input_field.text()
        cursor_pos = self.input_field.cursorPosition()

        # Use the completion prefix the completer determined to know what to replace
        prefix = self.completer.completionPrefix()
        start_pos = cursor_pos - len(prefix)

        # Construct the new text
        new_text = current_text[:start_pos] + completion + current_text[cursor_pos:]
        new_cursor_pos = start_pos + len(completion)

        # Set the text and move cursor
        self.input_field.setText(new_text)
        self.input_field.setCursorPosition(new_cursor_pos)

        # Hide the popup after inserting
        self.completer.popup().hide()

    def eventFilter(self, obj, event):
        if obj is self.input_field and event.type() == QKeyEvent.Type.KeyPress:
            key = event.key()
            modifiers = event.modifiers()
            is_completer_visible = self.completer.popup().isVisible()

            # --- Manual Completion Trigger ---
            if modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_Space:
                 print("Manual completion triggered (Ctrl+Space)")
                 # Directly call handle_input_change with manual trigger flag
                 self.handle_input_change(manual_trigger=True)
                 event.accept()
                 return True

            # --- Handle Completer Interaction ---
            if is_completer_visible:
                 current_completion = self.completer.currentCompletion() # Get currently highlighted item

                 if key == Qt.Key.Key_Tab:
                      if current_completion: # Ensure something is selected/highlighted
                          self.insert_completion(current_completion)
                          event.accept() # Consume the event!
                          return True # Prevent default Tab behavior (focus change)
                      else:
                           # Nothing selected? Hide popup? Or cycle focus? Let's hide.
                           self.completer.popup().hide()
                           event.accept()
                           return True


                 elif key == Qt.Key.Key_Escape:
                      self.completer.popup().hide()
                      event.accept()
                      return True

                 # Let Up/Down arrow keys pass through to QCompleter's default handling
                 elif key in [Qt.Key.Key_Up, Qt.Key.Key_Down]:
                      # Let the completer handle navigation
                      event.ignore() # Let Qt process it further (for the completer)
                      return False # Indicate event should be processed further


            # --- Original Key Handling (if completer didn't handle it) ---
            if key in [Qt.Key.Key_Return, Qt.Key.Key_Enter] and not is_completer_visible: # Only execute if completer isn't active
                if modifiers == Qt.KeyboardModifier.ShiftModifier:
                    current_text = self.input_field.text()
                    cursor_pos = self.input_field.cursorPosition()
                    new_text = current_text[:cursor_pos] + '\n' + current_text[cursor_pos:]
                    self.input_field.setText(new_text)
                    self.input_field.setCursorPosition(cursor_pos + 1)
                    return True

                if modifiers == Qt.KeyboardModifier.ControlModifier:
                    print("Ctrl+Enter detected, triggering manual preview update")
                    # Re-trigger preview update explicitly on Ctrl+Enter
                    # Pass manual=True to the plugin's update_preview
                    if self.active_plugin:
                         self.active_plugin.update_preview(
                             self.input_field.text(),
                             self.selected_text,
                             self.preview_output,
                             self.status_bar,
                             manual=True # Indicate manual trigger
                         )
                         self.adjustHeight() # Adjust height after potential preview change
                else:
                    # Normal Enter executes the command
                    self.execute_command()
                return True

            elif key == Qt.Key.Key_Escape:
                  if not self.completer.popup().isVisible(): # Only quit if completer closed
                     self.quit()
                     return True

        # Important: Pass events down for default QLineEdit/QCompleter handling
        # if we didn't explicitly handle them above (e.g., text input, basic cursor moves)
        return super().eventFilter(obj, event)



    def adjustHeight(self):
        """Adjusts window height based on visible elements."""
        QTimer.singleShot(0, self.adjust_preview_height)


    def adjust_preview_height(self):
        # by gemini
        # Get the QTextDocument associated with the QTextEdit
        document = self.preview_output.document()

        # Get the required height of the document's content based on layout
        # This correctly accounts for wrapping, font, and explicit newlines
        content_height = document.size().height()

        # Get font metrics for calculating line height
        font_metrics = QFontMetrics(self.preview_output.font())
        line_height = font_metrics.lineSpacing()

        # Define padding and frame space (as in the original function)
        padding_vertical = 4 * 2  # Assuming this is internal padding/margin
        frame_vertical_thickness = self.preview_output.frameWidth() * 2 # Top + Bottom frame thickness

        # Calculate the total height required for the content area + padding + frame
        required_total_height = content_height + padding_vertical + frame_vertical_thickness

        # Calculate the maximum height based on 5 lines (as in the original function)
        max_height_5_lines = 5 * line_height + padding_vertical + frame_vertical_thickness

        # Apply the maximum height constraint
        final_set_height = min(required_total_height, max_height_5_lines)

        # Check if there is any text content to decide whether to show or hide
        # Using isEmpty() on the document is often more robust than checking the plain text string
        if not document.isEmpty():
            self.preview_output.setFixedHeight(int(final_set_height))
            self.preview_output.show()
        else:
            # If empty, potentially set a minimum height or hide
            # Original hides, so let's keep that logic
            self.hide_preview()

        # Adjust the main window height (as in the original function)
        self.adjustSize()



    def hide_preview(self):
        """Utility to hide preview and adjust height."""
        self.preview_output.hide()
        self.preview_output.setFixedHeight(0)

    def execute_command(self):
        """Executes the command using the currently active plugin."""
        command_raw = self.input_field.text() # Full text with prefix/suffix

        if not self.active_plugin:
            self.status_bar.setText("No plugin active to execute.")
            return

        # Determine the actual command text to pass to the plugin
        # (strip prefix/suffix if they match the active plugin)
        command_to_execute = command_raw
        if self.active_plugin.PREFIX and command_raw.startswith(self.active_plugin.PREFIX):
            command_to_execute = command_raw[len(self.active_plugin.PREFIX):]
        elif self.active_plugin.SUFFIX and command_raw.endswith(self.active_plugin.SUFFIX):
             command_to_execute = command_raw[:-len(self.active_plugin.SUFFIX)]
        # Note: Default plugins receive the raw command

        print(f"Executing with plugin '{self.active_plugin.NAME}': '{command_to_execute}'")

        try:
            # Execute and get potential result for clipboard
            result = self.active_plugin.execute(command_to_execute, self.selected_text)

            if result is not None: # Plugin returned something synchronously for clipboard
                self.copy(result)

        except Exception as e:
            print(f"Error during execution by plugin {self.active_plugin.NAME}: {e}", file=sys.stderr)
            traceback.print_exc()
            self.status_bar.setText(f"💥 Plugin Error: {e}")

    def copy(self,result):
        clipboard = self.get_clipboard()
        if clipboard:
                clipboard.setText(str(result)) # Ensure it's a string
                result_preview = str(result).replace('\n', ' ')[ :50] # Truncate for status
                self.status_bar.setText(f"📋 Result copied: {result_preview}...")
                QTimer.singleShot(100, self.quit) # Quit after copying
        else:
                self.status_bar.setText("INTERNAL Error: Could not access clipboard.")

    def get_clipboard(self):
        """Safely get the clipboard."""
        return QGuiApplication.clipboard()


    def on_focus_changed(self, old, now):
        # Quit if focus is lost (unless a child widget like preview gained focus)
        # IMPORTANT: Check if now is None explicitly, as it happens during shutdown
        # Also check if 'now' is a Qt object before calling isAncestorOf
        if now is None or (isinstance(now, QWidget) and not self.isAncestorOf(now)):
             # Add a small delay to prevent quitting if focus briefly shifts during interaction
             QTimer.singleShot(150, self._check_and_quit_on_focus_loss)

    def _check_and_quit_on_focus_loss(self):
        """Check if the window still lacks focus before quitting."""
        # Check isActiveWindow AND check if the application is not shutting down
        if not self.isActiveWindow() and QApplication.instance() is not None:
             print("Focus lost, quitting.")
             self.quit()

    def focusOutEvent(self, event):
        # Fallback, though on_focus_changed is usually better
        # self.quit() # Removed direct quit here, rely on on_focus_changed
        super().focusOutEvent(event)


    def cleanup_plugins(self):
        """Call cleanup method on all loaded plugins before quitting."""
        print("Cleaning up plugins...")
        # Emit aboutToQuit signal for plugins that might connect to it
        self.aboutToQuit.emit()
        for plugin in self.plugins:
            try:
                # Check if the plugin instance has a callable 'cleanup' method
                if hasattr(plugin, 'cleanup') and callable(plugin.cleanup):
                     plugin.cleanup()
            except Exception as e:
                print(f"Error cleaning up plugin {plugin.NAME}: {e}", file=sys.stderr)


    def quit(self):
        # Don't call cleanup_plugins here directly, it's handled by app.aboutToQuit signal
        print("Quit requested.")
        QApplication.quit()

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True) # Ensure app exits cleanly

    # Set default font - consider making this configurable
    # Ensure 'Fira Code' or a suitable fallback is installed
    default_font = QFont("Fira Code", 10)
    app.setFont(default_font)

    try:
        launcher = SlickLauncher()
        launcher.show()
        # --- ADDED LINES FOR FOCUS on windows, as windows doesnt like just jumping windows---
        # Ensure the window is brought to front and becomes active
        launcher.showNormal() # Restore if minimized (optional, but good practice)
        launcher.activateWindow() # Activate the window
        launcher.raise_()       # Bring the window to the front

        # Set focus explicitly to the input field after showing
        launcher.input_field.setFocus()
        sys.exit(app.exec())
    except Exception as e:
         print(f"Critical error during application startup: {e}", file=sys.stderr)
         traceback.print_exc()
         sys.exit(1)


if __name__ == "__main__":
    main()