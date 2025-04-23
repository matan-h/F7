# slick_launcher.py
import sys,traceback
import os
import importlib

from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QFont, QGuiApplication
from PyQt6.QtWidgets import (QApplication, QMainWindow, QLineEdit,
                             QTextEdit, QVBoxLayout, QWidget, QLabel,
                             QFrame)

# Local imports
from .clip import get_selected_text
from .plugins.base_plugin import PluginInterface # For type hinting
from .plugins import plugins

d = os.path.dirname(__file__)
# --- Constants ---
class SlickLauncher(QMainWindow):
    # Signal to notify plugins about cleanup
    aboutToQuit = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.selected_text = ""
        self.plugins = []
        self.active_plugin = None
        self.load_plugins()
        self.initUI()
        self.capture_initial_selection() # Get text immediately
        self.resetStatus() # Set initial status based on default plugin

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

        self.preview_output = QTextEdit()
        self.preview_output.setObjectName("PreviewOutput")
        self.preview_output.setReadOnly(True)
        self.preview_output.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.preview_output.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.preview_output.setFrameStyle(QFrame.Shape.NoFrame)
        self.preview_output.setMaximumHeight(200) # Increased max height a bit
        self.preview_output.hide()
        layout.addWidget(self.preview_output)

        self.status_bar = QLabel()
        self.status_bar.setObjectName("StatusBar")
        layout.addWidget(self.status_bar)

        self.setStyleSheet("""
            #MainWidget {
                background: rgba(40, 44, 52, 0.98);
                border-radius: 6px;
                border: 1px solid rgba(255, 255, 255, 0.12);
            }
            #InputField {
                font-size: 16px;
                padding: 8px 12px;
                background: rgba(30, 34, 42, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                color: #abb2bf;
                margin-bottom: 4px;
            }
            #PreviewOutput {
                font-family: 'Fira Code', 'Consolas', monospace; /* Add fallback fonts */
                font-size: 13px;
                background: rgba(30, 34, 42, 0.9);
                color: #abb2bf;
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 4px;
                padding: 4px 8px;
            }
            #StatusBar {
                color: #5c6370;
                font-size: 11px;
                padding: 2px 4px;
                margin-top: 4px;
            }
        """)

        self.resize(500, 1) # Start minimal height
        self.centerWindow()

        # Signals
        self.input_field.textChanged.connect(self.handle_input_change)
        QApplication.instance().focusChanged.connect(self.on_focus_changed)
        # Connect the application's aboutToQuit signal to our cleanup handler
        QApplication.instance().aboutToQuit.connect(self.cleanup_plugins)


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


    def handle_input_change(self,manual=False):
        """Called when text in the input field changes."""
        command = self.input_field.text() # Get the raw command with potential prefix/suffix
        self.active_plugin = self.find_plugin(command)

        if not self.active_plugin:
            self.status_bar.setText("No matching plugin found!")
            self.preview_output.hide()
            self.adjustHeight()
            return
        
        self.resetStatus(self.active_plugin)

        # Let the active plugin handle the preview update
        # The command passed might include prefix/suffix, plugin decides how to use it
        self.active_plugin.update_preview(
            command,
            self.selected_text,
            self.preview_output,
            self.status_bar,
            manual
        )

        # Crucial: Adjust height *after* the plugin potentially shows/hides/resizes preview
        self.adjustHeight()

    def eventFilter(self, obj, event):
        if obj is self.input_field and event.type() == QKeyEvent.Type.KeyPress:
            key = event.key()
            modifiers = event.modifiers()

            if key in [Qt.Key.Key_Return, Qt.Key.Key_Enter]:
                # Check for Ctrl+Enter specifically for preview generation (if plugin supports it)
                # We let the *plugin* decide what Ctrl+Enter does in its update_preview
                # Here, we just differentiate between normal Enter (execute) and others
                if modifiers == Qt.KeyboardModifier.ControlModifier:
                    # Re-trigger preview update explicitly on Ctrl+Enter
                    # This allows plugins like AI to re-generate previews
                    print("Ctrl+Enter detected, triggering preview update")
                    self.handle_input_change(True) # Re-run the preview logic
                else:
                    # Normal Enter executes the command
                    self.execute_command()
                return True # Event handled

            elif key == Qt.Key.Key_Escape:
                self.quit()
                return True

        return super().eventFilter(obj, event)


    def adjustHeight(self):
        """Adjusts window height based on visible elements."""
        QTimer.singleShot(0, self._perform_adjust_height) # Defer adjustment slightly

    def _perform_adjust_height(self):
        """The actual height adjustment logic."""
        base_height = self.input_field.sizeHint().height() + self.status_bar.sizeHint().height() + self.layout().contentsMargins().top() + self.layout().contentsMargins().bottom() + self.layout().spacing() * 2 # Input + Status + Margins + Spacing

        if self.preview_output.isVisible():
            # Calculate required height for preview content dynamically
            doc_height = self.preview_output.document().size().height()
            # Add some padding and respect maximum height
            preview_height = min(int(doc_height) + self.preview_output.contentsMargins().top() * 2 + 5, # Base height + padding
                                 self.preview_output.maximumHeight())
            self.preview_output.setFixedHeight(preview_height) # Set fixed height based on content
            base_height += preview_height + self.layout().spacing()

        self.resize(QSize(self.width(), int(base_height)))

    def hide_preview(self):
        """Utility to hide preview and adjust height."""
        self.preview_output.hide()
        self.adjustHeight()

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
                clipboard = self.get_clipboard()
                if clipboard:
                     clipboard.setText(str(result)) # Ensure it's a string
                     result_preview = str(result).replace('\n', ' ')[ :50] # Truncate for status
                     self.status_bar.setText(f"📋 Result copied: {result_preview}...")
                     QTimer.singleShot(100, self.quit) # Quit after copying
                else:
                     self.status_bar.setText("INTERNAL Error: Could not access clipboard.")

        except Exception as e:
            print(f"Error during execution by plugin {self.active_plugin.NAME}: {e}", file=sys.stderr)
            traceback.print_exc()
            self.status_bar.setText(f"💥 Plugin Error: {e}")

    def get_clipboard(self):
        """Safely get the clipboard."""
        return QGuiApplication.clipboard()


    def on_focus_changed(self, old, now):
        # Quit if focus is lost (unless a child widget like preview gained focus)
        if now is None or not self.isAncestorOf(now):
             # Add a small delay to prevent quitting if focus briefly shifts during interaction
             QTimer.singleShot(150, self._check_and_quit_on_focus_loss)

    def _check_and_quit_on_focus_loss(self):
        """Check if the window still lacks focus before quitting."""
        if not self.isActiveWindow():
             print("Focus lost, quitting.")
             self.quit()

    def focusOutEvent(self, event):
        # Fallback, though on_focus_changed is usually better
        # self.quit()
        super().focusOutEvent(event)

    def cleanup_plugins(self):
        """Call cleanup method on all loaded plugins before quitting."""
        print("Cleaning up plugins...")
        self.aboutToQuit.emit() # Emit signal first (if plugins use it)
        for plugin in self.plugins:
            try:
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
        # Set focus explicitly to the input field after showing
        launcher.input_field.setFocus()
        sys.exit(app.exec())
    except Exception as e:
         print(f"Critical error during application startup: {e}", file=sys.stderr)
         traceback.print_exc()
         sys.exit(1)


if __name__ == "__main__":
    main()